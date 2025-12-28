from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle
from django.utils import timezone

from .models import ContactSubmission, ChatSession, ChatMessage
from .serializers import (
    ContactSubmissionSerializer,
    ContactSubmissionAdminSerializer,
    ChatSessionSerializer,
    ChatSessionCreateSerializer,
    ChatSessionListSerializer,
    ChatMessageSerializer,
    ChatMessageCreateSerializer,
)


# ==================== CUSTOM THROTTLES ====================

class ContactRateThrottle(AnonRateThrottle):
    """Throttle for contact form - prevents spam submissions"""
    scope = 'contact'


class IsAdminOrCreateOnly:
    """Allow anyone to create, but only admins can list/update/delete"""
    def has_permission(self, request, view):
        if view.action == 'create':
            return True
        return request.user and request.user.is_staff


class ContactSubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for contact form submissions.
    - Anyone can POST (submit a contact form) - rate limited to 5/hour
    - Only admins can GET/PUT/DELETE
    """
    throttle_classes = [ContactRateThrottle]
    
    def get_permissions(self):
        if self.action == 'create':
            return []
        from rest_framework.permissions import IsAdminUser
        return [IsAdminUser()]
    
    def get_queryset(self):
        return ContactSubmission.objects.all().select_related('user')
    
    def get_serializer_class(self):
        if self.request.user and self.request.user.is_staff:
            return ContactSubmissionAdminSerializer
        return ContactSubmissionSerializer
    
    def perform_create(self, serializer):
        # Link to user if authenticated
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a submission as read"""
        submission = self.get_object()
        submission.status = 'read'
        submission.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'marked as read'})
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Mark as replied with admin notes"""
        submission = self.get_object()
        submission.status = 'replied'
        submission.admin_notes = request.data.get('notes', '')
        submission.replied_at = timezone.now()
        submission.save(update_fields=['status', 'admin_notes', 'replied_at', 'updated_at'])
        return Response({'status': 'marked as replied'})


class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for chat sessions.
    - Users can create and view their own sessions
    - Admins can view and manage all sessions
    """
    
    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated, IsAdminUser
        # Chat sessions are linked to orders, so require authentication
        # Only admin can update, delete, close, assign
        if self.action in ['create', 'list', 'retrieve', 'messages']:
            return [IsAuthenticated()]
        return [IsAdminUser()]
    
    def get_queryset(self):
        user = self.request.user
        qs = ChatSession.objects.all().select_related('user', 'order', 'assigned_to')
        
        # Non-admin users only see their own sessions
        if not (user and user.is_staff):
            if user and user.is_authenticated:
                qs = qs.filter(user=user)
            else:
                # For anonymous users:
                # - Allow retrieving session by session_id query param
                # - Allow accessing session by pk (for messages action on detail routes)
                session_id = self.request.query_params.get('session_id')
                pk = self.kwargs.get('pk')
                
                if session_id:
                    qs = qs.filter(session_id=session_id)
                elif pk:
                    # Validate pk is a valid integer to prevent 500 errors
                    try:
                        pk_int = int(pk)
                        # Allow access by pk but only for sessions without a user (guest sessions)
                        qs = qs.filter(pk=pk_int, user__isnull=True)
                    except (ValueError, TypeError):
                        # Invalid pk (e.g., 'undefined', 'null', etc.) - return empty queryset
                        qs = qs.none()
                else:
                    qs = qs.none()
        
        return qs.prefetch_related('messages')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ChatSessionCreateSerializer
        if self.action == 'list':
            return ChatSessionListSerializer
        return ChatSessionSerializer
    
    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        """Get or post messages for a session"""
        # Validate pk is a valid integer
        if pk is None or pk == 'undefined' or pk == 'null':
            return Response(
                {'error': 'Invalid session ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pk_int = int(pk)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Session ID must be a valid integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = self.get_object()
        except Exception:
            return Response(
                {'error': 'Session not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'GET':
            messages = session.messages.all()
            # Mark messages as read for admin
            if request.user and request.user.is_staff:
                messages.filter(sender_type='user', is_read=False).update(
                    is_read=True, read_at=timezone.now()
                )
            serializer = ChatMessageSerializer(messages, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = ChatMessageCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Determine sender type
            sender_type = 'admin' if request.user and request.user.is_staff else 'user'
            sender_name = ''
            if sender_type == 'admin':
                sender_name = f"{request.user.first_name} {request.user.last_name}".strip() or 'Support'
            elif session.user:
                sender_name = f"{session.user.first_name} {session.user.last_name}".strip() or session.user.email
            else:
                sender_name = session.guest_name or 'Guest'
            
            message = ChatMessage.objects.create(
                session=session,
                sender_type=sender_type,
                sender_name=sender_name,
                message=serializer.validated_data['message']
            )
            
            # Update session timestamp
            session.save(update_fields=['updated_at'])
            
            return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a chat session"""
        session = self.get_object()
        session.status = 'closed'
        session.closed_at = timezone.now()
        session.save(update_fields=['status', 'closed_at', 'updated_at'])
        
        # Add system message
        ChatMessage.objects.create(
            session=session,
            sender_type='system',
            sender_name='System',
            message='This chat session has been closed. Thank you for contacting us!'
        )
        
        return Response({'status': 'session closed'})
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign session to an admin"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        session = self.get_object()
        session.assigned_to = request.user
        session.save(update_fields=['assigned_to', 'updated_at'])
        
        return Response({'status': f'assigned to {request.user.email}'})
