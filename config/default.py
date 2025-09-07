import os

class Config:
    """Base configuration."""
    # Secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY', 'my_precious_secret_key')
    
    # Webhook settings
    WEBHOOK_VERIFY_TOKEN = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'your_verification_token_here')
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your_webhook_secret_here')
