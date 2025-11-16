from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Cart, CartItem, Favorite
from products.models import Product
from .serializers import CartSerializer, CartItemSerializer, FavoriteSerializer

class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = []
        for cart_item in cart.items.all():
            items.append({
                'id': str(cart_item.product.id),
                'name': cart_item.product.name,
                'image': request.build_absolute_uri(cart_item.product.image.url) if cart_item.product.image else '',
                'price': float(cart_item.product.price),
                'originalPrice': float(cart_item.product.original_price) if getattr(cart_item.product, 'original_price', None) else None,
                'badge': getattr(cart_item.product, 'badge', None),
                'quantity': cart_item.quantity,
            })
        return Response({'success': True, 'items': items})

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id') or request.data.get('id')
        quantity = int(request.data.get('quantity', 1))
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'success': False, 'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        if product.stock < quantity:
            return Response({'success': False, 'error': f'Only {product.stock} units available'}, status=status.HTTP_400_BAD_REQUEST)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            if cart_item.quantity > product.stock:
                return Response({'success': False, 'error': f'Only {product.stock} units available'},
                                status=status.HTTP_400_BAD_REQUEST)
            cart_item.save()
        return self.list(request)

    @action(detail=False, methods=['post'])
    def update_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        product_id = request.data.get('product_id') or request.data.get('id')
        quantity = int(request.data.get('quantity', 1))
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            cart_item = CartItem.objects.get(cart=cart, product=product)
            if quantity <= 0:
                cart_item.delete()
            else:
                if product.stock < quantity:
                    return Response({'success': False, 'error': f'Only {product.stock} units available'},
                                    status=status.HTTP_400_BAD_REQUEST)
                cart_item.quantity = quantity
                cart_item.save()
            return self.list(request)
        except (CartItem.DoesNotExist, Product.DoesNotExist):
            return Response({'success': False, 'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete', 'post'])
    def remove_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        product_id = request.data.get('product_id') or request.data.get('id')
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            cart_item = CartItem.objects.get(cart=cart, product=product)
            cart_item.delete()
            return self.list(request)
        except (CartItem.DoesNotExist, Product.DoesNotExist):
            return Response({'success': False, 'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        cart.items.all().delete()
        return Response({'success': True, 'items': []})

    @action(detail=False, methods=['post'])
    def sync(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items_data = request.data.get('items', [])
        cart.items.all().delete()
        skipped = []
        for item_data in items_data:
            try:
                product_id = item_data.get('id')
                quantity = item_data.get('quantity', 1)
                if not product_id:
                    continue
                product = Product.objects.get(id=product_id, is_active=True)
                if product.stock < quantity:
                    skipped.append({'id': product_id, 'reason': 'not enough stock'})
                    continue
                CartItem.objects.create(cart=cart, product=product, quantity=quantity)
            except Product.DoesNotExist:
                skipped.append({'id': item_data.get('id'), 'reason': 'product not found'})
                continue
        data = self.list(request).data
        data['skipped'] = skipped
        return Response(data)

class FavoritesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        favorites = Favorite.objects.filter(user=request.user)
        serializer = FavoriteSerializer(favorites, many=True, context={'request': request})
        return Response({'success': True, 'items': serializer.data})

    def create(self, request):
        product_id = request.data.get('product_id') or request.data.get('id')
        if not product_id:
            return Response({'success': False, 'error': 'Product id required'}, status=status.HTTP_400_BAD_REQUEST)
        product = get_object_or_404(Product, id=product_id, is_active=True)
        Favorite.objects.get_or_create(user=request.user, product=product)
        return self.list(request)

    def destroy(self, request, pk=None):
        favorite = Favorite.objects.filter(user=request.user, product__id=pk).first()
        if favorite:
            favorite.delete()
        return self.list(request)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        product_ids = request.data.get('ids', [])
        Favorite.objects.filter(user=request.user).delete()
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        for product in products:
            Favorite.objects.get_or_create(user=request.user, product=product)
        return self.list(request)

    @action(detail=False, methods=['get'])
    def is_favorite(self, request):
        product_id = request.query_params.get('product_id') or request.query_params.get('id')
        is_fav = Favorite.objects.filter(user=request.user, product__id=product_id).exists()
        return Response({'isFavorite': is_fav})
