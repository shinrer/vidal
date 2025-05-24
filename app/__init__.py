from flask import Flask

app = Flask(__name__)
app.secret_key = 'dev_secret_key' # Replace with a proper secret key in production, e.g., from env var

# Import routes after app object is created to avoid circular imports
from app import routes 

# Load AI models and resources on startup
# This needs to be after app is defined and before first request if possible,
# or within an app_context if resources need app config.
# For simplicity, and since our load_ai_resources doesn't currently need app context,
# we can call it here. If it needed app context, it would be more complex.
from app.ai_models import load_ai_resources, sentence_model as ai_sentence_model # Import the model itself for status check
print("Attempting to load AI resources on application startup...")
with app.app_context(): # Ensures context is available if needed by load_ai_resources
    if load_ai_resources():
        print("AI resources loaded successfully via __init__.py.")
        app.config['AI_RESOURCES_LOADED'] = True
    else:
        print("Error loading AI resources via __init__.py. Semantic search may not be available.")
        app.config['AI_RESOURCES_LOADED'] = False
