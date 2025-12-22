# views.py - FIXED VERSION WITH PROPER CART DELETION
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
        return Order.objects.filter(user=self.request.user).prefetch_related('items__product')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderDetailSerializer

    def _validate_coupon(self, coupon_code, user):
        """
        Validates coupon code and returns the coupon object or error response.
        Only validates fields that exist in the Coupon model: code, is_active, valid_until, discount_percent
        """
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
        except Coupon.DoesNotExist:
            return None, {'error': 'Invalid coupon code'}

        # Check if coupon is active
        if not coupon.is_active:
            return None, {'error': 'This coupon is no longer active'}

        # Check validity date (only valid_until exists, not valid_from or valid_to)
        now = timezone.now()
        if coupon.valid_until and now > coupon.valid_until:
            return None, {'error': 'This coupon has expired'}

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

        # Validate coupon
        coupon, error = self._validate_coupon(coupon_code, request.user)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Calculate subtotal from cart
        subtotal = cart.total_price

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

        # Validate coupon if provided
        if coupon_code:
            coupon, error = self._validate_coupon(coupon_code, request.user)
            if error:
                return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Store cart items data before transaction
        cart_items_data = []
        subtotal = Decimal('0')
        
        for cart_item in cart.items.select_related('product').all():
            # Check stock availability
            if cart_item.product.stock < cart_item.quantity:
                return Response({
                    'error': f'Insufficient stock for {cart_item.product.name}. Available: {cart_item.product.stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            item_price = cart_item.product.final_price if hasattr(cart_item.product, 'final_price') else cart_item.product.price
            cart_items_data.append({
                'product': cart_item.product,
                'product_name': cart_item.product.name,
                'product_weight': getattr(cart_item.product, 'weight', ''),
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

                    OrderItem.objects.create(
                        order=order,
                        product=item_data['product'],
                        product_name=item_data['product_name'],
                        product_weight=item_data['product_weight'],
                        quantity=quantity,
                        price=item_price,
                        discount_amount=item_discount,
                        discounted_price=discounted_item_price,
                        tax_amount=item_tax,
                        final_price=discounted_item_total
                    )
                    
                    # Reduce stock
                    item_data['product'].stock -= quantity
                    item_data['product'].save(update_fields=['stock'])

                # Transaction complete - prepare response data
                order_data = OrderDetailSerializer(order).data

        except Exception as e:
            logger.error(f"Order creation failed: {str(e)}")
            return Response(
                {'error': f'Failed to create order: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # CART DELETION OUTSIDE TRANSACTION - This prevents rollback issues
        try:
            cart_item_count = cart.items.count()
            logger.info(f"Attempting to delete {cart_item_count} cart items for user {request.user.id}")
            
            # Delete cart items explicitly
            deleted_count, _ = cart.items.all().delete()
            logger.info(f"Successfully deleted {deleted_count} cart items")
            
            # Refresh cart to update total_price
            cart.refresh_from_db()
            
            # Verify deletion
            remaining_items = cart.items.count()
            if remaining_items > 0:
                logger.warning(f"Cart still has {remaining_items} items after deletion!")
            else:
                logger.info(f"Cart successfully cleared for user {request.user.id}")
                
        except Exception as e:
            # Log error but don't fail the order creation
            logger.error(f"Failed to clear cart for user {request.user.id}: {str(e)}")
            # Order is already created, so we return success
        
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
        Cancel order and restore stock
        """
        order = self.get_object()
        
        if order.status in ['delivered', 'cancelled', 'delivering']:
            return Response(
                {'error': f'Cannot cancel order with status: {order.status}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Restore stock
            for item in order.items.select_related('product').all():
                item.product.stock += item.quantity
                item.product.save(update_fields=['stock'])
            
            order.status = 'cancelled'
            if hasattr(order, 'cancelled_at'):
                order.cancelled_at = timezone.now()
                order.save(update_fields=['status', 'cancelled_at'])
            else:
                order.save(update_fields=['status'])
        
        return Response({
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
