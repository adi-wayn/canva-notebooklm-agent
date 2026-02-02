
import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"
TENANT_ID = "demo-tenant"
WORKFLOW_ID = "wf_ae2f24a2535a"

def run_retry_verification():
    print(f"🚀 Verifying Retry Logic for {WORKFLOW_ID}...")
    
    headers = {
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }
    
    # 1. Trigger Retry
    print(f"📡 Sending RETRY request to {BASE_URL}/workflows/{WORKFLOW_ID}/retry...")
    try:
        resp = requests.post(f"{BASE_URL}/workflows/{WORKFLOW_ID}/retry", json={}, headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"✅ Retry Triggered: {wf['id']} (Status: {wf['status']})")
    except Exception as e:
        print(f"❌ Failed to trigger retry: {e}")
        if 'resp' in locals():
            print(f"Response: {resp.text}")
        sys.exit(1)

    # 2. Poll Status
    print(f"⏳ Polling status for {WORKFLOW_ID}...")
    start_time = time.time()
    while True:
        if time.time() - start_time > 180: # 3 min timeout
            print("❌ Timeout awaiting completion.")
            break
            
        try:
            resp = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
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
                    print("✅ VERIFICATION PASSED: Real Canva URL generated after retry.")
                else:
                    print("⚠️ VERIFICATION PARTIAL: Completed but no Canva URL found in artifacts.")
                    print(f"   Artifacts: {json.dumps(artifacts, indent=2)}")
                break
                
            if status == "FAILED":
                print(f"\n❌ Workflow FAILED AGAIN: {data.get('error')}")
                break
                
        except Exception as e:
            print(f"⚠️ Error polling: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_retry_verification()
