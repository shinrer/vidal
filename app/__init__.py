from flask import Flask

app = Flask(__name__)
app.secret_key = 'dev_secret_key' # Replace with a proper secret key in production, e.g., from env var

# Import routes after app object is created to avoid circular imports
from app import routes
