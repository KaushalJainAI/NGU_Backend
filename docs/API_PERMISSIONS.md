# API Permissions Reference

Complete reference for all API endpoints and their permission requirements.

---

## Permission Classes Used

| Class | Description |
|-------|-------------|
| `AllowAny` | No authentication required |
| `IsAuthenticated` | Must be logged in |
| `IsAuthenticatedOrReadOnly` | Read = public, Write = auth required |
| `IsAdminOrReadOnly` | Read = public, Write = admin only |
| `IsAdminUser` | Admin only (`is_staff=True`) |

---

## 🔓 Public Endpoints (No Authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/categories/` | GET | List all categories |
| `/api/categories/{slug}/` | GET | Category detail |
| `/api/products/` | GET | List products (with filters) |
| `/api/products/{slug}/` | GET | Product detail |
| `/api/combos/` | GET | List combos |
| `/api/combos/{slug}/` | GET | Combo detail |
| `/api/product-images/` | GET | List product images |
| `/api/sections/` | GET | Homepage sections |
| `/api/reviews/` | GET | List reviews |
| `/api/policies/{type}/` | GET | View shipping/return policy |
| `/api/spice-forms/` | GET | Spice form options |
| `/api/auth/register/` | POST | User registration |
| `/api/auth/login/` | POST | User login (JWT) |
| `/api/auth/token/refresh/` | POST | Refresh JWT token |
| `/api/contact/` | POST | Submit contact form |

---

## 🔐 Authenticated Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/profile/` | GET | Get user profile |
| `/api/auth/profile/` | PUT/PATCH | Update profile |
| `/api/auth/change-password/` | POST | Change password |
| `/api/cart/` | GET | View cart |
| `/api/cart/add_item/` | POST | Add to cart |
| `/api/cart/update_item/` | POST | Update cart quantity |
| `/api/cart/remove_item/` | DELETE/POST | Remove from cart |
| `/api/cart/clear/` | POST | Clear cart |
| `/api/cart/sync/` | POST | Sync localStorage cart |
| `/api/cart/qr/` | POST | Generate UPI QR |
| `/api/favorites/` | GET | List favorites |
| `/api/favorites/` | POST | Add to favorites |
| `/api/favorites/{id}/` | DELETE | Remove from favorites |
| `/api/favorites/sync/` | POST | Sync favorites |
| `/api/orders/` | GET | List user's orders |
| `/api/orders/` | POST | Create order |
| `/api/orders/{id}/` | GET | Order detail |
| `/api/orders/{id}/cancel/` | POST | Cancel order |
| `/api/orders/validate_coupon/` | POST | Validate coupon |
| `/api/validate-coupon/` | POST | Validate coupon (alt) |
| `/api/reviews/` | POST | Create review* |
| `/api/chat-sessions/` | GET | List user's chat sessions |
| `/api/chat-sessions/` | POST | Create chat session |
| `/api/chat-sessions/{id}/` | GET | Session detail |
| `/api/chat-sessions/{id}/messages/` | GET/POST | Get/send messages |
| `/api/payment-account/` | GET | Get payment account |

*Reviews require verified purchase (delivered order containing the product)

---

## 👑 Admin Only (`is_staff=True`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/categories/` | POST/PUT/DELETE | Manage categories |
| `/api/products/` | POST/PUT/DELETE | Manage products |
| `/api/product-images/` | POST/PUT/DELETE | Manage images |
| `/api/combos/` | POST/PUT/DELETE | Manage combos |
| `/api/sections/` | POST/PUT/DELETE | Manage homepage sections |
| `/api/policies/{type}/` | PUT/PATCH | Update policies |
| `/api/dashboard/` | GET | Dashboard statistics |
| `/api/coupons/` | ALL | Manage coupons |
| `/api/receivable-accounts/` | ALL | Manage payment accounts |
| `/api/contact/` | GET/PUT/DELETE | Manage contact submissions |
| `/api/contact/{id}/mark_read/` | POST | Mark as read |
| `/api/contact/{id}/reply/` | POST | Mark as replied |
| `/api/chat-sessions/{id}/close/` | POST | Close chat session |
| `/api/chat-sessions/{id}/assign/` | POST | Assign to admin |
| `/api/orders/` | GET (all) | View all orders |
| `/api/orders/{id}/` | PUT/PATCH | Update order status |

---

## Rate Limiting

| Scope | Limit | Applied To |
|-------|-------|------------|
| `anon` | 100/hour | Anonymous requests |
| `user` | 1000/hour | Authenticated requests |
| `login` | 5/minute | Login endpoint |
| `register` | 3/minute | Registration endpoint |
| `contact` | 5/hour | Contact form submission |

---

## Data Access Control (BOLA Protection)

Users can only access their own:
- **Cart** - One cart per user
- **Orders** - Only their own orders
- **Favorites** - Their saved products
- **Chat Sessions** - Sessions they created
- **Profile** - Their own profile only

Admins (`is_staff=True`) can access all data.

---

## Special Permissions

### Review Verification
- Users can only review products from **delivered** orders
- Reviews are marked `is_verified_purchase=True`

### Order Access
- Regular users: Own orders only
- Admins: All orders (for management)

### Chat Sessions
- Sessions are linked to specific orders
- Users can only access sessions for their own orders
- Admins can access all sessions

---

## Security Notes

1. **Receivable Accounts** - Admin-only to protect payment collection details
2. **Dashboard** - Admin-only to protect business metrics
3. **JWT Tokens** - 1 hour access, 7 day refresh
4. **Password Hashing** - Django's PBKDF2 with SHA256
5. **CORS** - Configured for specific origins only

---

*Last Updated: December 2024*
