"""
Startup Service Module
Handles application initialization including embeddings check and generation
"""

import logging
import time
from typing import Dict, Any
from .embeddings import get_embedding_service

logger = logging.getLogger(__name__)

class StartupService:
    def __init__(self):
        self.embedding_service = get_embedding_service()
        
    def check_and_generate_embeddings(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Check if all products have embeddings and generate them if needed
        
        Args:
            force_regenerate: Whether to force regeneration of existing embeddings
            
        Returns:
            Dict with initialization status
        """
        try:
            logger.info("🔍 Checking embedding status...")
            
            # Get current embedding status
            status = self.embedding_service.get_embedding_status()
            
            if status['status'] != 'success':
                logger.error(f"❌ Failed to check embedding status: {status.get('message', 'Unknown error')}")
                return status
            
            total_products = status['total_products']
            products_with_embeddings = status['products_with_embeddings']
            products_without_embeddings = status['products_without_embeddings']
            completion_percentage = status['completion_percentage']
            
            logger.info(f"📊 Embedding Status:")
            logger.info(f"   - Total products: {total_products}")
            logger.info(f"   - Products with embeddings: {products_with_embeddings}")
            logger.info(f"   - Products without embeddings: {products_without_embeddings}")
            logger.info(f"   - Completion: {completion_percentage}%")
            
            # If all products have embeddings and not forcing regeneration
            if status['is_complete'] and not force_regenerate:
                logger.info("✅ All products already have embeddings. Ready to proceed!")
                return {
                    'status': 'success',
                    'message': 'All embeddings ready',
                    'embedding_status': status,
                    'action_taken': 'none'
                }
            
            # Generate missing embeddings or regenerate all
            if force_regenerate:
                logger.info("🔄 Force regeneration requested. Regenerating all embeddings...")
            else:
                logger.info(f"🔄 Generating embeddings for {products_without_embeddings} products...")
            
            start_time = time.time()
            
            generation_result = self.embedding_service.generate_embeddings_for_all_products(
                force_regenerate=force_regenerate,
                batch_size=50
            )
            
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            if generation_result['status'] == 'success':
                logger.info(f"✅ Embedding generation completed in {duration} seconds")
                logger.info(f"   - Total processed: {generation_result['total_products']}")
                logger.info(f"   - Successful: {generation_result['success_count']}")
                logger.info(f"   - Errors: {generation_result['error_count']}")
                logger.info(f"   - Skipped: {generation_result['skipped_count']}")
                
                return {
                    'status': 'success',
                    'message': f'Embeddings ready. Processed {generation_result["total_products"]} products in {duration}s',
                    'embedding_status': self.embedding_service.get_embedding_status(),
                    'generation_result': generation_result,
                    'action_taken': 'generated' if not generation_result.get('already_complete') else 'already_complete',
                    'duration_seconds': duration
                }
            else:
                logger.error(f"❌ Embedding generation failed: {generation_result.get('message', 'Unknown error')}")
                return {
                    'status': 'error',
                    'message': f'Embedding generation failed: {generation_result.get("message", "Unknown error")}',
                    'generation_result': generation_result,
                    'action_taken': 'failed'
                }
                
        except Exception as e:
            logger.error(f"❌ Startup embedding check failed: {e}")
            return {
                'status': 'error',
                'message': f'Startup embedding check failed: {str(e)}',
                'action_taken': 'failed'
            }
    
    def initialize_application(self, force_regenerate_embeddings: bool = False) -> Dict[str, Any]:
        """
        Complete application initialization including embeddings
        
        Args:
            force_regenerate_embeddings: Whether to force regeneration of embeddings
            
        Returns:
            Dict with initialization results
        """
        logger.info("🚀 Starting application initialization...")
        
        start_time = time.time()
        
        try:
            # Step 1: Check and generate embeddings
            embedding_result = self.check_and_generate_embeddings(force_regenerate_embeddings)
            
            if embedding_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': 'Application initialization failed during embedding setup',
                    'embedding_result': embedding_result,
                    'initialization_complete': False
                }
            
            # Step 2: Initialize global inventory (if needed)
            try:
                from .webhook_service import initialize_global_inventory
                initialize_global_inventory()
                logger.info("✅ Global inventory initialization completed")
            except Exception as e:
                logger.warning(f"⚠️ Global inventory initialization failed: {e}")
                # Don't fail startup for this as it can be initialized later
            
            end_time = time.time()
            total_duration = round(end_time - start_time, 2)
            
            logger.info(f"✅ Application initialization completed successfully in {total_duration} seconds")
            
            return {
                'status': 'success',
                'message': f'Application initialized successfully in {total_duration}s',
                'embedding_result': embedding_result,
                'initialization_complete': True,
                'total_duration_seconds': total_duration
            }
            
        except Exception as e:
            logger.error(f"❌ Application initialization failed: {e}")
            return {
                'status': 'error',
                'message': f'Application initialization failed: {str(e)}',
                'initialization_complete': False
            }

# Global startup service instance
startup_service = StartupService()

def initialize_app_on_startup(force_regenerate_embeddings: bool = False) -> Dict[str, Any]:
    """
    Convenience function to initialize the application
    
    Args:
        force_regenerate_embeddings: Whether to force regeneration of embeddings
        
    Returns:
        Dict with initialization results
    """
    return startup_service.initialize_application(force_regenerate_embeddings)
