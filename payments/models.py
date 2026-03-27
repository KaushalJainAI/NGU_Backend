from django.db import models
from orders.models import Order
from users.models import User
from django.core.validators import RegexValidator


class Payment(models.Model):
    """Payment Model for tracking payments"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('razorpay', 'Razorpay'),
        ('cod', 'Cash on Delivery'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    payment_id = models.CharField(max_length=200, unique=True)
    payment_gateway = models.CharField(max_length=20, choices=PAYMENT_GATEWAY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.payment_id} - {self.status}"
    
class PaymentMethod(models.Model):
    """
    Model to store user payment methods (NEVER store raw card numbers)
    """
    PAYMENT_TYPES = [
        ('UPI', 'UPI'),
        ('CARD', 'Card'),
        ('NETBANKING', 'Net Banking'),
        ('WALLET', 'Wallet'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For UPI
    upi_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        validators=[RegexValidator(
            regex=r'^[\w\.\-]+@[\w]+$',
            message='Enter a valid UPI ID (e.g., user@paytm)'
        )]
    )

    # For Cards - ONLY store last 4 digits and token from payment gateway
    card_last_four = models.CharField(max_length=4, blank=True, null=True)
    card_brand = models.CharField(max_length=20, blank=True, null=True)
    card_expiry_month = models.PositiveSmallIntegerField(blank=True, null=True)
    card_expiry_year = models.PositiveSmallIntegerField(blank=True, null=True)
    
    # Payment gateway token/reference
    gateway_token = models.CharField(max_length=255, blank=True, null=True)
    gateway_name = models.CharField(max_length=50, blank=True, null=True)

    # For Net Banking
    bank_name = models.CharField(max_length=100, blank=True, null=True)

    # For Wallets
    wallet_provider = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        if self.payment_type == 'UPI':
            return f"{self.user.email} - UPI ({self.upi_id})"
        elif self.payment_type == 'CARD':
            return f"{self.user.email} - {self.card_brand} ****{self.card_last_four}"
        elif self.payment_type == 'NETBANKING':
            return f"{self.user.email} - Net Banking ({self.bank_name})"
        else:
            return f"{self.user.email} - {self.wallet_provider}"

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Ensure only one default payment method per user
            if self.is_default:
                PaymentMethod.objects.filter(
                    user=self.user, 
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)

    @property
    def masked_display(self):
        """Return a masked version for display"""
        if self.payment_type == 'UPI':
            return self.upi_id
        elif self.payment_type == 'CARD':
            return f"{self.card_brand} ending in {self.card_last_four}"
        elif self.payment_type == 'NETBANKING':
            return f"{self.bank_name}"
        else:
            return f"{self.wallet_provider} Wallet"
