import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters.notebooklm_adapter import NotebookLMAdapter

async def verify():
    load_dotenv()
    api_key = os.getenv("NOTEBOOKLM_API_KEY")
    
    if not api_key:
        print("❌ NOTEBOOKLM_API_KEY not found in .env")
        print("Please add your Gemini API Key to run this verification.")
        return

    print(f"✓ Found API Key: {api_key[:4]}...{api_key[-4:]}")

    # --- DIAGNOSTIC START ---
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    print("\n[DIAGNOSTIC] Listing available models:")
    try:
        found_flash = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
                if "flash" in m.name:
                    found_flash = True
        if not found_flash:
            print("⚠️ WARNING: No 'flash' model found. Check your API Key permissions/region.")
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")
    # --- DIAGNOSTIC END ---
    
    print("\nInitializing Adapter (Real Mode)...")
    adapter = NotebookLMAdapter(
        client_id="dummy", 
        client_secret="dummy", 
        access_token=api_key, 
        mock_mode=False
    )
    
    try:
        print("Sending Query to Gemini 1.5 Flash...")
        msg = await adapter.send_message(
            notebook_id="test_nb", 
            content="Explain Quantum Entanglement in 2 bullet points."
        )
        
        print("\n✓ SUCCESS! Response received:")
        print("-" * 50)
        print(msg.content)
        print("-" * 50)
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
    finally:
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(verify())
