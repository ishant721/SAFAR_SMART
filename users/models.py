from django.contrib.auth.models import AbstractUser
from django.db import models
import random
import string
from django.utils import timezone
from datetime import timedelta

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

class User(AbstractUser):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    reset_otp = models.CharField(max_length=6, blank=True, null=True)
    reset_otp_created_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if not self.pk:
            self.otp = generate_otp()
            self.otp_created_at = timezone.now()
        super().save(*args, **kwargs)

    def is_otp_valid(self):
        if self.otp_created_at:
            return timezone.now() < self.otp_created_at + timedelta(minutes=10)
        return False

    def is_reset_otp_valid(self):
        if self.reset_otp_created_at:
            return timezone.now() < self.reset_otp_created_at + timedelta(minutes=10)
        return False

    def generate_new_otp(self, otp_type='registration'):
        if otp_type == 'registration':
            self.otp = generate_otp()
            self.otp_created_at = timezone.now()
        elif otp_type == 'reset':
            self.reset_otp = generate_otp()
            self.reset_otp_created_at = timezone.now()
        self.save()