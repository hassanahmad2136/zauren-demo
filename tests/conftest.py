"""
Basic test configuration and fixtures.
"""

import pytest
import asyncio
from typing import Generator

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_message():
    """Sample canonical message for testing."""
    return {
        "user_id": "test_user_123",
        "tenant_id": "test_tenant",
        "channel": "whatsapp", 
        "channel_user_id": "+1234567890",
        "content": "I want to buy a red dress",
        "timestamp": "2024-01-01T10:00:00Z",
        "metadata": {}
    }
