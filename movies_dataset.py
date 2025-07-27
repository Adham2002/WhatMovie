# Python inbuilt modules
import os
from dataclasses import dataclass

# Dataset modules
import pandas as pd
import kagglehub
from kagglehub import KaggleDatasetAdapter
from google.cloud import bigquery

@dataclass
class MovieDataset():
    #bq_client: bigquery.Client         # bq_client._default_query_job_config.default_dataset should be set it we are using an existing dataset
    project: str
    location: str
    dataset: str
    movie_df: pd.DataFrame = None
    
    def __post_init__(self):
        self.bq_client = bigquery.Client(
            project = self.project, 
            location = self.location,
            default_query_job_config = bigquery.QueryJobConfig(default_dataset = f'{self.project}.{self.dataset}')
        )
        
        if self.movie_df is None:
            # Get TMDB dataset
            self.movie_df = self.get_tmdb_dataframe()
            self.validate_tmdb_dataframe()
            self.movie_df = self.clean(self.movie_df)
            self.movie_df = self.fe(self.movie_df)

        # Create or update bq dataset with movie_df
        # datasets = set(dataset.dataset_id for dataset in list(self.bq_client.list_datasets()))
        # if False: #self.dataset in datasets:
        #     self.validate_bq_schema()
        #     self.update_bq_dataset()
        # else:
        #     self.create_bq_dataset()

    def validate_bq_client(self):
        # Validate bigquery client
        if not self.bq_client.project:
            raise Exception('MovieDataset init: bq_client did not have a project specified')
        
        datasets = set(dataset.dataset_id for dataset in list(self.bq_client.list_datasets()))
        qjob_dataset = self.bq_client._default_query_job_config.default_dataset
        
        if self.new_dataset and (qjob_dataset in datasets):
            raise Exception(f'MovieDataset init: dataset "{self.new_dataset}" already exists in project')
        if not (self.new_dataset or qjob_dataset):
            raise Exception('MovieDataset init: bq_client did not have a default dataset specified for query jobs')

    def validate_bq_schema(self):
        pass
    
    def get_tmdb_dataframe(self) -> pd.DataFrame:
        # Set the path to the file you'd like to load
        file_path = "TMDB_movie_dataset_v11.csv"

        # Load the latest version
        df: pd.DataFrame = kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        "asaniczka/tmdb-movies-dataset-2023-930k-movies",
        file_path,
        pandas_kwargs = {
                'usecols': [
                    'id', 
                    'title', 'overview', 'tagline',                                     # useful for semantic similarity
                    'genres', 'production_companies', 'keywords', 'release_date',       # useful features for semantic similarity, keyword matching and logical filtering
                    'vote_average', 'vote_count', 'popularity',                         # useful or logical ranking and filtering (popular movies are more likely to be searched)
                    'status', 'adult'                                                   # useful for filtering the dataset to get only non adult movies
                ]
            }
        )
        
        return df
        
    def validate_tmdb_dataframe(self):
        pass

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df.rename(columns = {'id': 'movie_id'}, inplace = True)
        df = df.loc[df['status'] == 'Released', df.columns.drop('status')]
        df = df.loc[~(df['adult']), df.columns.drop('adult')]
        
        df = df.loc[
            (df["title"].notnull()) & 
            (df["release_date"].notnull()) & 
            (df["overview"].notnull())
        ]
        df = df.fillna("NA")
        df.drop_duplicates(subset = ['movie_id'], keep = 'first', inplace = True)
        return df

    def fe(self, df: pd.DataFrame) -> pd.DataFrame:
        # Create 'movie_details' column that will be vectorised
        df['movie_details'] = "title: " + df["title"]
        df['movie_details'] += " release_date: " + df["release_date"] 
        df['movie_details'] += " genres: " + df["genres"]
        df['movie_details'] += " tagline: " + df["tagline"] 
        df['movie_details'] += " keywords: " + df["keywords"]  
        df['movie_details'] += " overview: " + df["overview"] 
        return df

    def create_bq_dataset(self):
        # Create new dataset
        self.bq_client.create_dataset(self.dataset, timeout = 30)
        
        # Upload movie dataframe to bq table
        job = self.bq_client.load_table_from_dataframe(self.movie_df, f'{self.bq_client.project}.{self.dataset}.movies')
        job.result()
        
        # Run create scripts
        create_files_dir = os.path.join(os.getcwd(), 'bigquery_scripts', 'create_dataset_scripts')
        create_files = sorted(os.listdir(create_files_dir))
        
        for filename in create_files:
            with open(os.path.join(create_files_dir, filename)) as q:
                self.bq_client.query_and_wait(q.read())
        
    def update_bq_dataset(self):
    # Get movie_ids in bq table
        get_ids_q = f'SELECT movie_id FROM movies.movies'
        bq_ids = self.bq_client.query_and_wait(get_ids_q).to_dataframe()
        
        # Find new movies
        new_ids = list(set(self.movie_df['movie_id']) - set(bq_ids['movie_id']))
        new_movies = self.movie_df.loc[new_ids]
        
        # Insert new movies into bq table
        job = self.bq_client.insert_rows_from_dataframe('movies', new_movies)
        
        # Run update scripts
        create_files_dir = os.path.join(os.getcwd(), 'bigquery_scripts', 'update_dataset_scripts')
        create_files = sorted(os.listdir(create_files_dir))
        for filename in create_files:
            with open(os.path.join(create_files_dir, filename)) as q:
                self.bq_client.query_and_wait(q.read())

