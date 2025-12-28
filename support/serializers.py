from rest_framework import serializers
from .models import ContactSubmission, ChatSession, ChatMessage


class ContactSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for creating and listing contact submissions"""
    
    class Meta:
        model = ContactSubmission
        fields = [
            'id', 'name', 'email', 'phone', 'subject', 'message',
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class ContactSubmissionAdminSerializer(serializers.ModelSerializer):
    """Admin serializer with all fields including admin notes"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = ContactSubmission
        fields = [
            'id', 'name', 'email', 'phone', 'subject', 'message',
            'status', 'user', 'user_email', 'admin_notes', 'replied_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'sender_type', 'sender_name', 'message',
            'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new message"""
    
    class Meta:
        model = ChatMessage
        fields = ['message']


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat sessions"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    order_number = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user', 'user_email', 'guest_name', 'guest_email',
            'order', 'order_number', 'subject', 'status', 'priority',
            'messages', 'unread_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'session_id', 'created_at', 'updated_at']
    
    def get_order_number(self, obj):
        if obj.order:
            return f"ORD-{obj.order.id:06d}"
        return None
    
    def get_unread_count(self, obj):
        return obj.messages.filter(is_read=False, sender_type='user').count()


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new chat session - requires order"""
    order_number = serializers.CharField(write_only=True, required=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'session_id', 'order_number', 'subject', 'status', 'messages', 'created_at']
        read_only_fields = ['id', 'session_id', 'status', 'messages', 'created_at']
    
    def validate_order_number(self, value):
        """Validate that order exists and belongs to the user"""
        from orders.models import Order
        
        if not value:
            raise serializers.ValidationError("Order number is required")
        
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        if not user:
            raise serializers.ValidationError("Authentication required")
        
        # Parse order number - format is "ORD-000001" where 000001 is the ID
        clean_value = value.replace('ORD-', '').replace('ORD', '').strip()
        
        try:
            order_id = int(clean_value)
            order = Order.objects.get(id=order_id, user=user)
            return order
        except ValueError:
            raise serializers.ValidationError("Invalid order number format")
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or doesn't belong to you")
    
    def create(self, validated_data):
        order = validated_data.pop('order_number')  # This is now the Order object from validate
        
        request = self.context.get('request')
        user = request.user
        
        # Format order number for display
        order_display = f"ORD-{order.id:06d}"
        
        # Check if there's already an open chat for this order
        existing = ChatSession.objects.filter(
            user=user,
            order=order,
            status__in=['open', 'waiting']
        ).first()
        
        if existing:
            return existing
        
        session = ChatSession.objects.create(
            user=user,
            order=order,
            subject=validated_data.get('subject', f'Support for Order {order_display}')
        )
        
        # Add welcome message
        ChatMessage.objects.create(
            session=session,
            sender_type='system',
            sender_name='Support Bot',
            message=f"Welcome to Nidhi Grah Udyog Support! We see you have a question about order {order_display}. How can we help you today?"
        )
        
        return session


class ChatSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing sessions"""
    order_number = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user_email', 'guest_name', 'subject', 'status', 'priority',
            'order_number', 'last_message', 'unread_count',
            'created_at', 'updated_at'
        ]
    
    def get_order_number(self, obj):
        if obj.order:
            return f"ORD-{obj.order.id:06d}"
        return None
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'sender_type': last_msg.sender_type,
                'message': last_msg.message[:100] + '...' if len(last_msg.message) > 100 else last_msg.message,
                'created_at': last_msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        return obj.messages.filter(is_read=False, sender_type='user').count()
