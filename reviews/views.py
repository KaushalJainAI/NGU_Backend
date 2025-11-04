from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from .models import Review
from .serializers import ReviewSerializer
from orders.models import OrderItem

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer()
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.all().select_related('user', 'product')
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        elif self.request.user.is_authenticated and self.action == 'list':
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        if Review.objects.filter(user=self.request.user, product=product).exists():
            raise serializer.ValidationError("You have already reviewed this product")
        
        has_purchased = OrderItem.objects.filter(
            order__user=self.request.user,
            product=product,
            order__status='delivered'
        ).exists()
        
        serializer.save(user=self.request.user, is_verified_purchase=has_purchased)