import json
import os
import pandas as pd
from dataclasses import dataclass

# Google modules to access genai and BigQuery APIs
from google import genai
from google.genai.types import GenerateContentConfig
from google.genai.types import UserContent, ModelContent, Content
from google.cloud import bigquery

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render


# --- MovieChat class to handle RAG chatbot ---
@dataclass
class MovieChat:
    MODEL_ID = "gemini-2.0-flash-001"
    
    genai_client: genai.Client
    bq_client: bigquery.Client
    
    def __post_init__(self):
        # Create chat with Gemini model
        self.system_instruction = [
            "You are a AI movie guessing chatbot named WhatMovie.",
            "Your mission is to guess the movie based on the description provided by the user.",
            "You will be 10 movies retrieved from a database, ranked by how closely they match the user's description, to help you.",
            "You're movie guess does not have to be one of the movies if they are obviously wrong."
        ]
        self._chat = self.genai_client.chats.create(
            model = self.MODEL_ID,
            config = GenerateContentConfig(system_instruction = self.system_instruction),
        )
    
    def send_message(self, movie_description: str) -> str:
        '''Sends movie description to the chatbot and returns the response'''
        search_results = self.query_hybrid_index(movie_description).str.cat(sep='\n')
        
        # Ensure model_contents is a list of Content objects
        # model_contents_for_gemini = [
        #     Content(role="model", parts=[{"text": search_results}])        # TODO: parse `search_results` into structured data and then format it carefully
        # ]
        
        # Extend system instructions with search results for the current turn
        # Note: system_instruction in config overrides the initial chat config.
        # For turn-by-turn context, it's often better to include this in the `contents` directly
        # or manage the chat history more explicitly.
        # For simplicity, let's append it to the user's message for the model to see.
        
        user_message_with_context = [
            movie_description,
            f"\n\nRelevant movie suggestions from database:\n{search_results}"
        ]

        # Send the message with the augmented context
        response = self._chat.send_message(user_message_with_context)
        return response.text
    
    def query_dense_index(self, movie_description: str) -> pd.DataFrame:
        '''Queries movie index endpoint given movie query'''
        query_index_q = f'CALL movies.query_dense_index("{movie_description}", 50)'
        return self.bq_client.query_and_wait(query_index_q).to_dataframe()
    
    def query_sparse_index(self, movie_description: str) -> pd.DataFrame:
        '''Queries movie index endpoint given movie query'''
        query_index_q = f'CALL movies.bm25_search("{movie_description}", 50);'
        return self.bq_client.query_and_wait(query_index_q).to_dataframe()
    
    def query_hybrid_index(self, movie_description: str) -> pd.DataFrame:
        semantic_search = self.query_dense_index(movie_description)
        keyword_search = self.query_sparse_index(movie_description)
        return self.rrf_rerank(semantic_search, keyword_search)
        
    def rrf_rerank(self, similarity_results: pd.DataFrame, keyword_results: pd.DataFrame) -> pd.DataFrame:
        similarity_results['rank'] = similarity_results.index + 1
        keyword_results['rank'] = keyword_results.index + 1
        df = pd.merge(similarity_results, keyword_results, 'outer', on = 'movie_id', suffixes = ['_similarity', '_keyword'])
        df['rrf'] = df['rank_similarity'].apply(self.rrf_value) + df['rank_keyword'].apply(self.rrf_value)
        
        # Format return movie details
        # TODO: Fix when both have a value the movie_details will be repeated twice in 1 cell
        # A more robust way would be to coalesce or pick one if they are identical, or combine if they are distinct parts.
        df['movie_details'] = df['movie_details_keyword'].combine_first(df['movie_details_similarity'])
        df = df.sort_values('rrf', ascending = False, ignore_index = True)[['movie_details']].head(10)
        df['rank'] = df.index + 1
        df['rank'] = df['rank'].apply(lambda x: str(x))
        return 'Hybrid search match ' + df['rank'] + ': ' + df['movie_details']
        
    def rrf_value(self, rank):
        return 0 if pd.isnull(rank) else 1/(60 + rank)


# --- Django View for the Chatbot API ---
# Initialize BigQuery and GenAI clients globally or within the view
# TODO For production, use service accounts and proper credential management

# Load GCP project info from config.json
config_path = os.path.join(os.getcwd(), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Initialise constants
PROJECT_ID = config['PROJECT_ID']
LOCATION = config['LOCATION']
bq_client = None
genai_client = None
movie_chatbot = None

# Initialize BigQuery client
try:
    bq_client = bigquery.Client()
    print("BigQuery client initialized.")
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")

# Initialize GenAI client
try:
    genai_client = genai.Client(vertexai = True, project = PROJECT_ID, location = LOCATION)
    print("GenAI client initialized.")
except Exception as e:
    print(f"Error initializing GenAI client: {e}")

# Instantiate the MovieChat class
# TODO For production instantiate per-user chat history, you'd manage _chat per session (once per server run, or per request if stateful chat is complex)
if genai_client and bq_client:
    try:
        movie_chatbot = MovieChat(genai_client=genai_client, bq_client=bq_client)
        print("MovieChat instance created.")
    except Exception as e:
        print(f"Error creating MovieChat instance: {e}")
else:
    print("Skipping MovieChat instance creation due to client initialization errors.")


@method_decorator(csrf_exempt, name='dispatch') # Disable CSRF for API POST requests (for demo, be careful in production)
class WhatMovieAPIView(View):
    def post(self, request, *args, **kwargs):
        if not movie_chatbot:
            return JsonResponse({'error': 'WhatMovie chatbot not initialized. Check backend logs for API client errors.'}, status=500)

        try:
            data = json.loads(request.body)
            user_message = data.get('message')

            if not user_message:
                return JsonResponse({'error': 'No message provided'}, status=400)

            # Send message to your MovieChat instance
            bot_response = movie_chatbot.send_message(user_message)

            return JsonResponse({'response': bot_response})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"Error in WhatMovieAPIView: {e}")
            return JsonResponse({'error': f'An internal server error occurred: {str(e)}'}, status=500)


