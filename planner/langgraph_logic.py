from .models import Trip, ChatMessage, Checkpoint
from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import GoogleSerperAPIWrapper
import os
from .models import Trip, ChatMessage, Checkpoint
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
import asyncio
from asgiref.sync import sync_to_async
from .rag_logic import hyde_search_trips
import json
from .utils import convert_markdown_to_html
from langchain_core.tools import tool
# Initialize LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize GoogleSerperAPIWrapper
search = GoogleSerperAPIWrapper(serper_api_key=os.getenv("SERPER_API_KEY"))

class ActivitySuggestion(BaseModel):
    name: str
    link: str
    snippet: str
    image_url: str = ""
    video_url: str = ""

class UsefulLink(BaseModel):
    title: str
    link: str

class FoodOption(BaseModel):
    name: str
    link: str
    snippet: str
    image_url: str = ""
    video_url: str = ""

class FoodCultureInfo(BaseModel):
    food_options: list[FoodOption]
    cultural_info: str

class AccommodationOption(BaseModel):
    name: str
    link: str
    snippet: str
    rating: str = "N/A"
    image_url: str = ""
    video_url: str = ""

class Place(BaseModel):
    day: int
    places: list[str]

class PlaceList(BaseModel):
    days: list[Place]

class ItineraryActivity(BaseModel):
    time: str
    description: str
    location: Optional[str] = None
    tips: Optional[str] = None
    google_maps_link: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None

class ItineraryDay(BaseModel):
    day_number: int
    theme: str = None
    activities: list[ItineraryActivity]

class StructuredItinerary(BaseModel):
    days: list[ItineraryDay]

# Define state
class GraphState(TypedDict):
    trip_id: int
    preferences_text: str
    itinerary: str
    activity_suggestions: list[ActivitySuggestion]
    useful_links: list[UsefulLink]
    weather_forecast: dict
    packing_list: str
    food_culture_info: FoodCultureInfo
    accommodation_info: list[AccommodationOption]
    expense_breakdown: str
    complete_trip_plan: str
    
    chat_history: Annotated[list[dict], "List of question-response pairs"]
    user_question: str
    chat_response: str

# Agent functions
import time

