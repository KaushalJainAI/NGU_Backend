from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    CustomTokenObtainPairSerializer,
)


# ==================== CUSTOM THROTTLES ====================

class LoginRateThrottle(AnonRateThrottle):
    """Throttle for login attempts - prevents brute force attacks"""
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Throttle for registration - prevents mass account creation"""
    scope = 'register'


# ========== User Authentication Views ==========

class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user
    Rate limited: 3 attempts per minute
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'user': UserSerializer(user).data,
            'message': 'User registered successfully. Please login to continue.'
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update user profile
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        if not old_password or not new_password:
            return Response({'detail': 'Both passwords required'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({'detail': 'Old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Enforce strong password validation
        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({'detail': e.messages}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password updated successfully'}, status=status.HTTP_200_OK)



class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view with additional user data
    Rate limited: 5 attempts per minute to prevent brute force
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


# ==================== PASSWORD RESET VIEWS ====================
import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from .serializers import PasswordResetRequestSerializer, OTPVerifySerializer, PasswordResetConfirmSerializer
from .models import PasswordResetOTP

User = get_user_model()


class PasswordResetRateThrottle(AnonRateThrottle):
    """Throttle for password reset - 10 attempts per day per IP."""
    scope = 'password_reset'


class PasswordResetRequestView(APIView):
    """
    Send an OTP to the user's email for password reset verification.
    Rate limited: 10 attempts per day.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
            
            # Generate 6-digit OTP
            otp_code = f"{random.randint(100000, 999999)}"
            
            # Invalidate previous unexpired OTPs for this user
            PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
            
            # Clean up expired OTPs older than 24 hours (opportunistic cleanup)
            PasswordResetOTP.objects.filter(
                user=user,
                expires_at__lt=timezone.now() - timedelta(hours=24)
            ).delete()
            
            # Create new OTP record (expires in 10 minutes)
            expires_at = timezone.now() + timedelta(minutes=10)
            PasswordResetOTP.objects.create(
                user=user,
                otp_code=otp_code,
                expires_at=expires_at
            )
            
            # Send Email
            send_mail(
                subject='Password Reset OTP - NGU Spices',
                message=f'Your OTP for password reset is: {otp_code}\n\nThis code will expire in 10 minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
        except User.DoesNotExist:
            # Prevent email enumeration by returning success even if user doesn't exist
            pass
            
        return Response(
            {'detail': 'If an account exists with this email, an OTP has been sent.'}, 
            status=status.HTTP_200_OK
        )

class PasswordResetVerifyView(APIView):
    """
    Verify the OTP code sent to the email (without resetting password yet).
    Rate limited: 10 attempts per day.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        
        try:
            user = User.objects.get(email=email)
            # Get the latest unused OTP for this user (regardless of the code submitted)
            otp_record = PasswordResetOTP.objects.filter(
                user=user,
                is_used=False
            ).latest('created_at')
            
            if otp_record.is_expired:
                return Response({'detail': 'OTP has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if otp_record.is_locked:
                return Response({'detail': 'Too many failed attempts. Please request a new OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Check if the submitted OTP code matches
            if otp_record.otp_code != otp_code:
                otp_record.failed_attempts += 1
                otp_record.save(update_fields=['failed_attempts'])
                remaining = PasswordResetOTP.MAX_FAILED_ATTEMPTS - otp_record.failed_attempts
                if remaining > 0:
                    return Response({'detail': f'Invalid OTP. {remaining} attempt(s) remaining.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'detail': 'Too many failed attempts. Please request a new OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
                
            return Response({'detail': 'OTP verified successfully. You may proceed to reset password.'}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            return Response({'detail': 'Invalid OTP or email.'}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    """
    Confirm OTP and reset the password.
    Rate limited: 10 attempts per day.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            # Get the latest unused OTP for this user
            otp_record = PasswordResetOTP.objects.filter(
                user=user,
                is_used=False
            ).latest('created_at')
            
            if otp_record.is_expired:
                return Response({'detail': 'OTP has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if otp_record.is_locked:
                return Response({'detail': 'Too many failed attempts. Please request a new OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Check if the submitted OTP code matches
            if otp_record.otp_code != otp_code:
                otp_record.failed_attempts += 1
                otp_record.save(update_fields=['failed_attempts'])
                remaining = PasswordResetOTP.MAX_FAILED_ATTEMPTS - otp_record.failed_attempts
                if remaining > 0:
                    return Response({'detail': f'Invalid OTP. {remaining} attempt(s) remaining.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'detail': 'Too many failed attempts. Please request a new OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
                
            # Valid OTP, update password
            user.set_password(new_password)
            user.save()
            
            # Mark OTP as used
            otp_record.is_used = True
            otp_record.save()
            
            return Response({'detail': 'Password has been reset successfully. You can now login.'}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            return Response({'detail': 'Invalid OTP or email.'}, status=status.HTTP_400_BAD_REQUEST)
