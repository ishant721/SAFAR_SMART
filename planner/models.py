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
    is_finalized = models.BooleanField(default=False)
    trip_status = models.CharField(max_length=20, default='draft')
    is_started = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Trip to {self.destination} for {self.user.username}"

class ChatMessage(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    question = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message for trip {self.trip.id}"

class Checkpoint(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    completed = models.BooleanField(default=False)
    
    # Enhanced fields for detailed timeline interface
    time = models.TimeField(blank=True, null=True, help_text="Activity time (e.g., 09:00)")
    location = models.CharField(max_length=255, blank=True, null=True, help_text="Specific location for this activity")
    tips = models.TextField(blank=True, null=True, help_text="Tips and advice for this activity")
    day_number = models.PositiveIntegerField(default=1, help_text="Day of the trip (1, 2, 3, etc.)")
    order_in_day = models.PositiveIntegerField(default=1, help_text="Order of activity within the day")

    class Meta:
        ordering = ['day_number', 'order_in_day', 'time']

    def __str__(self):
        return self.name

class Feedback(models.Model):
    LIKE = 1
    DISLIKE = 2
    RATING_CHOICES = (
        (LIKE, 'Like'),
        (DISLIKE, 'Dislike'),
    )
    checkpoint = models.ForeignKey(Checkpoint, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES, default=LIKE)
    feedback = models.TextField()

    def __str__(self):
        return f"Feedback for {self.checkpoint.name} by {self.user.username}"