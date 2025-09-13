from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from dotenv import load_dotenv
import os
from .models import Trip, ChatMessage
from langchain_core.messages import HumanMessage
import json
from .utils import convert_markdown_to_html
import re

# Load environment variables
import os
load_dotenv()

# Initialize LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize GoogleSerperAPIWrapper
search = GoogleSerperAPIWrapper(serper_api_key=os.getenv("SERPER_API_KEY"))

# Define state
class GraphState(TypedDict):
    trip_id: int
    preferences_text: str
    itinerary: str
    activity_suggestions: list[dict]
    useful_links: list[dict]
    weather_forecast: dict
    packing_list: str
    food_culture_info: list[dict]
    accommodation_info: list[dict]
    expense_breakdown: str
    complete_trip_plan: str
    chat_history: Annotated[list[dict], "List of question-response pairs"]
    user_question: str
    chat_response: str

# Agent functions

def generate_itinerary(state):
    trip = Trip.objects.get(id=state['trip_id'])
    preferences_text = f"Destination: {trip.destination}\nMonth: {trip.month}\nDuration: {trip.duration} days\nPeople: {trip.num_people}\nType: {trip.holiday_type}\nBudget: {trip.budget_type}\nComments: {trip.comments}"
    prompt = f"""
    Using the following preferences, create a detailed itinerary:
    {preferences_text}

    Include sections for each day, dining options, and downtime.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        trip.itinerary = convert_markdown_to_html(result.strip())
        trip.save()
        return {"itinerary": convert_markdown_to_html(result.strip())}
    except Exception as e:
        return {"itinerary": "", "warning": str(e)}

def recommend_activities_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    query = f"Unique local activities in {trip.destination} for {trip.month}"
    try:
        search_results = search.results(query)
        organic_results = search_results.get("organic", [])
        activities = []
        for result in organic_results[:5]: # Limit to top 5 results
            title = result.get("title", "No title")
            link = result.get("link", "")
            snippet = result.get("snippet", "")

            # Get image from the result if available
            image_url = result.get("thumbnail", "")

            activities.append({
                "name": title,
                "link": link,
                "snippet": snippet,
                "image_url": image_url,
                "video_url": ""
            })
        
        trip.activity_suggestions = activities
        trip.save()
        return {"activity_suggestions": activities}
    except Exception as e:
        return {"activity_suggestions": [], "warning": f"Failed to fetch activities: {str(e)}"}


def fetch_useful_links_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    query = f"Travel tips and guides for {trip.destination} in {trip.month}"
    try:
        search_results = search.results(query)
        organic_results = search_results.get("organic", [])
        links = [
            {"title": result.get("title", "No title"), "link": result.get("link", "")}
            for result in organic_results[:5]
        ]
        # Ensure uniqueness of links based on their content
        unique_links_set = set(frozenset(link.items()) for link in links)
        links = [dict(fs) for fs in unique_links_set]
        trip.useful_links = links
        trip.save()
        return {"useful_links": links}
    except Exception as e:
        return {"useful_links": [], "warning": f"Failed to fetch links: {str(e)}"}


def weather_forecaster_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    Based on the destination and month, provide a detailed weather forecast including temperature, precipitation, and advice for travelers:
    Destination: {trip.destination}
    Month: {trip.month}
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        trip.weather_forecast = convert_markdown_to_html(result.strip())
        trip.save()
        return {"weather_forecast": convert_markdown_to_html(result.strip())}
    except Exception as e:
        return {"weather_forecast": "", "warning": str(e)}


def packing_list_generator_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    Generate a comprehensive packing list for a {trip.holiday_type} holiday in {trip.destination} during {trip.month} for {trip.duration} days.
    Include essentials based on expected weather and trip type.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        trip.packing_list = convert_markdown_to_html(result.strip())
        trip.save()
        return {"packing_list": convert_markdown_to_html(result.strip())}
    except Exception as e:
        return {"packing_list": "", "warning": str(e)}


def food_culture_recommender_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    query = f"Popular local dishes and dining options in {trip.destination} for {trip.budget_type} budget"
    try:
        search_results = search.results(query)
        organic_results = search_results.get("organic", [])
        food_options = []
        for result in organic_results[:5]: # Limit to top 5 results
            title = result.get("title", "No title")
            link = result.get("link", "")
            snippet = result.get("snippet", "")

            # Get image from the result if available
            image_url = result.get("thumbnail", "")

            food_options.append({
                "name": title,
                "link": link,
                "snippet": snippet,
                "image_url": image_url,
                "video_url": ""
            })
        
        # Also add cultural norms and etiquette using LLM
        cultural_prompt = f"""
        For a trip to {trip.destination}, provide important cultural norms, etiquette tips, and things travelers should be aware of.
        Format the response with clear sections for 'Culture & Etiquette'.
        """
        cultural_info = llm.invoke([HumanMessage(content=cultural_prompt)]).content

        trip.food_culture_info = {"food_options": food_options, "cultural_info": convert_markdown_to_html(cultural_info.strip())}
        trip.save()
        return {"food_culture_info": {"food_options": food_options, "cultural_info": convert_markdown_to_html(cultural_info.strip())}}
    except Exception as e:
        return {"food_culture_info": [], "warning": f"Failed to fetch food and culture: {str(e)}"}

def generate_complete_trip_automatically(state):
    """
    Runs all AI agents automatically to generate a complete trip plan
    """
    print(f"Starting complete trip generation for trip {state['trip_id']}")
    warnings = []
    
    try:
        # Step 1: Generate basic itinerary
        print("Step 1: Generating basic itinerary...")
        itinerary_result = generate_itinerary(state)
        if itinerary_result.get('warning'):
            warnings.append(f"Itinerary: {itinerary_result['warning']}")
        
        # Step 2: Get activities
        print("Step 2: Getting activity suggestions...")
        activities_result = recommend_activities_agent(state)
        if activities_result.get('warning'):
            warnings.append(f"Activities: {activities_result['warning']}")
        
        # Step 3: Get useful links
        print("Step 3: Fetching useful links...")
        links_result = fetch_useful_links_agent(state)
        if links_result.get('warning'):
            warnings.append(f"Links: {links_result['warning']}")
            
        # Step 4: Get weather forecast
        print("Step 4: Getting weather forecast...")
        weather_result = weather_forecaster_agent(state)
        if weather_result.get('warning'):
            warnings.append(f"Weather: {weather_result['warning']}")
            
        # Step 5: Generate packing list
        print("Step 5: Creating packing list...")
        packing_result = packing_list_generator_agent(state)
        if packing_result.get('warning'):
            warnings.append(f"Packing: {packing_result['warning']}")
            
        # Step 6: Get food and culture info
        print("Step 6: Getting food and culture recommendations...")
        food_culture_result = food_culture_recommender_agent(state)
        if food_culture_result.get('warning'):
            warnings.append(f"Food/Culture: {food_culture_result['warning']}")
            
        # Step 7: Get accommodation
        print("Step 7: Finding accommodation options...")
        accommodation_result = accommodation_recommender_agent(state)
        if accommodation_result.get('warning'):
            warnings.append(f"Accommodation: {accommodation_result['warning']}")
            
        # Step 8: Calculate expense breakdown
        print("Step 8: Calculating expenses...")
        expense_result = expense_breakdown_agent(state)
        if expense_result.get('warning'):
            warnings.append(f"Expenses: {expense_result['warning']}")
            
        # Step 9: Generate comprehensive trip plan
        print("Step 9: Creating comprehensive trip plan...")
        complete_plan_result = complete_trip_plan_agent(state)
        if complete_plan_result.get('warning'):
            warnings.append(f"Complete Plan: {complete_plan_result['warning']}")
        
        # Refresh trip data
        trip = Trip.objects.get(id=state['trip_id'])
        
        print(f"Complete trip generation finished! Generated {len([r for r in [itinerary_result, activities_result, weather_result, packing_result, food_culture_result, accommodation_result, expense_result, complete_plan_result] if not r.get('warning')])} sections successfully.")
        
        return {
            "complete_generation": True,
            "itinerary": trip.itinerary,
            "activity_suggestions": trip.activity_suggestions,
            "useful_links": trip.useful_links,
            "weather_forecast": trip.weather_forecast,
            "packing_list": trip.packing_list,
            "food_culture_info": trip.food_culture_info,
            "accommodation_info": trip.accommodation_info,
            "expense_breakdown": trip.expense_breakdown,
            "complete_trip_plan": trip.complete_trip_plan,
            "warnings": warnings if warnings else None
        }
        
    except Exception as e:
        print(f"Error in complete trip generation: {str(e)}")
        return {
            "complete_generation": False,
            "warning": f"Failed to generate complete trip: {str(e)}"
        }

def chat_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    You are a helpful trip planning assistant. You can answer general questions about the trip and also modify the complete trip plan based on user requests.

    Current Trip Details:
    Destination: {trip.destination}
    Month: {trip.month}
    Duration: {trip.duration} days
    Number of People: {trip.num_people}
    Holiday Type: {trip.holiday_type}
    Budget Type: {trip.budget_type}

    Current Complete Trip Plan:
    {trip.complete_trip_plan if trip.complete_trip_plan else 'No complete trip plan generated yet.'}
    
    Current Itinerary:
    {trip.itinerary if trip.itinerary else 'No itinerary generated yet.'}

    User Question:
    {state['user_question']}

    Instructions:
    1. For MODIFICATION requests (like "change day 2 to include temples", "add more food options", "make it more budget-friendly"):
       - Output a JSON object: {{"updated_plan": "[ENTIRE UPDATED TRIP PLAN IN HTML]", "updated_itinerary": "[UPDATED ITINERARY IN HTML]"}}
       - Ensure both plans are comprehensive and include all details as previously generated
       - Keep the same structure and formatting as the original
       
    2. For GENERAL questions (like "what's the weather like", "tell me about the culture"):
       - Respond conversationally as plain text
       - Keep responses helpful and concise
       
    3. Do NOT attempt to modify trip details like destination, month, budget, etc.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        
        updated_plan_content = None
        updated_itinerary_content = None
        try:
            # Attempt to parse as JSON for modifications
            json_result = json.loads(result.strip())
            if "updated_plan" in json_result:
                updated_plan_content = json_result["updated_plan"]
            if "updated_itinerary" in json_result:
                updated_itinerary_content = json_result["updated_itinerary"]
        except json.JSONDecodeError:
            pass # Not a JSON response, treat as plain text

        if updated_plan_content or updated_itinerary_content:
            # Update trip plan and/or itinerary
            if updated_plan_content:
                trip.complete_trip_plan = convert_markdown_to_html(updated_plan_content)
            if updated_itinerary_content:
                trip.itinerary = convert_markdown_to_html(updated_itinerary_content)
            trip.save()
            
            chat_response_text = "✅ Your trip plan has been updated successfully! The changes are now reflected in your itinerary and complete plan sections."
        else:
            chat_response_text = result.strip()

        chat_message = ChatMessage.objects.create(
            trip=trip,
            question=state['user_question'],
            response=convert_markdown_to_html(chat_response_text)
        )
        return {"chat_response": convert_markdown_to_html(chat_response_text)}
    except Exception as e:
        return {"chat_response": "", "warning": str(e)}

def accommodation_recommender_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    query = f"Best hostels and stays in {trip.destination} for {trip.month} with {trip.budget_type} budget, including ratings and booking links"
    try:
        search_results = search.results(query)
        organic_results = search_results.get("organic", [])
        accommodations = []
        for result in organic_results[:5]: # Limit to top 5 results
            title = result.get("title", "No title")
            link = result.get("link", "")
            snippet = result.get("snippet", "")
            
            # Attempt to extract rating from snippet or title if available
            rating = "N/A"
            rating_match = re.search(r'(\d+\.?\d*)\s*out of\s*\d+', snippet)
            if not rating_match:
                rating_match = re.search(r'Rating:\s*(\d+\.?\d*)', snippet)
            if rating_match:
                rating = rating_match.group(1) + "/5" # Assuming 5-star scale

            # Get image from the result if available
            image_url = result.get("thumbnail", "")

            accommodations.append({
                "name": title,
                "link": link,
                "snippet": snippet,
                "rating": rating,
                "image_url": image_url,
                "video_url": ""
            })
        
        trip.accommodation_info = accommodations
        trip.save()
        return {"accommodation_info": accommodations}
    except Exception as e:
        return {"accommodation_info": [], "warning": f"Failed to fetch accommodation: {str(e)}"}


    except Exception as e:
        return {"accommodation_info": [], "warning": f"Failed to fetch accommodation: {str(e)}"}

def expense_breakdown_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    Based on the following trip details, itinerary, accommodation, food, and activity suggestions, provide a general expense breakdown.
    Assume average costs for {trip.destination} in {trip.month} for a {trip.budget_type} budget.
    
    Trip Details:
    Destination: {trip.destination}
    Month: {trip.month}
    Duration: {trip.duration} days
    Number of People: {trip.num_people}
    Holiday Type: {trip.holiday_type}
    Budget Type: {trip.budget_type}

    Itinerary: {trip.itinerary if trip.itinerary else 'Not available'}
    Accommodation Info: {trip.accommodation_info if trip.accommodation_info else 'Not available'}
    Food & Culture Info: {trip.food_culture_info if trip.food_culture_info else 'Not available'}
    Activity Suggestions: {trip.activity_suggestions if trip.activity_suggestions else 'Not available'}

    Provide the breakdown in a clear, structured format, including:
    - Estimated total cost.
    - Breakdown by categories: Accommodation, Food, Activities, Transportation (local), Miscellaneous.
    - Mention that these are estimates and actual costs may vary.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        trip.expense_breakdown = convert_markdown_to_html(result.strip())
        trip.save()
        return {"expense_breakdown": convert_markdown_to_html(result.strip())}
    except Exception as e:
        return {"expense_breakdown": "", "warning": str(e)}


    except Exception as e:
        return {"expense_breakdown": "", "warning": str(e)}

def complete_trip_plan_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    Synthesize all the following information into a comprehensive, single-page, day-by-day trip plan.
    For each day, detail the plan from morning to evening, including:
    - **Morning:** Start from your accommodation, suggest breakfast options (with links if available).
    - **Daytime Activities:** List specific activities with Google Maps links.
    - **Lunch/Dinner:** Suggest dining options (with links if available).
    - **Evening:** Suggest evening activities or return to accommodation.
    - **Accommodation:** Clearly state the recommended stay for that night (with booking links if available).

    Integrate weather forecasts and issue warnings if any dangerous weather is predicted for a specific day.
    Ensure the plan is balanced, considering activities, food, relaxation, and the overall budget type.
    Provide all relevant links (Google Maps for places, booking links for accommodation) directly within the plan. For activities, food options, and accommodation, also include image and video links if available, formatted as Markdown image `![Description](Image URL)` or video links `[Video Description](Video URL)`.

    Trip Details:
    Destination: {trip.destination}
    Month: {trip.month}
    Duration: {trip.duration} days
    Number of People: {trip.num_people}
    Holiday Type: {trip.holiday_type}
    Budget Type: {trip.budget_type}

    Itinerary: {trip.itinerary if trip.itinerary else 'Not available'}
    Accommodation Info: {trip.accommodation_info if trip.accommodation_info else 'Not available'}
    Food & Culture Info: {trip.food_culture_info if trip.food_culture_info else 'Not available'}
    Activity Suggestions: {trip.activity_suggestions if trip.activity_suggestions else 'Not available'}
    Expense Breakdown: {trip.expense_breakdown if trip.expense_breakdown else 'Not available'}

    Ensure the plan flows logically, is easy to read, and provides all necessary information for the user to follow.
    Additionally, enrich the plan with:
    - **Richer Descriptions:** Provide engaging and descriptive language for recommended places, activities, and food experiences.
    - **Local Insights & Tips:** Include small cultural notes, best times to visit, local customs, and hidden gems.
    - **Practical Advice:** Offer transportation tips, safety notes, currency advice, and essential phrases.
    - **Visual Appeal:** Utilize Markdown formatting (bolding, bullet points, headings) to make the plan easy to read and visually appealing.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        trip.complete_trip_plan = convert_markdown_to_html(result.strip())
        trip.save()
        return {"complete_trip_plan": convert_markdown_to_html(result.strip())}
    except Exception as e:
        return {"complete_trip_plan": "", "warning": str(e)}


# Define the graph
workflow = StateGraph(GraphState)
workflow.add_node("generate_itinerary", generate_itinerary)
workflow.add_node("accommodation_recommender", accommodation_recommender_agent)
workflow.add_node("expense_breakdown_node", expense_breakdown_agent)
workflow.add_node("complete_trip_plan_node", complete_trip_plan_agent)

workflow.set_entry_point("generate_itinerary")

workflow.add_edge("generate_itinerary", "accommodation_recommender")
workflow.add_edge("accommodation_recommender", "expense_breakdown_node")
workflow.add_edge("expense_breakdown_node", "complete_trip_plan_node")
workflow.add_edge("complete_trip_plan_node", END)

graph = workflow.compile()