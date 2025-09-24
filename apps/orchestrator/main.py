"""
Main FastAPI application for the LangGraph Orchestrator.
Manages workflow execution and agent coordination.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Retail AI - Orchestrator", 
    description="LangGraph workflow orchestrator for retail AI agents",
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator"}

@app.post("/workflows/retail")
async def execute_retail_workflow():
    return {"message": "Retail workflow executed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
