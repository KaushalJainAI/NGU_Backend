from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.

class ReceivableAccount(models.Model):
    """
    Model to store receivable account information
    """
    account_holder_name = models.CharField(max_length=255)
    upi_id = models.CharField(max_length=255, unique=True)
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    branch_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Receivable Account'
        verbose_name_plural = 'Receivable Accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_holder_name} - {self.upi_id}"
        
    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_default:
                ReceivableAccount.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
    

class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percent = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Discount percentage (1-100)"
    )
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    max_usage = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum global uses")
    usage_count = models.PositiveIntegerField(default=0)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def is_valid(self, order_amount=None):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.valid_until and self.valid_until < timezone.now():
            return False
        if self.max_usage is not None and self.usage_count >= self.max_usage:
            return False
        if order_amount is not None and order_amount < self.minimum_order_amount:
            return False
        return True

    def __str__(self):
        return self.code
    
class Policy(models.Model):
    POLICY_TYPES = [
        ('shipping', 'Shipping'),
        ('return', 'Return')
    ]
    type = models.CharField(max_length=16, choices=POLICY_TYPES, unique=True)
    content = models.TextField()

    def __str__(self):
        return f"{self.get_type_display()} Policy"
    


    

