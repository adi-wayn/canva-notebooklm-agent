# Canva-NotebookLM Integration Prototype

## Overview
This prototype demonstrates the integration between Canva and NotebookLM APIs for automatic content transformation and layout generation.

## Architecture
The prototype follows a microservices architecture with the following components:
- Authentication Service
- Content Transformation Service
- Queue System (simulated with background tasks)
- Monitoring endpoints

## Features
- OAuth authentication with both Canva and NotebookLM
- Content transformation between platforms
- Three transformation types:
  - Text-to-image generation
  - Image-to-text extraction
  - Automatic layout generation
- Request status tracking
- Health monitoring

## Installation
```bash
pip install -r requirements.txt
```

## Running the Prototype
```bash
python main.py
```

The API will be available at http://localhost:8000

## API Endpoints
- POST /authenticate - Authenticate with both platforms
- POST /transform - Request content transformation
- GET /status/{request_id} - Check transformation status
- GET /health - Health check endpoint

## Example Usage

### Authentication
```bash
curl -X POST http://localhost:8000/authenticate   -H "Content-Type: application/json"   -d '{"canva_auth_token": "your_canva_token", "notebooklm_auth_token": "your_notebooklm_token"}'
```

### Text-to-Image Transformation
```bash
curl -X POST http://localhost:8000/transform   -H "Content-Type: application/json"   -d '{
    "canva_design_id": "design_123",
    "notebooklm_source_id": "source_456",
    "transformation_type": "text_to_image",
    "content_data": {"text": "Sample text to convert to image"},
    "priority": 1
  }'
```

### Check Status
```bash
curl http://localhost:8000/status/YOUR_REQUEST_ID
```

## Implementation Notes
- This is a prototype implementation
- Real implementation would need proper API client libraries for Canva and NotebookLM
- Error handling and retry logic would be more sophisticated
- Queue system would be replaced with RabbitMQ or similar
