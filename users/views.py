from rest_framework import generics, status
from rest_framework.response import Response
from .models import User, UserProfile, generate_otp
from .serializers import UserSerializer, OTPSerializer, ForgotPasswordRequestSerializer, ResendOTPSerializer
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from .forms import LoginForm
from django.utils import timezone
from datetime import timedelta
from payments.models import Payment # Commented out

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send OTP email
        subject = 'Your OTP for Account Verification'
        context = {
            'username': user.username,
            'otp': user.otp
        }
        html_message = render_to_string('email/otp_email.html', context)
        plain_message = strip_tags(html_message)
        from_email = 'ishantsingh01275@gmail.com' # Replace with your email
        to_email = user.email

        send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

        return Response({"message": "User registered successfully. Please check your email for the OTP."}, status=status.HTTP_201_CREATED)

class VerifyOTPView(generics.GenericAPIView):
    serializer_class = OTPSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_otp_valid():
            return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        if user.otp != otp:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save()

        return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)

class ResendOTPView(generics.GenericAPIView):
    serializer_class = ResendOTPSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp_type = serializer.validated_data.get('otp_type', 'registration')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If your email is in our system, a new OTP has been sent."}, status=status.HTTP_200_OK)

        if otp_type == 'registration':
            user.generate_new_otp(otp_type='registration')
            subject = 'Your New OTP for Account Verification'
            otp_code = user.otp
        elif otp_type == 'reset':
            user.generate_new_otp(otp_type='reset')
            subject = 'Your New Password Reset OTP'
            otp_code = user.reset_otp
        else:
            return Response({"error": "Invalid OTP type."}, status=status.HTTP_400_BAD_REQUEST)

        context = {
            'username': user.username,
            'otp': otp_code
        }
        html_message = render_to_string('email/otp_email.html' if otp_type == 'registration' else 'email/password_reset_otp.html', context)
        plain_message = strip_tags(html_message)
        from_email = 'ishantsingh01275@gmail.com' # Replace with your email
        to_email = user.email

        send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

        return Response({"message": "A new OTP has been sent to your email."}, status=status.HTTP_200_OK)
def interactive_login_view(request):
    return render(request, 'login.html')

def interactive_register_view(request):
    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return redirect('/dashboard/')
                else:
                    form.add_error(None, "Your account is inactive. Please activate your account.")
            else:
                form.add_error(None, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})



class ForgotPasswordRequestView(generics.GenericAPIView):
    serializer_class = ForgotPasswordRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If your email is in our system, you will receive a password reset OTP."}, status=status.HTTP_200_OK)

        user.reset_otp = generate_otp()
        user.reset_otp_created_at = timezone.now()
        user.save()

        # Send reset OTP email
        subject = 'Your Password Reset OTP'
        context = {
            'username': user.username,
            'otp': user.reset_otp
        }
        html_message = render_to_string('email/password_reset_otp.html', context)
        plain_message = strip_tags(html_message)
        from_email = 'ishantsingh01275@gmail.com' # Replace with your email
        to_email = user.email

        send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

        return Response({"message": "If your email is in our system, you will receive a password reset OTP."}, status=status.HTTP_200_OK)

def forgot_password_confirm_view(request):
    if request.method == 'POST':
        email = request.session.get('reset_password_email')
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')

        if not email:
            return render(request, 'reset_password.html', {'error': 'Session expired. Please try again.'})

        if new_password != new_password2:
            return render(request, 'reset_password.html', {'error': 'Passwords must match.'})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'reset_password.html', {'error': 'User not found.'})

        user.set_password(new_password)
        user.reset_otp = None
        user.reset_otp_created_at = None
        user.save()

        # Clear the session variable
        del request.session['reset_password_email']

        return redirect('login')
    else:
        return render(request, 'reset_password.html')

def forgot_password_otp_verify_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp = request.POST.get('otp')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'forgot_password_otp_verify.html', {'error': 'User not found.', 'email': email})

        if not user.is_reset_otp_valid():
            return render(request, 'forgot_password_otp_verify.html', {'error': 'OTP has expired.', 'email': email})

        if user.reset_otp != otp:
            return render(request, 'forgot_password_otp_verify.html', {'error': 'Invalid OTP.', 'email': email})

        # OTP is valid, store email in session and redirect to reset password page
        request.session['reset_password_email'] = email
        return redirect('reset-password')
    else:
        email = request.GET.get('email')
        return render(request, 'forgot_password_otp_verify.html', {'email': email})

def forgot_password_request_view(request):
    return render(request, 'forgot_password.html')

@login_required
def profile_view(request):
    user = request.user
    user_profile, created = UserProfile.objects.get_or_create(user=user)
    payments = Payment.objects.filter(user=user).order_by('-timestamp')
    remaining_free_itineraries = 2 - user.free_itineraries_count # Calculate here
    
    context = {
        'user': user,
        'user_profile': user_profile,
        'free_itineraries_count': user.free_itineraries_count,
        'payments': payments,
        'remaining_free_itineraries': remaining_free_itineraries, # Pass to context
    }
    return render(request, 'users/profile.html', context)
