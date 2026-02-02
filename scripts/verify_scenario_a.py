
import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"
TENANT_ID = "demo-tenant"
USER_ID = "test-user"

def run_verification():
    print("🚀 Starting Scenario A: Create Presentation Verification (API Mode)")
    
    # 1. Create Workflow
    payload = {
        "user_id": USER_ID,
        "tenant_id": TENANT_ID,
        "config": {
            "prompt": "Create a 4-slide presentation about 'Quantum Computing Basics'. Include: definition, superposition, entanglement, and applications.",
            "slides": 4
        }
    }
    
    headers = {
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }
    
    print(f"📡 Submitting workflow request to {BASE_URL}/workflows...")
    try:
        resp = requests.post(f"{BASE_URL}/workflows", json=payload, headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        wf_id = wf["id"]
        print(f"✅ Workflow Created: {wf_id} (Status: {wf['status']})")
    except Exception as e:
        print(f"❌ Failed to create workflow: {e}")
        if 'resp' in locals():
            print(f"Response: {resp.text}")
        sys.exit(1)

    # 2. Poll Status
    print(f"⏳ Polling status for {wf_id}...")
    start_time = time.time()
    while True:
        if time.time() - start_time > 180: # 3 min timeout
            print("❌ Timeout awaiting completion.")
            break
            
        try:
            resp = requests.get(f"{BASE_URL}/workflows/{wf_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]
            progress = data.get("progress_pct", 0)
            step = data.get("step", "")
            
            print(f"   Status: {status} | Progress: {progress}% | Step: {step}")
            
            if status == "COMPLETED":
                print("\n🎉 Workflow COMPLETED Support!")
                artifacts = data.get("artifacts", [])
                canva_url = None
                for art in artifacts:
                    if "canva.com/design" in art.get("url", ""):
                        canva_url = art["url"]
                        print(f"   Found Canva Design: {canva_url}")
                
                if canva_url:
                    print("✅ VERIFICATION PASSED: Real Canva URL generated.")
                else:
                    print("⚠️ VERIFICATION PARTIAL: Completed but no Canva URL found in artifacts.")
                    print(f"   Artifacts: {json.dumps(artifacts, indent=2)}")
                break
                
            if status == "FAILED":
                print(f"\n❌ Workflow FAILED: {data.get('error')}")
                break
                
        except Exception as e:
            print(f"⚠️ Error polling: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_verification()
