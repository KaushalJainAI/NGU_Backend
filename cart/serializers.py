from rest_framework import serializers
from .models import Cart, CartItem, Favorite
from products.serializers import ProductListSerializer
from admin_panel.serializers import CouponSerializer


# ---------------------------------------------------------------------------
# Cart Item Serializer (polymorphic: product OR combo)
# ---------------------------------------------------------------------------

class CartItemResponseSerializer(serializers.Serializer):
    """
    Serializer for a single cart item returned in the cart list response.
    Handles both 'product' and 'combo' item types safely.
    All field access uses SerializerMethodField so that missing/null
    attributes never raise AttributeError.
    """
    id = serializers.SerializerMethodField()
    item_type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    originalPrice = serializers.SerializerMethodField()
    badge = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()
    subtotal = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    def _get_item(self, obj):
        """Return the underlying Product or ProductCombo instance."""
        item_type = getattr(obj, 'item_type', 'product') or 'product'
        if item_type == 'combo':
            return obj.combo
        return obj.product

    def get_id(self, obj):
        item = self._get_item(obj)
        return str(item.id) if item else None

    def get_item_type(self, obj):
        return getattr(obj, 'item_type', 'product') or 'product'

    def get_name(self, obj):
        item = self._get_item(obj)
        return getattr(item, 'name', '') if item else ''

    def get_image(self, obj):
        item = self._get_item(obj)
        if not item or not getattr(item, 'image', None):
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(item.image.url)
        return item.image.url

    def get_price(self, obj):
        item = self._get_item(obj)
        if not item:
            return 0
        if hasattr(item, 'final_price'):
            return float(item.final_price)
        return float(getattr(item, 'price', 0))

    def get_originalPrice(self, obj):
        """
        The original (non-discounted) price.
        Product model uses .price for original and .discount_price for discounted.
        """
        item = self._get_item(obj)
        if not item:
            return 0
        return float(getattr(item, 'price', 0))

    def get_badge(self, obj):
        item = self._get_item(obj)
        return getattr(item, 'badge', None) if item else None

    def get_subtotal(self, obj):
        return float(getattr(obj, 'subtotal', 0))

    def get_stock(self, obj):
        item_type = getattr(obj, 'item_type', 'product') or 'product'
        item = self._get_item(obj)
        if not item:
            return 0
        if item_type == 'product':
            return getattr(item, 'stock', 0)
        return getattr(item, 'stock', 999)  # combos default to 999

    def get_in_stock(self, obj):
        item_type = getattr(obj, 'item_type', 'product') or 'product'
        item = self._get_item(obj)
        if not item:
            return False
        if item_type == 'product' and hasattr(item, 'stock'):
            return item.stock > 0
        return True


# ---------------------------------------------------------------------------
# Cart Response Serializer (wraps items + summary)
# ---------------------------------------------------------------------------

class CartResponseSerializer(serializers.Serializer):
    """
    Top-level cart response.  Accepts a dict with 'cart' (Cart instance)
    and 'request' in the serializer context.
    """
    success = serializers.BooleanField(default=True)
    items = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    def get_items(self, obj):
        cart = obj['cart']
        cart_items = cart.items.select_related('product', 'product__category', 'combo').all()
        return CartItemResponseSerializer(
            cart_items,
            many=True,
            context=self.context,
        ).data

    def get_summary(self, obj):
        cart = obj['cart']
        subtotal = float(cart.total_price)
        tax = round(subtotal * 0.05, 2)
        discount = 0
        shipping = 0 if subtotal >= 500 or subtotal == 0 else 50
        total = round(subtotal + tax + shipping - discount, 2)
        return {
            'subtotal': subtotal,
            'tax': tax,
            'shipping': shipping,
            'discount': discount,
            'total': total,
        }


# ---------------------------------------------------------------------------
# Favorite Item Serializer
# ---------------------------------------------------------------------------

class FavoriteItemSerializer(serializers.Serializer):
    """
    Serializer for a single favorite item.
    All fields use safe getattr so that missing model attributes never crash.
    """
    id = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    weight = serializers.SerializerMethodField()
    badge = serializers.SerializerMethodField()
    added_at = serializers.SerializerMethodField()

    def get_id(self, obj):
        product = getattr(obj, 'product', None)
        return product.id if product else None

    def get_product_id(self, obj):
        product = getattr(obj, 'product', None)
        return product.id if product else None

    def get_name(self, obj):
        product = getattr(obj, 'product', None)
        return getattr(product, 'name', '') if product else ''

    def get_image(self, obj):
        product = getattr(obj, 'product', None)
        if not product or not getattr(product, 'image', None):
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(product.image.url)
        return product.image.url

    def get_price(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return 0
        if hasattr(product, 'final_price'):
            return float(product.final_price)
        return float(getattr(product, 'price', 0))

    def get_original_price(self, obj):
        """Original (non-discounted) price = product.price"""
        product = getattr(obj, 'product', None)
        if not product:
            return None
        price = getattr(product, 'price', None)
        return float(price) if price is not None else None

    def get_weight(self, obj):
        product = getattr(obj, 'product', None)
        return getattr(product, 'weight', None) if product else None

    def get_badge(self, obj):
        product = getattr(obj, 'product', None)
        return getattr(product, 'badge', None) if product else None

    def get_added_at(self, obj):
        added_at = getattr(obj, 'added_at', None)
        return added_at.isoformat() if added_at else None


# ---------------------------------------------------------------------------
# Legacy serializers (kept for backward compatibility)
# ---------------------------------------------------------------------------

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal', 'created_at', 'item_type']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price', 'total_items', 'created_at', 'updated_at']


class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50, required=True)


class FavoriteSerializer(serializers.ModelSerializer):
    """Legacy serializer kept for backward compatibility.
    Uses product.price for originalPrice since Product has no original_price field."""
    id = serializers.CharField(source='product.id')
    name = serializers.CharField(source='product.name')
    image = serializers.ImageField(source='product.image', allow_null=True)
    price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2)
    originalPrice = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, required=False)
    weight = serializers.CharField(source='product.weight', allow_null=True, required=False)
    badge = serializers.CharField(source='product.badge', allow_null=True, required=False)

    class Meta:
        model = Favorite
        fields = ('id', 'name', 'image', 'price', 'originalPrice', 'weight', 'badge')
