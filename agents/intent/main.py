"""
Intent Classification Agent
Classifies user messages into retail intents (product_search, cart_add, support, etc.)
"""

from fastapi import FastAPI

app = FastAPI(
    title="Retail AI - Intent Agent",
    description="Intent classification for retail conversations", 
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "intent_agent"}

@app.post("/classify")
async def classify_intent():
    return {"intent": "product_search", "confidence": 0.95}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
