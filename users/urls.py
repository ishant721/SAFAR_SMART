from django.urls import path
from .views import RegisterView, VerifyOTPView, ResendOTPView, interactive_login_view, interactive_register_view, ForgotPasswordRequestView, forgot_password_request_view, forgot_password_confirm_view, forgot_password_otp_verify_view, profile_view

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', interactive_login_view, name='login'),
    path('registration/', interactive_register_view, name='registration'),
    path('forgot-password-request/', ForgotPasswordRequestView.as_view(), name='forgot-password-request'),
    path('forgot-password-otp-verify/', forgot_password_otp_verify_view, name='forgot-password-otp-verify'),
    path('forgot-password-confirm/', forgot_password_confirm_view, name='forgot-password-confirm'),
    path('forgot-password/', forgot_password_request_view, name='forgot-password'),
    path('reset-password/', forgot_password_confirm_view, name='reset-password'),
    path('profile/', profile_view, name='profile'),
]
