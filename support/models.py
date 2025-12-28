from django.db import models
from django.conf import settings
from orders.models import Order


class ContactSubmission(models.Model):
    """Contact form submissions from the Contact Us page"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('closed', 'Closed'),
    ]
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default='')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Optional: link to user if logged in
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='contact_submissions'
    )
    
    # Admin response
    admin_notes = models.TextField(blank=True, default='')
    replied_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Submission'
        verbose_name_plural = 'Contact Submissions'

    def __str__(self):
        return f"{self.name} - {self.subject[:30]}"


class ChatSession(models.Model):
    """Chat support session - can be linked to an order or general inquiry"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('waiting', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Session identification
    session_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # User info (optional for guests)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='chat_sessions'
    )
    guest_name = models.CharField(max_length=100, blank=True, default='')
    guest_email = models.EmailField(blank=True, default='')
    
    # Link to order if order-specific
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_sessions'
    )
    
    # Session metadata
    subject = models.CharField(max_length=200, default='General Inquiry')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Assigned admin (optional)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_chats'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'

    def __str__(self):
        user_info = self.user.email if self.user else self.guest_name or 'Guest'
        return f"Chat #{self.session_id} - {user_info}"
    
    def save(self, *args, **kwargs):
        if not self.session_id:
            import uuid
            self.session_id = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)


class ChatMessage(models.Model):
    """Individual messages within a chat session"""
    SENDER_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    sender_name = models.CharField(max_length=100, blank=True, default='')
    message = models.TextField()
    
    # Optional: attachment support
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    
    # Read status for admin messages
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    def __str__(self):
        return f"{self.sender_type}: {self.message[:50]}..."
