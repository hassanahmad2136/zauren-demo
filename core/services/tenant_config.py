# core/services/tenant_config.py
"""
Tenant Configuration Manager
Handles loading and caching of tenant configurations from Redis/database
"""

import json
import logging
from typing import Dict, Any, Optional

from core.models.tenant import TenantConfiguration
from core.database.redis_client import RedisClient

logger = logging.getLogger(__name__)

class TenantConfigManager:
    """Manages tenant configurations with Redis caching"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.config_prefix = "tenant_config"
        self.cache_ttl = 3600  # 1 hour cache
        
    async def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfiguration]:
        """Get tenant configuration with caching"""
        cache_key = f"{self.config_prefix}:{tenant_id}"
        
        try:
            # Try cache first
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(f"Found cached config for tenant: {tenant_id}")
                return TenantConfiguration(**cached)
        except Exception as e:
            logger.warning(f"Cache read failed for tenant {tenant_id}: {e}")
        
        # Load from database/config source
        config_data = await self._load_tenant_config_from_source(tenant_id)
        if not config_data:
            logger.error(f"No configuration found for tenant: {tenant_id}")
            return None
            
        try:
            config = TenantConfiguration(**config_data)
            
            # Cache for future requests
            await self.redis.set(
                cache_key, 
                config.dict(), 
                ttl=self.cache_ttl
            )
            logger.info(f"Cached config for tenant: {tenant_id}")
            
            return config
        except Exception as e:
            logger.error(f"Failed to create config for tenant {tenant_id}: {e}")
            return None
    
    async def save_tenant_config(self, config: TenantConfiguration) -> bool:
        """Save tenant configuration and update cache"""
        try:
            # Update timestamp
            config.update_timestamp()
            
            # Save to cache
            cache_key = f"{self.config_prefix}:{config.tenant_id}"
            await self.redis.set(
                cache_key,
                config.dict(),
                ttl=self.cache_ttl
            )
            
            # TODO: Save to persistent storage (PostgreSQL/file)
            # await self._save_to_persistent_storage(config)
            
            logger.info(f"Saved config for tenant: {config.tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config for tenant {config.tenant_id}: {e}")
            return False
    
    async def _load_tenant_config_from_source(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Load tenant configuration from persistent source
        For now, uses hardcoded sample configs. In production, load from database.
        """
        
        # Sample tenant configurations for testing
        sample_configs = {
            "fashion_retailer": {
                "tenant_id": "fashion_retailer",
                "tenant_name": "Fashion Store Pro",
                "tenant_description": "Multi-brand fashion retailer with trendy clothing",
                "pinecone": {
                    "api_key": "pc-fashion-api-key-here", 
                    "index_name": "fashion-products-v1",
                    "namespace": "main",
                    "metadata_fields": ["category", "brand", "color", "size", "price_range", "style", "material"]
                },
                "supabase": {
                    "url": "https://fashion-retailer.supabase.co",
                    "api_key": "supabase-fashion-api-key-here",
                    "products_table": "products"
                },
                "product_schema": {
                    "custom_fields": {
                        "color": "text",
                        "size": "text", 
                        "style": "text",
                        "material": "text",
                        "season": "text",
                        "gender": "text",
                        "age_group": "text"
                    },
                    "filter_options": {
                        "category": ["dresses", "shirts", "pants", "shoes", "accessories", "jackets"],
                        "brand": ["Zara", "H&M", "Nike", "Adidas", "Uniqlo", "Forever 21"],
                        "color": ["red", "blue", "black", "white", "green", "yellow", "pink", "purple"],
                        "size": ["XS", "S", "M", "L", "XL", "XXL"],
                        "style": ["casual", "formal", "sporty", "bohemian", "vintage", "modern"],
                        "material": ["cotton", "polyester", "denim", "silk", "wool", "leather"],
                        "gender": ["men", "women", "unisex"],
                        "age_group": ["kids", "teens", "adults"]
                    }
                }
            },
            
            "electronics_store": {
                "tenant_id": "electronics_store",
                "tenant_name": "TechWorld Electronics",
                "tenant_description": "Consumer electronics and gadgets retailer",
                "pinecone": {
                    "api_key": "pc-electronics-api-key-here",
                    "index_name": "electronics-catalog-v1", 
                    "metadata_fields": ["category", "brand", "price_range", "specifications"]
                },
                "supabase": {
                    "url": "https://electronics-store.supabase.co",
                    "api_key": "supabase-electronics-api-key-here",
                    "products_table": "electronic_products"
                },
                "product_schema": {
                    "custom_fields": {
                        "specifications": "jsonb",
                        "warranty_months": "integer",
                        "model_number": "text",
                        "release_year": "integer",
                        "condition": "text"
                    },
                    "filter_options": {
                        "category": ["smartphones", "laptops", "tablets", "headphones", "speakers", "accessories"],
                        "brand": ["Apple", "Samsung", "Dell", "HP", "Sony", "Bose"],
                        "condition": ["new", "refurbished", "used"],
                        "warranty_months": ["12", "24", "36"]
                    }
                }
            },
            
            # Add a test tenant that matches your current test data
            "test_retailer": {
                "tenant_id": "test_retailer",
                "tenant_name": "Test Retail Store",
                "tenant_description": "Test configuration for development",
                "pinecone": {
                    "api_key": "test-pinecone-key",
                    "index_name": "test-products-index",
                    "metadata_fields": ["category", "brand", "color", "size", "price_range"]
                },
                "supabase": {
                    "url": "https://test.supabase.co",
                    "api_key": "test-supabase-key",
                    "products_table": "products"
                },
                "product_schema": {
                    "custom_fields": {
                        "color": "text",
                        "size": "text",
                        "style": "text"
                    },
                    "filter_options": {
                        "category": ["shoes", "clothing", "accessories"],
                        "brand": ["Nike", "Adidas", "Generic"],
                        "color": ["red", "blue", "black", "white"],
                        "size": ["7", "8", "9", "10", "S", "M", "L", "XL"]
                    }
                }
            }
        }
        
        config = sample_configs.get(tenant_id)
        if config:
            logger.info(f"Loaded sample config for tenant: {tenant_id}")
            return config
        
        logger.warning(f"No sample config found for tenant: {tenant_id}")
        return None
    
    async def list_tenants(self) -> List[str]:
        """Get list of available tenant IDs"""
        # In production, this would query your database
        # For now, return the sample tenant IDs
        return ["fashion_retailer", "electronics_store", "test_retailer"]
    
    async def delete_tenant_config(self, tenant_id: str) -> bool:
        """Delete tenant configuration from cache"""
        try:
            cache_key = f"{self.config_prefix}:{tenant_id}"
            await self.redis.delete(cache_key)
            logger.info(f"Deleted cached config for tenant: {tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete config for tenant {tenant_id}: {e}")
            return False