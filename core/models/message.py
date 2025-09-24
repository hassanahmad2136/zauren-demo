# core/models/message.py
"""
Core message models for the retail AI platform
Handles text, audio, images, and other media types
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

class ProcessingResult(BaseModel):
    """Result from message processing"""
    message_id: str
    status: str
    processing_time_ms: float
    response: Optional[str] = None
    error: Optional[str] = None