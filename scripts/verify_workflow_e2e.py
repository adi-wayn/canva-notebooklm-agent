#!/usr/bin/env python3
"""
E2E Verification Script for NotebookLM -> Canva Workflow.

Usage:
    python scripts/verify_workflow_e2e.py [prompt]

Prerequisites:
    - API: http://localhost:8000
    - Worker: Running (reloaded with latest code)
"""
import asyncio
import json
import uuid
import sys
import httpx
from httpx_sse import aconnect_sse

API_URL = "http://localhost:8000"

async def verify_workflow(prompt: str):
    print(f"🚀 Starting E2E Verification for prompt: '{prompt}'")
    
    # 1. Trigger Workflow
    headers = {"X-Tenant-ID": "demo-tenant"}
    # Increase timeout for long-running workflow steps
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        # We need a tenant_id and user_id context. 
        # Using seeded values from setup_db.py
        payload = {
            "user_id": "test-user",
            "tenant_id": "demo-tenant",
            "config": {
                "type": "generate_presentation_from_notebooklm",
                "prompt": prompt,
                "simulate_failure": None
            }
        }
        print(" -> Submitting workflow...")
        try:
            resp = await client.post(f"{API_URL}/api/v1/workflows", json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            workflow_id = data["id"]
            print(f"✅ Workflow Created: {workflow_id}")
        except Exception as e:
            print(f"❌ Failed to create workflow: {e}")
            return

        # 2. Listen to SSE
        print(f" -> Listening to SSE stream for {workflow_id}...")
        async with aconnect_sse(client, "GET", f"{API_URL}/api/v1/workflows/{workflow_id}/stream") as event_source:
            async for sse in event_source.aiter_sse():
                if sse.event == "keep-alive":
                    continue
                
                try:
                    event_data = json.loads(sse.data)
                    # The event payload is top-level in the data
                    event_type = event_data.get("event_type")
                    step = event_data.get("step")
                    status = event_data.get("new_status") or event_data.get("status")
                    
                    print(f"   event: {event_type} | status: {status} | step: {step}")
                    
                    if event_type == "workflow_completed" or status == "completed":
                        print("✅ Workflow COMPLETED!")
                        print(" -> Fetching full workflow details to inspect artifacts...")
                        
                        # Fetch details
                        w_resp = await client.get(f"{API_URL}/api/v1/workflows/{workflow_id}")
                        w_data = w_resp.json()
                        artifacts = w_data.get("artifacts", [])
                        
                        if artifacts:
                            print("\nGenerated Artifacts:")
                            for a in artifacts:
                                print(f" - [{a['content_type']}] {a['name']}")
                                print(f"   URL: {a['url']}")
                        else:
                            print("⚠️  No artifacts found (unexpected for success path).")
                            
                        break

                    if event_type == "workflow_failed" or status == "failed":
                        print("❌ Workflow FAILED!")
                        error = event_data.get("error")
                        print(f"   Error: {error}")
                        break
                        
                except Exception as e:
                    print(f"⚠️  Error parsing/handling event: {e}")

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Demo Presentation about AI Agents"
    try:
        asyncio.run(verify_workflow(prompt))
    except KeyboardInterrupt:
        print("\nStopped.")
