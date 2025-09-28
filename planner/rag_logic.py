import chromadb
import os
from .models import Trip
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from asgiref.sync import sync_to_async
from langchain_community.embeddings import OllamaEmbeddings

# Initialize LLM for HyDE
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))

class OllamaEmbeddingFunction(chromadb.EmbeddingFunction):
    def __init__(self):
        self.model = OllamaEmbeddings(model="llama3") # Assuming llama2 is available via Ollama

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        return self.model.embed_documents(input)

# Initialize the embedding function
embeddings = OllamaEmbeddingFunction()

# Initialize ChromaDB client
client = chromadb.Client()

# Create or get the collection with the specified embedding function
collection = client.get_or_create_collection(
    name="trip_plans",
    embedding_function=embeddings
)

def index_trips():
    """
    Indexes all trip plans into the ChromaDB collection.
    """
    trips = Trip.objects.all()
    documents = []
    metadatas = []
    ids = []
    
    for trip in trips:
        # Create a document from the trip details
        document = f"Trip to {trip.destination} for {trip.duration} days.\n"
        if trip.itinerary:
            document += f"Itinerary: {trip.itinerary}\n"
        if trip.comments:
            document += f"Comments: {trip.comments}\n"
        
        documents.append(document)
        metadatas.append({"trip_id": trip.id, "user_id": trip.user.id})
        ids.append(str(trip.id))

    if documents:
        # Clear the collection before adding new documents to avoid duplicates
        try:
            collection.delete(ids=ids)
        except Exception as e:
            print(f"Error deleting documents from collection: {e}")
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    print(f"Indexed {len(documents)} trips.")

def search_trips(query, user_id, n_results=3):
    """
    Searches for relevant trip plans for a specific user in the ChromaDB collection.
    """
    print(f"--- RAG: Searching for query: '{query}' for user_id: {user_id} ---")
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"user_id": user_id}
    )
    documents = results['documents'][0] if results['documents'] else []
    print(f"--- RAG: Found {len(documents)} documents. ---")
    return documents

async def hyde_search_trips(query, user_id, n_results=3):
    """
    Searches for relevant trip plans using the HyDE technique.
    """
    print(f"--- HyDE: Generating hypothetical document for query: '{query}' ---")
    # 1. Generate a hypothetical document
    hyde_prompt = f"Generate a concise trip plan summary for: {query}"
    llm_result = await sync_to_async(llm.invoke)([HumanMessage(content=hyde_prompt)])
    hypothetical_document = llm_result.content
    print(f"--- HyDE: Hypothetical document:\n{hypothetical_document} ---")

    # 2. Search for the hypothetical document
    return search_trips(hypothetical_document, user_id, n_results)