from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    from config.default import Config
    app.config.from_object(Config)
    
    # Register routes
    from app.routes.webhook_routes import webhook_bp
    app.register_blueprint(webhook_bp)
    
    return app
