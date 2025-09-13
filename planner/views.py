from django.shortcuts import render, redirect
import traceback
from django.contrib.auth.decorators import login_required
from .models import Trip, ChatMessage
from .forms import TripForm
from .langgraph_logic import graph, generate_itinerary, recommend_activities_agent, fetch_useful_links_agent, weather_forecaster_agent, packing_list_generator_agent, food_culture_recommender_agent, chat_agent, accommodation_recommender_agent, expense_breakdown_agent, complete_trip_plan_agent
from django.http import JsonResponse, HttpResponse
import json
from django.urls import reverse # Added import
from django.views.decorators.http import require_POST # Added import
from users.models import UserProfile
from django.contrib import messages
from fpdf import FPDF
import requests
import os
from datetime import datetime
import re

@login_required
def dashboard(request):
    return render(request, 'planner/dashboard.html')

@login_required
def create_trip(request):
    form = TripForm() # Initialize form outside if/else for GET request
    payment_required = False
    trip_data = {}
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            # Check for prepaid itineraries first
            if request.user.prepaid_itineraries_count > 0:
                request.user.prepaid_itineraries_count -= 1
                request.user.save()
                # Proceed with trip creation
            elif request.user.free_itineraries_count < 2:
                request.user.free_itineraries_count += 1
                request.user.save()
                # Proceed with trip creation
            elif user_profile.paid_plan_credits >= 5:
                user_profile.paid_plan_credits -= 5
                user_profile.save()
            else:
                # User has used up free itineraries and has no prepaid ones, payment required
                messages.warning(request, 'You have used all your free itineraries. Please add money to your wallet to create more.')
                return redirect('add_money')

            # If we reach here, it means either free or prepaid itinerary was consumed
            trip = form.save(commit=False)
            trip.user = request.user
            trip.save()
            config = {"configurable": {"thread_id": trip.id}}
            inputs = {"trip_id": trip.id}
            try:
                graph.invoke(inputs, config=config)
                trip.refresh_from_db() # Refresh to get the generated itinerary
            except Exception as e:
                print(f"Error generating itinerary automatically: {e}")
            return redirect('trip_detail', trip_id=trip.id)
    
    # Calculate remaining_free_itineraries for both GET and POST (if not redirected)
    remaining_free_itineraries = 2 - request.user.free_itineraries_count

    return render(request, 'planner/create_trip.html', {
        'form': form,
        'payment_required': payment_required,
        'trip_data': json.dumps(trip_data) if trip_data else '{}', # Ensure trip_data is JSON string
        'remaining_free_itineraries': remaining_free_itineraries,
    })

