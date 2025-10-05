# core/services/client_factory.py
"""
Tenant Client Factory
Creates isolated Pinecone, Supabase, and embedding clients per tenant
"""

import logging
from typing import Tuple, Any, Dict
from sentence_transformers import SentenceTransformer

from core.models.tenant import TenantConfiguration

logger = logging.getLogger(__name__)

class TenantClientFactory:
    """Creates isolated clients per tenant"""
    
    def __init__(self):
        self.pinecone_clients = {}  # tenant_id -> pinecone client
        self.supabase_clients = {}  # tenant_id -> supabase client  
        self.embedding_models = {}  # model_name -> loaded model
        
    async def get_tenant_clients(self, config: TenantConfiguration) -> Tuple[Any, Any, SentenceTransformer]:
        """Get or create all clients for a tenant"""
        
        # For now, we'll create mock clients since we don't have actual API keys
        # In production, these would be real clients
        
        try:
            # Real Pinecone client (using correct 7.2.0+ syntax)
            if config.tenant_id not in self.pinecone_clients:
                logger.info(f"Creating Pinecone client for tenant: {config.tenant_id}")
                try:
                    from pinecone import Pinecone
                    pc = Pinecone(api_key=config.pinecone.api_key)
                    index = pc.Index(config.pinecone.index_name)
                    self.pinecone_clients[config.tenant_id] = index
                    logger.info(f"Successfully connected to Pinecone index: {config.pinecone.index_name}")
                except Exception as e:
                    logger.warning(f"Failed to connect to Pinecone for tenant {config.tenant_id}: {e}")
                    # Fall back to mock client for development
                    mock_pinecone = MockPineconeClient(config.pinecone.index_name)
                    self.pinecone_clients[config.tenant_id] = mock_pinecone
                
            # Real Supabase client
            if config.tenant_id not in self.supabase_clients:
                logger.info(f"Creating Supabase client for tenant: {config.tenant_id}")
                try:
                    from supabase import create_client, Client
                    supabase_client = create_client(config.supabase.url, config.supabase.api_key)
                    self.supabase_clients[config.tenant_id] = supabase_client
                    logger.info(f"Successfully connected to Supabase: {config.supabase.url}")
                except Exception as e:
                    logger.warning(f"Failed to connect to Supabase for tenant {config.tenant_id}: {e}")
                    # Fall back to mock client for development
                    mock_supabase = MockSupabaseClient(config.supabase.products_table)
                    self.supabase_clients[config.tenant_id] = mock_supabase
                
            # Real embedding model (shared across tenants using same model)
            model_name = config.embedding.model_name
            if model_name not in self.embedding_models:
                logger.info(f"Loading embedding model: {model_name}")
                try:
                    # For now, use a lighter model for testing
                    # In production, use: self.embedding_models[model_name] = SentenceTransformer(model_name)
                    self.embedding_models[model_name] = SentenceTransformer('all-MiniLM-L6-v2')
                    logger.info(f"Successfully loaded embedding model: {model_name}")
                except Exception as e:
                    logger.error(f"Failed to load embedding model {model_name}: {e}")
                    # Fallback to a minimal model
                    self.embedding_models[model_name] = MockEmbeddingModel()
                
            return (
                self.pinecone_clients[config.tenant_id],
                self.supabase_clients[config.tenant_id], 
                self.embedding_models[model_name]
            )
            
        except Exception as e:
            logger.error(f"Failed to create clients for tenant {config.tenant_id}: {e}")
            raise
    
    async def close_tenant_clients(self, tenant_id: str):
        """Close and cleanup clients for a tenant"""
        if tenant_id in self.pinecone_clients:
            # Close Pinecone client if needed
            del self.pinecone_clients[tenant_id]
            
        if tenant_id in self.supabase_clients:
            # Close Supabase client if needed
            del self.supabase_clients[tenant_id]
            
        logger.info(f"Closed clients for tenant: {tenant_id}")


