import pandas as pd
from dataclasses import dataclass

# Google modules to access genai and BigQuery APIs
from google import genai
from google.genai.types import GenerateContentConfig
from google.genai.types import UserContent, ModelContent, Content
from google.cloud import bigquery


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
        #hybrid_search_results = self.query_hybrid_index(movie_description)
        search_results = self.query_hybrid_index(movie_description)
        model_contents = search_results.to_list()
        response = self._chat.send_message(movie_description, config= GenerateContentConfig(system_instruction = self.system_instruction.extend(model_contents)))
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
        m = pd.merge(similarity_results, keyword_results, 'outer', on = 'movie_id', suffixes = ['_similarity', '_keyword'])
        m['rrf'] = m['rank_similarity'].apply(self.rrf_value) + m['rank_keyword'].apply(self.rrf_value)
        
        # Format return movie details
        # Fix when both have a value the movie_details will be repeated twice in 1 cell
        m['movie_details'] = m['movie_details_keyword'].fillna('') + m['movie_details_similarity'].fillna('')
        m = m.sort_values('rrf', ascending = False, ignore_index = True)[['movie_details']].head(10)
        m['rank'] = m.index + 1
        m['rank'] = m['rank'].apply(lambda x: str(x))
        return 'Hybrid search match ' + m['rank'] + ': ' + m['movie_details']
    
    def rrf_value(self, rank):
        return 0 if pd.isnull(rank) else 1/(60 + rank)


