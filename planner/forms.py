from django import forms
from .models import Trip

HOLIDAY_TYPE_CHOICES = [
    ('adventure', 'Adventure'),
    ('relaxing', 'Relaxing'),
    ('cultural', 'Cultural'),
    ('beach', 'Beach'),
    ('city_break', 'City Break'),
    ('family', 'Family'),
    ('romantic', 'Romantic'),
    ('others', 'Others'),
]

class TripForm(forms.ModelForm):
    holiday_type = forms.ChoiceField(
        choices=HOLIDAY_TYPE_CHOICES,
        required=False # Allow no selection if needed
    )

    class Meta:
        model = Trip
        fields = ['destination', 'month', 'duration', 'num_people', 'holiday_type', 'budget_type', 'comments']