# Mock clients for testing (remove in production)
class MockPineconeClient:
    """Mock Pinecone client for testing"""
    
    def __init__(self, index_name: str):
        self.index_name = index_name
        logger.info(f"Mock Pinecone client created for index: {index_name}")
    
    def query(self, vector, top_k=10, include_metadata=True, filter=None, namespace=None):
        """Mock vector query"""
        logger.info(f"Mock Pinecone query: top_k={top_k}, filter={filter}")
        
        # Return mock results
        mock_results = MockPineconeResults([
            {"id": "prod_001", "score": 0.95, "metadata": {"category": "shoes", "brand": "nike", "price": 150}},
            {"id": "prod_002", "score": 0.87, "metadata": {"category": "shoes", "brand": "adidas", "price": 180}},
            {"id": "prod_003", "score": 0.82, "metadata": {"category": "clothing", "brand": "nike", "price": 35}}
        ])
        
        return mock_results


class MockPineconeResults:
    """Mock Pinecone query results"""
    
    def __init__(self, matches_data):
        self.matches = [MockPineconeMatch(data) for data in matches_data]


class MockPineconeMatch:
    """Mock Pinecone match result"""
    
    def __init__(self, data):
        self.id = data["id"]
        self.score = data["score"]
        self.metadata = data["metadata"]


class MockSupabaseClient:
    """Mock Supabase client for testing"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        logger.info(f"Mock Supabase client created for table: {table_name}")
        
        # Mock product data
        self.mock_products = [
            {
                "id": "prod_001",
                "name": "Nike Air Max 270",
                "description": "Comfortable running shoes with Air Max cushioning",
                "price": 150.00,
                "category": "shoes",
                "brand": "nike",
                "color": "red",
                "size": "10",
                "image_url": "https://example.com/nike-air-max.jpg",
                "in_stock": True
            },
            {
                "id": "prod_002", 
                "name": "Adidas Ultraboost 22",
                "description": "Premium running shoes with Boost technology",
                "price": 180.00,
                "category": "shoes",
                "brand": "adidas", 
                "color": "blue",
                "size": "10",
                "image_url": "https://example.com/adidas-ultraboost.jpg",
                "in_stock": True
            },
            {
                "id": "prod_003",
                "name": "Nike Pro T-Shirt",
                "description": "Moisture-wicking athletic t-shirt", 
                "price": 35.00,
                "category": "clothing",
                "brand": "nike",
                "color": "black",
                "size": "L",
                "image_url": "https://example.com/nike-tshirt.jpg",
                "in_stock": True
            }
        ]
    
    def table(self, table_name: str):
        """Return a mock table interface"""
        return MockSupabaseTable(self.mock_products)


class MockSupabaseTable:
    """Mock Supabase table interface"""
    
    def __init__(self, products):
        self.products = products
        self.query_filters = []
    
    def select(self, fields="*"):
        """Mock select operation"""
        return self
    
    def in_(self, field, values):
        """Mock 'in' filter"""
        self.query_filters.append(("in", field, values))
        return self
    
    def gte(self, field, value):
        """Mock greater than or equal filter"""
        self.query_filters.append(("gte", field, value))
        return self
    
    def lte(self, field, value):
        """Mock less than or equal filter"""
        self.query_filters.append(("lte", field, value))
        return self
    
    def execute(self):
        """Mock query execution"""
        filtered_products = self.products[:]
        
        # Apply filters
        for filter_type, field, value in self.query_filters:
            if filter_type == "in":
                filtered_products = [p for p in filtered_products if p.get(field) in value]
            elif filter_type == "gte":
                filtered_products = [p for p in filtered_products if p.get(field, 0) >= value]
            elif filter_type == "lte":
                filtered_products = [p for p in filtered_products if p.get(field, float('inf')) <= value]
        
        return MockSupabaseResult(filtered_products)


class MockSupabaseResult:
    """Mock Supabase query result"""
    
    def __init__(self, data):
        self.data = data


class MockEmbeddingModel:
    """Mock embedding model for fallback"""
    
    def encode(self, texts, **kwargs):
        """Return mock embeddings"""
        import numpy as np
        if isinstance(texts, str):
            texts = [texts]
        # Return random embeddings for testing
        return np.random.rand(len(texts), 384).astype(np.float32)