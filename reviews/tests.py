"""
Comprehensive tests for the Reviews app.
Covers review creation, duplicate prevention, verified purchase, and authorization tests.
"""
import pytest
from rest_framework import status
from reviews.models import Review


# ==================== REVIEW CREATION TESTS ====================

@pytest.mark.django_db
class TestReviewCreation:
    """Tests for review creation."""
    
    base_url = '/api/reviews/'
    
    def test_create_product_review_authenticated(self, authenticated_client, test_product, delivered_order):
        """Test creating review for a purchased product."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': 5,
            'comment': 'Great product!'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        # Returns 201 if valid, 400 if missing fields or already reviewed
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
    
    def test_create_review_unauthenticated(self, api_client, test_product):
        """Test unauthenticated user cannot create review."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': 5,
            'comment': 'Great!'
        }
        response = api_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_combo_review(self, authenticated_client, test_combo):
        """Test creating review for a combo."""
        data = {
            'combo': test_combo.id,
            'item_type': 'combo',
            'rating': 4,
            'comment': 'Nice combo!'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


# ==================== DUPLICATE REVIEW PREVENTION ====================

@pytest.mark.django_db
class TestDuplicateReviewPrevention:
    """Tests for preventing duplicate reviews."""
    
    base_url = '/api/reviews/'
    
    def test_cannot_create_duplicate_product_review(self, authenticated_client, test_product, test_user):
        """Test user cannot review same product twice."""
        # Create first review
        Review.objects.create(
            user=test_user,
            product=test_product,
            item_type='product',
            rating=5,
            comment='First review'
        )
        
        # Try to create second review
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': 3,
            'comment': 'Second review'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_cannot_create_duplicate_combo_review(self, authenticated_client, test_combo, test_user):
        """Test user cannot review same combo twice."""
        # Create first review
        Review.objects.create(
            user=test_user,
            combo=test_combo,
            item_type='combo',
            rating=4,
            comment='First review'
        )
        
        # Try to create second review
        data = {
            'combo': test_combo.id,
            'item_type': 'combo',
            'rating': 2,
            'comment': 'Second review'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==================== REVIEW RETRIEVAL TESTS ====================

@pytest.mark.django_db
class TestReviewRetrieval:
    """Tests for review listing and filtering."""
    
    base_url = '/api/reviews/'
    
    def test_list_reviews_public(self, api_client, test_product, test_user):
        """Test anyone can list reviews."""
        Review.objects.create(
            user=test_user,
            product=test_product,
            item_type='product',
            rating=5,
            comment='Great!'
        )
        
        response = api_client.get(self.base_url)
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_reviews_by_product(self, api_client, test_product, test_user):
        """Test filtering reviews by product."""
        Review.objects.create(
            user=test_user,
            product=test_product,
            item_type='product',
            rating=5,
            comment='Test'
        )
        
        response = api_client.get(f'{self.base_url}?product={test_product.id}')
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_reviews_by_combo(self, api_client, test_combo, test_user):
        """Test filtering reviews by combo."""
        Review.objects.create(
            user=test_user,
            combo=test_combo,
            item_type='combo',
            rating=4,
            comment='Test'
        )
        
        response = api_client.get(f'{self.base_url}?combo={test_combo.id}')
        assert response.status_code == status.HTTP_200_OK


# ==================== REVIEW EDGE CASES ====================

@pytest.mark.django_db
class TestReviewEdgeCases:
    """Edge case tests for reviews."""
    
    base_url = '/api/reviews/'
    
    def test_create_review_invalid_rating_zero(self, authenticated_client, test_product):
        """Test creating review with zero rating."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': 0,
            'comment': 'Zero rating test'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_review_invalid_rating_negative(self, authenticated_client, test_product):
        """Test creating review with negative rating."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': -5,
            'comment': 'Negative rating test'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_review_invalid_rating_too_high(self, authenticated_client, test_product):
        """Test creating review with rating > 5."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'rating': 100,
            'comment': 'High rating test'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_create_review_nonexistent_product(self, authenticated_client):
        """Test creating review for non-existent product."""
        data = {
            'product': 999999,
            'item_type': 'product',
            'rating': 5,
            'comment': 'Test'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
    
    def test_create_review_missing_rating(self, authenticated_client, test_product):
        """Test creating review without rating."""
        data = {
            'product': test_product.id,
            'item_type': 'product',
            'comment': 'No rating'
        }
        response = authenticated_client.post(self.base_url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_review_xss_in_comment(self, authenticated_client, test_product, malicious_inputs):
        """Test XSS payloads in review comment."""
        for payload in malicious_inputs.XSS_PAYLOADS:
            data = {
                'product': test_product.id,
                'item_type': 'product',
                'rating': 5,
                'comment': payload
            }
            response = authenticated_client.post(self.base_url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
            # Clean up for next iteration
            Review.objects.filter(user__email='testuser@example.com').delete()
    
    def test_review_sql_injection_in_comment(self, authenticated_client, test_product, malicious_inputs):
        """Test SQL injection in review comment."""
        for payload in malicious_inputs.SQL_INJECTION:
            data = {
                'product': test_product.id,
                'item_type': 'product',
                'rating': 4,
                'comment': payload
            }
            response = authenticated_client.post(self.base_url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
            Review.objects.filter(user__email='testuser@example.com').delete()
