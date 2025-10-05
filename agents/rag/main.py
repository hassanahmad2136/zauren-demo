# agents/rag/main.py
"""
Multi-Tenant RAG Agent for Product Search
Handles vector search with Pinecone and metadata filtering with Supabase
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our multi-tenant components
from core.services.tenant_config import TenantConfigManager
from core.services.client_factory import TenantClientFactory
from core.services.product_search import MultiTenantProductSearch
from core.database.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Global components
redis_client = None
config_manager = None
client_factory = None
product_search = None

# Request/Response Models
class SearchRequest(BaseModel):
    tenant_id: str
    search_entity: Dict[str, Any]
    max_results: Optional[int] = 20
    similarity_threshold: Optional[float] = 0.7
    user_id: Optional[str] = None

class ProductResult(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    brand: str
    image_url: str
    similarity_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchResponse(BaseModel):
    success: bool
    products: List[ProductResult]
    total_results: int
    tenant_id: str
    search_metadata: Dict[str, Any]
    execution_time_ms: int
    error_message: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    components: Dict[str, bool]
    timestamp: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global redis_client, config_manager, client_factory, product_search
    
    logger.info("Starting RAG Agent...")
    
    try:
        # Initialize Redis connection
        redis_client = RedisClient()
        await redis_client.connect()
        logger.info("Connected to Redis")
        
        # Initialize components
        config_manager = TenantConfigManager(redis_client)
        client_factory = TenantClientFactory()
        product_search = MultiTenantProductSearch(config_manager, client_factory)
        
        logger.info("RAG Agent initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG Agent: {e}")
        raise
    finally:
        # Cleanup
        if redis_client:
            await redis_client.disconnect()
        logger.info("RAG Agent shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Multi-Tenant RAG Agent",
    description="Vector-based product search with tenant isolation",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """Search products using tenant-specific configuration"""
    start_time = time.time()
    
    try:
        logger.info(f"Received search request for tenant: {request.tenant_id}")
        
        # Perform multi-tenant product search
        results = await product_search.search_products(
            request.tenant_id, 
            request.search_entity
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Convert products to ProductResult models
        products = []
        for product in results.get("products", []):
            products.append(ProductResult(
                id=product["id"],
                name=product["name"],
                description=product["description"],
                price=product["price"],
                category=product["category"],
                brand=product["brand"],
                image_url=product["image_url"],
                similarity_score=product.get("similarity_score", 0.0),
                metadata={k: v for k, v in product.items() 
                         if k not in ["id", "name", "description", "price", "category", "brand", "image_url", "similarity_score"]}
            ))
        
        return SearchResponse(
            success=True,
            products=products,
            total_results=results["total"],
            tenant_id=request.tenant_id,
            search_metadata=results.get("search_metadata", {}),
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        logger.error(f"RAG search error for tenant {request.tenant_id}: {str(e)}")
        
        return SearchResponse(
            success=False,
            products=[],
            total_results=0,
            tenant_id=request.tenant_id,
            search_metadata={},
            execution_time_ms=execution_time,
            error_message=str(e)
        )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    
    components = {
        "redis": False,
        "config_manager": False,
        "client_factory": False,
        "product_search": False
    }
    
    try:
        # Check Redis
        if redis_client:
            await redis_client.ping()
            components["redis"] = True
            
        # Check other components
        components["config_manager"] = config_manager is not None
        components["client_factory"] = client_factory is not None  
        components["product_search"] = product_search is not None
        
        all_healthy = all(components.values())
        
        return HealthResponse(
            status="healthy" if all_healthy else "degraded",
            service="rag-agent",
            components=components,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="rag-agent", 
            components=components,
            timestamp=datetime.now().isoformat()
        )

@app.get("/tenants")
async def list_tenants():
    """Get list of available tenants"""
    try:
        tenants = await config_manager.list_tenants()
        return {"tenants": tenants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tenants/{tenant_id}/config")
async def get_tenant_config(tenant_id: str):
    """Get tenant configuration (without sensitive data)"""
    try:
        config = await config_manager.get_tenant_config(tenant_id)
        if not config:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Return config without sensitive data
        return {
            "tenant_id": config.tenant_id,
            "tenant_name": config.tenant_name,
            "tenant_description": config.tenant_description,
            "has_pinecone_config": bool(config.pinecone),
            "has_supabase_config": bool(config.supabase),
            "embedding_model": config.embedding.model_name,
            "max_results": config.search.max_results,
            "similarity_threshold": config.search.similarity_threshold,
            "product_schema_fields": list(config.product_schema.custom_fields.keys()),
            "filterable_fields": config.pinecone.metadata_fields,
            "filter_options": config.product_schema.filter_options
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tenants/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: str):
    """Get product statistics for a tenant"""
    try:
        stats = await product_search.get_tenant_product_stats(tenant_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/{tenant_id}")
async def test_tenant_search(tenant_id: str):
    """Test endpoint to verify tenant configuration works"""
    try:
        # Test with a simple search
        test_search_entity = {
            "query": "test product search",
            "category": "shoes"
        }
        
        results = await product_search.search_products(tenant_id, test_search_entity)
        
        return {
            "tenant_id": tenant_id,
            "test_successful": results["total"] >= 0,  # Any result is fine for test
            "results_count": results["total"],
            "search_metadata": results.get("search_metadata", {}),
            "error": results.get("error")
        }
        
    except Exception as e:
        return {
            "tenant_id": tenant_id,
            "test_successful": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)