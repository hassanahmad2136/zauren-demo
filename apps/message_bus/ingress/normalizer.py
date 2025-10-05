# apps/message_bus/ingress/normalizer.py
"""
Message normalizers for different channels
Converts raw channel data to CanonicalMessage format
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request

from core.models.message import CanonicalMessage

class MessageNormalizer:
    """Normalizes messages from different channels to CanonicalMessage format"""
    
    async def normalize_whatsapp(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize WhatsApp Business API webhook to CanonicalMessage
        
        WhatsApp format:
        {
            "messages": [{
                "from": "1234567890",
                "body": "Hello world",  # Only for text messages
                "timestamp": "1234567890",
                "id": "wamid.xxx",
                "type": "text|audio|image|video|document",
                "audio": {"id": "media_id", "mime_type": "audio/ogg"},
                "image": {"id": "media_id", "mime_type": "image/jpeg", "caption": "Photo caption"}
            }],
            "contacts": [{
                "profile": {"name": "John Doe"},
                "wa_id": "1234567890"
            }]
        }
        """
        try:
            message = raw_data["messages"][0]
            contact = raw_data.get("contacts", [{}])[0]
            
            # Handle different message types
            content = ""
            message_type = message.get("type", "text")
            media_attachments = []
            
            if message_type == "text":
                content = message.get("body", "")
            
            elif message_type == "image":
                content = message.get("image", {}).get("caption", "")
                image_data = message.get("image", {})
                media_attachments.append(MediaAttachment(
                    type="image",
                    url=None,  # WhatsApp requires separate API call to get URL
                    filename=None,
                    mime_type=image_data.get("mime_type"),
                    size_bytes=None
                ))
            
            elif message_type == "audio":
                content = ""  # Audio messages typically have no text
                audio_data = message.get("audio", {})
                media_attachments.append(MediaAttachment(
                    type="audio",
                    url=None,  # WhatsApp requires separate API call
                    filename=None,
                    mime_type=audio_data.get("mime_type"),
                    size_bytes=None,
                    duration_seconds=audio_data.get("duration")
                ))
            
            elif message_type == "video":
                content = message.get("video", {}).get("caption", "")
                video_data = message.get("video", {})
                media_attachments.append(MediaAttachment(
                    type="video",
                    url=None,
                    filename=None,
                    mime_type=video_data.get("mime_type"),
                    size_bytes=None,
                    duration_seconds=video_data.get("duration")
                ))
            
            elif message_type == "document":
                content = message.get("document", {}).get("caption", "")
                doc_data = message.get("document", {})
                media_attachments.append(MediaAttachment(
                    type="document",
                    url=None,
                    filename=doc_data.get("filename"),
                    mime_type=doc_data.get("mime_type"),
                    size_bytes=None
                ))
            
            elif message_type == "location":
                location = message.get("location", {})
                content = f"Location: {location.get('name', 'Unknown location')}"
            
            else:
                content = f"[{message_type.title()} message]"
            
            return CanonicalMessage(
                user_id=f"whatsapp_{message['from']}",
                tenant_id=tenant_id,
                channel="whatsapp",
                channel_user_id=message["from"],
                content=content,
                message_type=message_type,
                media_attachments=media_attachments,
                timestamp=datetime.fromtimestamp(int(message.get("timestamp", datetime.now().timestamp()))),
                metadata={
                    "contact_name": contact.get("profile", {}).get("name"),
                    "contact_wa_id": contact.get("wa_id"),
                    "message_id": message.get("id"),
                    "whatsapp_media_ids": [
                        att.metadata.get("whatsapp_id") for att in media_attachments 
                        if att.metadata.get("whatsapp_id")
                    ],
                    "raw_message": message  # Keep original for debugging
                }
            )
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Invalid WhatsApp message format: {e}")
    
    async def normalize_web(self, raw_data: Dict[str, Any], tenant_id: str, request: Request) -> CanonicalMessage:
        """
        Normalize web widget data to CanonicalMessage
        
        Web format:
        {
            "session_id": "web_session_123",
            "message": "I need help with my order",
            "user_info": {
                "email": "john@example.com",
                "name": "John Doe",
                "user_id": "registered_user_456"
            },
            "page_info": {
                "url": "https://store.com/products/shoes",
                "title": "Nike Shoes - Store",
                "referrer": "https://google.com"
            }
        }
        """
        try:
            session_id = raw_data["session_id"]
            user_info = raw_data.get("user_info", {})
            page_info = raw_data.get("page_info", {})
            
            # Prefer registered user ID over session ID
            user_id = user_info.get("user_id", f"web_{session_id}")
            
            return CanonicalMessage(
                user_id=user_id,
                tenant_id=tenant_id,
                channel="web",
                channel_user_id=session_id,
                content=raw_data["message"],
                timestamp=datetime.now(),
                metadata={
                    "user_email": user_info.get("email"),
                    "user_name": user_info.get("name"),
                    "session_id": session_id,
                    "page_url": page_info.get("url"),
                    "page_title": page_info.get("title"),
                    "referrer": page_info.get("referrer"),
                    "user_agent": request.headers.get("user-agent"),
                    "ip_address": request.client.host if request.client else None,
                    "browser_info": {
                        "language": request.headers.get("accept-language"),
                        "timezone": raw_data.get("timezone")
                    }
                }
            )
        except KeyError as e:
            raise ValueError(f"Missing required web field: {e}")
    
    async def normalize_facebook(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize Facebook Messenger webhook to CanonicalMessage
        
        Facebook format:
        {
            "messaging": [{
                "sender": {"id": "1234567890"},
                "recipient": {"id": "PAGE_ID"},
                "timestamp": 1234567890123,
                "message": {
                    "mid": "message_id",
                    "text": "Hello",
                    "attachments": [...]
                }
            }]
        }
        """
        try:
            messaging = raw_data["messaging"][0]
            message = messaging.get("message", {})
            
            # Handle different message types
            content = ""
            if "text" in message:
                content = message["text"]
            elif "attachments" in message:
                attachments = message["attachments"]
                attachment_types = [att.get("type", "unknown") for att in attachments]
                content = f"[Attachments: {', '.join(attachment_types)}]"
            else:
                content = "[Facebook message]"
            
            return CanonicalMessage(
                user_id=f"facebook_{messaging['sender']['id']}",
                tenant_id=tenant_id,
                channel="facebook",
                channel_user_id=messaging["sender"]["id"],
                content=content,
                timestamp=datetime.fromtimestamp(messaging["timestamp"] / 1000),
                metadata={
                    "recipient_id": messaging["recipient"]["id"],
                    "message_id": message.get("mid"),
                    "attachments": message.get("attachments", []),
                    "raw_messaging": messaging
                }
            )
        except (KeyError, IndexError) as e:
            raise ValueError(f"Invalid Facebook message format: {e}")
    
    async def normalize_telegram(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize Telegram bot webhook data to CanonicalMessage
        
        Telegram format:
        {
            "update_id": 123456,
            "message": {
                "message_id": 789,
                "from": {
                    "id": 987654321,
                    "is_bot": false,
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe"
                },
                "chat": {
                    "id": 987654321,
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe",
                    "type": "private"
                },
                "date": 1234567890,
                "text": "Hello bot"
            }
        }
        """
        try:
            message = raw_data["message"]
            from_user = message["from"]
            
            # Handle different content types
            content = ""
            if "text" in message:
                content = message["text"]
            elif "photo" in message:
                content = message.get("caption", "[Photo]")
            elif "document" in message:
                doc_name = message["document"].get("file_name", "document")
                content = f"[Document: {doc_name}]"
            elif "voice" in message:
                content = "[Voice message]"
            elif "video" in message:
                content = message.get("caption", "[Video]")
            elif "location" in message:
                loc = message["location"]
                content = f"[Location: {loc['latitude']}, {loc['longitude']}]"
            else:
                content = "[Telegram message]"
            
            return CanonicalMessage(
                user_id=f"telegram_{from_user['id']}",
                tenant_id=tenant_id,
                channel="telegram",
                channel_user_id=str(from_user["id"]),
                content=content,
                timestamp=datetime.fromtimestamp(message["date"]),
                metadata={
                    "telegram_user": {
                        "first_name": from_user.get("first_name"),
                        "last_name": from_user.get("last_name"),
                        "username": from_user.get("username"),
                        "is_bot": from_user.get("is_bot", False)
                    },
                    "chat_info": message["chat"],
                    "message_id": message["message_id"],
                    "update_id": raw_data["update_id"]
                }
            )
        except KeyError as e:
            raise ValueError(f"Invalid Telegram message format: {e}")
    
    async def normalize_instagram(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize Instagram messaging webhook data to CanonicalMessage
        
        Instagram format (similar to Facebook):
        {
            "messaging": [{
                "sender": {"id": "instagram_user_id"},
                "recipient": {"id": "instagram_page_id"},
                "timestamp": 1234567890123,
                "message": {
                    "mid": "message_id",
                    "text": "Hello on Instagram"
                }
            }]
        }
        """
        try:
            messaging = raw_data["messaging"][0]
            message = messaging.get("message", {})
            
            content = message.get("text", "[Instagram message]")
            
            return CanonicalMessage(
                user_id=f"instagram_{messaging['sender']['id']}",
                tenant_id=tenant_id,
                channel="instagram",
                channel_user_id=messaging["sender"]["id"],
                content=content,
                timestamp=datetime.fromtimestamp(messaging["timestamp"] / 1000),
                metadata={
                    "recipient_id": messaging["recipient"]["id"],
                    "message_id": message.get("mid"),
                    "platform": "instagram"
                }
            )
        except (KeyError, IndexError) as e:
            raise ValueError(f"Invalid Instagram message format: {e}")
    
    async def normalize_sms(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize SMS (Twilio) webhook data to CanonicalMessage
        
        Twilio SMS format:
        {
            "From": "+1234567890",
            "To": "+0987654321", 
            "Body": "Hello via SMS",
            "MessageSid": "SM1234567890abcdef",
            "AccountSid": "AC1234567890abcdef",
            "NumMedia": "0"
        }
        """
        try:
            from_number = raw_data["From"]
            
            return CanonicalMessage(
                user_id=f"sms_{from_number.replace('+', '').replace(' ', '')}",
                tenant_id=tenant_id,
                channel="sms",
                channel_user_id=from_number,
                content=raw_data.get("Body", ""),
                timestamp=datetime.now(),  # Twilio doesn't provide timestamp in webhook
                metadata={
                    "to_number": raw_data.get("To"),
                    "message_sid": raw_data.get("MessageSid"),
                    "account_sid": raw_data.get("AccountSid"),
                    "num_media": raw_data.get("NumMedia", "0"),
                    "media_urls": [
                        raw_data.get(f"MediaUrl{i}") 
                        for i in range(int(raw_data.get("NumMedia", "0")))
                        if raw_data.get(f"MediaUrl{i}")
                    ]
                }
            )
        except KeyError as e:
            raise ValueError(f"Missing required SMS field: {e}")
    
    async def normalize_console(self, raw_data: Dict[str, Any], tenant_id: str) -> CanonicalMessage:
        """
        Normalize console input to CanonicalMessage (for testing)
        
        Console format:
        {
            "user_id": "console_user_001",
            "content": "I want to buy shoes",
            "metadata": {"source": "console", "test_mode": true}
        }
        """
        try:
            user_id = raw_data.get("user_id", f"console_user_{uuid.uuid4().hex[:8]}")
            
            return CanonicalMessage(
                user_id=user_id,
                tenant_id=tenant_id,
                channel="console",
                channel_user_id=user_id,
                content=raw_data["content"],
                timestamp=datetime.now(),
                metadata={
                    "source": "console",
                    "test_mode": True,
                    **raw_data.get("metadata", {})
                }
            )
        except KeyError as e:
            raise ValueError(f"Missing required console field: {e}")
    
    def _extract_user_info(self, raw_data: Dict[str, Any], channel: str) -> Dict[str, Any]:
        """Extract common user information across channels"""
        user_info = {}
        
        # Channel-specific user info extraction
        if channel == "whatsapp":
            contacts = raw_data.get("contacts", [{}])
            if contacts:
                profile = contacts[0].get("profile", {})
                user_info["name"] = profile.get("name")
                user_info["wa_id"] = contacts[0].get("wa_id")
        
        elif channel == "telegram":
            from_user = raw_data.get("message", {}).get("from", {})
            user_info["first_name"] = from_user.get("first_name")
            user_info["last_name"] = from_user.get("last_name")
            user_info["username"] = from_user.get("username")
        
        return user_info
    
    def _detect_message_intent_hints(self, content: str) -> Dict[str, Any]:
        """Extract basic intent hints from message content"""
        content_lower = content.lower()
        hints = {}
        
        # Simple keyword detection
        if any(word in content_lower for word in ["buy", "purchase", "order", "cart", "checkout"]):
            hints["likely_intent"] = "purchase"
        elif any(word in content_lower for word in ["help", "support", "problem", "issue"]):
            hints["likely_intent"] = "support"
        elif any(word in content_lower for word in ["track", "status", "where", "delivery"]):
            hints["likely_intent"] = "order_status"
        elif any(word in content_lower for word in ["return", "refund", "exchange"]):
            hints["likely_intent"] = "return"
        
        # Detect urgency
        if any(word in content_lower for word in ["urgent", "asap", "emergency", "immediately"]):
            hints["urgency"] = "high"
        
        return hints