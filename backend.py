from dotenv import load_dotenv
load_dotenv()
import os

# The backend rejects requests that don't carry its API key.
BACKEND_HEADERS = {"X-API-Key": os.getenv("BACKEND_API_KEY", "")}
