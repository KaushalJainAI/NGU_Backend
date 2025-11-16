from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify

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