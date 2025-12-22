from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PaymentMethod
from .serializers import PaymentMethodSerializer, PaymentMethodCreateSerializer

# Create your views here.


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment methods
    
    Endpoints:
    - GET /api/payment-methods/ - List all payment methods
    - POST /api/payment-methods/ - Create new payment method
    - GET /api/payment-methods/{id}/ - Get specific payment method
    - PUT/PATCH /api/payment-methods/{id}/ - Update payment method
    - DELETE /api/payment-methods/{id}/ - Delete (soft delete) payment method
    - POST /api/payment-methods/{id}/set_default/ - Set as default
    - GET /api/payment-methods/default/ - Get default payment method
    - GET /api/payment-methods/by_type/?type=UPI - Filter by type
    """
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Users can only see their own payment methods
        """
        return PaymentMethod.objects.filter(
            user=self.request.user,
            is_active=True
        )

    def get_serializer_class(self):
        """
        Use different serializer for create action
        """
        if self.action == 'create':
            return PaymentMethodCreateSerializer
        return PaymentMethodSerializer

    def perform_create(self, serializer):
        """
        Automatically set the user when creating a payment method
        """
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        """
        Soft delete - set is_active to False instead of deleting
        """
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """
        Set a payment method as default
        
        Usage: POST /api/payment-methods/{id}/set_default/
        """
        payment_method = self.get_object()
        
        # Remove default from all other payment methods
        PaymentMethod.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)
        
        # Set this one as default
        payment_method.is_default = True
        payment_method.save()
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def default(self, request):
        """
        Get the default payment method
        
        Usage: GET /api/payment-methods/default/
        """
        payment_method = PaymentMethod.objects.filter(
            user=request.user,
            is_default=True,
            is_active=True
        ).first()
        
        if not payment_method:
            return Response(
                {'detail': 'No default payment method found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get payment methods filtered by type
        
        Usage: GET /api/payment-methods/by_type/?type=UPI
        Supported types: UPI, CARD, NETBANKING, WALLET
        """
        payment_type = request.query_params.get('type', None)
        
        if not payment_type:
            return Response(
                {'detail': 'Payment type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate payment type
        valid_types = ['UPI', 'CARD', 'NETBANKING', 'WALLET']
        payment_type_upper = payment_type.upper()
        
        if payment_type_upper not in valid_types:
            return Response(
                {
                    'detail': f'Invalid payment type. Must be one of: {", ".join(valid_types)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_methods = self.get_queryset().filter(payment_type=payment_type_upper)
        serializer = self.get_serializer(payment_methods, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get statistics about user's payment methods
        
        Usage: GET /api/payment-methods/stats/
        """
        queryset = self.get_queryset()
        
        stats = {
            'total': queryset.count(),
            'by_type': {
                'upi': queryset.filter(payment_type='UPI').count(),
                'card': queryset.filter(payment_type='CARD').count(),
                'netbanking': queryset.filter(payment_type='NETBANKING').count(),
                'wallet': queryset.filter(payment_type='WALLET').count(),
            },
            'has_default': queryset.filter(is_default=True).exists()
        }
        
        return Response(stats)

