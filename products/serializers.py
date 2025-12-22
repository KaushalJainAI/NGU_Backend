import json
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductCombo, ProductComboItem, ProductSection


class ProductSectionSerializer(serializers.ModelSerializer):
    """Serializer for ProductSection"""
    class Meta:
        model = ProductSection
        fields = [
            'id', 'name', 'slug', 'section_type', 'description', 
            'icon', 'display_order', 'max_products', 'is_active'
        ]
        read_only_fields = ['slug']


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
        fields = ['id', 'product', 'image', 'alt_text']


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    average_rating = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    sections = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=ProductSection.objects.all(),
        required=False
    )
    section_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'category_name', 'spice_form',
            'price', 'discount_price', 'final_price', 'discount_percentage',
            'stock', 'in_stock', 'weight', 'organic', 'image', 'is_featured',
            'average_rating', 'created_at', 'badge', 'is_active', 'sections', 'section_names'
        ]
    
    def get_section_names(self, obj):
        return [section.name for section in obj.sections.all()]


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()
    reviews_count = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    in_stock = serializers.ReadOnlyField()
    sections = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=ProductSection.objects.all(),
        required=False
    )
    section_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'category_name', 'description',
            'spice_form', 'price', 'discount_price', 'final_price',
            'discount_percentage', 'stock', 'in_stock', 'weight',
            'origin_country', 'organic', 'shelf_life', 'ingredients',
            'image', 'images', 'is_featured', 'average_rating',
            'reviews_count', 'created_at', 'is_active', 'sections', 'section_names'
        ]
    
    def get_section_names(self, obj):
        return [section.name for section in obj.sections.all()]


class ProductComboItemReadSerializer(serializers.ModelSerializer):
    """For reading combo items with product details"""
    product = serializers.PrimaryKeyRelatedField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price', 
        max_digits=10, 
        decimal_places=2, 
        read_only=True
    )
    quantity = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ProductComboItem
        fields = [
            'product', 'product_name', 'product_slug', 
            'product_image', 'product_price', 'quantity'
        ]


class ProductComboSerializer(serializers.ModelSerializer):
    # Accept items as a JSON string (for FormData) or list
    items = serializers.CharField(write_only=True, required=False, allow_blank=True)
    sections = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=ProductSection.objects.all(),
        required=False
    )
    section_names = serializers.SerializerMethodField(read_only=True)
    discount_percentage = serializers.ReadOnlyField()
    display_title = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductCombo
        fields = [
            'id', 'name', 'slug', 'description', 'title', 'subtitle',
            'display_title', 'price', 'discount_price', 'discount_percentage',
            'image', 'is_active', 'is_featured', 'badge', 'created_at', 
            'items', 'sections', 'section_names'
        ]
        read_only_fields = ['slug', 'created_at']

    def get_section_names(self, obj):
        return [section.name for section in obj.sections.all()]

    def to_representation(self, instance):
        """Override to include items in read operations"""
        data = super().to_representation(instance)
        data['items'] = ProductComboItemReadSerializer(
            instance.productcomboitem_set.all(), 
            many=True
        ).data
        return data

    def _parse_items(self, items_raw):
        """Parse items from JSON string or return as-is if already a list"""
        if items_raw is None or items_raw == '':
            return []
        
        if isinstance(items_raw, list):
            return items_raw
        
        if isinstance(items_raw, str):
            try:
                return json.loads(items_raw)
            except json.JSONDecodeError:
                raise serializers.ValidationError({
                    'items': 'Invalid JSON format for items.'
                })
        
        return []

    def _validate_and_get_items(self, items_data):
        """Validate items and return product instances with quantities"""
        if not items_data:
            raise serializers.ValidationError({
                'items': 'At least one product must be added to the combo.'
            })
        
        validated_items = []
        product_ids = []
        
        for item in items_data:
            product_id = item.get('product')
            quantity = item.get('quantity', 1)
            
            if not product_id:
                continue
                
            # Convert to int if string
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                raise serializers.ValidationError({
                    'items': f'Invalid product ID: {product_id}'
                })
            
            # Check for duplicates
            if product_id in product_ids:
                raise serializers.ValidationError({
                    'items': 'Cannot add the same product multiple times.'
                })
            product_ids.append(product_id)
            
            # Validate product exists
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                raise serializers.ValidationError({
                    'items': f'Product with ID {product_id} does not exist.'
                })
            
            validated_items.append({
                'product': product,
                'quantity': max(1, int(quantity))
            })
        
        if not validated_items:
            raise serializers.ValidationError({
                'items': 'At least one valid product must be added to the combo.'
            })
        
        return validated_items

    def create(self, validated_data):
        items_raw = validated_data.pop('items', '[]')
        sections = validated_data.pop('sections', [])
        items_data = self._parse_items(items_raw)
        validated_items = self._validate_and_get_items(items_data)
        
        combo = ProductCombo.objects.create(**validated_data)
        
        # Add sections
        if sections:
            combo.sections.set(sections)
        
        for item_data in validated_items:
            ProductComboItem.objects.create(
                combo=combo,
                product=item_data['product'],
                quantity=item_data['quantity']
            )
        
        return combo

    def update(self, instance, validated_data):
        items_raw = validated_data.pop('items', None)
        sections = validated_data.pop('sections', None)
        
        # Update main combo fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update sections if provided
        if sections is not None:
            instance.sections.set(sections)
        
        # Handle nested items only if items were provided
        if items_raw is not None and items_raw != '':
            items_data = self._parse_items(items_raw)
            validated_items = self._validate_and_get_items(items_data)
            
            # Clear existing items and create new ones
            instance.productcomboitem_set.all().delete()
            
            for item_data in validated_items:
                ProductComboItem.objects.create(
                    combo=instance,
                    product=item_data['product'],
                    quantity=item_data['quantity']
                )
        
        return instance

    def validate(self, data):
        """Additional validation for price logic"""
        price = data.get('price')
        discount_price = data.get('discount_price')
        
        if discount_price and price and float(discount_price) >= float(price):
            raise serializers.ValidationError({
                'discount_price': 'Discount price must be less than the regular price.'
            })
        
        return data
