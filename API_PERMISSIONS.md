# API Permissions Reference

This document lists all API endpoints and their required permissions.

---

## 🔓 Public (No Authentication Required)

| Endpoint | Method | Permission | Rate Limit | Description |
|----------|--------|------------|------------|-------------|
| `/api/categories/` | GET | Public | 100/hr | List categories |
| `/api/products/` | GET | Public | 100/hr | List products |
| `/api/combos/` | GET | Public | 100/hr | List combos |
| `/api/product-images/` | GET | Public | 100/hr | View images |
| `/api/reviews/` | GET | Public | 100/hr | List reviews |
| `/api/policies/` | GET | Public | 100/hr | View policies |
| `/api/spice-forms/` | GET | Public | 100/hr | Spice options |
| `/api/search/` | GET | Public | 100/hr | Unified search |
| `/api/auth/register/` | POST | Public | **3/min** | Registration |
| `/api/auth/login/` | POST | Public | **5/min** | Login |
| `/api/auth/token/refresh/` | POST | Public | 100/hr | Refresh token |
| `/api/contact/` | POST | Public | **5/hr** | Contact form |

---

## 🔐 Authenticated Users Required

| Endpoint | Method | Permission | Rate Limit | Description |
|----------|--------|------------|------------|-------------|
| `/api/auth/profile/` | GET/PUT | Auth | 1000/hr | View/update profile |
| `/api/auth/change-password/` | POST | Auth | 1000/hr | Change password |
| `/api/auth/validate-coupon/` | POST | Auth | 1000/hr | Validate coupon |
| `/api/cart/` | ALL | Auth | 1000/hr | Cart operations |
| `/api/favorites/` | ALL | Auth | 1000/hr | Favorites |
| `/api/orders/` | ALL | Auth | 1000/hr | Orders (own only) |
| `/api/payment-methods/` | ALL | Auth | 1000/hr | Payment methods |
| `/api/reviews/` | POST | Auth + **Verified Purchase** | 1000/hr | Create review |
| `/api/chat-sessions/` | ALL | Auth | 1000/hr | Chat sessions |

---

## 👑 Admin Only (is_staff=True)

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/api/categories/` | POST/PUT/DELETE | Admin | Manage categories |
| `/api/products/` | POST/PUT/DELETE | Admin | Manage products |
| `/api/combos/` | POST/PUT/DELETE | Admin | Manage combos |
| `/api/product-images/` | POST/PUT/DELETE | Admin | Manage images |
| `/api/contact/` | GET/PUT/DELETE | Admin | Manage contacts |
| `/api/chat-sessions/{id}/close/` | POST | Admin | Close session |
| `/api/chat-sessions/{id}/assign/` | POST | Admin | Assign session |
| `/api/receivable-accounts/` | ALL | Admin | Payment accounts |
| `/api/dashboard/` | GET | Admin | Sales statistics |
| `/api/coupons/` | ALL | Admin | Manage coupons |
| `/api/policies/` | PUT/PATCH/DELETE | Admin | Update policies |

---

## Rate Limiting Configuration

| Scope | Limit | Purpose |
|-------|-------|---------|
| `anon` | 100/hour | General anonymous requests |
| `user` | 1000/hour | Authenticated user requests |
| `login` | 5/minute | Prevent brute force attacks |
| `register` | 3/minute | Prevent mass account creation |
| `contact` | 5/hour | Prevent contact form spam |

---

## Review Verification

Reviews now require **verified purchase**:
- User must have a **delivered** order containing the item
- Only verified purchases can submit reviews
- All verified reviews are marked `is_verified_purchase=True`

---

## BOLA Protection

All endpoints filter data by user:
- Users can only access their **own** orders, cart, payment methods, favorites, and chat sessions

---

## Security Notes

- **Receivable Accounts**: Admin-only (protects payment collection)
- **Dashboard**: Admin-only (protects business data)
- **Reviews**: Requires delivered order (prevents fake reviews)
- **Login/Register**: Rate limited (prevents attacks)

---

*Updated: December 2025*
