from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime
import json

from fastapi.middleware.cors import CORSMiddleware
from src.middleware.request_context import RequestContextMiddleware
from src.api.routes.workflows import router as workflow_router
from src.api.routes.auth import router as auth_router
from src.storage.database import database

app = FastAPI(title="Canva-NotebookLM Integration Prototype",
              description="Prototype API for integrating Canva and NotebookLM",
              version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request context middleware
app.add_middleware(RequestContextMiddleware)

# Register API routers
app.include_router(workflow_router)
app.include_router(auth_router)
# Initialize database on startup/shutdown
@app.on_event("startup")
async def on_startup():
    await database.connect()
    # Create tables for development/testing if migrations aren't applied
    try:
        await database.create_tables()
    except Exception:
        # Ignore if tables already exist or migrations manage schema
        pass


@app.on_event("shutdown")
async def on_shutdown():
    await database.disconnect()

# Mock database for storing requests and responses
request_db = {}
response_db = {}

class ContentRequest(BaseModel):
    canva_design_id: str
    notebooklm_source_id: str
    transformation_type: str  # e.g., "text_to_image", "image_to_text", "layout_generation"
    content_data: Dict[str, Any]
    priority: int = 1

class AuthRequest(BaseModel):
    canva_auth_token: str
    notebooklm_auth_token: str

class TransformationResult(BaseModel):
    request_id: str
    status: str
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str

@app.post("/authenticate")
async def authenticate(auth_data: AuthRequest):
    """
    Authenticate with both Canva and NotebookLM APIs
    """
    # In a real implementation, this would validate tokens with both APIs
    # For prototype, we'll just store them
    auth_id = str(uuid.uuid4())
    request_db[auth_id] = {
        "type": "auth",
        "canva_token": auth_data.canva_auth_token,
        "notebooklm_token": auth_data.notebooklm_auth_token,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "auth_id": auth_id,
        "status": "authenticated",
        "message": "Successfully authenticated with both platforms"
    }

@app.post("/transform")
async def request_transformation(
    request: ContentRequest,
    background_tasks: BackgroundTasks
):
    """
    Request content transformation between Canva and NotebookLM
    """
    request_id = str(uuid.uuid4())

    # Store the request
    request_db[request_id] = {
        "type": "transformation",
        "request_data": request.dict(),
        "status": "queued",
        "timestamp": datetime.now().isoformat()
    }

    # Add to background processing queue
    background_tasks.add_task(process_transformation, request_id, request)

    return {
        "request_id": request_id,
        "status": "queued",
        "message": "Transformation request added to queue"
    }

async def process_transformation(request_id: str, request: ContentRequest):
    """
    Background task to process the transformation
    """
    try:
        # Simulate processing delay
        await asyncio.sleep(2)

        # Update request status
        request_db[request_id]["status"] = "processing"

        # Simulate transformation processing
        # In a real implementation, this would call both APIs
        if request.transformation_type == "text_to_image":
            result = simulate_text_to_image(request.content_data)
        elif request.transformation_type == "image_to_text":
            result = simulate_image_to_text(request.content_data)
        elif request.transformation_type == "layout_generation":
            result = simulate_layout_generation(request.content_data)
        else:
            result = {"error": "Unknown transformation type"}

        # Store the result
        response_db[request_id] = {
            "request_id": request_id,
            "status": "completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

        request_db[request_id]["status"] = "completed"

    except Exception as e:
        response_db[request_id] = {
            "request_id": request_id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        request_db[request_id]["status"] = "failed"

def simulate_text_to_image(content_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate text-to-image transformation"""
    return {
        "transformation_type": "text_to_image",
        "input_text": content_data.get("text", ""),
        "generated_image_url": f"https://example.com/generated/{uuid.uuid4()}.png",
        "canva_design_update": {
            "elements": [
                {
                    "type": "image",
                    "url": f"https://example.com/generated/{uuid.uuid4()}.png",
                    "position": {"x": 100, "y": 100},
                    "size": {"width": 500, "height": 300}
                }
            ]
        }
    }

def simulate_image_to_text(content_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate image-to-text transformation"""
    return {
        "transformation_type": "image_to_text",
        "input_image_url": content_data.get("image_url", ""),
        "extracted_text": "This is sample text extracted from the image using NotebookLM's OCR capabilities.",
        "notebooklm_analysis": {
            "entities": ["sample", "text", "image", "OCR"],
            "summary": "The image contains text about sample content extraction using OCR technology."
        }
    }

def simulate_layout_generation(content_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate automatic layout generation"""
    return {
        "transformation_type": "layout_generation",
        "input_content": content_data.get("content", ""),
        "generated_layout": {
            "design_id": str(uuid.uuid4()),
            "elements": [
                {
                    "type": "text",
                    "content": "Main Title",
                    "position": {"x": 50, "y": 50},
                    "size": {"width": 600, "height": 100},
                    "style": {"font": "Arial", "size": 24, "weight": "bold"}
                },
                {
                    "type": "text",
                    "content": "Subtitle or description",
                    "position": {"x": 50, "y": 170},
                    "size": {"width": 600, "height": 50},
                    "style": {"font": "Arial", "size": 16}
                },
                {
                    "type": "image",
                    "url": "https://example.com/placeholder.png",
                    "position": {"x": 50, "y": 250},
                    "size": {"width": 300, "height": 200}
                }
            ]
        }
    }

@app.get("/status/{request_id}")
async def get_status(request_id: str):
    """
    Check the status of a transformation request
    """
    if request_id not in request_db:
        raise HTTPException(status_code=404, detail="Request not found")

    request_info = request_db[request_id]
    response_info = response_db.get(request_id, {})

    return {
        "request_id": request_id,
        "status": request_info.get("status", "unknown"),
        "request_details": request_info.get("request_data", {}),
        "response_details": response_info
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_requests": len([r for r in request_db.values() if r.get("status") in ["queued", "processing"]]),
        "completed_requests": len([r for r in request_db.values() if r.get("status") == "completed"])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
