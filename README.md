# Webhook Project

A Python-based webhook implementation using Flask.

## Setup

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and set your environment variables
5. Run the application:
   ```
   python run.py
   ```

## Testing Webhooks Locally

Visit `http://localhost:5000/test-webhook` to test your webhook implementation locally.

## Exposing Webhooks for Development

Use a tool like ngrok to expose your local server to the internet:

```
ngrok http 5000
```

Your webhook URL will be the ngrok URL provided + `/webhook`, for example:
`https://a1b2c3d4.ngrok.io/webhook`

## Running Tests

```
pytest
```
