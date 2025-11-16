from rest_framework import serializers
from .models import Category, Product, ProductImage

class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'is_active', 'products_count']
        read_only_fields = ['slug']

    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text']

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    average_rating = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'category', 'category_name', 'spice_form', 
                  'price', 'discount_price', 'final_price', 'discount_percentage', 
                  'stock', 'in_stock', 'weight', 'organic', 'image', 'is_featured', 
                  'average_rating', 'created_at', 'badge']
        
    def get_badge(self, obj):
        if obj.is_featured:
            return 'Featured'
        elif obj.in_stock:
            return 'In Stock'
        else:
            return 'Out of Stock'

class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()
    reviews_count = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'category', 'category_name', 'description', 
                  'spice_form', 'price', 'discount_price', 'final_price', 
                  'discount_percentage', 'stock', 'in_stock', 'weight', 
                  'origin_country', 'organic', 'shelf_life', 'ingredients', 
                  'image', 'images', 'is_featured', 'average_rating', 
                  'reviews_count', 'created_at']