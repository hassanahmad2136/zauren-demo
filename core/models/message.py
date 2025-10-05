# core/models/message.py
"""
Core message models for the retail AI platform
Handles text, audio, images, and other media types
Includes UserContext with search entity and AgentResponse
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class MessageType(str):
    """Message types"""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"

class MediaAttachment(BaseModel):
    """Media attachment information"""
    type: str = Field(..., description="Media type (audio, image, video, document)")
    url: Optional[str] = Field(None, description="URL to download media")
    filename: Optional[str] = Field(None, description="Original filename")
    mime_type: Optional[str] = Field(None, description="MIME type")
    size_bytes: Optional[int] = Field(None, description="File size")
    duration_seconds: Optional[float] = Field(None, description="Duration for audio/video")
    transcription: Optional[str] = Field(None, description="Transcription for audio messages")
    extracted_text: Optional[str] = Field(None, description="Extracted text from image/document")

class CanonicalMessage(BaseModel):
    """
    Standardized message format used throughout the system
    All channels normalize to this format
    """
    user_id: str = Field(..., description="Unique user identifier")
    tenant_id: str = Field(..., description="Tenant/retailer identifier")
    channel: str = Field(..., description="Source channel (whatsapp, web, etc)")
    channel_user_id: str = Field(..., description="Channel-specific user ID")
    
    # Content can be empty for media-only messages
    content: str = Field(default="", description="Text content (empty for media-only messages)")
    
    # Message type and media handling
    message_type: str = Field(default=MessageType.TEXT, description="Type of message")
    media_attachments: List[MediaAttachment] = Field(default_factory=list, description="Media attachments")
    
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional channel-specific data")
    
    @property
    def has_media(self) -> bool:
        """Check if message has media attachments"""
        return len(self.media_attachments) > 0
    
    @property
    def has_text(self) -> bool:
        """Check if message has text content"""
        return bool(self.content.strip())
    
    @property
    def display_content(self) -> str:
        """Get displayable content for logging/UI"""
        if self.has_text:
            return self.content
        elif self.has_media:
            media_types = [att.type for att in self.media_attachments]
            return f"[Media: {', '.join(media_types)}]"
        else:
            return "[Empty message]"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SearchEntity(BaseModel):
    """
    Standalone search entity for better type checking
    Used for product search and filtering
    """
    query: str = Field(default="", description="Refined search query")
    category: Optional[str] = None
    brand: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    style: Optional[str] = None
    material: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    referenced_item_id: Optional[str] = None
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Media-based search
    image_search: Optional[Dict[str, Any]] = Field(
        None, 
        description="Visual search parameters from uploaded images"
    )
    voice_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Preferences extracted from voice messages"
    )
    
    # Search metadata
    last_updated: datetime = Field(default_factory=datetime.now)
    search_history: List[str] = Field(default_factory=list)
    
    def merge_with(self, updates: Dict[str, Any]) -> "SearchEntity":
        """Merge updates into the search entity"""
        for field, value in updates.items():
            if value is not None:
                if field == "query" and hasattr(self, field) and getattr(self, field):
                    # Append to query instead of replacing
                    current = getattr(self, field)
                    setattr(self, field, f"{current} {value}".strip())
                elif field == "custom_attributes":
                    # Merge custom attributes
                    self.custom_attributes.update(value)
                elif field == "search_history":
                    # Append to history
                    self.search_history.extend(value if isinstance(value, list) else [value])
                elif hasattr(self, field):
                    setattr(self, field, value)
        
        self.last_updated = datetime.now()
        return self
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserContext(BaseModel):
    """
    Complete user context including conversation state, preferences, and search entity
    """
    user_id: str
    tenant_id: str
    session_id: str
    
    # Conversation context
    conversation_context: Dict[str, Any] = Field(default_factory=dict)
    session_data: Dict[str, Any] = Field(default_factory=dict)
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Search entity - accumulates across messages
    search_entity: Dict[str, Any] = Field(default_factory=lambda: {
        "query": "",
        "category": None,
        "brand": None,
        "color": None,
        "size": None,
        "style": None,
        "material": None,
        "min_price": None,
        "max_price": None,
        "referenced_item_id": None,
        "custom_attributes": {}
    })
    
    # Shopping cart
    current_cart: Dict[str, Any] = Field(default_factory=lambda: {
        "items": [],
        "total": 0.0,
        "currency": "USD"
    })
    
    # User preferences
    preferences: Dict[str, Any] = Field(default_factory=lambda: {
        "preferred_language": "en",
        "currency": "USD",
        "size_preference": None,
        "brand_preferences": [],
        "color_preferences": [],
        "style_preferences": [],
        "price_range": {"min": None, "max": None},
        "media_preferences": {
            "send_images": True,
            "voice_messages": True,
            "video_calls": False
        }
    })
    
    # Recent media for context
    recent_media: List[MediaAttachment] = Field(default_factory=list)
    
    # Timestamp
    last_updated: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentResponse(BaseModel):
    """
    Standard response format from agents
    Supports multi-modal responses
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: int
    agent_name: str
    
    # Response content
    text_response: Optional[str] = None
    media_responses: List[MediaAttachment] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[str] = None
    confidence: Optional[float] = None
    
    # For product searches
    products: Optional[List[Dict[str, Any]]] = None
    total_products_found: Optional[int] = None
    
    # For cart operations
    cart_update: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ProcessingResult(BaseModel):
    """Result from message processing"""
    message_id: str
    status: str
    processing_time_ms: float
    response: Optional[str] = None
    media_responses: List[MediaAttachment] = Field(default_factory=list)
    error: Optional[str] = None
    
    # Language and intent info
    detected_language: Optional[str] = None
    detected_intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    
    # Agents involved
    agents_used: List[str] = Field(default_factory=list)
    
    # Session info
    session_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }