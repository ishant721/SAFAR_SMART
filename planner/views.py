from django.shortcuts import render, redirect, get_object_or_404
import traceback
import asyncio
from django.contrib.auth.decorators import login_required
from .models import Trip, ChatMessage, Checkpoint, Feedback
from .forms import TripForm
from .langgraph_logic import graph, generate_itinerary, recommend_activities_agent, fetch_useful_links_agent, weather_forecaster_agent, packing_list_generator_agent, food_culture_recommender_agent, chat_agent, accommodation_recommender_agent, expense_breakdown_agent, complete_trip_plan_agent, generate_complete_trip_automatically
from django.http import JsonResponse, HttpResponse
import json
from django.urls import reverse
from django.views.decorators.http import require_POST
from users.models import UserProfile
from django.contrib import messages
from fpdf import FPDF
import requests
import os
from datetime import datetime
import re
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from asgiref.sync import sync_to_async

@login_required
def dashboard(request):
    return render(request, 'planner/dashboard.html')

@login_required
async def create_trip(request):
    form = TripForm()
    payment_required = False
    trip_data = {}
    user_profile, created = await sync_to_async(UserProfile.objects.get_or_create)(user=request.user)

    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            if request.user.prepaid_itineraries_count > 0:
                request.user.prepaid_itineraries_count -= 1
                await sync_to_async(request.user.save)()
            elif request.user.free_itineraries_count < 2:
                request.user.free_itineraries_count += 1
                await sync_to_async(request.user.save)()
            elif user_profile.paid_plan_credits >= 5:
                user_profile.paid_plan_credits -= 5
                await sync_to_async(user_profile.save)()
            else:
                messages.warning(request, 'You have used all your free itineraries. Please add money to your wallet to create more.')
                return redirect('add_money')

            trip = form.save(commit=False)
            trip.user = request.user
            await sync_to_async(trip.save)()
            
            inputs = {"trip_id": trip.id}
            try:
                await generate_complete_trip_automatically(inputs)
                await sync_to_async(trip.refresh_from_db)()
            except Exception as e:
                print(f"Error generating complete trip automatically: {e}")
            
            return redirect('planner:trip_detail', trip_id=trip.id)
    
    remaining_free_itineraries = 2 - request.user.free_itineraries_count

    return render(request, 'planner/create_trip.html', {
        'form': form,
        'payment_required': payment_required,
        'trip_data': json.dumps(trip_data) if trip_data else '{}',
        'remaining_free_itineraries': remaining_free_itineraries,
    })

