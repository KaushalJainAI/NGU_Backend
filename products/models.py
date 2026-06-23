from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models import Sum, Avg, Count
from django.core.files.base import ContentFile
from spices_backend.validators import validate_file_size, validate_image_extension
from PIL import Image
import io
import os


class ProductSection(models.Model):
    """Model for organizing products into homepage sections"""
    SECTION_TYPE_CHOICES = [
        ('special', 'Our Specials'),
        ('new', 'Newly Launched'),
        ('trending', 'Trending Now'),
        ('bestseller', 'Best Sellers'),
        ('seasonal', 'Seasonal'),
        ('custom', 'Custom Section'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_TYPE_CHOICES,
        default='custom'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon class name (e.g., fa-star)')
    display_order = models.PositiveIntegerField(
        default=0,
        help_text='Order in which sections appear on homepage'
    )
    max_products = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(1)],
        help_text='Maximum number of products to display in this section'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Product Section'
        verbose_name_plural = 'Product Sections'
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['section_type', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_products(self):
        """Get products for this section in the admin-defined order, limited by
        max_products. Ordered by the through model's position.

        NB: no .only() here — deferring fields hides modeltranslation's
        per-language columns (name_hi, ...), which would make translated
        content silently fall back to English."""
        return self.products.filter(
            is_active=True
        ).select_related('category').prefetch_related('variants').order_by(
            'productsectionplacement__position', 'productsectionplacement__id'
        )[:self.max_products]
    
    def get_combos(self):
        """Get combos for this section, limited by max_products - OPTIMIZED"""
        return self.combos.filter(
            is_active=True
        ).only(
            'id', 'name', 'slug', 'title', 'image', 'price', 'discount_price',
            'badge', 'weight', 'unit', 'is_featured'
        )[:self.max_products]


class Category(models.Model):
    """Product Category Model for organizing spices"""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='categories/', 
        blank=True, 
        null=True,
        validators=[validate_file_size, validate_image_extension]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if not base_slug:
                base_slug = "category"
            slug = base_slug
            counter = 1
            from django.core.exceptions import ValidationError
            from django.db import transaction, IntegrityError
            while True:
                self.slug = slug
                try:
                    self.full_clean()
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except (ValidationError, IntegrityError):
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                    
        self.full_clean()
        super().save(*args, **kwargs)


class Product(models.Model):
    """Product Model specifically designed for spices"""
    SPICE_FORM_CHOICES = [
        ('whole', 'Whole'),
        ('powder', 'Powder'),
        ('crushed', 'Crushed'),
        ('mixed', 'Mixed/Blend'),
    ]
    
    UNIT_CHOICES = [
        ('g', 'Grams'),
        ('kg', 'Kilograms'),
        ('ml', 'Milliliters'),
        ('l', 'Liters'),
        ('pc', 'Piece'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('combo', 'Combo'),
    ]
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='products'
    )
    description = models.TextField()
    spice_form = models.CharField(
        max_length=20, 
        choices=SPICE_FORM_CHOICES,
        help_text='Form of the spice (whole, powder, etc.)'
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    
    # Inventory
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Numerical value of the weight'
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=UNIT_CHOICES,
        help_text='e.g., pc, box, kg'
    )
    
    # Product Details
    origin_country = models.CharField(max_length=100, blank=True)
    organic = models.BooleanField(default=False)
    shelf_life = models.CharField(
        max_length=100, 
        blank=True, 
        help_text='e.g., 12 months, 24 months'
    )
    ingredients = models.TextField(blank=True)
    
    # Media
    image = models.ImageField(
        upload_to='products/',
        validators=[validate_file_size, validate_image_extension]
    )
    thumbnail = models.ImageField(
        upload_to='products/thumbnails/',
        blank=True,
        null=True,
        editable=False
    )
    
    # Flags
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=20, blank=True)
    
    # Section placement - ManyToMany relationship.
    # Uses an explicit through model so admins can order products WITHIN a
    # section (ProductSectionPlacement.position), not just pick which appear.
    sections = models.ManyToManyField(
        ProductSection,
        through='ProductSectionPlacement',
        related_name='products',
        blank=True,
        help_text='Homepage sections where this product appears'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['is_featured', '-created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_active', 'stock']),
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['spice_form', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(stock__gte=0), name='stock_non_negative'),
        ]

    def __str__(self):
        return f"{self.name} - {self.weight}"

    def clean(self):
        """Validate discount price is less than regular price"""
        if self.discount_price and self.price and self.discount_price >= self.price:
            raise ValidationError({
                'discount_price': 'Discount price must be less than regular price.'
            })

    def save(self, *args, **kwargs):
        if not self.slug:
            # Generate base slug from name and weight (handle None weight)
            weight_part = f"-{self.weight}" if self.weight else ""
            base_slug = slugify(f"{self.name}{weight_part}")
            
            # Fallback if slugify results in empty string
            if not base_slug:
                base_slug = "product"
                
            slug = base_slug
            counter = 1
            from django.core.exceptions import ValidationError
            from django.db import transaction, IntegrityError
            while True:
                self.slug = slug
                try:
                    self.full_clean()
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except (ValidationError, IntegrityError):
                    slug = f"{base_slug}-{counter}"
                    counter += 1
        
        # Run validation
        self.full_clean()
        
        # Generate thumbnail if image exists
        if self.image:
            self.generate_thumbnail()
            
        super().save(*args, **kwargs)

    def generate_thumbnail(self):
        """Generates a 300x300 thumbnail using Pillow"""
        if not self.image:
            return

        try:
            # Open the image using Pillow
            img = Image.open(self.image)
            img = img.convert('RGB')
            
            # Resize while maintaining aspect ratio
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            
            # Save the thumbnail to a BytesIO object
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            
            # Create a ContentFile from the BytesIO object
            filename = os.path.basename(self.image.name)
            thumb_filename = f"thumb_{filename}"
            
            # Save the thumbnail to the field
            self.thumbnail.save(
                thumb_filename, 
                ContentFile(thumb_io.getvalue()), 
                save=False
            )
        except Exception as e:
            print(f"Error generating thumbnail for product {self.name}: {e}")

    @property
    def final_price(self):
        """Returns the final price after discount if applicable"""
        return self.discount_price if self.discount_price else self.price

    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.discount_price and self.discount_price < self.price:
            return int(((self.price - self.discount_price) / self.price) * 100)
        return 0

    @property
    def in_stock(self):
        """Check if product is in stock"""
        return self.stock > 0

    @property
    def formatted_weight(self):
        """Returns weight with unit, formatted to remove trailing zeros (e.g., '250g')"""
        if self.weight and self.unit:
            w = float(self.weight)
            if w.is_integer():
                w = int(w)
            return f"{w}{self.unit}"
        return str(self.weight or "")


