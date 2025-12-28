import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spices_backend.settings')
import django
django.setup()

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

print('=== Storage Configuration ===')
print(f'STORAGES: {getattr(settings, "STORAGES", "Not set")}')
print(f'Storage class: {default_storage.__class__.__name__}')
print(f'Bucket: {getattr(default_storage, "bucket_name", "N/A")}')
print(f'Location: {getattr(default_storage, "location", "N/A")}')
print(f'USE_S3: {getattr(settings, "USE_S3", False)}')

print()
print('=== Testing Upload ===')
try:
    test_content = ContentFile(b'Django storage test file')
    path = default_storage.save('_test_django_storage.txt', test_content)
    print(f'File saved to: {path}')
    url = default_storage.url(path)
    print(f'File URL: {url}')
    exists = default_storage.exists(path)
    print(f'File exists: {exists}')
    # Clean up
    default_storage.delete(path)
    print('Test file deleted successfully')
    print()
    print('=== UPLOAD TEST: SUCCESS ===')
except Exception as e:
    print(f'=== UPLOAD TEST FAILED ===')
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
