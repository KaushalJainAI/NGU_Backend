from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'order', 'payment_gateway', 'amount', 'status', 'created_at']
    list_filter = ['payment_gateway', 'status', 'created_at']
    search_fields = ['payment_id', 'order__order_id']
    readonly_fields = ['payment_id', 'transaction_details']
    ordering = ['-created_at']