class ProductVariant(models.Model):
    """A specific packaging/size of a Product (e.g. 100g, 500g, 1kg).

    Lets one spice be offered in multiple packagings. Each variant carries its
    own price / discount / stock / weight; the parent Product holds the shared
    content (name, description, image, category, etc.).

    ADDITIVE ROLLOUT: the legacy per-size fields on Product
    (price/discount_price/stock/weight/unit) are intentionally KEPT for now.
    Every existing Product is backfilled with one is_default variant copying
    those values, so nothing downstream breaks until later phases move
    cart/orders/serializers onto variants.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )

    # Per-size attributes (mirror the legacy Product fields)
    weight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Numerical value of the weight'
    )
    unit = models.CharField(
        max_length=50, blank=True, null=True, choices=Product.UNIT_CHOICES,
        help_text='e.g., g, kg, pc'
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    sku = models.CharField(max_length=64, blank=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    is_default = models.BooleanField(
        default=False,
        help_text='The size shown by default on listings and the product page'
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(
        default=0, help_text='Order of this size on the product page (lower first)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product', 'display_order', 'weight']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock__gte=0), name='variant_stock_non_negative'
            ),
            # At most one default size per product (partial unique index — Postgres).
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_default=True),
                name='one_default_variant_per_product',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.formatted_weight}"

    def clean(self):
        if self.discount_price and self.price and self.discount_price >= self.price:
            raise ValidationError({
                'discount_price': 'Discount price must be less than regular price.'
            })

    def save(self, *args, **kwargs):
        if not self.slug:
            weight_part = f"-{self.formatted_weight}" if self.weight else ""
            base_slug = slugify(f"{self.product.name}{weight_part}") or "variant"
            slug = base_slug
            counter = 1
            from django.db import transaction, IntegrityError
            while True:
                self.slug = slug
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    slug = f"{base_slug}-{counter}"
                    counter += 1
        super().save(*args, **kwargs)

    @property
    def final_price(self):
        return self.discount_price if self.discount_price else self.price

    @property
    def discount_percentage(self):
        if self.discount_price and self.discount_price < self.price:
            return int(((self.price - self.discount_price) / self.price) * 100)
        return 0

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def formatted_weight(self):
        """Weight with unit, trailing zeros stripped (e.g. '250g', '1kg')."""
        if self.weight and self.unit:
            w = float(self.weight)
            if w.is_integer():
                w = int(w)
            return f"{w}{self.unit}"
        return str(self.weight or "")


class ProductSectionPlacement(models.Model):
    """Through model for Product.sections: lets an admin order products within
    a homepage section. Reuses the original auto-M2M join table (db_table +
    db_column below) so the conversion preserves existing placements."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    section = models.ForeignKey(
        ProductSection, on_delete=models.CASCADE, db_column='productsection_id'
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Order of this product within the section (lower shows first)'
    )

    class Meta:
        db_table = 'products_product_sections'
        ordering = ['position']
        unique_together = (('product', 'section'),)

    def __str__(self):
        return f"{self.product.name} in {self.section.name} @ {self.position}"


