from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models import Sum, Avg, Count


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
            'weight', 'badge', 'is_featured', 'category__name'
        )[:self.max_products]
    
    def get_combos(self):
        """Get combos for this section, limited by max_products - OPTIMIZED"""
        return self.combos.filter(
            is_active=True
        ).only(
            'id', 'name', 'slug', 'title', 'image', 'price', 'discount_price',
            'badge', 'is_featured'
        )[:self.max_products]


class Category(models.Model):
    """Product Category Model for organizing spices"""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
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
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """Product Model specifically designed for spices"""
    SPICE_FORM_CHOICES = [
        ('whole', 'Whole'),
        ('powder', 'Powder'),
        ('crushed', 'Crushed'),
        ('mixed', 'Mixed/Blend'),
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
    weight = models.CharField(
        max_length=50, 
        help_text='e.g., 100g, 250g, 500g, 1kg'
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
    image = models.ImageField(upload_to='products/')
    
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
            self.slug = slugify(f"{self.name}-{self.weight}")
        
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


class ProductImage(models.Model):
    """Additional images for products (gallery)"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='products/gallery/')
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
    image = models.ImageField(upload_to='combos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=20, blank=True)
    
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
            self.slug = slugify(self.name)
        
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
        weights = self.products.values_list('weight', flat=True)
        return ', '.join(set(weights)) if weights else ''
    
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
