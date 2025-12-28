from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from .models import Review
from .serializers import ReviewSerializer
from orders.models import OrderItem

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.all().select_related('user', 'product', 'combo')
        
        # Filter by product or combo
        product_id = self.request.query_params.get('product')
        combo_id = self.request.query_params.get('combo')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id, item_type='product')
        elif combo_id:
            queryset = queryset.filter(combo_id=combo_id, item_type='combo')
        elif self.request.user.is_authenticated and self.action == 'list':
            queryset = queryset.filter(user=self.request.user)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        item_type = serializer.validated_data.get('item_type', 'product')
        product = serializer.validated_data.get('product')
        combo = serializer.validated_data.get('combo')
        
        # Check for duplicate review
        if item_type == 'product' and product:
            if Review.objects.filter(user=self.request.user, product=product, item_type='product').exists():
                raise serializers.ValidationError({"error": "You have already reviewed this product"})
        elif item_type == 'combo' and combo:
            if Review.objects.filter(user=self.request.user, combo=combo, item_type='combo').exists():
                raise serializers.ValidationError({"error": "You have already reviewed this combo"})
        
        # ENFORCE verified purchase - user must have a delivered order with this item
        has_purchased = False
        if item_type == 'product' and product:
            has_purchased = OrderItem.objects.filter(
                order__user=self.request.user,
                product=product,
                order__status='delivered'
            ).exists()
        elif item_type == 'combo' and combo:
            has_purchased = OrderItem.objects.filter(
                order__user=self.request.user,
                combo=combo,
                order__status='delivered'
            ).exists()
        
        # Reject review if user hasn't purchased and received the item
        if not has_purchased:
            raise serializers.ValidationError({
                "error": "You can only review items from orders that have been delivered to you"
            })
        
        serializer.save(user=self.request.user, is_verified_purchase=True)
