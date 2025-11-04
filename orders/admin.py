from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'product_weight', 'quantity', 'price', 'subtotal']
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'status', 'payment_method', 'total_amount', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['order_id', 'user__email', 'user__username']
    readonly_fields = ['order_id', 'subtotal', 'tax', 'total_amount']
    list_editable = ['status']
    ordering = ['-created_at']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_id', 'user', 'status', 'payment_method', 'payment_status')
        }),
        ('Shipping Details', {
            'fields': ('shipping_address', 'shipping_city', 'shipping_state', 'shipping_pincode', 'phone')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'shipping_charge', 'tax', 'total_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'delivered_at')
        }),
    )