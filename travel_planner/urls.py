"""
URL configuration for travel_planner project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.views import LogoutView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from users.views import login_view, interactive_register_view, forgot_password_request_view, forgot_password_confirm_view, forgot_password_otp_verify_view, login_verify_otp_view, registration_verify_otp_view


urlpatterns = [
    path("", TemplateView.as_view(template_name="welcome.html"), name="home"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("contact/", TemplateView.as_view(template_name="contact.html"), name="contact"),
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', login_view, name='login'),
    path('login-verify-otp/', login_verify_otp_view, name='login-verify-otp'),
    path('logout/', LogoutView.as_view(next_page='/login/'), name='logout'),
    path('registration/', interactive_register_view, name='registration'),
    path('registration-verify-otp/', registration_verify_otp_view, name='registration-verify-otp'),
    
    path('forgot-password/', forgot_password_request_view, name='forgot-password'),
    path('forgot-password-otp-verify/', forgot_password_otp_verify_view, name='forgot-password-otp-verify'),
    path('reset-password/', forgot_password_confirm_view, name='reset-password'),
    path('planner/', include('planner.urls')),
    path('payments/', include('payments.urls')),
]
