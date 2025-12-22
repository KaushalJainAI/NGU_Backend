from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from users.views import (
    UserRegistrationView, UserProfileView, CustomTokenObtainPairView, ChangePasswordView
)
from products.views import (
    CategoryViewSet, ProductViewSet, ComboProductViewSet, ProductImageViewSet, get_spice_forms
)
from cart.views import CartViewSet, ValidateCouponAPIView
from orders.views import OrderViewSet
from reviews.views import ReviewViewSet
from payments.views import PaymentMethodViewSet
from admin_panel.views import ReceivableAccountViewSet, DashboardViewSet, CouponViewSet, PolicyViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'combos', ComboProductViewSet, basename='combos')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-methods')
router.register(r'receivable-accounts', ReceivableAccountViewSet, basename='receivable-accounts')
router.register(r'product-images', ProductImageViewSet, basename='product-image')
router.register(r'coupons', CouponViewSet, basename='coupon')

router.register(r'policies', PolicyViewSet, basename='policy')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')


urlpatterns = [
    path('admin/', admin.site.urls),

    # Main API endpoints
    path('api/', include(router.urls)),

    # Authentication endpoints
    path('api/auth/register/', UserRegistrationView.as_view(), name='register'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/profile/', UserProfileView.as_view(), name='profile'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password'),

    # Coupon validation endpoint
    path('api/auth/validate-coupon/', ValidateCouponAPIView.as_view(), name='validate-coupon'),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

     path('api/spice-forms/', get_spice_forms, name='spice-forms'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
