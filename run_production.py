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

def main():
    """Main production server entry point"""

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

    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))

    logger.info("🚀 Starting Waitress production server...")
    logger.info(f"👥 Optimized for 30+ concurrent WhatsApp users")
    logger.info(f"🌐 Server will be available at http://0.0.0.0:{port}")
    logger.info(f"🔍 PORT environment variable: {os.getenv('PORT', 'not set')}")
    logger.info(f"🔍 Using port: {port}")

    # Start Waitress server with optimized settings for concurrency
    serve(
        app,
        host='0.0.0.0',
        port=port,
        threads=50,  # Number of threads for handling requests
        connection_limit=1000,  # Maximum number of connections
        cleanup_interval=30,  # Cleanup interval in seconds
        channel_timeout=120,  # Channel timeout in seconds
        log_socket_errors=True,
        clear_untrusted_proxy_headers=True,
        # Performance tuning
        backlog=2048,  # Socket backlog
        recv_bytes=65536,  # Receive buffer size
        send_bytes=65536,  # Send buffer size
        # Security
        trusted_proxy='*',  # Trust all proxies (adjust for production)
        trusted_proxy_count=1,
        trusted_proxy_headers='x-forwarded-for x-forwarded-host x-forwarded-proto x-forwarded-port',
    )

if __name__ == '__main__':
    main()