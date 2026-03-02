# Payments Integration

The NGU Spices Backend handles payment orchestration primarily through specialized providers depending on the order type.

## Supported Payment Methods

1. **Cash on Delivery (COD)**
2. **Online Payment (Razorpay/Stripe)**
3. **Saved User Payment Methods** (`PaymentMethodSet`)

### Payment Models

- **`PaymentMethod`:** Users can securely save their payment references (UPI IDs, Card tokens, Wallets) for faster checkouts. It supports setting a "default" method and soft deletion.

### Payment Flow (Online / Razorpay)

1. **Order Creation:** User checks out their Cart via the `orders` app.
2. **Gateway Initialization:** If the payment method is `razorpay` or `ONLINE`, the backend creates a Razorpay Order ID.
3. **Frontend Handoff:** The `order_id` and payment tokens are returned to the frontend (`nidhi-brand-forge`), which pops open the respective payment modal.
4. **Webhook Confirmation:** Upon successful payment, Razorpay hits a backend webhook. The server validates the signature and updates the `Order` instance's `payment_status` to `confirmed`.

### Configuration Requirements

The following environment variables in `.env` govern payments:

```env
# Stripe
STRIPE_PUBLIC_KEY=...
STRIPE_SECRET_KEY=...

# Razorpay
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

*Note: Order amounts are stored strictly as exact Decimals (`max_digits=10, decimal_places=2`) to prevent floating-point calculation errors during currency conversions.*