@login_required
@require_POST
async def create_paid_trip(request):
    form = TripForm(request.POST)
    if form.is_valid():
        user_profile = await sync_to_async(UserProfile.objects.get)(user=request.user)
        if user_profile.paid_plan_credits >= 5:
            user_profile.paid_plan_credits -= 5
            await sync_to_async(user_profile.save)()

            trip = form.save(commit=False)
            trip.user = request.user
            await sync_to_async(trip.save)()
            
            state = {"trip_id": trip.id}
            await generate_itinerary(state)
            await sync_to_async(trip.refresh_from_db)()

            

            return JsonResponse({'status': 'success', 'redirect_url': reverse('planner:trip_detail', kwargs={'trip_id': trip.id})})
        else:
            return JsonResponse({'status': 'error', 'message': 'Insufficient balance.'}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid form data', 'errors': form.errors}, status=400)

@login_required
def trip_detail(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, user=request.user)
    checkpoints = trip.checkpoint_set.all().order_by('id')

    daily_checkpoints_data = {}
    for checkpoint in checkpoints:
        day_prefix_match = re.match(r'(Day \d+)', checkpoint.name)
        day_prefix = day_prefix_match.group(1) if day_prefix_match else "Other Checkpoints"

        if day_prefix not in daily_checkpoints_data:
            daily_checkpoints_data[day_prefix] = {
                'checkpoints': [], 'completed_count': 0, 'total_count': 0, 'progress_percentage': 0
            }
        
        daily_checkpoints_data[day_prefix]['checkpoints'].append(checkpoint)
        daily_checkpoints_data[day_prefix]['total_count'] += 1
        if checkpoint.completed:
            daily_checkpoints_data[day_prefix]['completed_count'] += 1
    
    for day_data in daily_checkpoints_data.values():
        if day_data['total_count'] > 0:
            day_data['progress_percentage'] = round((day_data['completed_count'] / day_data['total_count']) * 100, 2)

    weather_data = get_current_weather(trip.destination)
    progress_data = calculate_trip_progress(trip)
    
    context = {
        'trip': trip,
        'weather_data': weather_data,
        'progress_data': progress_data,
        'daily_checkpoints_data': daily_checkpoints_data,
    }
    return render(request, 'planner/trip_detail_interactive.html', context)

@login_required
async def process_trip(request, trip_id):
    trip = await sync_to_async(Trip.objects.get)(id=trip_id, user=request.user)
    if request.method == 'POST':
        agent_name = request.POST.get('agent_name')
        user_question = request.POST.get('user_question')

        agent_functions = {
            "generate_itinerary": generate_itinerary,
            "generate_complete_trip": generate_complete_trip_automatically,
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

        state = {
            "trip_id": trip.id, "preferences_text": "", "itinerary": trip.itinerary,
            "activity_suggestions": trip.activity_suggestions, "useful_links": trip.useful_links,
            "weather_forecast": trip.weather_forecast, "packing_list": trip.packing_list,
            "food_culture_info": trip.food_culture_info, "accommodation_info": trip.accommodation_info,
            "expense_breakdown": trip.expense_breakdown,
            "chat_history": [], "user_question": user_question, "chat_response": "",
        }

        try:
            result = await selected_agent_function(state)
            await sync_to_async(trip.refresh_from_db)()
            
            last_chat_message = await sync_to_async(trip.chatmessage_set.last)()
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
                'chat_response': last_chat_message.response if last_chat_message else ''
            }
            if isinstance(result, dict) and "warning" in result:
                response_data["warning"] = result["warning"]
            if isinstance(result, dict) and "warnings" in result:
                response_data["warnings"] = result["warnings"]
            return JsonResponse(response_data)
        except Exception as e:
            print(f"Error in process_trip: {e}")
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
async def chat_with_agent(request, trip_id):
    trip = await sync_to_async(Trip.objects.get)(id=trip_id, user=request.user)
    if request.method == 'POST':
        user_question = request.POST.get('user_question')
        
        state = {
            "trip_id": trip.id, "user_question": user_question,
            "chat_history": [], "chat_response": "",
        }

        try:
            result = await chat_agent(state)
            await sync_to_async(trip.refresh_from_db)()
            chat_message = await sync_to_async(trip.chatmessage_set.last)()
            response_data = {'status': 'success', 'chat_response': chat_message.response}
            if isinstance(result, dict) and "warning" in result:
                response_data["warning"] = result["warning"]
            return JsonResponse(response_data)
        except Exception as e:
            print(f"Error in chat_with_agent: {e}")
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
@require_POST
def mark_checkpoint_complete(request, trip_id, checkpoint_id):
    checkpoint = get_object_or_404(Checkpoint, id=checkpoint_id, trip__user=request.user, trip_id=trip_id)
    try:
        data = json.loads(request.body)
        completed = data.get('completed')
        if isinstance(completed, bool):
            checkpoint.completed = completed
            checkpoint.save()
            return JsonResponse({'status': 'success', 'completed': completed})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid value for completed'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

@login_required
@require_POST
def submit_checkpoint_feedback(request, trip_id, checkpoint_id):
    checkpoint = get_object_or_404(Checkpoint, id=checkpoint_id, trip__user=request.user, trip_id=trip_id)
    try:
        data = json.loads(request.body)
        feedback_text = data.get('feedback')
        if feedback_text is not None:
            feedback, created = Feedback.objects.update_or_create(
                checkpoint=checkpoint,
                user=request.user,
                defaults={'feedback': feedback_text}
            )
            return JsonResponse({'status': 'success', 'feedback': feedback_text})
        else:
            return JsonResponse({'status': 'error', 'message': 'Feedback text is required'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

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
        total_checkpoints = trip.checkpoint_set.count()
        completed_checkpoints = trip.checkpoint_set.filter(completed=True).count()
        
        progress_percentage = 0
        if total_checkpoints > 0:
            progress_percentage = (completed_checkpoints / total_checkpoints) * 100

        progress_data = {
            'total_stops': total_checkpoints,
            'completed_stops': completed_checkpoints,
            'progress_percentage': round(progress_percentage, 2),
            'remaining_stops': total_checkpoints - completed_checkpoints,
        }
        return progress_data
    except Exception:
        return {'total_stops': 0, 'completed_stops': 0, 'remaining_stops': 0, 'progress_percentage': 0}

@login_required
def download_trip_pdf(request, trip_id):
    """Generate and download PDF of the complete trip itinerary"""
    trip = Trip.objects.get(id=trip_id, user=request.user)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('helvetica', '', 16)
    pdf.cell(190, 10, f"Trip to {trip.destination}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font('helvetica', '', 12)
    pdf.cell(190, 10, "Trip Details", ln=True)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(190, 8, f"Destination: {trip.destination}", ln=True)
    pdf.cell(190, 8, f"Duration: {trip.duration} days", ln=True)
    pdf.cell(190, 8, f"Month: {trip.month}", ln=True)
    pdf.cell(190, 8, f"Type: {trip.holiday_type}", ln=True)
    pdf.ln(10)
    
    def write_html(html):
        clean_text = re.sub('<.*?>', '', html)
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&')
        lines = clean_text.split('\n')
        for line in lines:
            if len(line.strip()) > 0:
                while len(line) > 80:
                    pdf.cell(190, 5, line[:80], ln=True)
                    line = line[80:]
                if line.strip():
                    pdf.cell(190, 5, line, ln=True)

    if trip.itinerary:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Itinerary", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(trip.itinerary)
        pdf.ln(10)

    if trip.activity_suggestions:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Activity Suggestions", ln=True)
        pdf.set_font('helvetica', '', 8)
        for activity in trip.activity_suggestions:
            pdf.cell(190, 5, f"- {activity['name']}", ln=True)
        pdf.ln(10)

    if trip.useful_links:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Useful Links", ln=True)
        pdf.set_font('helvetica', '', 8)
        for link in trip.useful_links:
            pdf.cell(190, 5, f"- {link['title']}: {link['link']}", ln=True)
        pdf.ln(10)

    if trip.weather_forecast:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Weather Forecast", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(trip.weather_forecast)
        pdf.ln(10)

    if trip.packing_list:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Packing List", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(trip.packing_list)
        pdf.ln(10)

    if trip.food_culture_info:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Food and Culture", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(json.dumps(trip.food_culture_info, indent=4))
        pdf.ln(10)

    if trip.accommodation_info:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Accommodation", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(json.dumps(trip.accommodation_info, indent=4))
        pdf.ln(10)

    if trip.expense_breakdown:
        pdf.set_font('helvetica', '', 12)
        pdf.cell(190, 10, "Expense Breakdown", ln=True)
        pdf.set_font('helvetica', '', 8)
        write_html(trip.expense_breakdown)
        pdf.ln(10)

    
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="trip_{trip.destination}_{trip.id}.pdf"'
    response.write(pdf.output(dest='S'))
    return response


@login_required
def finalize_trip(request, trip_id):
    trip = Trip.objects.get(id=trip_id, user=request.user)
    
    messages.info(request, 'Finalize trip functionality has been removed.')
    return redirect('planner:trip_detail', trip_id=trip.id)