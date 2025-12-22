from django.db import models

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Receivable Account'
        verbose_name_plural = 'Receivable Accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_holder_name} - {self.upi_id}"
    

class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percent = models.PositiveIntegerField()  # E.g., 10 for 10% off
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        from django.utils import timezone
        return self.is_active and (not self.valid_until or self.valid_until > timezone.now())

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
    


    

