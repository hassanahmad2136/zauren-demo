import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "WEBHOOK_SECRET": "test_secret"
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_webhook_verification(client):
    """Test webhook verification endpoint."""
    # Test with correct token
    response = client.get('/webhook?hub.verify_token=test_token&hub.challenge=challenge_accepted')
    assert response.status_code == 200
    assert response.data == b'challenge_accepted'
    
    # Test with incorrect token
    response = client.get('/webhook?hub.verify_token=wrong_token&hub.challenge=challenge')
    assert response.status_code == 403
