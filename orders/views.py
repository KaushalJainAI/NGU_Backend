from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Order, OrderItem
from .serializers import OrderListSerializer, OrderDetailSerializer, OrderCreateSerializer
from cart.models import Cart

class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderDetailSerializer

    @transaction.atomic
    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        if not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        subtotal = cart.total_price
        shipping_charge = 0 if subtotal >= 500 else 50
        tax = subtotal * 0.05
        total_amount = subtotal + shipping_charge + tax

        order = Order.objects.create(
            user=request.user,
            subtotal=subtotal,
            shipping_charge=shipping_charge,
            tax=tax,
            total_amount=total_amount,
            **serializer.validated_data
        )

        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                product_name=cart_item.product.name,
                product_weight=cart_item.product.weight,
                quantity=cart_item.quantity,
                price=cart_item.product.final_price
            )
            cart_item.product.stock -= cart_item.quantity
            cart_item.product.save()

        cart.items.all().delete()
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in ['delivered', 'cancelled']:
            return Response({'error': 'Cannot cancel this order'}, status=status.HTTP_400_BAD_REQUEST)
        
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save()
        
        order.status = 'cancelled'
        order.save()
        return Response(OrderDetailSerializer(order).data)
