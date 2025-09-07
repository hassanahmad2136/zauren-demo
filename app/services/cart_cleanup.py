"""
Cart cleanup service for inactive users and expired reservations
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from .db_inventory import cleanup_expired_reservations, get_supabase_client
from .session_manager_conversation import get_user_session

# Configure logging
logger = logging.getLogger(__name__)

class CartCleanupService:
    """Service to clean up inactive carts and expired stock reservations"""
    
    def __init__(self, cleanup_interval_hours=2, cart_expiry_hours=24, reservation_expiry_hours=24):
        """
        Initialize cart cleanup service
        
        Args:
            cleanup_interval_hours: How often to run cleanup (in hours)
            cart_expiry_hours: How long carts remain active (in hours)
            reservation_expiry_hours: How long stock reservations last (in hours)
        """
        self.cleanup_interval_hours = cleanup_interval_hours
        self.cart_expiry_hours = cart_expiry_hours
        self.reservation_expiry_hours = reservation_expiry_hours
        self.running = False
        self.cleanup_thread = None
    
    def start_cleanup_service(self):
        """Start the cart cleanup background service"""
        if self.running:
            logger.warning("⚠️ Cart cleanup service is already running")
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info(f"✅ Cart cleanup service started (interval: {self.cleanup_interval_hours}h, cart expiry: {self.cart_expiry_hours}h)")
    
    def stop_cleanup_service(self):
        """Stop the cart cleanup background service"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("⏹️ Cart cleanup service stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop that runs in background"""
        while self.running:
            try:
                self.cleanup_inactive_carts()
                self.cleanup_expired_stock_reservations()
                
                # Sleep for cleanup interval
                time.sleep(self.cleanup_interval_hours * 3600)  # Convert hours to seconds
                
            except Exception as e:
                logger.error(f"❌ Error in cart cleanup loop: {e}")
                time.sleep(300)  # Sleep 5 minutes on error before retrying
    
    def cleanup_inactive_carts(self):
        """Clean up carts for inactive users"""
        try:
            supabase = get_supabase_client()
            
            # Calculate expiry time
            expiry_time = datetime.now() - timedelta(hours=self.cart_expiry_hours)
            
            # Find inactive user sessions with non-empty carts
            inactive_sessions_response = supabase.table('user_sessions')\
                .select('user_id, cart')\
                .lt('last_interaction', expiry_time.isoformat())\
                .execute()
            
            if not inactive_sessions_response.data:
                logger.info("ℹ️ No inactive carts found to clean up")
                return
            
            cleaned_carts = 0
            for session in inactive_sessions_response.data:
                user_id = session['user_id']
                cart = session.get('cart', {})
                
                # Check if cart has items
                if isinstance(cart, dict) and cart.get('items'):
                    # Release reserved stock for cart items
                    for item in cart['items']:
                        if isinstance(item, dict) and item.get('id'):
                            from .db_inventory import release_reserved_stock
                            release_result = release_reserved_stock(
                                item.get('id'), 
                                item.get('quantity', 0), 
                                user_id
                            )
                            if release_result['status'] == 'success':
                                logger.info(f"🧹 Released {release_result['released_quantity']} units of product {item.get('id')} for inactive user {user_id}")
                    
                    # Clear the cart
                    supabase.table('user_sessions')\
                        .update({'cart': {'items': [], 'total': 0}})\
                        .eq('user_id', user_id)\
                        .execute()
                    
                    cleaned_carts += 1
                    logger.info(f"🧹 Cleaned inactive cart for user {user_id}")
            
            logger.info(f"✅ Cart cleanup completed: {cleaned_carts} inactive carts cleaned")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up inactive carts: {e}")
    
    def cleanup_expired_stock_reservations(self):
        """Clean up expired stock reservations"""
        try:
            result = cleanup_expired_reservations(self.reservation_expiry_hours)
            
            if result['status'] == 'success':
                cleaned_count = result['cleaned_reservations']
                if cleaned_count > 0:
                    logger.info(f"🧹 Cleaned up {cleaned_count} expired stock reservations")
                else:
                    logger.info("ℹ️ No expired stock reservations found")
            else:
                logger.error(f"❌ Error cleaning up stock reservations: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Error in stock reservation cleanup: {e}")

# Global cleanup service instance
cleanup_service = CartCleanupService()

def start_cart_cleanup():
    """Start the cart cleanup service"""
    cleanup_service.start_cleanup_service()

def stop_cart_cleanup():
    """Stop the cart cleanup service"""
    cleanup_service.stop_cleanup_service()

def manual_cleanup():
    """Manually trigger a cleanup operation"""
    logger.info("🔄 Running manual cart cleanup...")
    cleanup_service.cleanup_inactive_carts()
    cleanup_service.cleanup_expired_stock_reservations()
    logger.info("✅ Manual cleanup completed")
