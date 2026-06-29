from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import os

def validate_file_size(value):
    """
    Validator to check the file size.
    Maximum size is 500MB (524288000 bytes).
    """
    limit = 524288000  # 500MB
    if value.size > limit:
        raise ValidationError(
            _('File too large. Size should not exceed 500MB.')
        )

def validate_image_extension(value):
    """
    Validator for image extensions.

    Only NEW uploads are checked. An already-stored file may have no extension
    in its name (e.g. a Cloudinary public_id like ``ngu/products/turmeric_x``);
    these validators run again on every ``full_clean()``/save, so re-validating a
    stored, extension-less name would wrongly reject unrelated updates. Uploads
    always carry a filename with an extension, so "no extension" means
    "already persisted" -> nothing to validate.
    """
    ext = os.path.splitext(getattr(value, 'name', '') or '')[1]
    if not ext:
        return
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Supported extensions are: ') + ", ".join(valid_extensions))

def validate_video_extension(value):
    """
    Validator for video extensions. See ``validate_image_extension`` for why an
    extension-less (already-stored) name is treated as nothing-to-validate.
    """
    ext = os.path.splitext(getattr(value, 'name', '') or '')[1]
    if not ext:
        return
    valid_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported video extension. Supported extensions are: ') + ", ".join(valid_extensions))
