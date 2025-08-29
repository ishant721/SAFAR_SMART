from django.shortcuts import render, redirect
import traceback
from django.contrib.auth.decorators import login_required
from .models import Trip, ChatMessage
from .forms import TripForm
from .langgraph_logic import graph, generate_itinerary, recommend_activities_agent, fetch_useful_links_agent, weather_forecaster_agent, packing_list_generator_agent, food_culture_recommender_agent, chat_agent, accommodation_recommender_agent, expense_breakdown_agent, complete_trip_plan_agent
from django.http import JsonResponse
import json

@login_required
def dashboard(request):
    return render(request, 'planner/dashboard.html')

@login_required
def create_trip(request):
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save(commit=False)
            trip.user = request.user
            trip.save()
            # Automatically generate itinerary
            config = {"configurable": {"thread_id": trip.id}}
            inputs = {"trip_id": trip.id}
            try:
                graph.invoke(inputs, config=config)
                trip.refresh_from_db() # Refresh to get the generated itinerary
            except Exception as e:
                print(f"Error generating itinerary automatically: {e}")
            return redirect('trip_detail', trip_id=trip.id)
    else:
        form = TripForm()
    return render(request, 'planner/create_trip.html', {'form': form})

@login_required
def trip_detail(request, trip_id):
    trip = Trip.objects.get(id=trip_id, user=request.user)
    return render(request, 'planner/trip_detail.html', {'trip': trip})

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
