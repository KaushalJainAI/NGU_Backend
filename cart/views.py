from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Cart, CartItem, Favorite
from admin_panel.utils import generate_upi_qr_code
from decimal import Decimal
from rest_framework.views import APIView
from admin_panel.models import Coupon, ReceivableAccount
from products.models import Product, ProductCombo
from .serializers import ValidateCouponSerializer, FavoriteSerializer


class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = []
        
        for cart_item in cart.items.select_related('product', 'combo').all():
            item_type = cart_item.item_type or 'product'
            item_obj = cart_item.product if item_type == 'product' else cart_item.combo
            
            if not item_obj:
                continue
            
            # Get price
            if hasattr(item_obj, 'final_price'):
                price = float(item_obj.final_price)
            else:
                price = float(item_obj.price)
            
            # Get original price
            if hasattr(item_obj, 'original_price') and item_obj.original_price:
                original_price = float(item_obj.original_price)
            else:
                original_price = price
                
            items.append({
                'id': str(item_obj.id),
                'item_type': item_type,
                'name': item_obj.name,
                'image': request.build_absolute_uri(item_obj.image.url) if item_obj.image else '',
                'price': price,
                'originalPrice': original_price,
                'badge': getattr(item_obj, 'badge', None),
                'quantity': cart_item.quantity,
                'subtotal': float(cart_item.subtotal),
                'stock': getattr(item_obj, 'stock', 999) if item_type == 'product' else 999,
                'in_stock': item_obj.stock > 0 if item_type == 'product' and hasattr(item_obj, 'stock') else True,
            })

        # Calculate summary
        subtotal = float(cart.total_price)
        tax = round(subtotal * 0.05, 2)
        discount = 0
        total = round(subtotal + tax - discount, 2)

        summary = {
            "subtotal": subtotal,
            "tax": tax,
            "discount": discount,
            "total": total
        }

        return Response({
            'success': True,
            'items': items,
            'summary': summary
        })

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        product_id = request.data.get('product_id') or request.data.get('id')
        item_type = request.data.get('item_type', 'product')
        
        # Validate quantity is a natural number (positive integer >= 1)
        raw_quantity = request.data.get('quantity', 1)
        try:
            quantity = int(raw_quantity)
            if quantity < 1:
                return Response({
                    'success': False, 
                    'error': 'Quantity must be a positive integer (1 or greater)'
                }, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({
                'success': False, 
                'error': 'Quantity must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate product_id is provided and is a valid integer
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response({
                'success': False, 
                'error': 'Product id must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                cart, _ = Cart.objects.get_or_create(user=request.user)
                
                if item_type == 'combo':
                    item = ProductCombo.objects.get(id=product_id, is_active=True)
                    stock = getattr(item, 'stock', 999)
                    
                    # Check for existing cart item
                    cart_item = CartItem.objects.filter(
                        cart=cart, combo=item, item_type='combo'
                    ).first()
                    
                    if cart_item:
                        new_quantity = cart_item.quantity + quantity
                        if new_quantity > stock:
                            return Response({'success': False, 'error': f'Only {stock} units available'},
                                          status=status.HTTP_400_BAD_REQUEST)
                        cart_item.quantity = new_quantity
                        cart_item.save()
                    else:
                        if quantity > stock:
                            return Response({'success': False, 'error': f'Only {stock} units available'},
                                          status=status.HTTP_400_BAD_REQUEST)
                        CartItem.objects.create(cart=cart, combo=item, item_type='combo', quantity=quantity)
                else:
                    item = Product.objects.get(id=product_id, is_active=True)
                    stock = item.stock
                    
                    # Check for existing cart item
                    cart_item = CartItem.objects.filter(
                        cart=cart, product=item, item_type='product'
                    ).first()
                    
                    if cart_item:
                        new_quantity = cart_item.quantity + quantity
                        if new_quantity > stock:
                            return Response({'success': False, 'error': f'Only {stock} units available'},
                                          status=status.HTTP_400_BAD_REQUEST)
                        cart_item.quantity = new_quantity
                        cart_item.save()
                    else:
                        if quantity > stock:
                            return Response({'success': False, 'error': f'Only {stock} units available'},
                                          status=status.HTTP_400_BAD_REQUEST)
                        CartItem.objects.create(cart=cart, product=item, item_type='product', quantity=quantity)
                    
        except (Product.DoesNotExist, ProductCombo.DoesNotExist):
            return Response({'success': False, 'error': 'Item not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return self.list(request)

    @action(detail=False, methods=['post'])
    def update_item(self, request):
        product_id = request.data.get('product_id') or request.data.get('id')
        item_type = request.data.get('item_type', 'product')
        
        # Validate quantity is a valid integer
        raw_quantity = request.data.get('quantity', 1)
        try:
            quantity = int(raw_quantity)
            # For update, allow 0 or positive (0 means remove)
            if quantity < 0:
                return Response({
                    'success': False, 
                    'error': 'Quantity cannot be negative'
                }, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({
                'success': False, 
                'error': 'Quantity must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response({
                'success': False, 
                'error': 'Product id must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                cart = get_object_or_404(Cart, user=request.user)
                
                if item_type == 'combo':
                    item = ProductCombo.objects.get(id=product_id, is_active=True)
                    cart_item = CartItem.objects.get(cart=cart, combo=item, item_type='combo')
                    stock = getattr(item, 'stock', 999)
                else:
                    item = Product.objects.get(id=product_id, is_active=True)
                    cart_item = CartItem.objects.get(cart=cart, product=item, item_type='product')
                    stock = item.stock
                    
                if quantity <= 0:
                    cart_item.delete()
                else:
                    if stock < quantity:
                        return Response({'success': False, 'error': f'Only {stock} units available'},
                                      status=status.HTTP_400_BAD_REQUEST)
                    cart_item.quantity = quantity
                    cart_item.save()
                
        except (CartItem.DoesNotExist, Product.DoesNotExist, ProductCombo.DoesNotExist):
            return Response({'success': False, 'error': 'Cart item not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return self.list(request)

    @action(detail=False, methods=['delete', 'post'])
    def remove_item(self, request):
        item_id = request.data.get('product_id') or request.data.get('id')
        
        if not item_id:
            return Response({'success': False, 'error': 'Item id required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Parse composite key if provided (e.g., "product-1" or "combo-1")
        if isinstance(item_id, str) and '-' in item_id:
            parts = item_id.split('-', 1)
            if len(parts) == 2:
                item_type, product_id = parts
            else:
                return Response({'success': False, 'error': 'Invalid item id format'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        else:
            # Fallback to item_type parameter
            item_type = request.data.get('item_type', 'product')
            product_id = item_id
        
        try:
            with transaction.atomic():
                cart = get_object_or_404(Cart, user=request.user)
                
                if item_type == 'combo':
                    cart_item = CartItem.objects.get(cart=cart, combo__id=product_id, item_type='combo')
                else:
                    cart_item = CartItem.objects.get(cart=cart, product__id=product_id, item_type='product')
                    
                cart_item.delete()
                
        except CartItem.DoesNotExist:
            return Response({'success': False, 'error': 'Cart item not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return self.list(request)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        try:
            with transaction.atomic():
                cart = get_object_or_404(Cart, user=request.user)
                cart.items.all().delete()
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response({'success': True, 'items': []})

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Sync cart items from frontend to backend"""
        items_data = request.data.get('items', [])
        skipped = []
        
        try:
            with transaction.atomic():
                cart, _ = Cart.objects.get_or_create(user=request.user)
                
                # Clear existing cart items
                cart.items.all().delete()
                
                for item_data in items_data:
                    try:
                        product_id = item_data.get('product_id') or item_data.get('id')
                        item_type = item_data.get('item_type', 'product')
                        
                        # Validate quantity
                        raw_quantity = item_data.get('quantity', 1)
                        try:
                            quantity = int(raw_quantity)
                            if quantity < 1:
                                skipped.append({
                                    'id': str(product_id or 'unknown'), 
                                    'type': item_type, 
                                    'reason': 'quantity must be a positive integer'
                                })
                                continue
                        except (ValueError, TypeError):
                            skipped.append({
                                'id': str(product_id or 'unknown'), 
                                'type': item_type, 
                                'reason': 'invalid quantity format'
                            })
                            continue
                        
                        if not product_id:
                            continue
                        
                        if item_type == 'combo':
                            try:
                                item = ProductCombo.objects.get(id=product_id, is_active=True)
                            except ProductCombo.DoesNotExist:
                                skipped.append({
                                    'id': str(product_id), 
                                    'type': 'combo', 
                                    'reason': 'combo not found'
                                })
                                continue
                            
                            stock = getattr(item, 'stock', 999)
                            if stock < quantity:
                                skipped.append({
                                    'id': str(product_id), 
                                    'type': 'combo', 
                                    'reason': f'only {stock} available'
                                })
                                continue
                            
                            # Create cart item
                            CartItem.objects.create(
                                cart=cart,
                                combo=item,
                                item_type='combo',
                                quantity=quantity
                            )
                            
                        else:
                            try:
                                item = Product.objects.get(id=product_id, is_active=True)
                            except Product.DoesNotExist:
                                skipped.append({
                                    'id': str(product_id), 
                                    'type': 'product', 
                                    'reason': 'product not found'
                                })
                                continue
                            
                            if item.stock < quantity:
                                skipped.append({
                                    'id': str(product_id), 
                                    'type': 'product', 
                                    'reason': f'only {item.stock} available'
                                })
                                continue
                            
                            # Create cart item
                            CartItem.objects.create(
                                cart=cart,
                                product=item,
                                item_type='product',
                                quantity=quantity
                            )
                            
                    except ValueError as e:
                        skipped.append({
                            'id': str(item_data.get('product_id', item_data.get('id', 'unknown'))), 
                            'type': item_type, 
                            'reason': f'invalid data: {str(e)}'
                        })
                        continue
                    except Exception as e:
                        skipped.append({
                            'id': str(item_data.get('product_id', item_data.get('id', 'unknown'))), 
                            'type': item_type, 
                            'reason': str(e)
                        })
                        continue
        
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to sync cart: {str(e)}',
                'items': [],
                'skipped': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Fetch and return the updated cart (outside the transaction)
        response_data = self.list(request).data
        response_data['skipped'] = skipped
        return Response(response_data)

class ValidateCouponAPIView(APIView):
    def post(self, request):
        print(f"Received request data: {request.data}")  # Debug log
        print(f"Request content type: {request.content_type}")  # Debug log
        
        serializer = ValidateCouponSerializer(data=request.data)
        if serializer.is_valid():
            code = serializer.validated_data['code']
            try:
                coupon = Coupon.objects.get(code=code)
                if coupon.is_valid():
                    return Response({
                        'valid': True,
                        'message': 'Coupon is valid.', 
                        'coupon_id': coupon.id, 
                        'discount_percent': coupon.discount_percent
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'valid': False,
                        'message': 'Coupon is expired or inactive.'
                    }, status=status.HTTP_200_OK)
            except Coupon.DoesNotExist:
                return Response({
                    'valid': False,
                    'message': 'Coupon does not exist.'
                }, status=status.HTTP_200_OK)
        
        print(f"Serializer errors: {serializer.errors}")  # Debug log
        return Response({
            'valid': False,
            'message': 'Invalid request data.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class CartPaymentQRView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        cart, _ = Cart.objects.get_or_create(user=user)

        total_amount = Decimal(cart.total_price)
        summary = {
            "original": float(total_amount),
            "discount": 0.0,
            "final": float(total_amount),
        }

        coupon_code = request.data.get('coupon_code')
        discount_applied = 0
        
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                if coupon.is_valid():
                    discount_applied = coupon.discount_percent
                    discount_amount = (total_amount * Decimal(discount_applied) / Decimal(100)).quantize(Decimal('0.01'))
                    total_amount = (total_amount - discount_amount).quantize(Decimal('0.01'))
                    summary["discount"] = float(discount_amount)
                    summary["final"] = float(total_amount)
                else:
                    return Response({'error': 'Coupon expired or inactive.'}, status=400)
            except Coupon.DoesNotExist:
                return Response({'error': 'Invalid coupon code.'}, status=400)

        if total_amount <= 0:
            return Response({'error': 'Cart is empty or total amount is invalid.'}, status=400)

        acc_id = request.data.get("receivable_account_id")
        if not acc_id:
            return Response({'error': 'receivable_account_id is required.'}, status=400)

        try:
            account = ReceivableAccount.objects.get(id=acc_id)
        except ReceivableAccount.DoesNotExist:
            return Response({'error': 'Receivable account not found.'}, status=404)

        qr_base64, upi_uri = generate_upi_qr_code(
            account=account,
            amount=total_amount,
            transaction_note=f"Cart Payment{f' (Coupon: {coupon_code})' if coupon_code else ''}"
        )

        return Response({
            # 'qr_code_base64': qr_base64,
            'upi_uri': upi_uri,
            'amount': float(total_amount),
            'discount_percent': discount_applied,
            "summary": summary,
        })


class FavoritesViewSet(viewsets.ViewSet):
    """ViewSet for managing user favorites - similar to CartViewSet"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get all favorites for the current user"""
        favorites = Favorite.objects.filter(user=request.user).select_related('product')
        items = []
        
        for fav in favorites:
            product = fav.product
            if not product or not product.is_active:
                continue
                
            items.append({
                'id': product.id,
                'product_id': product.id,
                'name': product.name,
                'image': request.build_absolute_uri(product.image.url) if product.image else '',
                'price': float(product.final_price),
                'original_price': float(product.original_price) if product.original_price else None,
                'weight': product.weight,
                'badge': getattr(product, 'badge', None),
                'added_at': fav.added_at.isoformat(),
            })
        
        return Response(items)

    def create(self, request):
        """Add a product to favorites"""
        product_id = request.data.get('product_id')
        
        if not product_id:
            return Response({'success': False, 'error': 'product_id is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            
            # Check if already favorited
            fav, created = Favorite.objects.get_or_create(
                user=request.user,
                product=product
            )
            
            return Response({
                'success': True,
                'created': created,
                'message': 'Added to favorites' if created else 'Already in favorites'
            })
            
        except Product.DoesNotExist:
            return Response({'success': False, 'error': 'Product not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, pk=None):
        """Remove a product from favorites"""
        try:
            fav = Favorite.objects.get(user=request.user, product_id=pk)
            fav.delete()
            return Response({'success': True, 'message': 'Removed from favorites'})
        except Favorite.DoesNotExist:
            return Response({'success': False, 'error': 'Favorite not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Sync favorites from frontend to backend"""
        items_data = request.data.get('items', [])
        
        try:
            with transaction.atomic():
                # Get existing favorites
                existing_ids = set(
                    Favorite.objects.filter(user=request.user).values_list('product_id', flat=True)
                )
                
                incoming_ids = set()
                for item in items_data:
                    product_id = item.get('id') or item.get('product_id')
                    if product_id:
                        incoming_ids.add(int(product_id))
                
                # Add new favorites
                to_add = incoming_ids - existing_ids
                for product_id in to_add:
                    try:
                        product = Product.objects.get(id=product_id, is_active=True)
                        Favorite.objects.get_or_create(user=request.user, product=product)
                    except Product.DoesNotExist:
                        continue
                
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Return updated favorites list
        return self.list(request)

