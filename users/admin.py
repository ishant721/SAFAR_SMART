from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Payment Information', {'fields': ('free_itineraries_count', 'prepaid_itineraries_count')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Payment Information', {'fields': ('free_itineraries_count', 'prepaid_itineraries_count')}),
    )
    list_display = BaseUserAdmin.list_display + ('free_itineraries_count', 'prepaid_itineraries_count',)