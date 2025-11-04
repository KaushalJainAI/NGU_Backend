# COMPLETE SETUP AND INSTALLATION GUIDE
## Django REST Framework Spices E-commerce Backend

---

## 📋 TABLE OF CONTENTS

1. [Initial Setup](#initial-setup)
2. [Project Structure](#project-structure)
3. [Installation Steps](#installation-steps)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [API Testing](#api-testing)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 INITIAL SETUP

### Step 1: Create Project Directory

```bash
# Create and navigate to project directory
mkdir spices_ecommerce
cd spices_ecommerce

# Initialize git (optional)
git init
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# Verify activation (should show (venv) in terminal)
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install from requirements.txt
pip install -r requirements.txt
```

---

## 📁 PROJECT STRUCTURE

Create this folder structure:

```
spices_ecommerce/
│
├── spices_backend/          # Project config folder
│   ├── __init__.py
│   ├── settings.py          # Main settings file
│   ├── urls.py              # Main URL configuration
│   ├── asgi.py
│   └── wsgi.py
│
├── users/                   # User app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── tests.py
│   └── urls.py
│
├── products/                # Products app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── tests.py
│   └── urls.py
│
├── cart/                    # Cart app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── orders/                  # Orders app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── payments/                # Payments app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── reviews/                 # Reviews app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── media/                   # User uploaded files
├── staticfiles/             # Static files
├── .env                     # Environment variables
├── .env.example             # Example env file
├── .gitignore               # Git ignore file
├── requirements.txt         # Python dependencies
├── manage.py                # Django management
└── db.sqlite3              # Database (development only)
```

---

## 📦 INSTALLATION STEPS

### Step 1: Create Django Project and Apps

```bash
# Navigate to project directory
cd spices_ecommerce

# Create Django project
django-admin startproject spices_backend .

# Create Django apps
python manage.py startapp users
python manage.py startapp products
python manage.py startapp cart
python manage.py startapp orders
python manage.py startapp payments
python manage.py startapp reviews
```

### Step 2: Copy Configuration Files

1. **Copy settings.py** - Replace the generated `spices_backend/settings.py` with the provided `settings.py` file

2. **Copy .env file**:
```bash
# Create .env file from example
cp .env.example .env

# Edit .env with your settings
# Important: Change SECRET_KEY for production
```

3. **Copy all model files**:
   - Copy User model from `all-models.py` into `users/models.py`
   - Copy Category, Product, ProductImage models into `products/models.py`
   - Copy Cart, CartItem models into `cart/models.py`
   - Copy Order, OrderItem models into `orders/models.py`
   - Copy Payment model into `payments/models.py`
   - Copy Review model into `reviews/models.py`

4. **Copy all serializer files**:
   - Copy user serializers into `users/serializers.py`
   - Copy product serializers into `products/serializers.py`
   - Copy cart serializers into `cart/serializers.py`
   - Copy order serializers into `orders/serializers.py`
   - Copy payment serializers into `payments/serializers.py`
   - Copy review serializers into `reviews/serializers.py`

5. **Copy all view files**:
   - Copy user views into `users/views.py`
   - Copy product views into `products/views.py`
   - Copy cart views into `cart/views.py`
   - Copy order views into `orders/views.py`
   - Copy review views into `reviews/views.py`

6. **Copy URLs and Admin files**:
   - Copy URL configuration into `spices_backend/urls.py`
   - Copy each app's admin configuration into respective `app/admin.py`

---

## 🗄️ DATABASE SETUP

### Step 1: Create Migrations

```bash
# Create migration files for all models
python manage.py makemigrations

# Apply migrations to database
python manage.py migrate
```

### Step 2: Create Superuser

```bash
# Create admin user
python manage.py createsuperuser

# Follow the prompts:
# Email: admin@example.com
# Username: admin
# Password: ••••••••
# Password (again): ••••••••
```

### Step 3: Create Sample Data (Optional)

Create a `load_sample_data.py` script in project root:

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spices_backend.settings')
django.setup()

from products.models import Category, Product
from decimal import Decimal

# Create categories
categories = [
    Category.objects.create(name='Whole Spices', description='Premium whole spices'),
    Category.objects.create(name='Spice Powders', description='Finely ground spice powders'),
    Category.objects.create(name='Spice Blends', description='Pre-mixed spice blends'),
    Category.objects.create(name='Organic Spices', description='Certified organic spices'),
]

# Create sample products
products_data = [
    {
        'name': 'Black Pepper',
        'category': categories[0],
        'description': 'Premium black pepper from Kerala',
        'spice_form': 'whole',
        'price': Decimal('250.00'),
        'discount_price': Decimal('200.00'),
        'stock': 100,
        'weight': '100g',
        'organic': True,
    },
    {
        'name': 'Turmeric Powder',
        'category': categories[1],
        'description': 'Pure turmeric powder',
        'spice_form': 'powder',
        'price': Decimal('150.00'),
        'stock': 200,
        'weight': '250g',
        'organic': True,
    },
    {
        'name': 'Garam Masala',
        'category': categories[2],
        'description': 'Traditional Indian spice blend',
        'spice_form': 'mixed',
        'price': Decimal('300.00'),
        'stock': 150,
        'weight': '100g',
    },
]

for data in products_data:
    Product.objects.create(**data)

print("Sample data loaded successfully!")
```

Run it:
```bash
python load_sample_data.py
```

---

## ▶️ RUNNING THE APPLICATION

### Start Development Server

```bash
# Run development server
python manage.py runserver

# Server will start at http://127.0.0.1:8000/
```

### Access the Application

- **Admin Panel**: http://localhost:8000/admin/
- **API Browsable**: http://localhost:8000/api/
- **API Docs (Swagger)**: http://localhost:8000/api/docs/

---

## 🧪 API TESTING

### Using Postman or Thunder Client

1. **Register User**:
```
POST http://localhost:8000/api/auth/register/
Content-Type: application/json

{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "password2": "SecurePass123!",
    "phone": "9876543210"
}
```

2. **Login**:
```
POST http://localhost:8000/api/auth/login/
Content-Type: application/json

{
    "email": "test@example.com",
    "password": "SecurePass123!"
}
```

Response:
```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

3. **Get Products**:
```
GET http://localhost:8000/api/products/
Authorization: Bearer YOUR_ACCESS_TOKEN
```

4. **Add to Cart**:
```
POST http://localhost:8000/api/cart/add_item/
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
    "product_id": 1,
    "quantity": 2
}
```

5. **Create Order**:
```
POST http://localhost:8000/api/orders/
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
    "shipping_address": "123 Main St",
    "shipping_city": "Delhi",
    "shipping_state": "Delhi",
    "shipping_pincode": "110001",
    "phone": "9876543210",
    "payment_method": "cod"
}
```

---

## 🐛 TROUBLESHOOTING

### Common Issues and Solutions

**Issue 1: ModuleNotFoundError: No module named 'decouple'**
```bash
pip install python-decouple
```

**Issue 2: No such table: auth_user**
```bash
python manage.py migrate
```

**Issue 3: STATIC_ROOT or MEDIA_ROOT issues**
```bash
# Create directories
mkdir media staticfiles
python manage.py collectstatic
```

**Issue 4: Port 8000 already in use**
```bash
python manage.py runserver 8001
```

**Issue 5: Secret key is not secure**
```python
# Generate new secret key
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())

# Update in .env
SECRET_KEY=your-new-generated-key
```

---

## 📝 IMPORTANT NOTES

1. **Never commit .env file** - Add to .gitignore
2. **Change SECRET_KEY** in production
3. **Use PostgreSQL** in production instead of SQLite
4. **Enable HTTPS** for production
5. **Set DEBUG=False** in production
6. **Use environment variables** for sensitive data

---

## 🎯 QUICK START CHECKLIST

- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Create Django project and apps
- [ ] Copy configuration files
- [ ] Copy models, serializers, views
- [ ] Create and apply migrations
- [ ] Create superuser
- [ ] Load sample data
- [ ] Start development server
- [ ] Test API endpoints
- [ ] Configure frontend integration

---

## 📚 USEFUL COMMANDS

```bash
# Database operations
python manage.py makemigrations          # Create migrations
python manage.py migrate                 # Apply migrations
python manage.py createsuperuser         # Create admin user

# Development
python manage.py runserver               # Start dev server
python manage.py shell                   # Python shell with Django

# Static files
python manage.py collectstatic           # Collect static files

# Cleaning
python manage.py flush                   # Reset database

# Testing
python manage.py test                    # Run tests
```

---

**Setup Complete! 🎉 Your Django REST Framework backend is ready to use.**
