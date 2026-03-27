"""
Order Views - Order Management API

Architecture:
- OrderViewSet: Complete order CRUD with role-based filtering
  - Regular users: see only their orders
  - Admins (is_staff): see all orders

Order Creation Flow:
1. Validate cart exists and has items
2. Validate coupon if provided (checks is_active, valid_until)
3. Calculate totals: subtotal, discount, shipping (free >₹500), tax (5%)
4. Create Order + OrderItems in atomic transaction
5. Reduce product stock within transaction
6. Clear cart AFTER successful transaction (prevents rollback issues)

Key Design Decisions:
1. Cart cleared OUTSIDE transaction - if cart deletion fails, order still succeeds
2. Proportional discount - each item gets discount proportional to its share of subtotal
3. Stock validation before order creation - prevents overselling
4. Combos have default stock of 999 (effectively unlimited)
5. Order number format: ORD-XXXXXX (6 digit padded ID)

Status Workflow:
pending → confirmed → processing → shipped → delivered
    └──────────────────────────────────────→ cancelled
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
from .models import Order, OrderItem
from .serializers import OrderListSerializer, OrderDetailSerializer, OrderCreateSerializer
from cart.models import Cart
from admin_panel.models import Coupon

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Admin/superusers can see all orders
        if user.is_staff or user.is_superuser:
            return Order.objects.all().prefetch_related('items__product', 'items__combo').select_related('user')
        # Regular users only see their own orders
        return Order.objects.filter(user=user).prefetch_related('items__product', 'items__combo')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderDetailSerializer

    def _validate_coupon(self, coupon_code, user, order_amount=None):
        """
        Validates coupon code and returns the coupon object or error response.
        Checks is_active, expiration, max_usage, and minimum_order_amount.
        """
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
        except Coupon.DoesNotExist:
            return None, {'error': 'Invalid coupon code'}

        if not coupon.is_valid(order_amount=order_amount):
            return None, {'error': 'This coupon is invalid, expired, or you do not meet the requirements'}

        return coupon, None

    def _calculate_discount(self, price, coupon):
        """
        Calculate discount based on coupon's discount_percent field.
        Simple percentage calculation only.
        """
        if not coupon:
            return Decimal('0.00')

        # Use discount_percent field (not discount_type or discount_value)
        discount = price * (Decimal(str(coupon.discount_percent)) / Decimal('100'))
        return discount.quantize(Decimal('0.01'))

    @action(detail=False, methods=['post'])
    def validate_coupon(self, request):
        """
        Endpoint to validate coupon before placing order
        """
        coupon_code = request.data.get('coupon_code', '').strip()
        
        if not coupon_code:
            return Response({'error': 'Coupon code is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        if not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate subtotal from cart to validate coupon against minimum
        subtotal = cart.total_price

        # Validate coupon
        coupon, error = self._validate_coupon(coupon_code, request.user, order_amount=subtotal)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Calculate discount using discount_percent
        total_discount = self._calculate_discount(subtotal, coupon)

        # Calculate order breakdown
        discounted_subtotal = subtotal - total_discount
        shipping_charge = Decimal('0') if discounted_subtotal >= 500 else Decimal('50')
        tax = (discounted_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        total_amount = discounted_subtotal + shipping_charge + tax

        return Response({
            'valid': True,
            'coupon_code': coupon.code,
            'discount_percent': coupon.discount_percent,
            'subtotal': float(subtotal),
            'discount_amount': float(total_discount),
            'discounted_subtotal': float(discounted_subtotal),
            'shipping_charge': float(shipping_charge),
            'tax': float(tax),
            'total_amount': float(total_amount),
            'savings': float(total_discount)
        })

    def create(self, request):
        """
        Create order with optional coupon validation and clear cart
        CART DELETION IS DONE AFTER TRANSACTION TO PREVENT ROLLBACK
        """
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        coupon_code = request.data.get('coupon_code', '').strip()
        coupon = None
        
        # Validate cart
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        if not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        subtotal_for_validation = cart.total_price

        # Validate coupon if provided
        if coupon_code:
            coupon, error = self._validate_coupon(coupon_code, request.user, order_amount=subtotal_for_validation)
            if error:
                return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Store cart items data before transaction
        cart_items_data = []
        subtotal = Decimal('0')
        
        for cart_item in cart.items.select_related('product', 'combo').all():
            # Handle both products and combos
            if cart_item.item_type == 'product' and cart_item.product:
                item = cart_item.product
                item_name = cart_item.product.name
                item_weight = cart_item.product.formatted_weight
                
                item_stock = cart_item.product.stock
                item_price = cart_item.product.final_price if hasattr(cart_item.product, 'final_price') else cart_item.product.price
                product_ref = cart_item.product
            elif cart_item.item_type == 'combo' and cart_item.combo:
                item = cart_item.combo
                item_name = cart_item.combo.name
                # Use combo's own weight if available
                if cart_item.combo.weight and cart_item.combo.unit:
                    w = float(cart_item.combo.weight)
                    if w.is_integer():
                        w = int(w)
                    item_weight = f"{w}{cart_item.combo.unit}"
                else:
                    item_weight = "Combo"
                
                item_stock = getattr(cart_item.combo, 'stock', 999)  # Combos may not have stock limit
                item_price = cart_item.combo.final_price if hasattr(cart_item.combo, 'final_price') else cart_item.combo.price
                product_ref = None  # Combos don't have a product reference
            else:
                # Skip invalid items
                logger.warning(f"Skipping invalid cart item: {cart_item.id}")
                continue
            
            # Check stock availability
            if item_stock < cart_item.quantity:
                return Response({
                    'error': f'Insufficient stock for {item_name}. Available: {item_stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            cart_items_data.append({
                'item': item,
                'product': product_ref,  # Will be None for combos
                'item_type': cart_item.item_type,
                'product_name': item_name,
                'product_weight': item_weight,
                'quantity': cart_item.quantity,
                'item_price': item_price,
            })
            subtotal += item_price * cart_item.quantity

        # Calculate discount
        total_discount = self._calculate_discount(subtotal, coupon) if coupon else Decimal('0')
        discounted_subtotal = subtotal - total_discount

        # Calculate shipping, tax, and total
        shipping_charge = Decimal('0') if discounted_subtotal >= 500 else Decimal('50')
        tax = (discounted_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        total_amount = (discounted_subtotal + shipping_charge + tax).quantize(Decimal('0.01'))

        # Create order in transaction
        try:
            with transaction.atomic():
                # Create order
                order = Order.objects.create(
                    user=request.user,
                    subtotal=subtotal,
                    discount_amount=total_discount,
                    shipping_charge=shipping_charge,
                    tax=tax,
                    total_amount=total_amount,
                    coupon=coupon,
                    status='pending',
                    **serializer.validated_data
                )

                # Create order items with proportional discounts
                for item_data in cart_items_data:
                    item_price = item_data['item_price']
                    quantity = item_data['quantity']
                    item_total = item_price * quantity
                    
                    # Calculate proportional discount for this item
                    if total_discount > 0 and subtotal > 0:
                        item_discount = ((item_total / subtotal) * total_discount).quantize(Decimal('0.01'))
                    else:
                        item_discount = Decimal('0')
                    
                    discounted_item_price = (item_price - (item_discount / quantity)).quantize(Decimal('0.01'))
                    discounted_item_total = (discounted_item_price * quantity).quantize(Decimal('0.01'))
                    
                    # Calculate tax for this item after discount
                    item_tax = (discounted_item_total * Decimal('0.05')).quantize(Decimal('0.01'))

                    # Create OrderItem with proper product/combo reference
                    order_item_data = {
                        'order': order,
                        'item_type': item_data['item_type'],
                        'product_name': item_data['product_name'],
                        'product_weight': item_data['product_weight'],
                        'quantity': quantity,
                        'price': item_price,
                        'discount_amount': item_discount,
                        'discounted_price': discounted_item_price,
                        'tax_amount': item_tax,
                        'final_price': discounted_item_total,
                    }
                    
                    # Set product or combo reference based on item type
                    if item_data['item_type'] == 'product':
                        order_item_data['product'] = item_data['product']
                    elif item_data['item_type'] == 'combo':
                        order_item_data['combo'] = item_data['item']

                    OrderItem.objects.create(**order_item_data)
                    
                # Gather IDs for batch stock update
                product_updates = {}
                combo_updates = {}
                
                for item_data in cart_items_data:
                    quantity = item_data['quantity']
                    if item_data['item_type'] == 'product' and item_data.get('product'):
                        product_updates[item_data['product'].pk] = product_updates.get(item_data['product'].pk, 0) + quantity
                    elif item_data['item_type'] == 'combo' and item_data.get('item'):
                        combo_updates[item_data['item'].pk] = combo_updates.get(item_data['item'].pk, 0) + quantity

                from products.models import Product, ProductCombo

                # Batch reduce stock for products
                if product_updates:
                    products = list(Product.objects.select_for_update().filter(pk__in=product_updates.keys()))
                    for product in products:
                        reduce_by = product_updates[product.pk]
                        if product.stock < reduce_by:
                            raise ValueError(f'Insufficient stock for {product.name}. Available: {product.stock}')
                        product.stock -= reduce_by
                    Product.objects.bulk_update(products, ['stock'])

                # Batch reduce stock for combos
                if combo_updates:
                    combos = list(ProductCombo.objects.select_for_update().filter(pk__in=combo_updates.keys()))
                    for combo in combos:
                        reduce_by = combo_updates[combo.pk]
                        if not hasattr(combo, 'stock'):
                            continue
                        if combo.stock < reduce_by:
                            raise ValueError(f'Insufficient stock for {combo.name}. Available: {combo.stock}')
                        combo.stock -= reduce_by
                    ProductCombo.objects.bulk_update(combos, ['stock'])
                            
                # Increase usage count on coupon
                if coupon:
                    coupon.usage_count = models.F('usage_count') + 1
                    coupon.save(update_fields=['usage_count'])

                # Clear cart items securely inside the transaction to prevent desynchronization
                cart.items.all().delete()

                # Transaction complete - prepare response data
                order_data = OrderDetailSerializer(order).data

        except ValueError as e:
            logger.warning(f"Order creation validation failed: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Order creation failed: {str(e)}")
            return Response(
                {'error': f'Failed to create order: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Generate order number
        order_number = f"ORD-{order.id:06d}"
        
        return Response({
            'message': 'Order created successfully',
            'order_id': order.id,
            'order_number': order_number,
            'total_amount': float(total_amount),
            'order': order_data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel order and restore stock (both products AND combos)
        """
        with transaction.atomic():
            # Lock the order to prevent concurrent cancellations
            obj = self.get_object()
            if obj.user != request.user and not request.user.is_staff:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You do not have permission to cancel this order.")
                
            order = Order.objects.select_for_update().get(pk=obj.pk)
            
            if order.status in ['delivered', 'cancelled', 'delivering']:
                return Response(
                    {'success': False, 'error': f'Cannot cancel order with status: {order.status}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from products.models import Product, ProductCombo
            
            # Gather quantities for batch stock restoration
            product_updates = {}
            combo_updates = {}
            
            for item in order.items.select_related('product', 'combo').all():
                if item.product:
                    product_updates[item.product.pk] = product_updates.get(item.product.pk, 0) + item.quantity
                elif item.combo and hasattr(item.combo, 'stock'):
                    combo_updates[item.combo.pk] = combo_updates.get(item.combo.pk, 0) + item.quantity
                    
            # Batch restore stock for products
            if product_updates:
                products = list(Product.objects.select_for_update().filter(pk__in=product_updates.keys()))
                for product in products:
                    product.stock += product_updates[product.pk]
                Product.objects.bulk_update(products, ['stock'])
                
            # Batch restore stock for combos
            if combo_updates:
                combos = list(ProductCombo.objects.select_for_update().filter(pk__in=combo_updates.keys()))
                for combo in combos:
                    combo.stock += combo_updates[combo.pk]
                ProductCombo.objects.bulk_update(combos, ['stock'])
            
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.save(update_fields=['status', 'cancelled_at'])
        
        return Response({
            'success': True,
            'message': 'Order cancelled successfully',
            'order': OrderDetailSerializer(order).data
        })

    def list(self, request):
        """
        List all orders for the authenticated user
        """
        orders = self.get_queryset().order_by('-created_at')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Get detailed information about a specific order
        """
        order = self.get_object()
        serializer = self.get_serializer(order)
        return Response(serializer.data)
