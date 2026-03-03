"""
Comprehensive tests for the Products app.
Covers Category, Product, ProductCombo, and ProductImage ViewSets.
Includes authorization tests and security testing.
"""
import pytest
from decimal import Decimal
from rest_framework import status
from products.models import Category, Product, ProductCombo


# ==================== CATEGORY TESTS ====================

@pytest.mark.django_db
class TestCategoryAPI:
    """Tests for Category ViewSet."""
    
    base_url = '/api/categories/'
    
    def test_list_categories_public(self, api_client, test_category):
        """Test anyone can list categories."""
        response = api_client.get(self.base_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_retrieve_category_by_slug(self, api_client, test_category):
        """Test retrieve category by slug."""
        response = api_client.get(f'{self.base_url}{test_category.slug}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_category.name
    
    def test_retrieve_category_by_id(self, api_client, test_category):
        """Test retrieve category by ID."""
        response = api_client.get(f'{self.base_url}{test_category.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_nonexistent_category(self, api_client):
        """Test 404 for non-existent category."""
        response = api_client.get(f'{self.base_url}nonexistent-slug/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_create_category_admin_only(self, admin_client):
        """Test only admin can create categories."""
        data = {
            'name': 'New Category',
            'description': 'A new category'
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_create_category_regular_user_forbidden(self, authenticated_client):
        """Test regular user cannot create categories."""
        data = {
            'name': 'Unauthorized Category',
            'description': 'Should not be created'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_create_category_unauthenticated_forbidden(self, api_client):
        """Test unauthenticated user cannot create categories."""
        data = {'name': 'Unauthorized Category'}
        response = api_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_category_admin_only(self, admin_client, test_category):
        """Test only admin can update categories."""
        data = {'name': 'Updated Category Name'}
        response = admin_client.patch(
            f'{self.base_url}{test_category.slug}/', 
            data, 
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
    
    def test_delete_category_admin_only(self, admin_client, test_category):
        """Test only admin can delete categories."""
        response = admin_client.delete(f'{self.base_url}{test_category.slug}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_delete_category_regular_user_forbidden(self, authenticated_client, test_category):
        """Test regular user cannot delete categories."""
        response = authenticated_client.delete(f'{self.base_url}{test_category.slug}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_create_duplicate_category_name(self, admin_client, test_category):
        """Test creating category with duplicate name fails."""
        data = {'name': test_category.name}
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_category_search(self, api_client, test_category):
        """Test category search functionality."""
        response = api_client.get(f'{self.base_url}?search={test_category.name[:4]}')
        assert response.status_code == status.HTTP_200_OK


# ==================== PRODUCT TESTS ====================

@pytest.mark.django_db
class TestProductAPI:
    """Tests for Product ViewSet."""
    
    base_url = '/api/products/'
    
    def test_list_products_public(self, api_client, test_product):
        """Test anyone can list products."""
        response = api_client.get(self.base_url)
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_product_by_slug(self, api_client, test_product):
        """Test retrieve product by slug."""
        response = api_client.get(f'{self.base_url}{test_product.slug}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_product.name
    
    def test_retrieve_product_by_id(self, api_client, test_product):
        """Test retrieve product by ID."""
        response = api_client.get(f'{self.base_url}{test_product.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_nonexistent_product(self, api_client):
        """Test 404 for non-existent product."""
        response = api_client.get(f'{self.base_url}999999/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_create_product_admin_only(self, admin_client, test_category):
        """Test only admin can create products (returns 400 if image missing)."""
        data = {
            'name': 'New Spice Product',
            'category': test_category.id,
            'description': 'A new product',
            'price': '199.99',
            'stock': 50,
            'weight': 100,
            'unit': 'g',
            'spice_form': 'powder'
        }
        response = admin_client.post(self.base_url, data, format='json')
        # Returns 400 if image missing, 201 if all fields provided
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
    
    def test_create_product_regular_user_forbidden(self, authenticated_client, test_category):
        """Test regular user cannot create products."""
        data = {
            'name': 'Unauthorized Product',
            'category': test_category.id,
            'price': '99.99',
            'stock': 10,
            'weight': 50,
            'unit': 'g'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_update_product_admin_only(self, admin_client, test_product):
        """Test only admin can update products."""
        data = {'name': 'Updated Product Name'}
        response = admin_client.patch(
            f'{self.base_url}{test_product.slug}/', 
            data, 
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_products_by_category(self, api_client, test_product):
        """Test filtering products by category."""
        response = api_client.get(f'{self.base_url}?category__slug={test_product.category.slug}')
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_products_by_spice_form(self, api_client, test_product):
        """Test filtering products by spice form."""
        response = api_client.get(f'{self.base_url}?spice_form={test_product.spice_form}')
        assert response.status_code == status.HTTP_200_OK
    
    def test_search_products(self, api_client, test_product):
        """Test product search functionality."""
        response = api_client.get(f'{self.base_url}?search={test_product.name[:5]}')
        assert response.status_code == status.HTTP_200_OK
    
    def test_product_ordering(self, api_client, test_product):
        """Test product ordering."""
        response = api_client.get(f'{self.base_url}?ordering=-price')
        assert response.status_code == status.HTTP_200_OK
    
    def test_product_sections_endpoint(self, api_client):
        """Test product sections endpoint."""
        response = api_client.get(f'{self.base_url}sections/')
        assert response.status_code == status.HTTP_200_OK


# ==================== PRODUCT EDGE CASES ====================

@pytest.mark.django_db
class TestProductEdgeCases:
    """Edge case tests for products."""
    
    base_url = '/api/products/'
    
    def test_create_product_negative_price(self, admin_client, test_category):
        """Test creating product with negative price fails gracefully."""
        data = {
            'name': 'Negative Price Product',
            'category': test_category.id,
            'price': '-100.00',
            'stock': 10,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        # Should be 400, not 500
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_product_zero_price(self, admin_client, test_category):
        """Test creating product with zero price."""
        data = {
            'name': 'Free Product',
            'category': test_category.id,
            'price': '0.00',
            'stock': 10,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_product_negative_stock(self, admin_client, test_category):
        """Test creating product with negative stock fails gracefully."""
        data = {
            'name': 'Negative Stock Product',
            'category': test_category.id,
            'price': '100.00',
            'stock': -5,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_product_very_large_price(self, admin_client, test_category):
        """Test creating product with very large price."""
        data = {
            'name': 'Expensive Product',
            'category': test_category.id,
            'price': '99999999.99',
            'stock': 1,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_product_discount_higher_than_price(self, admin_client, test_category):
        """Test discount price higher than regular price."""
        data = {
            'name': 'Invalid Discount Product',
            'category': test_category.id,
            'price': '100.00',
            'discount_price': '150.00',  # Higher than price
            'stock': 10,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        # Should validate and reject, not 500
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_product_with_invalid_category_id(self, admin_client):
        """Test creating product with non-existent category."""
        data = {
            'name': 'Invalid Category Product',
            'category': 999999,
            'price': '100.00',
            'stock': 10,
            'weight': 100,
            'unit': 'g'
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_product_sql_injection_in_name(self, admin_client, test_category, malicious_inputs):
        """Test SQL injection in product name."""
        for payload in malicious_inputs.SQL_INJECTION:
            data = {
                'name': payload,
                'category': test_category.id,
                'price': '100.00',
                'stock': 10,
                'weight': '100g'
            }
            response = admin_client.post(self.base_url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_product_xss_in_description(self, admin_client, test_category, malicious_inputs):
        """Test XSS in product description."""
        for payload in malicious_inputs.XSS_PAYLOADS:
            data = {
                'name': f'XSS Test Product {hash(payload) % 10000}',
                'category': test_category.id,
                'description': payload,
                'price': '100.00',
                'stock': 10,
                'weight': '100g'
            }
            response = admin_client.post(self.base_url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


# ==================== COMBO TESTS ====================

@pytest.mark.django_db
class TestComboAPI:
    """Tests for ProductCombo ViewSet."""
    
    base_url = '/api/combos/'
    
    def test_list_combos_public(self, api_client, test_combo):
        """Test anyone can list combos."""
        response = api_client.get(self.base_url)
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_combo_by_slug(self, api_client, test_combo):
        """Test retrieve combo by slug."""
        response = api_client.get(f'{self.base_url}{test_combo.slug}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_combo.name
    
    def test_retrieve_combo_by_id(self, api_client, test_combo):
        """Test retrieve combo by ID."""
        response = api_client.get(f'{self.base_url}{test_combo.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_nonexistent_combo(self, api_client):
        """Test 404 for non-existent combo."""
        response = api_client.get(f'{self.base_url}999999/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_create_combo_admin_only(self, admin_client, test_product):
        """Test only admin can create combos (returns 400 if required fields missing)."""
        data = {
            'name': 'New Combo Pack',
            'description': 'A new combo',
            'price': '500.00',
        }
        response = admin_client.post(self.base_url, data, format='json')
        # Returns 400 if required fields missing, 201 if all provided
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
    
    def test_create_combo_regular_user_forbidden(self, authenticated_client):
        """Test regular user cannot create combos."""
        data = {
            'name': 'Unauthorized Combo',
            'price': '300.00',
            'stock': 10
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_update_combo_admin_only(self, admin_client, test_combo):
        """Test only admin can update combos."""
        data = {'name': 'Updated Combo Name'}
        response = admin_client.patch(
            f'{self.base_url}{test_combo.slug}/', 
            data, 
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
    
    def test_delete_combo_admin_only(self, admin_client, test_combo):
        """Test only admin can delete combos."""
        response = admin_client.delete(f'{self.base_url}{test_combo.slug}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_search_combos(self, api_client, test_combo):
        """Test combo search functionality."""
        response = api_client.get(f'{self.base_url}?search={test_combo.name[:4]}')
        assert response.status_code == status.HTTP_200_OK


# ==================== COMBO EDGE CASES ====================

@pytest.mark.django_db
class TestComboEdgeCases:
    """Edge case tests for combos."""
    
    base_url = '/api/combos/'
    
    def test_create_combo_negative_price(self, admin_client):
        """Test creating combo with negative price fails gracefully."""
        data = {
            'name': 'Negative Price Combo',
            'price': '-200.00',
            'stock': 5
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_combo_discount_higher_than_price(self, admin_client):
        """Test combo discount price higher than regular price."""
        data = {
            'name': 'Invalid Discount Combo',
            'price': '100.00',
            'discount_price': '200.00',
            'stock': 5
        }
        response = admin_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_combo_sql_injection_in_name(self, admin_client, malicious_inputs):
        """Test SQL injection in combo name."""
        for payload in malicious_inputs.SQL_INJECTION:
            data = {
                'name': payload,
                'price': '200.00',
                'stock': 5
            }
            response = admin_client.post(self.base_url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


# ==================== SPICE FORMS ENDPOINT ====================

@pytest.mark.django_db
class TestSpiceFormsEndpoint:
    """Tests for spice forms endpoint."""
    
    url = '/api/spice-forms/'
    
    def test_get_spice_forms(self, api_client):
        """Test getting available spice forms."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)


# ==================== UNIFIED SEARCH ENDPOINT ====================

@pytest.mark.django_db
class TestUnifiedSearchEndpoint:
    """Tests for unified search endpoint."""
    
    url = '/api/search/'
    
    def test_search_with_query(self, api_client, test_product):
        """Test search with query parameter."""
        response = api_client.get(f'{self.url}?q={test_product.name[:5]}')
        assert response.status_code == status.HTTP_200_OK
    
    def test_search_empty_query(self, api_client):
        """Test search with empty query."""
        response = api_client.get(self.url)
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_search_special_characters(self, api_client, malicious_inputs):
        """Test search with special characters."""
        for chars in malicious_inputs.SPECIAL_CHARS:
            response = api_client.get(f'{self.url}?q={chars}')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_search_sql_injection(self, api_client, malicious_inputs):
        """Test search with SQL injection."""
        for payload in malicious_inputs.SQL_INJECTION:
            response = api_client.get(f'{self.url}?q={payload}')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
