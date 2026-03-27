from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        
        # Check cookie if no Authorization header
        is_cookie = False
        if header is None:
            raw_token = request.COOKIES.get('access_token') or None
            is_cookie = True
        else:
            raw_token = self.get_raw_token(header)
            
        if raw_token is None:
            return None

        # Enforce CSRF check if using cookie-based authentication
        if is_cookie:
            self.enforce_csrf(request)

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def enforce_csrf(self, request):
        from rest_framework.authentication import CSRFCheck
        from rest_framework.exceptions import PermissionDenied
        
        check = CSRFCheck(lambda req: None) # placeholder view
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f'CSRF Failed: {reason}')
