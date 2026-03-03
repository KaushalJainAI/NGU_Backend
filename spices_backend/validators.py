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
    """
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Supported extensions are: ') + ", ".join(valid_extensions))

def validate_video_extension(value):
    """
    Validator for video extensions.
    """
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    if not ext.lower() in valid_extensions:
        raise ValidationError(_('Unsupported video extension. Supported extensions are: ') + ", ".join(valid_extensions))
