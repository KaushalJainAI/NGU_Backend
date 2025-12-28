from rest_framework import serializers
from .models import Review

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    item_name = serializers.CharField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'item_type', 'product', 'combo', 'user', 'user_name', 'item_name',
                  'rating', 'title', 'comment', 'is_verified_purchase', 'created_at']
        read_only_fields = ['user', 'is_verified_purchase', 'item_name']
    
    def validate(self, data):
        item_type = data.get('item_type', 'product')
        product = data.get('product')
        combo = data.get('combo')
        
        if item_type == 'product' and not product:
            raise serializers.ValidationError("Product is required for product reviews")
        if item_type == 'combo' and not combo:
            raise serializers.ValidationError("Combo is required for combo reviews")
        
        return data
