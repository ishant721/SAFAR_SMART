from django import forms
from .models import Trip

class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ['destination', 'month', 'duration', 'num_people', 'holiday_type', 'budget_type', 'comments']
