from django.contrib import admin
from .models import Category, Product, ProductImage, ProductCombo, ProductComboItem, ProductSection, ProductSearchKB, ProductComboSearchKB


@admin.register(ProductSection)
class ProductSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'section_type', 'display_order', 'max_products', 'is_active', 'created_at']
    list_filter = ['section_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['display_order', 'is_active']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'section_type', 'description')
        }),
        ('Display Settings', {
            'fields': ('icon', 'display_order', 'max_products')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


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
    list_filter = ['category', 'spice_form', 'organic', 'is_featured', 'is_active', 
                   'sections', 'created_at']
    search_fields = ['name', 'description', 'ingredients']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_featured', 'is_active']
    ordering = ['-created_at']
    inlines = [ProductImageInline]
    filter_horizontal = ['sections']
    
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
        ('Flags & Placement', {
            'fields': ('is_active', 'is_featured', 'badge', 'sections')
        }),
    )


class ProductComboItemInline(admin.TabularInline):
    model = ProductComboItem
    extra = 1
    fields = ['product', 'quantity']
    autocomplete_fields = ['product']


@admin.register(ProductCombo)
class ProductComboAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'discount_price', 'is_active', 'is_featured', 
                    'badge', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductComboItemInline]
    search_fields = ['name', 'slug', 'description', 'title', 'subtitle']
    list_filter = ['is_active', 'is_featured', 'sections', 'created_at']
    list_editable = ['is_featured', 'is_active']
    ordering = ['-created_at']
    filter_horizontal = ['sections']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Display Titles', {
            'fields': ('title', 'subtitle'),
            'description': 'Custom titles for marketing and display purposes'
        }),
        ('Pricing', {
            'fields': ('price', 'discount_price')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Flags & Placement', {
            'fields': ('is_active', 'is_featured', 'badge', 'sections')
        }),
    )


# Optional: Register ProductComboItem if you need standalone access
@admin.register(ProductComboItem)
class ProductComboItemAdmin(admin.ModelAdmin):
    list_display = ['combo', 'product', 'quantity']
    list_filter = ['combo']
    search_fields = ['combo__name', 'product__name']
    autocomplete_fields = ['combo', 'product']

@admin.register(ProductSearchKB)
class ProductSearchKBAdmin(admin.ModelAdmin):
    list_display = ['product', 'last_updated']
    search_fields = ['product__name', 'synonyms']
    list_filter = ['last_updated']
    autocomplete_fields = ['product']
    ordering = ['-last_updated']
    readonly_fields = ['last_updated']
    
    fieldsets = (
        ('Product Link', {
            'fields': ('product',)
        }),
        ('Search Data', {
            'fields': ('synonyms', 'last_updated')
        }),
    )


@admin.register(ProductComboSearchKB)
class ProductComboSearchKBAdmin(admin.ModelAdmin):
    list_display = ['combo', 'last_updated']
    search_fields = ['combo__name', 'synonyms']
    list_filter = ['last_updated']
    autocomplete_fields = ['combo']
    ordering = ['-last_updated']
    readonly_fields = ['last_updated']
    
    fieldsets = (
        ('Combo Link', {
            'fields': ('combo',)
        }),
        ('Search Data', {
            'fields': ('synonyms', 'last_updated')
        }),
    )
