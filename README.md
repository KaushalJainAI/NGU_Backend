# 🌶️ Django REST Framework - Spices E-commerce Backend
## Complete Implementation Guide

---

## 📖 README

This is a **production-ready, complete Django REST Framework backend** for a spices e-commerce website. All code is provided and ready to use.

### ✨ Features Included

✅ **JWT Authentication** - Secure user authentication with tokens  
✅ **User Management** - Registration, profile, address  
✅ **Product Catalog** - Categories, products with variants  
✅ **Shopping Cart** - Add, update, remove items  
✅ **Order Management** - Full order lifecycle  
✅ **Payment Integration** - Stripe, Razorpay, COD  
✅ **Reviews System** - Ratings and verified purchases  
✅ **Admin Dashboard** - Full customized Django admin  
✅ **API Documentation** - Swagger/OpenAPI  
✅ **Pagination & Filtering** - Advanced search options  

### 🛠️ Technology Stack

- **Framework**: Django 4.2+
- **API**: Django REST Framework
- **Authentication**: Simple JWT
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Payment**: Stripe, Razorpay
- **Image Processing**: Pillow
- **Other**: CORS, Filters, DRF Spectacular

---

## 📦 FILES PROVIDED

| File | Purpose |
|------|---------|
| `requirements.txt` | All Python dependencies |
| `settings.py` | Django configuration |
| `.env.example` | Environment variables template |
| `all-models.py` | All model definitions |
| `all-serializers.py` | All serializer definitions |
| `all-views.py` | All view definitions |
| `urls-and-admin.py` | URL routing and admin config |
| `SETUP-GUIDE.md` | Step-by-step setup instructions |
| `README.md` | This file |

---

## 🚀 QUICK START (5 MINUTES)

### 1. Create Project Structure

```bash
mkdir spices_ecommerce && cd spices_ecommerce
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
django-admin startproject spices_backend .
python manage.py startapp users
python manage.py startapp products
python manage.py startapp cart
python manage.py startapp orders
python manage.py startapp payments
python manage.py startapp reviews
```

### 2. Copy Provided Files

1. Copy `settings.py` → `spices_backend/settings.py`
2. Copy content from `all-models.py` to respective app `models.py` files
3. Copy content from `all-serializers.py` to respective app `serializers.py` files
4. Copy content from `all-views.py` to respective app `views.py` files
5. Copy content from `urls-and-admin.py` to respective files
6. Copy `.env.example` as `.env` and update with your values

### 3. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run Server

```bash
python manage.py runserver
```

✅ Access at `http://localhost:8000`

---

## 📊 API ENDPOINTS

### Authentication (6 endpoints)
```
POST   /api/auth/register/           - Register new user
POST   /api/auth/login/              - Login (JWT tokens)
POST   /api/auth/token/refresh/      - Refresh token
GET    /api/auth/profile/            - Get user profile
PUT    /api/auth/profile/            - Update profile
```

### Products (4 endpoints)
```
GET    /api/categories/              - List categories
GET    /api/categories/{slug}/       - Category detail
GET    /api/products/                - List products (with filters)
GET    /api/products/{slug}/         - Product detail
```

### Cart (6 endpoints)
```
GET    /api/cart/                    - Get cart
POST   /api/cart/add_item/           - Add to cart
POST   /api/cart/update_item/        - Update quantity
DELETE /api/cart/remove_item/        - Remove from cart
POST   /api/cart/clear/              - Clear cart
```

### Orders (4 endpoints)
```
GET    /api/orders/                  - List orders
POST   /api/orders/                  - Create order
GET    /api/orders/{id}/             - Order detail
POST   /api/orders/{id}/cancel/      - Cancel order
```

### Reviews (4 endpoints)
```
GET    /api/reviews/                 - List reviews
POST   /api/reviews/                 - Create review
GET    /api/reviews/{id}/            - Review detail
PUT    /api/reviews/{id}/            - Update review
DELETE /api/reviews/{id}/            - Delete review
```

**Total: 24+ RESTful API endpoints**

---

## 📱 Request/Response Examples

### Register User
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "email": "john@example.com",
    "password": "Pass123!@#",
    "password2": "Pass123!@#",
    "phone": "9876543210"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "Pass123!@#"
  }'

# Response:
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Get Products (with filtering)
```bash
curl -X GET "http://localhost:8000/api/products/?category=1&organic=true&search=pepper" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Add to Cart
```bash
curl -X POST http://localhost:8000/api/cart/add_item/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "quantity": 2
  }'
```

### Create Order
```bash
curl -X POST http://localhost:8000/api/orders/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shipping_address": "123 Main St",
    "shipping_city": "Delhi",
    "shipping_state": "Delhi",
    "shipping_pincode": "110001",
    "phone": "9876543210",
    "payment_method": "cod"
  }'
```

### Add Review
```bash
curl -X POST http://localhost:8000/api/reviews/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product": 1,
    "rating": 5,
    "title": "Excellent Quality",
    "comment": "Best spices I have ever bought!"
  }'
