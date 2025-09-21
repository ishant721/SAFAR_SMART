from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from dotenv import load_dotenv
import os
from .models import Trip, ChatMessage, Checkpoint
import json
from .utils import convert_markdown_to_html
import re
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
import asyncio
from asgiref.sync import sync_to_async

# Load environment variables
load_dotenv()

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
    
    chat_history: Annotated[list[dict], "List of question-response pairs"]
    user_question: str
    chat_response: str

# Agent functions
async def generate_itinerary(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    preferences_text = f"Destination: {trip.destination}\nMonth: {trip.month}\nDuration: {trip.duration} days\nPeople: {trip.num_people}\nType: {trip.holiday_type}\nBudget: {trip.budget_type}\nComments: {trip.comments}"
    prompt = f"""
    Using the following preferences, create a detailed itinerary:
    {preferences_text}

    Include sections for each day, dining options, and downtime.
    """
    try:
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        trip.itinerary = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        return {"itinerary": trip.itinerary}
    except Exception as e:
        return {"itinerary": "", "warning": str(e)}

async def recommend_activities_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Unique local activities in {trip.destination} for {trip.month}"
    try:
        search_results = await sync_to_async(search.results)(query)
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
        return {"activity_suggestions": trip.activity_suggestions}
    except Exception as e:
        return {"activity_suggestions": [], "warning": f"Failed to fetch activities: {str(e)}"}

async def fetch_useful_links_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Travel tips and guides for {trip.destination} in {trip.month}"
    try:
        search_results = await sync_to_async(search.results)(query)
        organic_results = search_results.get("organic", [])
        links = [
            UsefulLink(title=result.get("title", "No title"), link=result.get("link", ""))
            for result in organic_results[:5]
        ]
        unique_links_data = set((link.title, link.link) for link in links)
        links = [UsefulLink(title=title, link=link) for title, link in unique_links_data]
        trip.useful_links = [link.dict() for link in links]
        await sync_to_async(trip.save)()
        return {"useful_links": trip.useful_links}
    except Exception as e:
        return {"useful_links": [], "warning": f"Failed to fetch links: {str(e)}"}

async def weather_forecaster_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Based on the destination and month, provide a detailed weather forecast including temperature, precipitation, and advice for travelers:
    Destination: {trip.destination}
    Month: {trip.month}
    """
    try:
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        trip.weather_forecast = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        return {"weather_forecast": trip.weather_forecast}
    except Exception as e:
        return {"weather_forecast": "", "warning": str(e)}

async def packing_list_generator_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Generate a comprehensive packing list for a {trip.holiday_type} holiday in {trip.destination} during {trip.month} for {trip.duration} days.
    Include essentials based on expected weather and trip type.
    """
    try:
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        trip.packing_list = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        return {"packing_list": trip.packing_list}
    except Exception as e:
        return {"packing_list": "", "warning": str(e)}

async def food_culture_recommender_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Popular local dishes and dining options in {trip.destination} for {trip.budget_type} budget"
    try:
        search_results = await sync_to_async(search.results)(query)
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
        For a trip to {trip.destination}, provide important cultural norms, etiquette tips, and things travelers should be aware of.
        Format the response with clear sections for 'Culture & Etiquette'.
        """
        cultural_info_result = await sync_to_async(llm.invoke)([HumanMessage(content=cultural_prompt)])
        cultural_info = convert_markdown_to_html(cultural_info_result.content.strip())

        food_culture_info = FoodCultureInfo(food_options=[fo.dict() for fo in food_options], cultural_info=cultural_info)
        trip.food_culture_info = food_culture_info.dict()
        await sync_to_async(trip.save)()
        return {"food_culture_info": trip.food_culture_info}
    except Exception as e:
        return {"food_culture_info": {}, "warning": f"Failed to fetch food and culture: {str(e)}"}

async def generate_complete_trip_automatically(state):
    print(f"Starting complete trip generation for trip {state['trip_id']}")
    warnings = []
    
    try:
        itinerary_result = await generate_itinerary(state)
        if itinerary_result.get('warning'): warnings.append(f"Itinerary: {itinerary_result['warning']}")
        
        activities_result = await recommend_activities_agent(state)
        if activities_result.get('warning'): warnings.append(f"Activities: {activities_result['warning']}")
        
        links_result = await fetch_useful_links_agent(state)
        if links_result.get('warning'): warnings.append(f"Links: {links_result['warning']}")
            
        weather_result = await weather_forecaster_agent(state)
        if weather_result.get('warning'): warnings.append(f"Weather: {weather_result['warning']}")
            
        packing_result = await packing_list_generator_agent(state)
        if packing_result.get('warning'): warnings.append(f"Packing: {packing_result['warning']}")
            
        food_culture_result = await food_culture_recommender_agent(state)
        if food_culture_result.get('warning'): warnings.append(f"Food/Culture: {food_culture_result['warning']}")
            
        accommodation_result = await accommodation_recommender_agent(state)
        if accommodation_result.get('warning'): warnings.append(f"Accommodation: {accommodation_result['warning']}")
            
        expense_result = await expense_breakdown_agent(state)
        if expense_result.get('warning'): warnings.append(f"Expenses: {expense_result['warning']}")
            
        complete_plan_result = await complete_trip_plan_agent(state)
        if complete_plan_result.get('warning'): warnings.append(f"Complete Plan: {complete_plan_result['warning']}")
        
        trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
        
        return {
            "complete_generation": True, "itinerary": trip.itinerary,
            "activity_suggestions": trip.activity_suggestions, "useful_links": trip.useful_links,
            "weather_forecast": trip.weather_forecast, "packing_list": trip.packing_list,
            "food_culture_info": trip.food_culture_info, "accommodation_info": trip.accommodation_info,
            "expense_breakdown": trip.expense_breakdown,
            "warnings": warnings if warnings else None
        }
        
    except Exception as e:
        print(f"Error in complete trip generation: {str(e)}")
        return {"complete_generation": False, "warning": f"Failed to generate complete trip: {str(e)}"}

@tool
async def update_activities(trip_id: int, instruction: str = None) -> str:
    """
    Updates the activity suggestions for a trip based on the provided instruction.
    Use this tool when the user asks to modify or get new activity suggestions.
    The instruction should describe the type of activities the user is looking for.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await recommend_activities_agent(state)
    if result.get("warning"): return f"Failed to update activities: {result['warning']}"
    return "Activity suggestions updated successfully."

@tool
async def update_useful_links(trip_id: int, instruction: str = None) -> str:
    """
    Fetches and updates useful links for a trip based on the provided instruction.
    Use this tool when the user asks for more useful links or specific types of links.
    The instruction should describe the type of links the user is looking for.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await fetch_useful_links_agent(state)
    if result.get("warning"): return f"Failed to update useful links: {result['warning']}"
    return "Useful links updated successfully."

@tool
async def update_weather_forecast(trip_id: int, instruction: str = None) -> str:
    """
    Fetches and updates the weather forecast for a trip based on the provided instruction.
    Use this tool when the user asks for updated weather information or a more detailed forecast.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await weather_forecaster_agent(state)
    if result.get("warning"): return f"Failed to update weather forecast: {result['warning']}"
    return "Weather forecast updated successfully."

@tool
async def update_packing_list(trip_id: int, instruction: str = None) -> str:
    """
    Generates and updates the packing list for a trip based on the provided instruction.
    Use this tool when the user asks to modify or get a new packing list.
    The instruction should describe any specific requirements for the packing list.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await packing_list_generator_agent(state)
    if result.get("warning"): return f"Failed to update packing list: {result['warning']}"
    return "Packing list updated successfully."

@tool
async def update_food_culture_info(trip_id: int, instruction: str = None) -> str:
    """
    Fetches and updates food and culture information for a trip based on the provided instruction.
    Use this tool when the user asks for more food options, cultural tips, or specific dietary information.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await food_culture_recommender_agent(state)
    if result.get("warning"): return f"Failed to update food and culture information: {result['warning']}"
    return "Food and culture information updated successfully."

@tool
async def update_accommodation_info(trip_id: int, instruction: str = None) -> str:
    """
    Fetches and updates accommodation recommendations for a trip based on the provided instruction.
    Use this tool when the user asks for different types of accommodation or specific booking information.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await accommodation_recommender_agent(state)
    if result.get("warning"): return f"Failed to update accommodation information: {result['warning']}"
    return "Accommodation information updated successfully."

@tool
async def update_expense_breakdown(trip_id: int, instruction: str = None) -> str:
    """
    Generates and updates the expense breakdown for a trip based on the provided instruction.
    Use this tool when the user asks for a revised expense breakdown or a breakdown for a specific budget.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await expense_breakdown_agent(state)
    if result.get("warning"): return f"Failed to update expense breakdown: {result['warning']}"
    return "Expense breakdown updated successfully."

@tool
async def update_complete_trip_plan(trip_id: int, instruction: str = None) -> str:
    """
    Generates and updates the complete trip plan based on the provided instruction.
    This tool should be used when the user asks for a comprehensive regeneration or significant modification of the entire trip plan.
    """
    state = {"trip_id": trip_id, "user_question": instruction or ""}
    result = await complete_trip_plan_agent(state)
    if result.get("warning"): return f"Failed to update complete trip plan: {result['warning']}"
    return "Complete trip plan updated successfully."

tools = [
    update_activities, update_useful_links, update_weather_forecast, update_packing_list,
    update_food_culture_info, update_accommodation_info, update_expense_breakdown, update_complete_trip_plan,
]

llm_with_tools = llm.bind_tools(tools)

async def chat_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    user_question = state['user_question']

    messages = [HumanMessage(content=user_question)]

    response = await sync_to_async(llm_with_tools.invoke)(messages)

    if response.tool_calls:
        tool_outputs = []
        for tool_call in response.tool_calls:
            selected_tool = next((t for t in tools if t.name == tool_call.name), None)
            if selected_tool:
                try:
                    tool_args = tool_call.args
                    tool_args['trip_id'] = trip.id
                    tool_output = await selected_tool.invoke(tool_args)
                    tool_outputs.append(f"Tool {tool_call.name} executed: {tool_output}")
                except Exception as e:
                    tool_outputs.append(f"Error executing tool {tool_call.name}: {str(e)}")
            else:
                tool_outputs.append(f"Tool {tool_call.name} not found.")
        
        messages.append(response)
        messages.append(AIMessage(content=str(tool_outputs)))
        final_response = await sync_to_async(llm.invoke)(messages)
        chat_response_text = final_response.content
    else:
        chat_response_text = response.content

    chat_message = await sync_to_async(ChatMessage.objects.create)(
        trip=trip, question=user_question, response=convert_markdown_to_html(chat_response_text)
    )
    return {"chat_response": convert_markdown_to_html(chat_response_text)}

async def accommodation_recommender_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    query = f"Best hostels and stays in {trip.destination} for {trip.month} with {trip.budget_type} budget, including ratings and booking links"
    try:
        search_results = await sync_to_async(search.results)(query)
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
        return {"accommodation_info": trip.accommodation_info}
    except Exception as e:
        return {"accommodation_info": [], "warning": f"Failed to fetch accommodation: {str(e)}"}

async def expense_breakdown_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Based on the following trip details, provide a general expense breakdown.
    Assume average costs for {trip.destination} in {trip.month} for a {trip.budget_type} budget.
    ... (rest of the prompt)
    """
    try:
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        trip.expense_breakdown = convert_markdown_to_html(result.content.strip())
        await sync_to_async(trip.save)()
        return {"expense_breakdown": trip.expense_breakdown}
    except Exception as e:
        return {"expense_breakdown": "", "warning": str(e)}

async def complete_trip_plan_agent(state):
    trip = await sync_to_async(Trip.objects.get)(id=state['trip_id'])
    prompt = f"""
    Synthesize all the following information into a comprehensive, single-page, day-by-day trip plan.
    For each day, detail the plan from morning to evening, including:
    - **Morning:** Start from your accommodation, suggest breakfast options (with links if available).
    - **Daytime Activities:** List specific activities with Google Maps links. Each activity should be a separate bullet point, starting with the activity name in bold, followed by a brief description and a Google Maps link if available. Example: - **Eiffel Tower:** Iconic landmark in Paris. [Google Maps](https://maps.app.goo.gl/example)
    - **Lunch/Dinner:** Suggest dining options (with links if available).
    - **Evening:** Suggest evening activities or return to accommodation.
    - **Accommodation:** Clearly state the recommended stay for that night (with booking links if available).

    Integrate weather forecasts and issue warnings if any dangerous weather is predicted for a specific day.
    Ensure the plan is balanced, considering activities, food, relaxation, and the overall budget type.
    Provide all relevant links (Google Maps for places, booking links for accommodation) directly within the plan. For activities, food options, and accommodation, also include image and video links if available, formatted as Markdown image `![Description](Image URL)` or video links `[Video URL]`.

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
    print(f"--- complete_trip_plan_agent: Starting for trip_id={{trip.id}} ---")
    try:
        result = await sync_to_async(llm.invoke)([HumanMessage(content=prompt)])
        result_content = result.content.strip()
        print(f"--- complete_trip_plan_agent: Raw LLM output ---\n{{result_content}}\n--- End Raw LLM output ---")
        
        await sync_to_async(Checkpoint.objects.filter(trip=trip).delete)()
        print(f"--- complete_trip_plan_agent: Cleared existing checkpoints for trip_id={{trip.id}} ---")

        day_patterns = re.findall(r'(## Day \d+:.*?)(?=## Day \d+:|\Z)', result_content, re.DOTALL)
        print(f"--- complete_trip_plan_agent: Day patterns found: {{len(day_patterns)}} ---")
        if not day_patterns:
            print("--- complete_trip_plan_agent: No day patterns found. Creating single fallback checkpoint. ---")
            await sync_to_async(Checkpoint.objects.create)(
                trip=trip, name=f"Trip to {trip.destination}", description=result_content
            )
            print(f"--- complete_trip_plan_agent: Created fallback checkpoint: Trip to {trip.destination} ---")
        else:
            for day_plan in day_patterns:
                day_match = re.match(r'## (Day \d+:.*?)\n', day_plan)
                day_name = day_match.group(1).strip() if day_match else "Unknown Day"
                print(f"--- complete_trip_plan_agent: Processing day: {{day_name}} ---")
                
                sections = re.split(r'\n- \*\*(Morning|Daytime Activities|Lunch/Dinner|Evening|Accommodation):\*\*', day_plan)
                print(f"--- complete_trip_plan_agent: Sections found for {{day_name}}: {{len(sections) // 2}} ---")
                
                for i in range(1, len(sections), 2):
                    section_name = sections[i].strip()
                    section_content = sections[i+1].strip() if (i+1) < len(sections) else ""
                    
                    print(f"--- complete_trip_plan_agent: Processing section: {{section_name}} for {{day_name}} ---")
                    if section_name == "Daytime Activities":
                        activity_patterns = re.findall(r'- \*\*(.*?):\*\*(.*?)(?=\n- \*\*|\Z)', section_content, re.DOTALL)
                        print(f"--- complete_trip_plan_agent: Activities found in '{{section_name}}': {{len(activity_patterns)}} ---")
                        if activity_patterns:
                            for activity_name, activity_description in activity_patterns:
                                if activity_description.strip():
                                    await sync_to_async(Checkpoint.objects.create)(
                                        trip=trip, name=f"{day_name} - {activity_name.strip()}",
                                        description=activity_description.strip()
                                    )
                                    print(f"--- complete_trip_plan_agent: Created granular checkpoint: {day_name} - {activity_name.strip()} ---")
                        elif section_content:
                            await sync_to_async(Checkpoint.objects.create)(
                                trip=trip, name=f"{day_name} - {section_name}", description=section_content
                            )
                            print(f"--- complete_trip_plan_agent: Created general checkpoint for '{{section_name}}': {day_name} ---")
                    elif section_content:
                        await sync_to_async(Checkpoint.objects.create)(
                            trip=trip, name=f"{day_name} - {section_name}", description=section_content
                        )
                        print(f"--- complete_trip_plan_agent: Created section checkpoint: {day_name} - {section_name} ---")

        return {"status": "checkpoints_generated"}
    except Exception as e:
        print(f"--- complete_trip_plan_agent: An error occurred: {e} ---")
        import traceback
        print(traceback.format_exc())
        return {"complete_trip_plan": "", "warning": str(e)}


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

workflow.set_entry_point("generate_itinerary")

workflow.add_edge("generate_itinerary", "recommend_activities")
workflow.add_edge("recommend_activities", "fetch_useful_links")
workflow.add_edge("fetch_useful_links", "weather_forecaster")
workflow.add_edge("weather_forecaster", "packing_list_generator")
workflow.add_edge("packing_list_generator", "food_culture_recommender")
workflow.add_edge("food_culture_recommender", "accommodation_recommender")
workflow.add_edge("accommodation_recommender", "expense_breakdown_node")
workflow.add_edge("expense_breakdown_node", END)


graph = workflow.compile()