# New view for creating trip after payment
@login_required
@require_POST
def create_paid_trip(request):
    form = TripForm(request.POST)
    if form.is_valid():
        user_profile = UserProfile.objects.get(user=request.user)
        if user_profile.paid_plan_credits >= 5:
            user_profile.paid_plan_credits -= 5
            user_profile.save()

            trip = form.save(commit=False)
            trip.user = request.user
            trip.save()
            config = {"configurable": {"thread_id": trip.id}}
            inputs = {"trip_id": trip.id}
            try:
                graph.invoke(inputs, config=config)
                trip.refresh_from_db() # Refresh to get the generated itinerary
            except Exception as e:
                print(f"Error generating itinerary automatically: {e}")
            return JsonResponse({'status': 'success', 'redirect_url': reverse('trip_detail', kwargs={'trip_id': trip.id})})
        else:
            return JsonResponse({'status': 'error', 'message': 'Insufficient balance.'}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid form data', 'errors': form.errors}, status=400)


@login_required
def trip_detail(request, trip_id):
    trip = Trip.objects.get(id=trip_id, user=request.user)
    
    # Get weather data for the destination
    weather_data = get_current_weather(trip.destination)
    
    # Calculate progress - using existing data structure
    progress_data = calculate_trip_progress(trip)
    
    context = {
        'trip': trip,
        'weather_data': weather_data,
        'progress_data': progress_data,
    }
    return render(request, 'planner/trip_detail_interactive.html', context)

@login_required
def process_trip(request, trip_id):
    trip = Trip.objects.get(id=trip_id, user=request.user)
    if request.method == 'POST':
        agent_name = request.POST.get('agent_name')
        user_question = request.POST.get('user_question')

        # Map agent names to their functions
        agent_functions = {
            "generate_itinerary": generate_itinerary,
            "recommend_activities": recommend_activities_agent,
            "fetch_useful_links": fetch_useful_links_agent,
            "weather_forecaster": weather_forecaster_agent,
            "packing_list_generator": packing_list_generator_agent,
            "food_culture_recommender": food_culture_recommender_agent,
            "accommodation_recommender": accommodation_recommender_agent,
            "expense_breakdown": expense_breakdown_agent,
            "complete_trip_plan": complete_trip_plan_agent,
            "chat": chat_agent,
        }

        selected_agent_function = agent_functions.get(agent_name)

        if not selected_agent_function:
            return JsonResponse({'status': 'error', 'message': 'Invalid agent name provided.'})

        # Construct the state dictionary for the agent function
        # This needs to match the GraphState structure expected by the agent functions
        state = {
            "trip_id": trip.id,
            "preferences_text": "", # Not directly used by all agents, but part of GraphState
            "itinerary": trip.itinerary,
            "activity_suggestions": trip.activity_suggestions,
            "useful_links": trip.useful_links,
            "weather_forecast": trip.weather_forecast,
            "packing_list": trip.packing_list,
            "food_culture_info": trip.food_culture_info,
            "accommodation_info": trip.accommodation_info,
            "expense_breakdown": trip.expense_breakdown,
            "complete_trip_plan": trip.complete_trip_plan,
            "chat_history": [], # Chat history is handled separately in chat_agent
            "user_question": user_question,
            "chat_response": "",
        }

        try:
            # Directly call the selected agent function
            result = selected_agent_function(state)
            
            # Refresh trip object to get latest data updated by the agent
            trip.refresh_from_db()
            
            response_data = {
                'status': 'success',
                'itinerary': trip.itinerary,
                'activity_suggestions': trip.activity_suggestions,
                'useful_links': trip.useful_links,
                'weather_forecast': trip.weather_forecast,
                'packing_list': trip.packing_list,
                'food_culture_info': trip.food_culture_info,
                'accommodation_info': trip.accommodation_info,
                'expense_breakdown': trip.expense_breakdown,
                'complete_trip_plan': trip.complete_trip_plan,
                'chat_response': trip.chatmessage_set.last().response if trip.chatmessage_set.exists() else ''
            }
            # Add warning if present in agent's result
            if isinstance(result, dict) and "warning" in result:
                response_data["warning"] = result["warning"]
            return JsonResponse(response_data)
        except Exception as e:
            print(f"Error in process_trip: {e}")
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def chat_with_agent(request, trip_id):
    trip = Trip.objects.get(id=trip_id, user=request.user)
    if request.method == 'POST':
        user_question = request.POST.get('user_question')
        
        # Construct the state dictionary for the chat_agent function
        state = {
            "trip_id": trip.id,
            "user_question": user_question,
            "complete_trip_plan": trip.complete_trip_plan,
            "chat_history": [], # Chat history is handled within the agent
            "chat_response": "",
        }

        print(f"Inputs to chat_agent: {state}")

        try:
            result = chat_agent(state)
            trip.refresh_from_db()
            chat_message = trip.chatmessage_set.last()
            response_data = {'status': 'success', 'chat_response': chat_message.response}
            if isinstance(result, dict) and "warning" in result:
                response_data["warning"] = result["warning"]
            return JsonResponse(response_data)
        except Exception as e:
            print(f"Error in chat_with_agent: {e}")
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

# Helper functions for weather and progress tracking
def get_current_weather(destination):
    """Get current weather for destination"""
    try:
        weather_data = {
            'temperature': 25,
            'condition': 'broken clouds',
            'humidity': 85,
            'wind_speed': 1.79,
            'visibility': 10.0,
        }
        return weather_data
    except Exception:
        return None

def calculate_trip_progress(trip):
    """Calculate trip progress based on existing itinerary data"""
    try:
        progress_data = {
            'total_stops': 14,
            'completed_stops': 0,
            'progress_percentage': 0,
        }
        
        if trip.itinerary:
            activities = len(re.findall(r'Day \d+', trip.itinerary))
            progress_data['total_stops'] = max(activities, 14)
        
        progress_data['remaining_stops'] = progress_data['total_stops'] - progress_data['completed_stops']
        return progress_data
    except Exception:
        return {'total_stops': 14, 'completed_stops': 0, 'remaining_stops': 14, 'progress_percentage': 0}

@login_required
def download_trip_pdf(request, trip_id):
    """Generate and download PDF of the complete trip itinerary"""
    trip = Trip.objects.get(id=trip_id, user=request.user)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Trip to {trip.destination}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "Trip Details", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f"Destination: {trip.destination}", ln=True)
    pdf.cell(190, 8, f"Duration: {trip.duration} days", ln=True)
    pdf.cell(190, 8, f"Month: {trip.month}", ln=True)
    pdf.cell(190, 8, f"Type: {trip.holiday_type}", ln=True)
    pdf.ln(10)
    
    if trip.complete_trip_plan:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, "Complete Itinerary", ln=True)
        pdf.set_font("Arial", '', 8)
        
        clean_text = re.sub('<.*?>', '', trip.complete_trip_plan)
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&')
        
        lines = clean_text.split('\n')
        for line in lines:
            if len(line.strip()) > 0:
                while len(line) > 80:
                    pdf.cell(190, 5, line[:80], ln=True)
                    line = line[80:]
                if line.strip():
                    pdf.cell(190, 5, line, ln=True)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="trip_{trip.destination}_{trip.id}.pdf"'
    response.write(pdf.output(dest='S').encode('latin-1'))
    return response
