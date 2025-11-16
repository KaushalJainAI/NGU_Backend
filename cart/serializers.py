from rest_framework import serializers
from .models import Cart, CartItem, Favorite
from products.serializers import ProductListSerializer

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal', 'created_at']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price', 'total_items', 'created_at', 'updated_at']

class FavoriteSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='product.id')
    name = serializers.CharField(source='product.name')
    image = serializers.ImageField(source='product.image', allow_null=True)
    price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2)
    originalPrice = serializers.DecimalField(source='product.original_price', max_digits=10, decimal_places=2, required=False)
    weight = serializers.CharField(source='product.weight', allow_null=True, required=False)
    badge = serializers.CharField(source='product.badge', allow_null=True, required=False)

    class Meta:
        model = Favorite
        fields = ('id', 'name', 'image', 'price', 'originalPrice', 'weight', 'badge')

