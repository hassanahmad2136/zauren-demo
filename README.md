# Zauren WhatsApp E-commerce Bot

A production-ready WhatsApp chatbot for e-commerce built with Flask, OpenAI, and advanced AI capabilities.

## Features

- 🤖 **AI-Powered Conversations** - GPT-4 powered natural language understanding
- 🛍️ **Product Search & Recommendations** - Semantic search using embeddings
- 🛒 **Shopping Cart Management** - Add, remove, and manage cart items
- 💳 **Payment Integration** - OneLink payment processing
- 📱 **WhatsApp Integration** - Full WhatsApp Business API support
- 🔒 **Security** - GuardRails AI validation and security measures
- 🚀 **Production Ready** - Optimized for 30+ concurrent users

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd zauren-demo

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` file with your credentials:

```env
# WhatsApp API
WHATSAPP_ACCESS_TOKEN=your_whatsapp_access_token
WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Database
INVENTORY_SUPABASE_URL=https://your-project.supabase.co
INVENTORY_SUPABASE_KEY=your_supabase_key

# Vector Database
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_index_name

# Payment Processing
ONELINK_MERCHANT_ALIAS=your_merchant_alias
ONELINK_MERCHANT_SECRET=your_merchant_secret
```

### 3. Run the Application

**Development:**
```bash
python run.py
```

**Production:**
```bash
python run_production.py
```

## Architecture

### Core Components

- **`app/`** - Main application package
  - **`routes/`** - Flask routes and webhook handlers
  - **`services/`** - Business logic and AI services
  - **`utils/`** - Utility functions and helpers
- **`config/`** - Configuration management
- **`1link/`** - Payment processing integration

### Key Services

- **`webhook_service.py`** - Handles incoming WhatsApp messages
- **`LLM.py`** - AI conversation management
- **`embeddings.py`** - Product semantic search
- **`cart_manager.py`** - Shopping cart operations
- **`messaging_service.py`** - WhatsApp message sending

## API Endpoints

- **`GET /webhook`** - Webhook verification
- **`POST /webhook`** - Message processing
- **`GET /test-webhook`** - Test interface (development)

## Performance

Optimized for high-concurrency scenarios:
- **50 threads** for concurrent request handling
- **1000 connection limit**
- Background webhook processing
- Database connection pooling
- Optimized AI inference

## Dependencies

### Core Framework
- Flask 2.3+ - Web framework
- Waitress 2.1+ - Production WSGI server

### AI & Machine Learning
- OpenAI 1.0+ - GPT-4 integration
- sentence-transformers 2.2+ - Embeddings
- GuardRails AI 0.6+ - Response validation

### Database & Storage
- Supabase 1.0+ - PostgreSQL database
- Pinecone 3.0+ - Vector database

### External APIs
- WhatsApp Business API
- OneLink Payment API
- Groq API (audio transcription)

## Deployment

### Windows Production Server

The application is optimized for Windows deployment using Waitress:

```bash
# Set production environment
set SKIP_EMBEDDINGS_ON_STARTUP=true

# Start production server
python run_production.py
```

### Environment Variables for Production

```env
PORT=5000
FLASK_ENV=production
SKIP_EMBEDDINGS_ON_STARTUP=false
FORCE_REGENERATE_EMBEDDINGS=false
```

## Security

- **Input Validation** - All user inputs are validated
- **GuardRails AI** - Prevents AI hallucination and inappropriate responses
- **Token-based Authentication** - Secure webhook verification
- **Rate Limiting** - Built-in request throttling

## Monitoring & Logging

- Structured logging with timestamps
- Request/response debugging
- Error tracking and reporting
- Performance metrics

## Support

For issues and questions, please check the documentation or contact the development team.

## License

[Add your license information here]