# Backend Architecture

This document explains the design principles, data flow, and non-obvious implementation details.

---

## Design Principles

### 1. **Layered Architecture**
```
┌─────────────────────────────────────────────────┐
│                  API Layer                       │
│           (views.py - ViewSets)                  │
├─────────────────────────────────────────────────┤
│              Serialization Layer                 │
│    (serializers.py - Data transformation)        │
├─────────────────────────────────────────────────┤
│               Business Logic                     │
│        (models.py - Methods on models)           │
├─────────────────────────────────────────────────┤
│                Data Layer                        │
│          (Django ORM → PostgreSQL)               │
└─────────────────────────────────────────────────┘
```

### 2. **Permission-Based Access Control**
Each ViewSet declares explicit permissions. The pattern:
- **Public read, Admin write**: Products, Categories, Combos
- **Authenticated only**: Cart, Orders, User Profile
- **Admin only**: Dashboard, Coupons, Receivable Accounts

### 3. **Slug-Based Lookups**
Products and Combos use slugs instead of IDs in URLs for SEO-friendly URLs.
```python
# Instead of: /api/products/123/
# We use:     /api/products/organic-turmeric-powder/
lookup_field = 'slug'
```

### 4. **Intelligent Caching**
Redis caches are scoped with prefixes and invalidated on writes:
- `ngu:products:list` - Product listing
- `ngu:categories:list` - Category listing  
- `ngu:dashboard:stats` - Dashboard statistics

---

## Application Flow

### User Registration → Order Placement

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│Register │────▶│  Login  │────▶│Add Cart │────▶│Checkout │────▶│  Order  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │               │
  users/          JWT            cart/           orders/          orders/
  views.py       tokens         views.py        views.py         models.py
```

### Order Lifecycle

```
PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
    │         │            │           │          │
    └─────────┴────────────┴───────────┴──────────┘
              Status updated via admin panel
```

---

## Key Implementation Details

### 1. Cart: Product vs Combo Items

The cart supports both products and combos through **separate fields**:
```python
class CartItem(models.Model):
    product = models.ForeignKey(Product, null=True)      # Regular product
    combo = models.ForeignKey(ProductCombo, null=True)   # Combo pack
    # Either product OR combo is set, never both
```

**Why?** Combos have different pricing logic (bundled discount) and different stock tracking (per-product in combo).

### 2. Order ID Format

Orders use a human-readable format: `ORD-XXXXXX`
```python
def generate_order_id():
    return f"ORD-{uuid.uuid4().hex[:6].upper()}"
```

**Why?** Easier for customer support to reference verbally and in chat.

### 3. Product Images: Main vs Gallery

Products have TWO image sources:
1. **Main image** (`Product.image`) - Primary display image
2. **Gallery images** (`ProductImage` model) - Additional views

```python
class Product(models.Model):
    image = models.ImageField()  # Main image, stored on model
    
class ProductImage(models.Model):
    product = ForeignKey(Product)
    image = models.ImageField()  # Gallery images, separate model
```

### 4. Combo Pricing

Combos store `original_price` and `price` (discounted):
```python
class ProductCombo(models.Model):
    original_price = models.DecimalField()  # Sum of individual products
    price = models.DecimalField()           # Discounted combo price
    
    @property
    def discount_percentage(self):
        return ((original_price - price) / original_price) * 100
```

### 5. S3 Storage Configuration (Django 5.x)

Django 5.x uses `STORAGES` dict instead of deprecated `DEFAULT_FILE_STORAGE`:
```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {"location": "media"},
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
        "OPTIONS": {"location": "static"},
    },
}
```

### 6. Chat Support: Order-Scoped Sessions

Chat sessions are tied to specific orders:
```python
class ChatSession(models.Model):
    user = ForeignKey(User)
    order = ForeignKey(Order)  # Session is per-order
    is_active = models.BooleanField()
```

**Why?** Allows customer to discuss issues about a specific order without confusion.

---

## Module Responsibilities

| App | Responsibility |
|-----|----------------|
| `users` | Authentication, profiles, JWT tokens |
| `products` | Catalog (products, combos, categories, images) |
| `cart` | Shopping cart with stock validation |
| `orders` | Order creation, status, history |
| `payments` | Payment processing (Razorpay) |
| `reviews` | Product ratings and reviews |
| `support` | Customer chat per order |
| `admin_panel` | Dashboard, coupons, policies, receivable accounts |

---

## Database Relationships

```
User ──┬── Cart ──── CartItem ──┬── Product
       │                        └── ProductCombo ── ProductComboItem ── Product
       │
       ├── Order ── OrderItem ──┬── Product
       │                        └── ProductCombo
       │
       ├── Review ── Product
       │
       └── ChatSession ── ChatMessage

Category ── Product ── ProductImage
```

---

## Security Considerations

1. **Input Validation**: Cart quantities must be positive integers (checked in `add_item`)
2. **Stock Check**: Orders validate stock before creation
3. **Owner Check**: Users can only access their own carts, orders, profiles
4. **Admin Check**: Dashboard/coupons require `is_staff=True`
5. **Payment Verification**: Razorpay signatures verified server-side

---

## Extending the Application

### Adding a New Feature

1. **Create app**: `python manage.py startapp feature_name`
2. **Define models** in `models.py`
3. **Add serializers** in `serializers.py`
4. **Create ViewSet** in `views.py`
5. **Register route** in `urls.py` via router
6. **Run migrations**: `python manage.py makemigrations && migrate`

### Adding a New API Endpoint to Existing ViewSet

Use `@action` decorator:
```python
class ProductViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['get'])
    def featured(self, request):
        # Custom endpoint: GET /api/products/featured/
        return Response(...)
```
