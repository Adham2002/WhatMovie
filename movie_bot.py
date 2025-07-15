import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
# lightweight client library for interacting with GenAI APIs
from google import genai
from google.genai.types import GenerateContentConfig
# Full low level client library for interacting with Vertex AI APIs
from google.cloud import aiplatform
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import HybridQuery


class MovieBot:
    def __init__(self, name: str, movies_df: pd.DataFrame, client: genai.Client, index_endpoint_id: str = '5749047234477948928', deployed_index_id: str = "WhatMovie-1-deployed-index"):
        self.name = name
        self._client = client
        self.movies_df = movies_df
        aiplatform.init(project = "synthetic-diode-459014-v9", location = "europe-west1")
        self._index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name = index_endpoint_id)
        self._deployed_index_id = deployed_index_id
        self._model = "gemini-2.0-flash-001"
        
        # Create sparse and dense vectorizers
        self._sparse_vectorizer = SparseVectorizer(movies_df['movie_details'].tolist())
        self._dense_vectorizer = DenseVectorizer(client)

        # Create chat with Gemini model
        self._chat = client.chats.create(
            model = self._model,
            config = GenerateContentConfig(
                system_instruction=[
                    "You are a AI movie guessing chatbot named WhatMovie.",
                    "Your mission is to guess the movie based on the description provided by the user.",
                    "You will be provided with movie details of the 5 movies that most closely match the description, according to a vector search, to help you.",
                    "You're movie guess does not have to be one of the movies if they are obviously wrong.",
                ]
            ),
        )
    
    def prompt(self, movie_description):
        '''Sends movie description to the chatbot and returns the response'''
        index_response = self.query_movie_index(movie_description)
        contents = [movie_description, index_response]
        response = self._chat.send_message(contents)
        return response.text
    
    def query_movie_index(self, movie_description):
        '''Queries movie index endpoint given movie query'''
        # Create HybridQuery
        query_dense_emb = self._dense_vectorizer.embed([movie_description])
        query_sparse_emb = self._sparse_vectorizer.embed([movie_description])
        query = HybridQuery(
            dense_embedding = query_dense_emb,
            sparse_embedding_values = query_sparse_emb["values"],
            sparse_embedding_dimensions = query_sparse_emb["dimensions"],
            rrf_ranking_alpha = 0.5,
        )
    
        # Run hybrid query
        response = self._index_endpoint.find_neighbors(
            deployed_index_id = self._deployed_index_id,
            queries = [query],
            num_neighbors = 10,
        )
        
        # Get movie details from response
        return str([
            f'Rank: {i}, Probability: {neighbor.distance if neighbor.distance else 0.0}, Movie details: {self.movies_df.loc[int(neighbor.id), 'movie_details']}'
            for i, neighbor in enumerate(response[0])
        ])


class SparseVectorizer():
    def __init__(self, corpus):
        self.vectorizer = TfidfVectorizer()
        self.vectorizer.fit_transform(corpus)

    def embed(self, texts: list[str]):
        '''Vectorises movie details using TF-IDF encoding'''
        vector = self.vectorizer.transform(texts)
        # Convert to google embedding format
        return {"values": list(vector.data), "dimensions": list(vector.indices)}


class DenseVectorizer():
    def __init__(self, client: genai.Client, model = "text-embedding-005"):
        self.client = client
        self.model = model

    def embed(self, texts: list[str]):
        '''Wrapper for dense embedding method'''
        return self.client.models.embed_content(model = self.model, contents = texts).embeddings[0].values

