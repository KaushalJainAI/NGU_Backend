from rest_framework import serializers
from .models import ReceivableAccount, Coupon
from orders.models import Order


class ReceivableAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceivableAccount
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            'id',
            'code',
            'discount_percent',
            'is_active',
            'valid_until',
        ]
        read_only_fields = ['id']
        

    def is_valid(self, *, raise_exception=False):
        return super().is_valid(raise_exception=raise_exception)
    
class RecentOrderSerializer(serializers.ModelSerializer):
    customerName = serializers.CharField(source='customer.name')
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    createdAt = serializers.DateTimeField(source='created_at')
    
    class Meta:
        model = Order
        fields = ['id', 'customerName', 'totalAmount', 'status', 'createdAt']
    
from rest_framework import serializers
from .models import Policy

class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = ['type', 'content']
