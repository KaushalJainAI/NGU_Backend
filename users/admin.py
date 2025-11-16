from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PaymentMethod

class PaymentMethodInline(admin.TabularInline):
    model = PaymentMethod
    extra = 0
    fields = ['payment_type', 'upi_id', 'card_last_four', 'card_brand', 
              'bank_name', 'wallet_provider', 'is_default', 'is_active']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'phone', 'is_staff', 'created_at']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'created_at']
    search_fields = ['email', 'username', 'phone']
    ordering = ['-created_at']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone', 'address', 'city', 'state', 'pincode', 'profile_picture')
        }),
    )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['user', 'payment_type', 'masked_display', 'is_default', 
                    'is_active', 'created_at']
    list_filter = ['payment_type', 'is_default', 'is_active', 'created_at']
    search_fields = ['user__email', 'upi_id', 'card_brand', 'bank_name']
    readonly_fields = ['created_at', 'updated_at', 'masked_display']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'payment_type', 'is_default', 'is_active')
        }),
        ('UPI Details', {
            'fields': ('upi_id',),
            'classes': ('collapse',)
        }),
        ('Card Details', {
            'fields': ('card_last_four', 'card_brand', 'card_expiry_month', 
                      'card_expiry_year', 'gateway_token', 'gateway_name'),
            'classes': ('collapse',)
        }),
        ('Banking Details', {
            'fields': ('bank_name',),
            'classes': ('collapse',)
        }),
        ('Wallet Details', {
            'fields': ('wallet_provider',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )