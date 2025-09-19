"""
Production server for Windows using Waitress
Optimized for handling 30+ concurrent WhatsApp users
"""

import logging
import os
from waitress import serve
from app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    # Check if embeddings should be skipped for faster startup
    skip_embeddings = os.getenv('SKIP_EMBEDDINGS_ON_STARTUP', 'true').lower() == 'true'

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

    # Create Flask app
    app = create_app()

    # Get port and start server
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting server on 0.0.0.0:{port} (optimized for 30+ concurrent users)")
    serve(
        app,
        host='0.0.0.0',
        port=port,
        threads=50,
        connection_limit=1000,
        channel_timeout=120
    )