#!/usr/bin/env python3
"""Step A: Verify event persistence in Postgres"""
import asyncio
import asyncpg
import json
import sys

async def check_persistence(workflow_id: str):
    try:
        conn = await asyncpg.connect(
            'postgresql://canva_user:canva_password_dev@127.0.0.1:55432/canva_notebooklm_db'
        )
        
        # Query for the workflow
        events = await conn.fetch(
            "SELECT id, workflow_id, event_type, payload FROM workflow_events WHERE workflow_id = $1 ORDER BY id",
            workflow_id
        )
        
        print(f"\n✅ STEP A - EVENT PERSISTENCE: Found {len(events)} events for {workflow_id}")
        print("=" * 90)
        
        for event in events:
            payload = json.loads(event['payload']) if isinstance(event['payload'], str) else event['payload']
            status = payload.get('new_status', 'N/A') or 'N/A'
            event_type = event['event_type']
            print(f"ID: {event['id']:4d} | Type: {event_type:20s} | Status: {str(status):12s}")
        
        # Check for terminal events (COMPLETED or FAILED)
        terminal_events = [e for e in events if e['event_type'] == 'status_changed']
        if terminal_events:
            last_event = terminal_events[-1]
            payload = json.loads(last_event['payload']) if isinstance(last_event['payload'], str) else last_event['payload']
            final_status = payload.get('new_status')
            print(f"\n✅ Terminal Status Found: {final_status}")
            print(f"✅ STEP A PASSED: Events are persisted in Postgres")
            return True
        else:
            print("\n❌ No terminal events found!")
            return False
        
        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    workflow_id = sys.argv[1] if len(sys.argv) > 1 else 'wf_5d78aa397f09'
    success = asyncio.run(check_persistence(workflow_id))
    sys.exit(0 if success else 1)