```

---

## 🗄️ Database Models

### Users
- Custom User model with extended fields
- Email-based authentication
- Address and phone fields

### Products
- Category system
- Product with variants (weight-based)
- Spice-specific fields (form, origin, organic, shelf-life)
- Multiple images support
- Discount tracking
- Stock management

### Cart
- Per-user cart
- Cart items with quantity
- Automatic subtotal calculation

### Orders
- UUID-based order IDs
- Shipping details
- Order items tracking
- Order status workflow
- Payment status tracking

### Payments
- Payment gateway integration
- Transaction details storage
- Payment status tracking

### Reviews
- Product ratings (1-5 stars)
- Verified purchase badges
- Average rating calculation

---

## 🔐 Security Features

✅ JWT Token Authentication  
✅ CORS Configuration  
✅ Password Validation  
✅ Token Rotation & Blacklisting  
✅ Permission-based Access Control  
✅ Environment Variable Protection  
✅ SQL Injection Prevention (ORM)  
✅ CSRF Protection  

---

## 📊 Admin Features

Complete Django admin with:

- User management with profile fields
- Product management with inline gallery
- Category with slug auto-population
- Cart monitoring
- Order management with inline items
- Payment tracking
- Review moderation
- Filtering, searching, and sorting
- Bulk actions support

Access at: `http://localhost:8000/admin/`

---

## 🧪 Testing API

### Option 1: Postman
- Import endpoints from API documentation
- Set authentication tokens
- Test all endpoints

### Option 2: Thunder Client (VS Code)
- VS Code Extension
- Similar to Postman
- Lightweight

### Option 3: curl
- Command-line tool
- Perfect for testing

### Option 4: Swagger UI
- Built-in API documentation
- Interactive testing
- Access at: `/api/docs/`

---

## 🚢 Deployment

### Option 1: Heroku
```bash
heroku create your-app-name
heroku config:set DEBUG=False
git push heroku main
heroku run python manage.py migrate
```

### Option 2: Railway
1. Create account on railway.app
2. Connect GitHub repository
3. Add environment variables
4. Deploy automatically

### Option 3: AWS/DigitalOcean/Azure
- Use Gunicorn as WSGI server
- Nginx as reverse proxy
- PostgreSQL as database
- Follow platform-specific guides

---

## 🔧 Configuration

### Essential Environment Variables

```
SECRET_KEY=your-secret-key-here
DEBUG=False (production)
ALLOWED_HOSTS=yourdomain.com

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=spices_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Payment Gateways
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
RAZORPAY_KEY_ID=key_id...
RAZORPAY_KEY_SECRET=key_secret...

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

---

## 📈 Performance Tips

1. **Use PostgreSQL** in production
2. **Enable Redis Caching**
3. **Use CDN** for static/media files
4. **Compress Images** before upload
5. **Database Indexing** on frequent queries
6. **Pagination** for large datasets
7. **Lazy Loading** for images
8. **API Rate Limiting**

---

## 🐛 Common Issues

### Issue: Port 8000 already in use
```bash
python manage.py runserver 8001
```

### Issue: No module named 'decouple'
```bash
pip install python-decouple
```

### Issue: Static files not loading
```bash
python manage.py collectstatic --noinput
```

### Issue: Database migration errors
```bash
python manage.py migrate --fake-initial
```

---

## 📚 Resources

- Django Docs: https://docs.djangoproject.com/
- DRF Docs: https://www.django-rest-framework.org/
- Simple JWT: https://django-rest-framework-simplejwt.readthedocs.io/
- Stripe Docs: https://stripe.com/docs/api
- Razorpay Docs: https://razorpay.com/docs/

---

## 💡 Next Steps

1. ✅ Follow SETUP-GUIDE.md for installation
2. ✅ Test all API endpoints
3. ✅ Add payment gateway keys
4. ✅ Create frontend (React/Vue/Next.js)
5. ✅ Deploy to production
6. ✅ Monitor and optimize

---

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review Django documentation
3. Check DRF documentation
4. Search Stack Overflow

---

## 📝 License

This code is provided as-is for your spices e-commerce backend.

---

## 🎉 You're All Set!

Your complete Django REST Framework backend for spices e-commerce is ready to use. 

**Start building! 🚀**

---

## Checklist for Production

- [ ] Change SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Use PostgreSQL
- [ ] Setup HTTPS
- [ ] Configure ALLOWED_HOSTS
- [ ] Setup email backend
- [ ] Add payment gateway credentials
- [ ] Setup Redis for caching
- [ ] Configure media file storage (AWS S3)
- [ ] Add logging and monitoring
- [ ] Setup CI/CD pipeline
- [ ] Add rate limiting
- [ ] Enable CORS properly
- [ ] Add security headers
- [ ] Backup database regularly

---

Made with ❤️ for spices e-commerce
