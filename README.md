# Retail AI Platform

A scalable conversational AI system for retailers supporting multi-channel messaging (WhatsApp, Web, Mobile) with intelligent agents for intent classification, RAG, cart management, and customer support.

## Quick Start

`ash
# Setup development environment
pip install -e .
python scripts/setup_tenant.py --tenant retail_demo

# Run individual services
python -m apps.message_bus.main
python -m apps.orchestrator.main
python -m agents.intent.main
`

## Architecture

See docs/architecture/ for detailed system design and component interactions.
