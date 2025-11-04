from django.contrib import admin
from .models import Category, Product, ProductImage

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'spice_form', 'price', 'discount_price', 
                    'stock', 'organic', 'is_featured', 'is_active', 'created_at']
    list_filter = ['category', 'spice_form', 'organic', 'is_featured', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'ingredients']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_featured', 'is_active']
    ordering = ['-created_at']
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description')
        }),
        ('Spice Details', {
            'fields': ('spice_form', 'weight', 'origin_country', 'organic', 'shelf_life', 'ingredients')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'discount_price', 'stock')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Flags', {
            'fields': ('is_active', 'is_featured')
        }),
    )