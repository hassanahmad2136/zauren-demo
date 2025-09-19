from flask import Blueprint, request, abort, render_template, jsonify
from app.services.webhook_service import process_webhook_event
from app.utils.security import verify_webhook_signature
import os
import threading
import logging

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Handle the webhook verification request.
    This endpoint is used when the webhook is first registered with the service.
    """
    # Check if token parameter matches our verification token
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if token is None or challenge is None:
        return 'Missing parameters', 400
        
    if token == os.environ.get('WEBHOOK_VERIFY_TOKEN', 'your_verification_token_here'):
        # If verification is successful, return the challenge
        return challenge
    else:
        # If verification fails, return 403 Forbidden
        abort(403)

@webhook_bp.route('/webhook', methods=['POST'])
def webhook_handler():
    """
    Handle incoming webhook events.
    This endpoint receives the actual webhook payloads.
    Uses background processing for better concurrency.
    """
    try:
        # if not verify_webhook_signature(request):
        #     abort(403)

        # Get webhook data
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        logger.info(f"Received webhook data: {data}")

        # Process webhook in background thread for better concurrency
        def background_process():
            try:
                process_webhook_event(data)
            except Exception as e:
                logger.error(f"Error processing webhook in background: {e}")

        thread = threading.Thread(target=background_process, daemon=True)
        thread.start()

        # Return immediately to improve response time
        return jsonify({'status': 'received'}), 200

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@webhook_bp.route('/test-webhook', methods=['GET'])
def test_webhook_form():
    """Display a form to test the webhook locally"""
    return render_template('test_webhook.html')

@webhook_bp.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Process the test webhook form submission"""
    import json
    
    event_type = request.form.get('event_type', 'message')
    payload = request.form.get('payload', '{}')
    
    try:
        data = json.loads(payload)
        data['type'] = event_type
        
        # Process the webhook event
        process_webhook_event(data)
        
        return f"Successfully processed test webhook of type: {event_type}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON payload", 400