class ProductImage(models.Model):
    """Additional images for products (gallery)"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(
        upload_to='products/gallery/',
        validators=[validate_file_size, validate_image_extension]
    )
    alt_text = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product.name} - Image"


class ProductCombo(models.Model):
    """Model to represent a combo/bundle of multiple products"""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    # Custom titles for combo display
    title = models.CharField(
        max_length=300, 
        blank=True,
        help_text='Custom display title for the combo (e.g., "Ultimate Spice Collection - Save 30%")'
    )
    subtitle = models.CharField(
        max_length=300, 
        blank=True,
        help_text='Subtitle or tagline for the combo'
    )
    
    products = models.ManyToManyField(
        Product,  # Direct reference since Product is defined above
        through='ProductComboItem',
        related_name='combos'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        upload_to='combos/', 
        blank=True, 
        null=True,
        validators=[validate_file_size, validate_image_extension]
    )
    thumbnail = models.ImageField(
        upload_to='combos/thumbnails/',
        blank=True,
        null=True,
        editable=False
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=20, blank=True)
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Numerical value of the weight'
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=Product.UNIT_CHOICES,
        help_text='e.g., pc, box, kg'
    )
    
    # Section placement - ManyToMany relationship
    sections = models.ManyToManyField(
        ProductSection,
        related_name='combos',
        blank=True,
        help_text='Homepage sections where this combo appears'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_featured', '-created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate discount price is less than regular price"""
        if self.discount_price and self.price and self.discount_price >= self.price:
            raise ValidationError({
                'discount_price': 'Discount price must be less than regular price.'
            })

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if not base_slug:
                base_slug = "combo"
            slug = base_slug
            counter = 1
            from django.core.exceptions import ValidationError
            from django.db import transaction, IntegrityError
            while True:
                self.slug = slug
                try:
                    self.full_clean()
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except (ValidationError, IntegrityError):
                    slug = f"{base_slug}-{counter}"
                    counter += 1
        
        # Run validation
        self.full_clean()
        
        # Generate thumbnail if image exists
        if self.image:
            self.generate_thumbnail()
            
        super().save(*args, **kwargs)

    def generate_thumbnail(self):
        """Generates a 300x300 thumbnail using Pillow"""
        if not self.image:
            return

        try:
            img = Image.open(self.image)
            img = img.convert('RGB')
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            
            filename = os.path.basename(self.image.name)
            thumb_filename = f"thumb_{filename}"
            
            self.thumbnail.save(
                thumb_filename, 
                ContentFile(thumb_io.getvalue()), 
                save=False
            )
        except Exception as e:
            print(f"Error generating thumbnail for combo {self.name}: {e}")

    @property
    def final_price(self):
        """Returns final price after discount if applicable"""
        return self.discount_price if self.discount_price else self.price

    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.discount_price and self.discount_price < self.price:
            return int(((self.price - self.discount_price) / self.price) * 100)
        return 0

    @property
    def total_original_price(self):
        """Sum of original prices of products in the combo"""
        total = self.productcomboitem_set.aggregate(
            total=Sum(models.F('product__price') * models.F('quantity'))
        )['total']
        return total or 0

    @property
    def total_weight(self):
        """Concat weights of products in the combo"""
        # Formatted string like "250g, 500g"
        weights = []
        for product in self.products.all():
            if product.weight and product.unit:
                # Format to remove trailing zeros if it's an integer
                w = float(product.weight)
                if w.is_integer():
                    w = int(w)
                weights.append(f"{w}{product.unit}")
        return ', '.join(weights) if weights else ''
    
    @property
    def display_title(self):
        """Returns custom title if set, otherwise returns name"""
        return self.title if self.title else self.name


class ProductComboItem(models.Model):
    """Intermediate model for combo items with quantity"""
    combo = models.ForeignKey(ProductCombo, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # Direct reference
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ('combo', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.combo.name}"


class ProductSearchKB(models.Model):
    """LLM-generated search synonyms for products"""
    product = models.OneToOneField(
        Product, 
        on_delete=models.CASCADE, 
        related_name='search_kb'
    )
    synonyms = models.JSONField(default=list)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [models.Index(fields=['last_updated'])]
        verbose_name = 'Product Search KB'
        verbose_name_plural = 'Product Search KBs'
    
    def get_synonyms_list(self):
        return self.synonyms if isinstance(self.synonyms, list) else []


class ProductComboSearchKB(models.Model):
    """LLM-generated search synonyms for combos"""
    combo = models.OneToOneField(
        ProductCombo, 
        on_delete=models.CASCADE, 
        related_name='search_kb'
    )
    synonyms = models.JSONField(default=list)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [models.Index(fields=['last_updated'])]
        verbose_name = 'Combo Search KB'
        verbose_name_plural = 'Combo Search KBs'
    
    def get_synonyms_list(self):
        return self.synonyms if isinstance(self.synonyms, list) else []
