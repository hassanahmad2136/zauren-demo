import hashlib
import hmac
import os
from flask import Request

def verify_webhook_signature(request: Request) -> bool:
    """
    Verify the signature of an incoming webhook request.
    
    Args:
        request (Request): The Flask request object
    
    Returns:
        bool: True if signature is valid or no signature verification is required
    """
    # Get the signature from header
    signature = request.headers.get('X-Hub-Signature')
    webhook_secret = os.environ.get('WEBHOOK_SECRET')
    
    # If no signature or secret is provided, skip verification
    if not signature or not webhook_secret:
        return True
    
    # Create expected signature
    payload = request.get_data()
    expected_signature = 'sha1=' + hmac.new(
        webhook_secret.encode('utf-8'),
        payload,
        hashlib.sha1
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)
