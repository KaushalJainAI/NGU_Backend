# Caching Strategy

To deliver a high-speed e-commerce experience globally, the NGU backend aggressively caches frequently accessed endpoint responses and product permutations.

## Redis Implementation

The caching backend defaults to **Redis** (via `django_redis`). If `REDIS_URL` is not provided in `.env`, the system gracefully falls back to Django's `LocMemCache` (local memory).

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'TIMEOUT': 300, # 5 Mins Default
    }
}
```

## Cache Namespacing

Cache keys are highly structured and prefixed to prevent collisions across different environments. Generation lives in `products/cache.py`.

Prefix examples:
- `products:...`
- `categories:...`
- `combos:...`
- `sections:...`

## Automatic Invalidation

Because prices and stocks change dynamically, caching requires robust invalidation.

The system uses **Django Signals** (`post_save` and `post_delete`) inside `products/signals.py` to selectively purge redis namespaced caches.

| Action | Invalidation Triggered |
|--------|------------------------|
| Save `Product` | Drops `products:*` and `sections:*` |
| Save `ProductCombo` | Drops `combos:*` and `sections:*` |
| Save `Category` | Drops `categories:*` |
| Save `ProductSection` | Drops `sections:*` |

*When a product is saved, its cache is invalidated and its AI-generated synonyms are refreshed simultaneously (in a background thread).*

## Time-to-Live (TTL) Settings

- **Short (60s):** Frequently changing data.
- **Medium (300s):** Default. Product lists and combo displays.
- **Long (900s):** Static data (Categories). 
