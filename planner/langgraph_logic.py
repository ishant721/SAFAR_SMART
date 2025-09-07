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
try:
    if os.getenv("GOOGLE_API_KEY"):
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))
    else:
        llm = None
except Exception:
    llm = None

# Initialize GoogleSerperAPIWrapper
try:
    if os.getenv("SERPER_API_KEY"):
        search = GoogleSerperAPIWrapper(serper_api_key=os.getenv("SERPER_API_KEY"))
    else:
        search = None
except Exception:
    search = None

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

def chat_agent(state):
    trip = Trip.objects.get(id=state['trip_id'])
    prompt = f"""
    You are a helpful trip planning assistant. You can answer general questions about the trip and also modify *only* the complete trip plan based on user requests.

    Current Trip Details:
    Destination: {trip.destination}
    Month: {trip.month}
    Duration: {trip.duration} days
    Number of People: {trip.num_people}
    Holiday Type: {trip.holiday_type}
    Budget Type: {trip.budget_type}

    Current Complete Trip Plan:
    {trip.complete_trip_plan if trip.complete_trip_plan else 'No complete trip plan generated yet.'}

    User Question:
    {state['user_question']}

    If the user asks to modify the trip plan, output a JSON object in the format: {{"updated_plan": "[THE ENTIRE UPDATED TRIP PLAN IN MARKDOWN]"}}. 
    Ensure the updated plan is comprehensive and includes all details as previously generated (day-by-day, activities, food, accommodation, links, weather warnings, etc.).
    If the user asks a general question, respond conversationally as a plain text string. Keep responses concise. Do NOT attempt to modify any other trip details (like destination, month, budget, etc.) besides the complete trip plan.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)]).content
        
        updated_plan_content = None
        try:
            # Attempt to parse as JSON
            json_result = json.loads(result.strip())
            if "updated_plan" in json_result:
                updated_plan_content = json_result["updated_plan"]
        except json.JSONDecodeError:
            pass # Not a JSON response, treat as plain text

        if updated_plan_content:
            trip.complete_trip_plan = convert_markdown_to_html(updated_plan_content)
            trip.save()
            chat_response_text = "Your trip plan has been updated. Here is the new plan: " + updated_plan_content
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



    except Exception as e:
        return {"food_culture_info": "", "warning": str(e)}

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