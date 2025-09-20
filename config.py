import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# API Endpoints
NEWSAPI_BASE_URL = "https://newsapi.org/v2"
GOOGLE_GENERATIVE_AI_BASE_URL = "https://generativelanguage.googleapis.com"

# Kafka Configuration
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")

# Application Configuration
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "120"))  # seconds
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
