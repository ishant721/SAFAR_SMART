from django.core.management.base import BaseCommand
from django.utils import timezone
from planner.models import Trip
from planner.views import get_current_weather # Reusing existing weather function
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import requests
import os
from datetime import timedelta

NEWS_API_KEY = os.getenv('NEWSDATA_API_KEY')
NEWS_API_URL = "https://newsdata.io/api/1/news"

def fetch_news_alerts(destination):
    if not NEWS_API_KEY:
        return []

    try:
        params = {
            'apikey': NEWS_API_KEY,
            'q': destination, # Search query
            'language': 'en',
            'country': 'us', # You might want to make this dynamic based on destination
            'category': 'travel', # Filter by category
            'timeframe': 24, # News from the last 24 hours
        }
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors
        data = response.json()
        
        alerts = []
        for article in data.get('results', [])[:3]: # Get top 3 articles
            # Simple check for keywords that might indicate an alert
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            if any(keyword in title or keyword in description for keyword in ['warning', 'alert', 'disruption', 'strike', 'advisory', 'emergency']):
                alerts.append(f"News Alert: {article.get('title')} - {article.get('link')}")
        return alerts
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news from NewsData.io: {e}")
        return []

class Command(BaseCommand):
    help = 'Checks for weather and news alerts for active trips and sends email notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--secure', action='store_true', help='Use HTTPS for URLs in emails')
        parser.add_argument('--domain', type=str, default='localhost:8000', help='Domain to use for URLs in emails')

    def handle(self, *args, **options):
        self.stdout.write("Checking for trip alerts...")
        
        active_trips = Trip.objects.filter(is_started=True, has_been_reviewed=False)
        
        for trip in active_trips:
            self.stdout.write(f"Processing trip {trip.id} to {trip.destination} for user {trip.user.email}")
            
            alert_message = []
            
            # 1. Check Weather Alerts
            weather_data = get_current_weather(trip.destination)
            if weather_data and weather_data.get('condition') in ['thunderstorm', 'snow', 'rain', 'extreme']:
                alert_message.append(f"Severe weather warning for {trip.destination}: {weather_data.get('condition').title()} with {weather_data.get('temperature')}°C.")

            # 2. Check News Alerts
            news_alerts = fetch_news_alerts(trip.destination)
            alert_message.extend(news_alerts)

            # 3. Send Email if Alerts Exist and Not Sent Recently
            if alert_message:
                # Check if an alert has been sent in the last 24 hours
                if not trip.last_alert_sent or (timezone.now() - trip.last_alert_sent > timedelta(hours=24)):
                    self.stdout.write(f"Sending alert email for trip {trip.id}...")
                    
                    subject = f"Travel Alert for your trip to {trip.destination}"
                    html_message = render_to_string('planner/alert_email.html', {
                        'trip': trip,
                        'alert_message': alert_message,
                        'protocol': 'https' if options['secure'] else 'http',
                        'domain': options['domain'],
                    })
                    plain_message = strip_tags(html_message)
                    from_email = settings.DEFAULT_FROM_EMAIL
                    to_email = trip.user.email

                    try:
                        send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
                        trip.last_alert_sent = timezone.now()
                        trip.save()
                        self.stdout.write(self.style.SUCCESS(f"Successfully sent alert for trip {trip.id}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to send email for trip {trip.id}: {e}"))
                else:
                    self.stdout.write(f"Alert for trip {trip.id} already sent recently. Skipping.")
            else:
                self.stdout.write(f"No alerts for trip {trip.id}.")

        self.stdout.write("Alert check complete.")