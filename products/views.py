from rest_framework import viewsets, filters, status
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings

from .models import Category, Product, ProductCombo, ProductImage, ProductSection
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductComboSerializer,
    ProductImageSerializer
)
from .cache import (
    make_cache_key,
    CACHE_PREFIX_PRODUCTS,
    CACHE_PREFIX_CATEGORIES,
    CACHE_PREFIX_COMBOS,
    CACHE_PREFIX_SECTIONS,
    TTL_MEDIUM,
    TTL_LONG,
)

# Cache TTLs from settings
CACHE_TTL = getattr(settings, 'CACHE_TTL_MEDIUM', 300)
CACHE_TTL_CATEGORIES = getattr(settings, 'CACHE_TTL_LONG', 900)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


@api_view(['GET'])
def get_spice_forms(request):
    from .models import Product
    spice_forms = [
        {'value': choice[0], 'label': choice[1]}
        for choice in Product.SPICE_FORM_CHOICES
    ]
    return Response(spice_forms)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = Category.objects.all()
        user = self.request.user
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs

    def list(self, request, *args, **kwargs):
        """Cached category list for non-admin users."""
        # Skip cache for staff users - they need to see fresh data
        if request.user and request.user.is_staff:
            return super().list(request, *args, **kwargs)
        
        cache_key = make_cache_key(CACHE_PREFIX_CATEGORIES, 'list')
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, CACHE_TTL_CATEGORIES)
        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to support both ID and slug lookup
        """
        lookup_value = kwargs.get('slug')
        qs = self.get_queryset()
        
        try:
            if lookup_value and lookup_value.isdigit():
                # Numeric ID lookup
                instance = get_object_or_404(qs, id=int(lookup_value))
            else:
                # Slug lookup
                instance = get_object_or_404(qs, slug=lookup_value)
        except Category.DoesNotExist:
            return Response(
                {"detail": "No Category matches the given query."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'spice_form', 'organic', 'is_featured', 'is_active']
    search_fields = ['name', 'description', 'ingredients']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        """Optimized queryset with conditional field selection"""
        user = self.request.user
        is_staff = user and user.is_staff
        
        # Base queryset with select_related for category
        qs = Product.objects.select_related('category')
        
        # Filter for non-staff users
        if not is_staff:
            qs = qs.filter(is_active=True)
        
        # For list action, use only() to fetch minimal fields
        if self.action == 'list':
            qs = qs.only(
                'id', 'name', 'slug', 'image', 'price', 'discount_price',
                'weight', 'badge', 'is_featured', 'stock', 'organic',
                'spice_form', 'category__id', 'category__name', 'category__slug',
                'created_at', 'is_active'
            )
        else:
            # For detail views, prefetch related data
            qs = qs.prefetch_related('images', 'sections')
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

    def list(self, request, *args, **kwargs):
        """Cached product list for non-admin users."""
        # Skip cache for staff users
        if request.user and request.user.is_staff:
            return super().list(request, *args, **kwargs)
        
        # Build cache key from query params
        query_params = dict(request.query_params)
        cache_key = make_cache_key(CACHE_PREFIX_PRODUCTS, 'list', **query_params)
        
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, CACHE_TTL)
        return response


    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to support both ID and slug lookup
        """
        lookup_value = kwargs.get('slug')
        qs = self.get_queryset()
        
        try:
            if lookup_value and lookup_value.isdigit():
                # Numeric ID lookup
                instance = get_object_or_404(qs, id=int(lookup_value))
            else:
                # Slug lookup
                instance = get_object_or_404(qs, slug=lookup_value)
        except Product.DoesNotExist:
            return Response(
                {"detail": "No Product matches the given query."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def sections(self, request):
        """Get all active product sections with their products and combos - CACHED"""
        # Check cache for non-staff users
        cache_key = make_cache_key(CACHE_PREFIX_SECTIONS, 'all')
        if not (request.user and request.user.is_staff):
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
        
        sections = ProductSection.objects.filter(is_active=True).order_by('display_order')
        
        results = []
        for section in sections:
            # Get products for this section
            products = []
            for product in section.get_products():
                products.append({
                    'id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'image': request.build_absolute_uri(product.image.url) if product.image else '',
                    'price': float(product.final_price),
                    'original_price': float(product.price),
                    'discount': product.discount_percentage,
                    'weight': product.weight,
                    'badge': product.badge,
                    'is_featured': product.is_featured,
                })
            
            # Get combos for this section
            combos = []
            for combo in section.get_combos():
                combos.append({
                    'id': combo.id,
                    'name': combo.display_title,
                    'slug': combo.slug,
                    'image': request.build_absolute_uri(combo.image.url) if combo.image else '',
                    'price': float(combo.final_price),
                    'original_price': float(combo.price),
                    'discount': combo.discount_percentage,
                    'badge': combo.badge or 'Combo',
                    'is_featured': combo.is_featured,
                })
            
            results.append({
                'id': section.id,
                'name': section.name,
                'slug': section.slug,
                'section_type': section.section_type,
                'description': section.description,
                'products': products,
                'combos': combos,
            })
        
        response_data = {'results': results}
        
        # Cache for non-staff users
        if not (request.user and request.user.is_staff):
            cache.set(cache_key, response_data, CACHE_TTL)
        
        return Response(response_data)


class ComboProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductComboSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_featured', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Optimized queryset with conditional field selection"""
        user = self.request.user
        is_staff = user and user.is_staff
        
        # Base queryset
        qs = ProductCombo.objects.all()
        
        # Filter for non-staff users
        if not is_staff:
            qs = qs.filter(is_active=True)
        
        # For list action, use only() to fetch minimal fields
        if self.action == 'list':
            qs = qs.only(
                'id', 'name', 'slug', 'title', 'image', 'price', 'discount_price',
                'badge', 'is_featured', 'is_active', 'created_at'
            )
        else:
            # For detail views, prefetch related data
            qs = qs.prefetch_related('productcomboitem_set__product', 'sections')
        
        return qs

    def list(self, request, *args, **kwargs):
        """Cached combo list for non-admin users."""
        # Skip cache for staff users
        if request.user and request.user.is_staff:
            return super().list(request, *args, **kwargs)
        
        # Build cache key from query params
        query_params = dict(request.query_params)
        cache_key = make_cache_key(CACHE_PREFIX_COMBOS, 'list', **query_params)
        
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, CACHE_TTL)
        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to support both ID and slug lookup
        """
        lookup_value = kwargs.get('slug')
        qs = self.get_queryset()
        
        try:
            if lookup_value and lookup_value.isdigit():
                # Numeric ID lookup
                instance = get_object_or_404(qs, id=int(lookup_value))
            else:
                # Slug lookup
                instance = get_object_or_404(qs, slug=lookup_value)
        except ProductCombo.DoesNotExist:
            return Response(
                {"detail": "No ProductCombo matches the given query."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        qs = ProductImage.objects.select_related('product')
        product_id = self.request.query_params.get('product', None)
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs
    

from .recommendations import SpiceSearchEngine
search_engine = SpiceSearchEngine()

@api_view(['GET'])
def unified_search(request):
    """SINGLE ENDPOINT: Search + All Recommendations (Products + Combos ranked)"""
    query = request.GET.get('q', '').strip()
    top_k = int(request.GET.get('top_k', 20))
    threshold = int(request.GET.get('threshold', 60))
    
    if not query:
        return Response({'error': 'Query "q" required'}, status=400)
    
    results = search_engine.unified_search(query, top_k, threshold)
    return Response(results)
