# AWS S3 Storage Integration

The NGU Spices Backend offloads all media and static files to Amazon S3 to ensure rapid global content delivery and preserve local server storage.

## Architectural Setup

The integration is built upon `boto3` and `django-storages`.

### Configuration Toggle
S3 uploading is controlled by the `USE_S3` variable in the environment.
- If `USE_S3=False` (Default for local development without keys), files are stored locally in the `/media/` folder and served directly by Django.
- If `USE_S3=True` (Production), standard Django `ImageField` saving automatically routes the byte stream to S3 instead of disk space.

### Security and Permissions
- We do **not** use AWS ACLs (`AWS_DEFAULT_ACL = None`). We map permissions through the AWS Bucket Policy instead.
- We do **not** use signed URLs (`AWS_QUERYSTRING_AUTH = False`) to allow CDN proxy caching effortlessly.
- Public files are heavily cached (`CacheControl: max-age=86400`).

## Environment Configuration

For S3 to activate, populate these `.env` properties:
```env
USE_S3=True
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_REGION_NAME=ap-south-1
```

## Storage Routing
- **Media Uploads** (e.g. `ProductImage`, `pfp.png`) go to the S3 `media/` prefix via `storages.backends.s3boto3.S3Boto3Storage`.
- **Static Files** (e.g. `admin.css`, `bundle.js`) go to the S3 `static/` prefix via `S3StaticStorage` upon running `python manage.py collectstatic`.
