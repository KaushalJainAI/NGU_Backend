from django.shortcuts import render, get_object_or_404

from rest_framework import viewsets, permissions, status, mixins
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from decimal import Decimal

from .utils import generate_upi_qr_code
from .models import ReceivableAccount, Coupon, Policy
from .serializers import (
    ReceivableAccountSerializer, 
    CouponSerializer, 
    RecentOrderSerializer,
    PolicySerializer
)
from cart.models import Cart
from orders.models import Order
from products.models import Product, ProductCombo, ProductComboItem


# ==================== PERMISSIONS ====================

class IsSuperUser(permissions.BasePermission):
    """
    Custom permission to allow only superusers
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsReadOnlyOrSuperUser(permissions.BasePermission):
    """
    - Read-only access for everyone (including unauthenticated users)
    - Write access only for superusers
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_superuser


# ==================== VIEWSETS ====================

class ReceivableAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet to manage receivable accounts by admin (superuser) only
    """
    queryset = ReceivableAccount.objects.all()
    serializer_class = ReceivableAccountSerializer
    permission_classes = [IsAuthenticated]


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsSuperUser]


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        total_orders = Order.objects.count()
        total_products = Product.objects.count()
        total_combos = ProductCombo.objects.count()
        active_coupons = Coupon.objects.count()
        graph_node_count = 0
        graph_edges_count = 0

        recent_orders_qs = Order.objects.order_by('-created_at')[:5]
        recent_orders = RecentOrderSerializer(recent_orders_qs, many=True).data

        data = {
            "totalProducts": total_products,
            "totalCombos": total_combos,
            "totalOrders": total_orders,
            "activeCoupons": active_coupons,
            "graphNodesCount": graph_node_count,
            "graphEdgeCount": graph_edges_count,
            "recentOrders": recent_orders
        }

        return Response(data)


class PolicyViewSet(viewsets.ModelViewSet):
    """
    Policy ViewSet:
    - Read-only (retrieve/list) for all users including anonymous
    - Update/Create/Delete only for superusers
    """
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsReadOnlyOrSuperUser]
    lookup_field = 'type'

    def get_object(self):
        return get_object_or_404(Policy, type=self.kwargs.get('type'))

    def update(self, request, *args, **kwargs):
        policy = self.get_object()
        if hasattr(policy, 'can_edit_by') and not policy.can_edit_by(request.user):
            return Response(
                {"error": "No permission to edit"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        policy = self.get_object()
        if hasattr(policy, 'can_edit_by') and not policy.can_edit_by(request.user):
            return Response(
                {"error": "No permission to edit"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)
