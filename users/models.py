from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def full_address(self):
        """Returns complete formatted address"""
        parts = [self.address, self.city, self.state, self.pincode]
        return ', '.join(filter(None, parts))


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
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

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
