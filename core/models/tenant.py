# core/models/tenant.py
"""
Multi-tenant configuration models for the retail AI platform
Each tenant has isolated Pinecone indexes, Supabase databases, and custom schemas
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class TenantPineconeConfig(BaseModel):
    """Pinecone configuration per tenant - using 7.2.0+ serverless"""
    api_key: str = Field(..., description="Tenant's Pinecone API key")
    index_name: str = Field(..., description="Tenant's Pinecone index name")
    namespace: Optional[str] = Field(None, description="Optional namespace within index")
    dimension: int = Field(1024, description="Embedding dimension (multilingual-e5-large = 1024)")
    metric: str = Field("cosine", description="Distance metric for similarity search")
    metadata_fields: List[str] = Field(default_factory=list, description="Filterable metadata fields")

class TenantSupabaseConfig(BaseModel):
    """Supabase configuration per tenant"""
    url: str = Field(..., description="Tenant's Supabase project URL")
    api_key: str = Field(..., description="Tenant's Supabase API key (service_role key)")
    products_table: str = Field("products", description="Products table name")
    schema_name: str = Field("public", description="Database schema name")
    
class TenantProductSchema(BaseModel):
    """Dynamic product schema configuration per tenant"""
    
    # Core fields that all tenants must have
    required_fields: Dict[str, str] = Field(
        default_factory=lambda: {
            "id": "text",
            "name": "text", 
            "description": "text",
            "price": "numeric",
            "category": "text",
            "brand": "text",
            "image_url": "text",
            "in_stock": "boolean",
            "created_at": "timestamp",
            "updated_at": "timestamp"
        },
        description="Required fields that all tenants must have"
    )
    
    # Custom fields specific to each tenant's business
    custom_fields: Dict[str, str] = Field(
        default_factory=dict, 
        description="Custom fields per tenant (field_name -> data_type)"
    )
    
    # Mapping from search_entity fields to database columns
    search_field_mappings: Dict[str, str] = Field(
        default_factory=lambda: {
            "category": "category",
            "brand": "brand", 
            "color": "color",
            "size": "size",
            "style": "style",
            "material": "material",
            "min_price": "price",
            "max_price": "price"
        },
        description="Maps search_entity fields to database columns"
    )
    
    # Available filter options for each tenant
    filter_options: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Available filter values per field (e.g., categories, brands, colors)"
    )
    
    # Display settings
    display_fields: List[str] = Field(
        default_factory=lambda: ["name", "price", "category", "brand", "image_url"],
        description="Fields to return in search results"
    )

class TenantEmbeddingConfig(BaseModel):
    """Embedding model configuration per tenant"""
    model_name: str = Field(
        "intfloat/multilingual-e5-large",
        description="HuggingFace model name for embeddings"
    )
    dimension: int = Field(1024, description="Embedding vector dimension")
    batch_size: int = Field(32, description="Batch size for embedding generation")
    
    # E5 model requires specific prefixes
    query_prefix: str = Field("query: ", description="Prefix for search queries")
    document_prefix: str = Field("passage: ", description="Prefix for documents")
    
    # Performance settings
    max_length: int = Field(512, description="Maximum token length for embeddings")
    normalize_embeddings: bool = Field(True, description="Whether to normalize embeddings")

class TenantSearchConfig(BaseModel):
    """Search behavior configuration per tenant"""
    max_results: int = Field(20, description="Maximum results to return")
    similarity_threshold: float = Field(0.7, description="Minimum similarity score")
    enable_reranking: bool = Field(True, description="Whether to apply reranking")
    
    # Price range defaults for this tenant
    default_price_range: Dict[str, Optional[float]] = Field(
        default_factory=lambda: {"min": None, "max": None},
        description="Default price range for searches"
    )
    
    # Search weights for different fields
    field_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "name": 1.5,
            "description": 1.0, 
            "category": 1.2,
            "brand": 1.3
        },
        description="Weights for different fields in search scoring"
    )

class TenantConfiguration(BaseModel):
    """Complete tenant configuration combining all settings"""
    
    # Tenant identification
    tenant_id: str = Field(..., description="Unique tenant identifier")
    tenant_name: str = Field(..., description="Human-readable tenant name")
    tenant_description: Optional[str] = Field(None, description="Tenant description")
    
    # External service configurations
    pinecone: TenantPineconeConfig = Field(..., description="Pinecone vector database config")
    supabase: TenantSupabaseConfig = Field(..., description="Supabase database config")
    
    # AI and search configurations
    embedding: TenantEmbeddingConfig = Field(
        default_factory=TenantEmbeddingConfig,
        description="Embedding model configuration"
    )
    search: TenantSearchConfig = Field(
        default_factory=TenantSearchConfig,
        description="Search behavior configuration"
    )
    
    # Business-specific configurations
    product_schema: TenantProductSchema = Field(
        default_factory=TenantProductSchema,
        description="Product schema and field mappings"
    )
    
    # Caching and performance
    cache_ttl_seconds: int = Field(300, description="Cache TTL in seconds (5 minutes)")
    enable_caching: bool = Field(True, description="Whether to enable Redis caching")
    
    # Rate limiting per tenant
    rate_limit_per_minute: int = Field(100, description="API calls per minute per tenant")
    rate_limit_per_hour: int = Field(1000, description="API calls per hour per tenant")
    
    # Status and metadata
    is_active: bool = Field(True, description="Whether tenant is active")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Additional tenant-specific metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional tenant-specific configuration"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now()
        
    def get_search_fields(self) -> List[str]:
        """Get all searchable fields for this tenant"""
        base_fields = list(self.product_schema.required_fields.keys())
        custom_fields = list(self.product_schema.custom_fields.keys())
        return base_fields + custom_fields
    
    def get_filterable_fields(self) -> List[str]:
        """Get fields that can be used for filtering"""
        return self.pinecone.metadata_fields
    
    def validate_search_entity(self, search_entity: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean search entity based on tenant schema"""
        valid_entity = {}
        
        # Only include fields that are mapped in the schema
        for field, value in search_entity.items():
            if field in self.product_schema.search_field_mappings and value is not None:
                valid_entity[field] = value
                
        return valid_entity