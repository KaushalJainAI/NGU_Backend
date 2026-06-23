from django.db import models
from django.conf import settings


class UserEvent(models.Model):
    """
    A single behavioral interaction by a logged-in user.

    These rows are the raw signal that powers personalized recommendations
    (see products/personalization.py). Kept deliberately lightweight so the
    write path on POST /api/events/ stays cheap; aggregation happens at read
    time (or via a periodic rollup) rather than here.
    """

    EVENT_TYPE_CHOICES = [
        ('view', 'Product View'),
        ('click', 'Product Click'),
        ('add_to_cart', 'Add To Cart'),
        ('remove_from_cart', 'Remove From Cart'),
        ('favorite', 'Favorite'),
        ('search', 'Search'),
        ('purchase', 'Purchase'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)

    # Optional targets — which entity the event is about. All nullable because
    # not every event references one (e.g. a bare search has only a query).
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    combo = models.ForeignKey(
        'products.ProductCombo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    category = models.ForeignKey(
        'products.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    query = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    session_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['product']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.event_type}:{self.product_id or self.query}"


class UserGeo(models.Model):
    """
    Coarse, consent-based location for a single user.

    Captured only after the user explicitly shares their location on the
    storefront (browser geolocation -> reverse geocode). Deliberately coarse:
    we never persist precise GPS coordinates here. ``lat_coarse``/``lng_coarse``
    are rounded to ~city-block resolution (3 decimals) so they cannot pinpoint
    a home, while ``city``/``state``/``pincode_prefix`` drive (future) regional
    recommendation ranking. See products/personalization.py (W_GEO slot).

    One row per user (latest known location); updating overwrites it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='geo',
    )
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    # First 3 digits of the Indian PIN code — region, not exact locality.
    pincode_prefix = models.CharField(max_length=3, blank=True)
    # Rounded to 3 decimals (~110 m) at the API boundary; never raw GPS.
    lat_coarse = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
    )
    lng_coarse = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Location'
        verbose_name_plural = 'User Locations'
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['pincode_prefix']),
        ]

    def __str__(self):
        loc = ', '.join(filter(None, [self.city, self.state])) or 'unknown'
        return f"{self.user_id}: {loc}"
