from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
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

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data['access']
            refresh_token = response.data['refresh']
            
            # Set access token in secure HttpOnly cookie
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=3600 # 1 hour
            )
            # Set refresh token in secure HttpOnly cookie
            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=3600 * 24 * 7 # 7 days
            )
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom Token Refresh View to update cookies
    """
    def post(self, request, *args, **kwargs):
        # Allow refresh from cookie if not in body
        refresh_from_cookie = request.COOKIES.get('refresh_token')
        if not request.data.get('refresh') and refresh_from_cookie:
            request.data['refresh'] = refresh_from_cookie
            
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data['access']
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=3600
            )
            # If rotation is on, we'll get a new refresh token
            if 'refresh' in response.data:
                refresh_token = response.data['refresh']
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    httponly=True,
                    secure=not settings.DEBUG,
                    samesite='Lax',
                    max_age=3600 * 24 * 7
                )
        return response


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
            otp_record = PasswordResetOTP(
                user=user,
                expires_at=expires_at
            )
            otp_record.set_otp(otp_code)
            otp_record.save()
            
            # Send Email asynchronously to prevent blocking and timing attacks
            import threading
            threading.Thread(target=send_mail, kwargs={
                'subject': 'Password Reset OTP - NGU Spices',
                'message': f'Your OTP for password reset is: {otp_code}\n\nThis code will expire in 10 minutes.',
                'from_email': settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
                'recipient_list': [user.email],
                'fail_silently': True,
            }).start()
            
        except User.DoesNotExist:
            # Prevent email enumeration via timing attack
            User().set_password('dummy_password')
            
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
            if not otp_record.check_otp(otp_code):
                otp_record.failed_attempts += 1
                otp_record.save(update_fields=['failed_attempts'])
                remaining = PasswordResetOTP.MAX_FAILED_ATTEMPTS - otp_record.failed_attempts
                if remaining > 0:
                    return Response({'detail': f'Invalid OTP. {remaining} attempt(s) remaining.'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'detail': 'Too many failed attempts. Please request a new OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
                
            import uuid
            otp_record.is_used = True
            otp_record.reset_token = str(uuid.uuid4())
            otp_record.save(update_fields=['is_used', 'reset_token'])

            return Response({
                'detail': 'OTP verified successfully. You may proceed to reset password.',
                'reset_token': otp_record.reset_token
            }, status=status.HTTP_200_OK)
            
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
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            # Find the OTP record by reset_token
            otp_record = PasswordResetOTP.objects.get(
                user=user,
                reset_token=reset_token,
                is_used=True
            )
            
            if otp_record.is_expired:
                return Response({'detail': 'Password reset session has expired. Please request a new OTP.'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Valid OTP, update password
            user.set_password(new_password)
            user.save()
            
            # Clear reset token
            otp_record.reset_token = None
            otp_record.save()
            
            return Response({'detail': 'Password has been reset successfully. You can now login.'}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            return Response({'detail': 'Invalid OTP or email.'}, status=status.HTTP_400_BAD_REQUEST)
