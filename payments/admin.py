from django.contrib import admin
from .models import Payment, PaymentMethod



@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'order', 'payment_gateway', 'amount', 'status', 'created_at']
    list_filter = ['payment_gateway', 'status', 'created_at']
    search_fields = ['payment_id', 'order__order_id']
    readonly_fields = ['payment_id', 'transaction_details']
    ordering = ['-created_at']


class PaymentMethodInline(admin.TabularInline):
    model = PaymentMethod
    extra = 0
    fields = ['payment_type', 'upi_id', 'card_last_four', 'card_brand', 
              'bank_name', 'wallet_provider', 'is_default', 'is_active']
    readonly_fields = ['created_at', 'updated_at']


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