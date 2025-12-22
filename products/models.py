from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.db.models import Sum


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

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_products(self):
        """Get products for this section, limited by max_products"""
        return self.products.filter(is_active=True)[:self.max_products]
    
    def get_combos(self):
        """Get combos for this section, limited by max_products"""
        return self.combos.filter(is_active=True)[:self.max_products]


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
        ]

    def __str__(self):
        return f"{self.name} - {self.weight}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.weight}")
        
        # Track if this is a new product
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Auto-assign to "Newly Launched" section if it's a new product
        if is_new:
            try:
                newly_launched = ProductSection.objects.get(section_type='new')
                self.sections.add(newly_launched)
            except ProductSection.DoesNotExist:
                pass

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
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = self.reviews.all()
        if reviews:
            return round(sum([review.rating for review in reviews]) / len(reviews), 1)
        return 0

    @property
    def reviews_count(self):
        """Get total number of reviews"""
        return self.reviews.count()

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
        'Product',
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
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Track if this is a new combo
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Auto-assign to "Newly Launched" section if it's a new combo
        if is_new:
            try:
                newly_launched = ProductSection.objects.get(section_type='new')
                self.sections.add(newly_launched)
            except ProductSection.DoesNotExist:
                pass

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
        total = self.products.aggregate(
            total_price=Sum('price')
        )['total_price']
        return total or 0

    @property
    def total_weight(self):
        """Concat weights of products in the combo"""
        weights = self.products.values_list('weight', flat=True)
        return ', '.join(set(weights))
    
    @property
    def display_title(self):
        """Returns custom title if set, otherwise returns name"""
        return self.title if self.title else self.name


class ProductComboItem(models.Model):
    """Intermediate model for combo items with quantity"""
    combo = models.ForeignKey(ProductCombo, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ('combo', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.combo.name}"
