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
        user = self.request.user
        queryset = Review.objects.all().select_related('user', 'product', 'combo')
        
        # Filter by product or combo
        product_id = self.request.query_params.get('product')
        combo_id = self.request.query_params.get('combo')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id, item_type='product')
        elif combo_id:
            queryset = queryset.filter(combo_id=combo_id, item_type='combo')
        elif user.is_authenticated and self.action == 'list':
            queryset = queryset.filter(user=user)

        # SECURITY: If not staff, ensure user can only edit/delete their own reviews
        if not (user.is_authenticated and user.is_staff) and self.action not in ['list', 'retrieve']:
            if user.is_authenticated:
                queryset = queryset.filter(user=user)
            else:
                queryset = queryset.none()
            
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
        
        # ENFORCE verified purchase - user must have a shipped/delivered order with this item
        has_purchased = False
        allowed_statuses = ['shipped', 'delivered', 'delivering']
        
        if item_type == 'product' and product:
            has_purchased = OrderItem.objects.filter(
                order__user=self.request.user,
                product=product,
                order__status__in=allowed_statuses
            ).exists()
        elif item_type == 'combo' and combo:
            has_purchased = OrderItem.objects.filter(
                order__user=self.request.user,
                combo=combo,
                order__status__in=allowed_statuses
            ).exists()
        
        # Reject review if user hasn't purchased and received the item
        if not has_purchased:
            raise serializers.ValidationError({
                "error": "You can only review items from orders that have been shipped or delivered"
            })
        
        serializer.save(user=self.request.user, is_verified_purchase=True)
