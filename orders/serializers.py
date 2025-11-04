from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_weight', 'quantity', 'price', 'subtotal']

class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = ['id', 'order_id', 'status', 'payment_method', 'total_amount', 'items_count', 'created_at']

    def get_items_count(self, obj):
        return obj.items.count()

class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_id', 'user', 'status', 'payment_method', 
                  'shipping_address', 'shipping_city', 'shipping_state', 
                  'shipping_pincode', 'phone', 'subtotal', 'shipping_charge', 
                  'tax', 'total_amount', 'items', 'created_at', 'updated_at']

class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['shipping_address', 'shipping_city', 'shipping_state', 
                  'shipping_pincode', 'phone', 'payment_method']