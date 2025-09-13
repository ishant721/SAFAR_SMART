from django.db import models
from users.models import User
from datetime import datetime, timedelta

class Trip(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    destination = models.CharField(max_length=255)
    month = models.CharField(max_length=255)
    duration = models.IntegerField()
    num_people = models.CharField(max_length=255)
    holiday_type = models.CharField(max_length=255)
    budget_type = models.CharField(max_length=255)
    comments = models.TextField(blank=True, null=True)
    itinerary = models.TextField(blank=True, null=True)
    activity_suggestions = models.JSONField(blank=True, null=True)
    useful_links = models.JSONField(blank=True, null=True)
    weather_forecast = models.JSONField(blank=True, null=True)
    packing_list = models.TextField(blank=True, null=True)
    food_culture_info = models.JSONField(blank=True, null=True)
    accommodation_info = models.JSONField(blank=True, null=True)
    expense_breakdown = models.TextField(blank=True, null=True)
    complete_trip_plan = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    
    # New fields for progress tracking
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    current_weather = models.JSONField(blank=True, null=True)
    trip_status = models.CharField(max_length=20, choices=[
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed')
    ], default='planned')
    
    def __str__(self):
        return f"Trip to {self.destination} for {self.user.username}"
    
    @property
    def progress_percentage(self):
        """Calculate trip completion percentage"""
        if not hasattr(self, '_progress_percentage'):
            total_activities = self.dayactivity_set.count()
            if total_activities == 0:
                self._progress_percentage = 0
            else:
                completed_activities = self.dayactivity_set.filter(completed=True).count()
                self._progress_percentage = int((completed_activities / total_activities) * 100)
        return self._progress_percentage
    
    @property
    def total_stops(self):
        return self.dayactivity_set.count()
    
    @property
    def completed_stops(self):
        return self.dayactivity_set.filter(completed=True).count()
    
    @property
    def remaining_stops(self):
        return self.total_stops - self.completed_stops

class DayActivity(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    day_number = models.IntegerField()
    time = models.TimeField()
    location = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField()
    tip = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    experience_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['day_number', 'time']
    
    def __str__(self):
        return f"Day {self.day_number}: {self.title}"

class WeatherData(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    temperature = models.IntegerField()
    condition = models.CharField(max_length=100)
    humidity = models.IntegerField()
    wind_speed = models.FloatField()
    visibility = models.FloatField()
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Weather for {self.trip.destination}"

class ChatMessage(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    question = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message for trip {self.trip.id}"