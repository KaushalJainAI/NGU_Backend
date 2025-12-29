from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Case, When, DecimalField, Value, IntegerField
from django.db.models.functions import Coalesce
from products.models import Product, ProductCombo


class Cart(models.Model):
    """Shopping Cart Model"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='cart',
        primary_key=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart - {self.user.email}"

    @property
    def total_price(self):
        """Calculate total price of all items in cart - OPTIMIZED with DB aggregation"""
        result = self.items.annotate(
            item_price=Case(
                When(
                    item_type='product',
                    then=Coalesce(F('product__discount_price'), F('product__price'))
                ),
                When(
                    item_type='combo',
                    then=Coalesce(F('combo__discount_price'), F('combo__price'))
                ),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Sum(F('item_price') * F('quantity'), output_field=DecimalField())
        )
        return result['total'] or 0

    @property
    def total_items(self):
        """Calculate total number of items in cart - OPTIMIZED with DB aggregation"""
        result = self.items.aggregate(total=Sum('quantity'))
        return result['total'] or 0

    def get_items_with_details(self):
        """Get cart items with related product/combo data in a single query - OPTIMIZED"""
        return self.items.select_related(
            'product', 
            'product__category',
            'combo'
        ).only(
            'id', 'item_type', 'quantity', 'created_at',
            'product__id', 'product__name', 'product__slug', 'product__image',
            'product__price', 'product__discount_price', 'product__weight', 
            'product__stock', 'product__category__name',
            'combo__id', 'combo__name', 'combo__slug', 'combo__image',
            'combo__price', 'combo__discount_price'
        )


class CartItem(models.Model):
    """Individual items in the shopping cart"""
    ITEM_TYPE_CHOICES = [
        ('product', 'Product'),
        ('combo', 'Combo'),
    ]
    
    cart = models.ForeignKey(
        Cart, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    combo = models.ForeignKey(
        ProductCombo, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    item_type = models.CharField(
        max_length=10, 
        choices=ITEM_TYPE_CHOICES, 
        default='product'
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        # Improved constraints to prevent any duplicate cart items
        constraints = [
            # Ensure only one product per cart (when item_type is 'product')
            models.UniqueConstraint(
                fields=['cart', 'product'],
                condition=models.Q(item_type='product', product__isnull=False),
                name='unique_cart_product'
            ),
            # Ensure only one combo per cart (when item_type is 'combo')
            models.UniqueConstraint(
                fields=['cart', 'combo'],
                condition=models.Q(item_type='combo', combo__isnull=False),
                name='unique_cart_combo'
            ),
            # Ensure quantity is always positive
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='positive_quantity'
            ),
            # Ensure either product or combo is set, but not both
            models.CheckConstraint(
                condition=(
                    models.Q(item_type='product', product__isnull=False, combo__isnull=True) |
                    models.Q(item_type='combo', combo__isnull=False, product__isnull=True)
                ),
                name='valid_item_type_reference'
            ),
        ]
        # Add indexes for better query performance
        indexes = [
            models.Index(fields=['cart', 'item_type']),
            models.Index(fields=['cart', 'product']),
            models.Index(fields=['cart', 'combo']),
        ]

    def __str__(self):
        item = self.product if self.item_type == 'product' else self.combo
        return f"{item.name if item else 'Unknown'} x {self.quantity}"

    @property
    def subtotal(self):
        """Calculate subtotal for this cart item"""
        if self.item_type == 'product' and self.product:
            return self.product.final_price * self.quantity
        elif self.item_type == 'combo' and self.combo:
            price = self.combo.final_price if hasattr(self.combo, 'final_price') else self.combo.price
            return price * self.quantity
        return 0

    def clean(self):
        """Validate that either product or combo is set based on item_type"""
        errors = {}
        
        # Check item_type specific validations
        if self.item_type == 'product':
            if not self.product:
                errors['product'] = 'Product must be set when item_type is product'
            if self.combo:
                errors['combo'] = 'Combo should be null when item_type is product'
        
        elif self.item_type == 'combo':
            if not self.combo:
                errors['combo'] = 'Combo must be set when item_type is combo'
            if self.product:
                errors['product'] = 'Product should be null when item_type is combo'
        
        # Validate quantity
        if self.quantity and self.quantity < 1:
            errors['quantity'] = 'Quantity must be at least 1'
        
        # Check stock availability
        if self.item_type == 'product' and self.product:
            if self.quantity > self.product.stock:
                errors['quantity'] = f'Only {self.product.stock} units available for {self.product.name}'
        
        elif self.item_type == 'combo' and self.combo:
            combo_stock = getattr(self.combo, 'stock', 999)
            if self.quantity > combo_stock:
                errors['quantity'] = f'Only {combo_stock} units available for {self.combo.name}'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to call clean method"""
        self.full_clean()
        super().save(*args, **kwargs)


class Favorite(models.Model):
    """User's favorite products"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='favorites'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate favorites
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_favorite'
            )
        ]
        # Add index for faster lookups
        indexes = [
            models.Index(fields=['user', 'added_at']),
        ]
        ordering = ['-added_at']
        verbose_name = 'Favorite'
        verbose_name_plural = 'Favorites'

    def __str__(self):
        return f"{self.user.email} - {self.product.name}"
