# Database Schema Documentation

This document describes the core Entity-Relationship structure and data models that drive the NGU Spices Backend, organized by application.

## 1. Users App

The core authentication system extends Django's `AbstractUser` to support e-commerce profiles.

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **User** | Custom User Profile | `email` (login identifier), `phone`, `address`, `city`, `state`, `pincode`, `profile_picture` |

## 2. Products App

The core catalog handling individual spices, combos, and homepage display sections.

| Model | Purpose | Key Fields/Relationships |
|-------|---------|--------------------------|
| **Category** | Organizational folders for spices | `name`, `slug`, `image` |
| **Product** | Individual spice item | `category` (FK), `spice_form`, `price`, `discount_price`, `stock`, `weight` |
| **ProductImage** | Image gallery for spices | `product` (FK), `image`, `alt_text` |
| **ProductCombo** | Bundled spice packages | Many-to-Many with `Product` via `ProductComboItem` |
| **ProductComboItem** | Junction table for Combos | `combo` (FK), `product` (FK), `quantity` |
| **ProductSection** | Homepage display groups (Trending, New) | `name`, `section_type`, `max_products` |
| **ProductSearchKB** | LLM-generated search synonyms | `product` (OneToOne), `synonyms` (JSONField) |
| **ProductComboSearchKB** | LLM generated combo synonyms | `combo` (OneToOne), `synonyms` (JSONField) |

## 3. Cart App

Persistent shopping carts tracked per user.

| Model | Purpose | Key Fields/Relationships |
|-------|---------|--------------------------|
| **Cart** | Holds a user's items | `user` (OneToOne), calculated `total_price` property |
| **CartItem** | Individual products/combos in cart | `cart` (FK), `product` (FK, nullable), `combo` (FK, nullable), `item_type`, `quantity` |
| **Favorite** | User's wishlist | `user` (FK), `product` (FK) |

*Note: `CartItem` relies on database constraints to guarantee either `product` or `combo` is populated, but not both simultaneously.*

## 4. Orders App

Complete lifecycle tracking of user purchases and coupon redemptions.

| Model | Purpose | Key Fields/Relationships |
|-------|---------|--------------------------|
| **Order** | Full invoice/order ticket | `order_id` (UUID), `user` (FK), `status`, `payment_method`, `total_amount`, `coupon` (FK) |
| **OrderItem** | Specific items bought | `order` (FK), `product`/`combo` (FK), snapshot fields (`price`, `discounted_price`, `final_price`) |

*Note: `OrderItem` stores historical snapshots of prices (e.g., `price`, `final_price`) rather than live references, ensuring past orders do not change if active product prices are updated.*

## Architectural Principles

1. **UUID Primary Keys:** Important public-facing identifiers (like `Order.order_id`) use UUIDs rather than sequential integers to prevent enumeration attacks.
2. **Soft vs Hard Deletes:** Deleting a `Product` is generally prevented (`on_delete=models.PROTECT`) if it is attached to an `OrderItem`, ensuring historical order data remains intact.
3. **Database Constraints:** Models heavily leverage Django `CheckConstraint` and `UniqueConstraint` directly at the database level (e.g., preventing duplicate favorites, asserting quantities are positive).
