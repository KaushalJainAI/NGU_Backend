from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models import Sum, Avg, Count
from spices_backend.validators import validate_file_size, validate_image_extension


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
        default=8,
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
        """Get products for this section, limited by max_products - OPTIMIZED"""
        return self.products.filter(
            is_active=True
        ).select_related('category').only(
            'id', 'name', 'slug', 'image', 'price', 'discount_price',
            'weight', 'unit', 'badge', 'is_featured', 'category__name'
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
            models.Index(fields=['is_active', 'name']),
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
    
    # Flags
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=20, blank=True)
    
    # Section placement - ManyToMany relationship
    sections = models.ManyToManyField(
        ProductSection,
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
        
        super().save(*args, **kwargs)

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
        
        super().save(*args, **kwargs)

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
