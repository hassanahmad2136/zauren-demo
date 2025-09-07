from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    from config.default import Config
    app.config.from_object(Config)
    
    # Register routes
    from app.routes.webhook_routes import webhook_bp
    from app.routes.admin_routes import admin_bp
    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)
    
    # Start cart cleanup service
    try:
        from app.services.cart_cleanup import start_cart_cleanup
        start_cart_cleanup()
        print("✅ Cart cleanup service started")
    except Exception as e:
        print(f"⚠️ Failed to start cart cleanup service: {e}")
    
    return app
