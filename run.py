import logging
import os
from app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main application entry point"""

    # Check if embeddings should be skipped for faster development startup
    skip_embeddings = os.getenv('SKIP_EMBEDDINGS_ON_STARTUP', 'false').lower() == 'true'

    if not skip_embeddings:
        # Check and generate embeddings before starting the app
        logger.info("🔍 Checking embeddings before starting server...")

        try:
            from app.services.startup_service import initialize_app_on_startup

            # Check for force regeneration flag
            force_regenerate = os.getenv('FORCE_REGENERATE_EMBEDDINGS', 'false').lower() == 'true'

            if force_regenerate:
                logger.info("🔄 Force regeneration flag detected")

            result = initialize_app_on_startup(force_regenerate_embeddings=force_regenerate)

            if result['status'] == 'success':
                logger.info(f"✅ Startup check completed: {result['message']}")
            else:
                logger.error(f"❌ Startup check failed: {result['message']}")
                logger.info("🔄 Continuing with server startup anyway...")

        except Exception as e:
            logger.error(f"❌ Critical startup error: {e}")
            logger.info("🔄 Continuing with server startup anyway...")
    else:
        logger.info("⏩ Skipping embeddings check for faster startup (SKIP_EMBEDDINGS_ON_STARTUP=true)")
    
    # Create and run the Flask app
    app = create_app()
    
    logger.info("🚀 Starting Flask server...")
    
    if __name__ == '__main__':
        # Optimized for concurrent users on Windows
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Disable debug for better performance
            threaded=True,  # Enable threading for concurrency
            processes=1  # Single process with threading
        )

if __name__ == '__main__':
    main()