async def generate_itinerary(state):
    print("--- generate_itinerary: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])

    # 1. Generate multiple search queries
    query_generation_prompt = f"""
    Based on the following user preferences for a trip, generate 3 diverse and specific search queries that would be useful for finding information to create a detailed itinerary.
    The queries should cover different aspects of the trip, such as activities, dining, and local culture.
    Return the queries as a JSON list of strings.

    User Preferences:
    - Destination: {trip.destination}
    - Month: {trip.month}
    - Duration: {trip.duration} days
    - People: {trip.num_people}
    - Type: {trip.holiday_type}
    - Budget: {trip.budget_type}
    - Comments: {trip.comments}

    Example Output:
    ["best restaurants in {trip.destination} for {trip.budget_type} budget", "unique cultural experiences in {trip.destination}", "day trips from {trip.destination}"]
    """
    try:
        print("--- generate_itinerary: Generating search queries... ---")
        query_generation_result = await sync_to_async(llm.invoke)([HumanMessage(content=query_generation_prompt)])
        json_string = query_generation_result.content.strip()
        # Extract JSON from markdown code block if present
        if json_string.startswith('```json') and json_string.endswith('```'):
            json_string = json_string[len('```json'):-len('```')].strip()
        elif json_string.startswith('```') and json_string.endswith('```'):
            json_string = json_string[len('```'):-len('```')].strip()
        queries = json.loads(json_string)
        print(f"--- generate_itinerary: Generated queries: {queries} ---")
    except Exception as e:
        print(f"--- generate_itinerary: Query generation failed: {e} ---")
        queries = [f"best things to do in {trip.destination} in {trip.month}"]

    # 2. Execute all queries and combine the results
    search_context = ""
    print("--- generate_itinerary: Executing search queries... ---")
    for query in queries:
        try:
            search_results = await sync_to_async(search.results)(query)
            search_context += "\n".join([r['snippet'] for r in search_results.get('organic', [])[:3]])
            search_context += "\n"
        except Exception as e:
            print(f"--- generate_itinerary: Serper API Error for query '{query}': {e} ---")
            search_context += f"Could not retrieve information for query: {query}\n"
    print(f"--- generate_itinerary: Combined search context:\n{search_context} ---")


    # 3. Build the prompt with the combined context
    prompt = f"""
    You are a world-class travel planner. Create a detailed, day-by-day itinerary in JSON format based on the user's preferences and the provided context.
    The itinerary should be comprehensive, covering activities, dining, and practical tips.

    User Preferences:
    - Destination: {trip.destination}
    - Month: {trip.month}
    - Duration: {trip.duration} days
    - People: {trip.num_people}
    - Type: {trip.holiday_type}
    - Budget: {trip.budget_type}
    - Comments: {trip.comments}

    Up-to-date Context from the Web:
    {search_context}

    For each day, include a theme and a list of activities. Each activity should have:
    - 'time': A time slot (e.g., "Morning", "9:00 AM - 12:00 PM", "Evening").
    - 'description': A detailed description of the activity.
    - 'location': (Optional) The specific location name (e.g., "Eiffel Tower").
    - 'tips': (Optional) Any useful tips for the activity.
    - 'google_maps_link': (Optional) A Google Maps URL for the location.
    - 'image_url': (Optional) A URL for an image related to the activity.
    - 'video_url': (Optional) A URL for a video related to the activity.

    Ensure the JSON output strictly conforms to the following Pydantic schema:
    ```json
    {{
        "days": [
            {{
                "day_number": 1,
                "theme": "Arrival and City Exploration",
                "activities": [
                    {{
                        "time": "Morning",
                        "description": "Arrive at {trip.destination} and check into your accommodation.",
                        "location": "Your Hotel",
                        "tips": "Pre-book airport transfer for convenience.",
                        "google_maps_link": "https://maps.google.com/?q=Your+Hotel",
                        "image_url": "https://example.com/hotel.jpg",
                        "video_url": null
                    }},
                    {{
                        "time": "Afternoon",
                        "description": "Explore the historic city center, visiting local markets and landmarks.",
                        "location": "City Center",
                        "tips": "Wear comfortable shoes.",
                        "google_maps_link": "https://maps.google.com/?q=City+Center",
                        "image_url": null,
                        "video_url": null
                    }}
                ]
            }},
            {{
                "day_number": 2,
                "theme": "Cultural Immersion",
                "activities": [
                    {{
                        "time": "Morning",
                        "description": "Visit a famous local landmark, such as the Grand Museum.",
                        "location": "Grand Museum",
                        "tips": "Arrive early to avoid crowds.",
                        "google_maps_link": "https://maps.google.com/?q=Grand+Museum",
                        "image_url": "https://example.com/grand_museum.jpg",
                        "video_url": null
                    }}
                ]
            }}
        ]
    }}
    ```
    Provide only the JSON output, no additional text or markdown outside the JSON block.
    """
    try:
        print("--- generate_itinerary: Generating itinerary with LLM... ---")
        llm_start_time = time.time()
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        llm_end_time = time.time()
        print(f"--- generate_itinerary: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")
        
        json_string = result.content.strip()
        # Extract JSON from markdown code block if present
        if json_string.startswith('```json') and json_string.endswith('```'):
            json_string = json_string[len('```json'):-len('```')].strip()
        elif json_string.startswith('```') and json_string.endswith('```'):
            json_string = json_string[len('```'):-len('```')].strip()

        print(f"--- generate_itinerary: Raw LLM output:\n{json_string} ---")
        parsed_itinerary = json.loads(json_string)
        validated_itinerary = StructuredItinerary(**parsed_itinerary)
        
        trip.itinerary = json.dumps(validated_itinerary.dict()) # Store as JSON string
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- generate_itinerary: END ({end_time - start_time:.2f} seconds) ---")
        return {"itinerary": trip.itinerary}
    except json.JSONDecodeError as e:
        print(f"--- generate_itinerary: JSON Decode Error: {e} ---")
        print(f"--- generate_itinerary: Raw LLM output: {json_string} ---")
        return {"itinerary": "", "warning": f"Failed to parse LLM output as JSON: {e}"}
    except Exception as e:
        print(f"--- generate_itinerary: ERROR ({time.time() - start_time:.2f} seconds) - {e} ---")
        import traceback
        print(traceback.format_exc())
        return {"itinerary": "", "warning": str(e)}

async def recommend_activities_agent(state):
    print("--- recommend_activities_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Unique local activities in {trip.destination} for {trip.month}"
    try:
        search_start_time = time.time()
        search_results = await sync_to_async(search.results)(query)
        search_end_time = time.time()
        print(f"--- recommend_activities_agent: Search call took {search_end_time - search_start_time:.2f} seconds ---")
        organic_results = search_results.get("organic", [])
        activities = []
        for result in organic_results[:5]:
            activities.append(ActivitySuggestion(
                name=result.get("title", "No title"),
                link=result.get("link", ""),
                snippet=result.get("snippet", ""),
                image_url=result.get("thumbnail", ""),
                video_url=""
            ))
        
        trip.activity_suggestions = [act.dict() for act in activities]
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- recommend_activities_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"activity_suggestions": trip.activity_suggestions}
    except Exception as e:
        end_time = time.time()
        print(f"--- recommend_activities_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"activity_suggestions": [], "warning": f"Failed to fetch activities: {str(e)}"}

async def fetch_useful_links_agent(state):
    print("--- fetch_useful_links_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Travel tips and guides for {trip.destination} in {trip.month}"
    try:
        search_start_time = time.time()
        search_results = await sync_to_async(search.results)(query)
        search_end_time = time.time()
        print(f"--- fetch_useful_links_agent: Search call took {search_end_time - search_start_time:.2f} seconds ---")
        organic_results = search_results.get("organic", [])
        links = [
            UsefulLink(title=result.get("title", "No title"), link=result.get("link", ""))
            for result in organic_results[:5]
        ]
        unique_links_data = set((link.title, link.link) for link in links)
        links = [UsefulLink(title=title, link=link) for title, link in unique_links_data]
        trip.useful_links = [link.dict() for link in links]
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- fetch_useful_links_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"useful_links": trip.useful_links}
    except Exception as e:
        end_time = time.time()
        print(f"--- fetch_useful_links_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"useful_links": [], "warning": f"Failed to fetch links: {str(e)}"}

async def weather_forecaster_agent(state):
    print("--- weather_forecaster_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Provide a weather forecast for {trip.destination} in {trip.month}.
    Include temperature, precipitation, and travel advice.
    Do not repeat any section headers or content.
    """
    try:
        llm_start_time = time.time()
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        llm_end_time = time.time()
        print(f"--- weather_forecaster_agent: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")
        trip.weather_forecast = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- weather_forecaster_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"weather_forecast": trip.weather_forecast}
    except Exception as e:
        end_time = time.time()
        print(f"--- weather_forecaster_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"weather_forecast": "", "warning": str(e)}

async def packing_list_generator_agent(state):
    print("--- packing_list_generator_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Generate a packing list for a {trip.holiday_type} trip to {trip.destination} in {trip.month} for {trip.duration} days.
    Use bullet points for each item.
    Base the list on the weather and trip type.
    Do not repeat any section headers or content.
    """
    try:
        llm_start_time = time.time()
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        llm_end_time = time.time()
        print(f"--- packing_list_generator_agent: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")
        trip.packing_list = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- packing_list_generator_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"packing_list": trip.packing_list}
    except Exception as e:
        end_time = time.time()
        print(f"--- packing_list_generator_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"packing_list": "", "warning": str(e)}

async def food_culture_recommender_agent(state):
    print("--- food_culture_recommender_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Popular local dishes and dining options in {trip.destination} for {trip.budget_type} budget"
    try:
        search_start_time = time.time()
        search_results = await sync_to_async(search.results)(query)
        search_end_time = time.time()
        print(f"--- food_culture_recommender_agent: Search call took {search_end_time - search_start_time:.2f} seconds ---")
        organic_results = search_results.get("organic", [])
        food_options = []
        for result in organic_results[:5]:
            food_options.append(FoodOption(
                name=result.get("title", "No title"),
                link=result.get("link", ""),
                snippet=result.get("snippet", ""),
                image_url=result.get("thumbnail", ""),
                video_url=""
            ))
        
        cultural_prompt = f"""
        Provide a list of important cultural norms and etiquette tips for a trip to {trip.destination}.
        Do not repeat any section headers or content.
        """
        llm_start_time = time.time()
        cultural_info_result = await sync_to_async(llm.invoke)([HumanMessage(content=cultural_prompt)])
        llm_end_time = time.time()
        print(f"--- food_culture_recommender_agent: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")
        cultural_info = convert_markdown_to_html(cultural_info_result.content.strip())

        food_culture_info = FoodCultureInfo(food_options=[fo.dict() for fo in food_options], cultural_info=cultural_info)
        trip.food_culture_info = food_culture_info.dict()
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- food_culture_recommender_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"food_culture_info": trip.food_culture_info}
    except Exception as e:
        end_time = time.time()
        print(f"--- food_culture_recommender_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"food_culture_info": {}, "warning": f"Failed to fetch food and culture: {str(e)}"}

async def generate_complete_trip_automatically(state):
    print(f"Starting complete trip generation for trip {state['trip_id']}")
    
    config = {"configurable": {"thread_id": str(state['trip_id'])}}
    
    try:
        final_state = await graph.ainvoke(state, config=config)
        print(f"Finished complete trip generation for trip {state['trip_id']}")
        return {
            "complete_generation": True,
            **final_state
        }
        
    except Exception as e:
        print(f"Error in complete trip generation: {str(e)}")
        return {"complete_generation": False, "warning": f"Failed to generate complete trip: {str(e)}"}

@tool
async def update_activities(instruction: str = None, trip_id: int = None) -> str:
    """
    Updates the activity suggestions for the current trip based on an instruction.
    Use this tool when the user asks to modify or get new activity suggestions.
    The instruction should describe the type of activities the user is looking for.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await recommend_activities_agent(state)
    if result.get("warning"): return f"Failed to update activities: {result['warning']}"
    return "Activity suggestions updated successfully."

@tool
async def update_useful_links(instruction: str = None, trip_id: int = None) -> str:
    """
    Fetches and updates useful links for the current trip based on an instruction.
    Use this tool when the user asks for more useful links or specific types of links.
    The instruction should describe the type of links the user is looking for.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await fetch_useful_links_agent(state)
    if result.get("warning"): return f"Failed to update useful links: {result['warning']}"
    return "Useful links updated successfully."

@tool
async def update_weather_forecast(instruction: str = None, trip_id: int = None) -> str:
    """
    Fetches and updates the weather forecast for the current trip based on an instruction.
    Use this tool when the user asks for updated weather information or a more detailed forecast.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await weather_forecaster_agent(state)
    if result.get("warning"): return f"Failed to update weather forecast: {result['warning']}"
    return "Weather forecast updated successfully."

@tool
async def update_packing_list(instruction: str = None, trip_id: int = None) -> str:
    """
    Generates and updates the packing list for the current trip based on an instruction.
    Use this tool when the user asks to modify or get a new packing list.
    The instruction should describe any specific requirements for the packing list.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await packing_list_generator_agent(state)
    if result.get("warning"): return f"Failed to update packing list: {result['warning']}"
    return "Packing list updated successfully."

@tool
async def update_food_culture_info(instruction: str = None, trip_id: int = None) -> str:
    """
    Fetches and updates food and culture information for the current trip based on an instruction.
    Use this tool when the user asks for more food options, cultural tips, or specific dietary information.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await food_culture_recommender_agent(state)
    if result.get("warning"): return f"Failed to update food and culture information: {result['warning']}"
    return "Food and culture information updated successfully."

@tool
async def update_accommodation_info(instruction: str = None, trip_id: int = None) -> str:
    """
    Fetches and updates accommodation recommendations for the current trip based on an instruction.
    Use this tool when the user asks for different types of accommodation or specific booking information.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await accommodation_recommender_agent(state)
    if result.get("warning"): return f"Failed to update accommodation information: {result['warning']}"
    return "Accommodation information updated successfully."

@tool
async def update_expense_breakdown(instruction: str = None, trip_id: int = None) -> str:
    """
    Generates and updates the expense breakdown for the current trip based on an instruction.
    Use this tool when the user asks for a revised expense breakdown or a breakdown for a specific budget.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await expense_breakdown_agent(state)
    if result.get("warning"): return f"Failed to update expense breakdown: {result['warning']}"
    return "Expense breakdown updated successfully."

@tool
async def update_complete_trip_plan(instruction: str = None, trip_id: int = None) -> str:
    """
    Generates and updates the complete trip plan for the current trip based on an instruction.
    This tool should be used when the user asks for a comprehensive regeneration or significant modification of the entire trip plan.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await complete_trip_plan_agent(state)
    if result.get("warning"): return f"Failed to update complete trip plan: {result['warning']}"
    return "Complete trip plan updated successfully."

@tool
async def generate_full_trip_plan(instruction: str = None, trip_id: int = None) -> str:
    """
    Generates a complete trip plan from scratch for the current trip, including itinerary, activities, and all other details.
    Use this tool when the user asks to generate a new trip plan or to start over.
    The trip ID is handled automatically. Do not ask the user for it.
    """
    if not trip_id:
        return "Error: trip_id was not provided to the tool."
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await generate_complete_trip_automatically(state)
    if result.get("warning"):
        return f"Failed to generate full trip plan: {result['warning']}"
    return "Full trip plan generated successfully."

tools = [
    update_activities, update_useful_links, update_weather_forecast, update_packing_list,
    update_food_culture_info, update_accommodation_info, update_expense_breakdown, update_complete_trip_plan,
    generate_full_trip_plan,
]

llm_with_tools = llm.bind_tools(tools)

async def chat_agent(state):
    print("--- chat_agent: START ---")
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    user_question = state['user_question']
    chat_history = state.get('chat_history', [])
    print(f"--- chat_agent: User question: {user_question} ---")

    # RAG with HyDE: Search for relevant trip plans
    print("--- chat_agent: Starting RAG with HyDE search... ---")
    user_id = await sync_to_async(lambda: trip.user.id)()
    retrieved_docs = await hyde_search_trips(user_question, user_id=user_id)
    context = "\n".join(retrieved_docs)
    print(f"--- chat_agent: Retrieved context:\n{context} ---")


    # Build the prompt with context
    prompt_with_context = f"""
    You are a helpful travel assistant. Use the following context to answer the user's question.
    If the context doesn't contain the answer, say that you don't have enough information.

    Context:
    {context}

    Conversation History:
    """
    
    messages = []
    for msg in chat_history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            messages.append(AIMessage(content=msg['content']))

    # Add the system prompt with context to the beginning of the messages
    messages.insert(0, HumanMessage(content=prompt_with_context))
            
    messages.append(HumanMessage(content=user_question))

    print("--- chat_agent: Calling LLM with tools... ---")
    response = await sync_to_async(llm_with_tools.invoke)(messages)

    if response.tool_calls:
        print(f"--- chat_agent: LLM decided to use tools: {response.tool_calls} ---")
        tool_outputs = []
        for tool_call in response.tool_calls:
            selected_tool = next((t for t in tools if t.name == tool_call.name), None)
            if selected_tool:
                try:
                    tool_args = tool_call.args
                    tool_args['trip_id'] = trip.id
                    print(f"--- chat_agent: Executing tool '{tool_call.name}' with args: {tool_args} ---")
                    tool_output = await selected_tool.invoke(tool_args)
                    print(f"--- chat_agent: Tool '{tool_call.name}' output: {tool_output} ---")
                    tool_outputs.append(f"Tool {tool_call.name} executed: {tool_output}")
                except Exception as e:
                    print(f"--- chat_agent: Error executing tool {tool_call.name}: {str(e)} ---")
                    tool_outputs.append(f"Error executing tool {tool_call.name}: {str(e)}")
            else:
                print(f"--- chat_agent: Tool {tool_call.name} not found. ---")
                tool_outputs.append(f"Tool {tool_call.name} not found.")
        
        messages.append(response)
        messages.append(AIMessage(content=str(tool_outputs)))
        print("--- chat_agent: Calling LLM again with tool results... ---")
        final_response = await sync_to_async(llm.invoke)(messages)
        chat_response_text = final_response.content
    else:
        print("--- chat_agent: LLM answered directly. ---")
        chat_response_text = response.content

    print(f"--- chat_agent: Final response:\n{chat_response_text} ---")
    chat_message = await sync_to_async(ChatMessage.objects.create)(
        trip=trip, question=user_question, response=convert_markdown_to_html(chat_response_text)
    )
    print("--- chat_agent: END ---")
    return {"chat_response": convert_markdown_to_html(chat_response_text)}

async def accommodation_recommender_agent(state):
    print("--- accommodation_recommender_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Best hostels and stays in {trip.destination} for {trip.month} with {trip.budget_type} budget, including ratings and booking links"
    try:
        search_start_time = time.time()
        search_results = await sync_to_async(search.results)(query)
        search_end_time = time.time()
        print(f"--- accommodation_recommender_agent: Search call took {search_end_time - search_start_time:.2f} seconds ---")
        organic_results = search_results.get("organic", [])
        accommodations = []
        for result in organic_results[:5]:
            rating = "N/A"
            rating_match = re.search(r'(\d+\.?\d*)\s*out of\s*\d+', result.get("snippet", ""))
            if not rating_match: rating_match = re.search(r'Rating:\s*(\d+\.?\d*)', result.get("snippet", ""))
            if rating_match: rating = rating_match.group(1) + "/5"

            accommodations.append(AccommodationOption(
                name=result.get("title", "No title"), link=result.get("link", ""),
                snippet=result.get("snippet", ""), rating=rating,
                image_url=result.get("thumbnail", ""), video_url=""
            ))
        
        trip.accommodation_info = [acc.dict() for acc in accommodations]
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- accommodation_recommender_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"accommodation_info": trip.accommodation_info}
    except Exception as e:
        end_time = time.time()
        print(f"--- accommodation_recommender_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"accommodation_info": [], "warning": f"Failed to fetch accommodation: {str(e)}"}

async def expense_breakdown_agent(state):
    print("--- expense_breakdown_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Based on the following trip details, provide a general expense breakdown.
    Assume average costs for {trip.destination} in {trip.month} for a {trip.budget_type} budget.
    Consider categories like:
    - Accommodation
    - Flights/Transportation
    - Food & Dining
    - Activities & Sightseeing
    - Miscellaneous (shopping, emergencies)

    Provide a breakdown per person and total for {trip.num_people} people.
    Use a clear, readable format, preferably markdown tables or bullet points.
    Do not repeat any section headers or content.
    """
    try:
        llm_start_time = time.time()
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        llm_end_time = time.time()
        print(f"--- expense_breakdown_agent: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")

        result_content = ""
        if isinstance(result.content, list):
            for part in result.content:
                if isinstance(part, dict) and 'text' in part:
                    result_content += part['text']
                elif isinstance(part, str):
                    result_content += part
        else:
            result_content = result.content

        trip.expense_breakdown = convert_markdown_to_html(result_content.strip())
        await sync_to_async(trip.save)()
        end_time = time.time()
        print(f"--- expense_breakdown_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"expense_breakdown": trip.expense_breakdown}
    except Exception as e:
        end_time = time.time()
        print(f"--- expense_breakdown_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        return {"expense_breakdown": "", "warning": str(e)}

async def complete_trip_plan_agent(state):
    print("--- complete_trip_plan_agent: START ---")
    start_time = time.time()
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Create a day-by-day trip plan based on the following details.

    **Trip Details:**
    - Destination: {trip.destination}
    - Month: {trip.month}
    - Duration: {trip.duration} days
    - People: {trip.num_people}
    - Holiday Type: {trip.holiday_type}
    - Budget: {trip.budget_type}



    **Instructions:**
    For each day, provide a schedule from morning to evening.
    Include the following for each day:
    - Morning, Daytime, and Evening activities.
    - Lunch and Dinner suggestions.
    - Recommended accommodation for the night.
    - Mention weather warnings if applicable.
    - Add local tips and practical advice.
    - For EVERY specific place to visit (like a temple, museum, palace, park, zoo, dam, fort, etc.), you MUST enclose its name in <place> tags. For example: <place>Gwalior Fort</place>, <place>Gwalior Zoo</place>, <place>Tighra Dam</place>. Do NOT tag restaurants, hotels, or general activities as places.
    """
    print(f"--- complete_trip_plan_agent: Starting for trip_id={{trip.id}} ---")
    try:
        llm_start_time = time.time()
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        llm_end_time = time.time()
        print(f"--- complete_trip_plan_agent: LLM call took {llm_end_time - llm_start_time:.2f} seconds ---")
        
        result_content = ""
        if isinstance(result.content, list):
            for part in result.content:
                if isinstance(part, dict) and 'text' in part:
                    result_content += part['text']
                elif isinstance(part, str):
                    result_content += part
        else:
            result_content = result.content

        result_content = result_content.strip()
        print(f"--- complete_trip_plan_agent: Raw LLM output ---\n{{result_content}}\n--- End Raw LLM output ---")

        if not result_content:
            print("--- complete_trip_plan_agent: LLM output is empty. Returning warning. ---")
            return {"complete_trip_plan": "", "warning": "LLM returned an empty plan."}

        end_time = time.time()
        print(f"--- complete_trip_plan_agent: END ({end_time - start_time:.2f} seconds) ---")
        return {"complete_trip_plan": result_content}
    except Exception as e:
        end_time = time.time()
        print(f"--- complete_trip_plan_agent: ERROR ({end_time - start_time:.2f} seconds) - {e} ---")
        import traceback
        print(traceback.format_exc())
        return {"complete_trip_plan": "", "warning": str(e)}


async def extract_places_agent(state):
    print("--- extract_places_agent: START ---")
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    
    itinerary_json = trip.itinerary
    if not itinerary_json:
        print("--- extract_places_agent: No itinerary found in trip. Skipping. ---")
        return {"trip_id": state['trip_id']}

    try:
        itinerary_data = json.loads(itinerary_json)
        validated_itinerary = StructuredItinerary(**itinerary_data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"--- extract_places_agent: Error parsing or validating itinerary JSON: {e} ---")
        return {"warning": f"Failed to process itinerary data: {e}", "trip_id": state['trip_id']}

    await sync_to_async(Checkpoint.objects.filter(trip=trip).delete)()

    for day in validated_itinerary.days:
        activity_order = 1
        for activity in day.activities:
            # Basic filtering to avoid creating checkpoints for generic activities
            if "arrive" in activity.description.lower() or "depart" in activity.description.lower() or "check into" in activity.description.lower():
                continue

            await sync_to_async(Checkpoint.objects.create)(
                trip=trip,
                name=activity.location or activity.description[:100],
                description=activity.description,
                day_number=day.day_number,
                order_in_day=activity_order,
                time=None,  # The ItineraryActivity.time is a string like "Morning", not a TimeField
                location=activity.location,
                tips=activity.tips,
                image_url=activity.image_url,
                video_url=activity.video_url,
            )
            activity_order += 1
    
    print("--- extract_places_agent: END ---")
    return {"trip_id": state['trip_id']}


# Define the graph
workflow = StateGraph(GraphState)
workflow.add_node("generate_itinerary", generate_itinerary)
workflow.add_node("recommend_activities", recommend_activities_agent)
workflow.add_node("fetch_useful_links", fetch_useful_links_agent)
workflow.add_node("weather_forecaster", weather_forecaster_agent)
workflow.add_node("packing_list_generator", packing_list_generator_agent)
workflow.add_node("food_culture_recommender", food_culture_recommender_agent)
workflow.add_node("accommodation_recommender", accommodation_recommender_agent)
workflow.add_node("expense_breakdown_node", expense_breakdown_agent)

def join_node(state):
    # This node doesn't need to do anything, it just serves as a join point
    # for the parallel branches.
    return {"user_question": ""}

workflow.add_node("join_node", join_node)
workflow.add_node("generate_complete_trip_plan", complete_trip_plan_agent)
workflow.add_node("extract_places", extract_places_agent)


workflow.set_entry_point("generate_itinerary")

workflow.add_edge("generate_itinerary", "recommend_activities")
workflow.add_edge("generate_itinerary", "fetch_useful_links")
workflow.add_edge("generate_itinerary", "weather_forecaster")
workflow.add_edge("generate_itinerary", "packing_list_generator")
workflow.add_edge("generate_itinerary", "food_culture_recommender")
workflow.add_edge("generate_itinerary", "accommodation_recommender")

workflow.add_edge("recommend_activities", "join_node")
workflow.add_edge("fetch_useful_links", "join_node")
workflow.add_edge("weather_forecaster", "join_node")
workflow.add_edge("packing_list_generator", "join_node")
workflow.add_edge("food_culture_recommender", "join_node")
workflow.add_edge("accommodation_recommender", "join_node")

workflow.add_edge("join_node", "generate_complete_trip_plan")
workflow.add_edge("generate_complete_trip_plan", "extract_places")
workflow.add_edge("extract_places", "expense_breakdown_node")
workflow.add_edge("expense_breakdown_node", END)


from langgraph.checkpoint.memory import MemorySaver

graph = workflow.compile(checkpointer=MemorySaver())
