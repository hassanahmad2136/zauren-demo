import pytest
from app.services.webhook_service import process_webhook_event

def test_process_message_event(caplog):
    """Test processing a message event."""
    # Sample message event
    data = {
        "type": "message",
        "message": {"text": "Hello webhook"},
        "sender": {"id": "user123"}
    }
    
    # Process the event
    process_webhook_event(data)
    
    # Check that the message was logged correctly
    assert "Processing message from user123: Hello webhook" in caplog.text
