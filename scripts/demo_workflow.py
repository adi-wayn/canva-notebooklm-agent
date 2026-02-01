#!/usr/bin/env python
"""CLI demo: Workflow creation and event streaming.

Demonstrates the workflow engine with mocked adapters.
Run: python scripts/demo_workflow.py

No external services required; all mocks are in-process.
"""

import asyncio
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + "/..")

from src.orchestration import (
    WorkflowStatus,
    ErrorType,
    WorkflowEngine,
)
from src.utils.llm_exceptions import LLMTimeoutError, InvalidResponseError


async def demo_happy_path():
    """Demo: Workflow from creation to completion."""
    print("\n" + "=" * 80)
    print("DEMO 1: Happy Path Workflow (SUBMITTED → COMPLETED)")
    print("=" * 80 + "\n")

    engine = WorkflowEngine()

    # Create workflow
    print("[1] Creating workflow...")
    workflow = engine.create_workflow(
        tenant_id="demo_tenant",
        user_id="demo_user",
        input_data={
            "source_id": "notebooklm_src_demo",
            "title": "Q4 Marketing Strategy",
        },
    )
    print(f"    ✓ Created: {workflow.id}")
    print(f"    Status: {workflow.status.value}")
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Queue
    print("[2] Queueing workflow...")
    engine.queue_workflow(workflow)
    print(f"    ✓ Status: {workflow.status.value}")
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Start processing
    print("[3] Starting processing...")
    engine.start_processing(workflow)
    print(f"    ✓ Status: {workflow.status.value}")
    print(f"    Step: {workflow.step}")
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Simulate progress
    steps = [
        ("analyzing_content", 20),
        ("generating_layout", 40),
        ("creating_design", 60),
        ("populating_content", 80),
        ("finalizing", 95),
    ]

    for step_name, progress in steps:
        print(f"[+] {step_name.replace('_', ' ').title()}...")
        engine.update_progress(workflow, step_name, progress)
        print(f"    Progress: {workflow.progress_pct}%")

        # Simulate artifact creation at certain steps
        if step_name == "analyzing_content":
            engine.add_artifact(
                workflow,
                "content_analysis",
                "application/json",
                data={"slides": 10, "topics": 5, "references": 20},
            )
            print(f"    + Artifact: content_analysis.json")
        elif step_name == "generating_layout":
            engine.add_artifact(
                workflow,
                "layout_decision",
                "application/json",
                data={"template": "grid", "columns": 3, "colors": ["#3b82f6", "#60a5fa"]},
            )
            print(f"    + Artifact: layout_decision.json")
        elif step_name == "finalizing":
            engine.add_artifact(
                workflow,
                "design_export",
                "application/pdf",
                url="https://storage.example.com/designs/wf_abc/presentation.pdf",
            )
            print(f"    + Artifact: design_export.pdf")

        await asyncio.sleep(0.5)  # Simulate processing time
        print()

    # Complete
    print("[4] Completing workflow...")
    engine.complete_workflow(workflow)
    print(f"    ✓ Status: {workflow.status.value}")
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Display summary
    print("[SUMMARY]")
    api_response = workflow.to_dict()
    print(f"  Workflow ID: {api_response['id']}")
    print(f"  Status: {api_response['status']}")
    print(f"  Progress: {api_response['progress_pct']}%")
    print(f"  Artifacts: {len(api_response['artifacts'])}")
    for artifact in api_response['artifacts']:
        print(f"    - {artifact['name']} ({artifact['content_type']})")
    print(f"  Duration: {(api_response['updated_at'])} from {api_response['created_at']}")
    print()


async def demo_transient_failure():
    """Demo: Workflow failing with transient error (retryable)."""
    print("\n" + "=" * 80)
    print("DEMO 2: Transient Failure (Retryable)")
    print("=" * 80 + "\n")

    engine = WorkflowEngine()

    # Create and queue
    print("[1] Creating workflow...")
    workflow = engine.create_workflow(
        tenant_id="demo_tenant",
        user_id="demo_user",
        input_data={"source_id": "notebooklm_src_demo"},
    )
    print(f"    ✓ Created: {workflow.id}\n")

    engine.queue_workflow(workflow)
    engine.start_processing(workflow)
    print("[2] Started processing...\n")

    # Progress
    print("[3] Analyzing content...")
    engine.update_progress(workflow, "analyzing_content", 25)
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Fail with transient error
    print("[4] Request timeout (transient error)...")
    timeout_error = LLMTimeoutError(
        "API request timed out after 30 seconds",
        timeout_seconds=30,
    )
    engine.fail_workflow(workflow, timeout_error, step="analyzing_content")
    print(f"    ✓ Status: {workflow.status.value}\n")

    # Display error details
    print("[ERROR DETAILS]")
    api_response = workflow.to_dict()
    print(f"  Error Type: {api_response['error']['type']}")
    print(f"  Message: {api_response['error']['message']}")
    print(f"  Retryable: {api_response['error']['retryable']}\n")

    print("[USER ACTION]")
    print("  User sees: ⚠ Request Timed Out")
    print("  Message: 'The API took too long to respond. Please try again.'")
    print("  Buttons: [Retry] [Cancel] [Details]\n")


async def demo_permanent_failure():
    """Demo: Workflow failing with permanent error (not retryable)."""
    print("\n" + "=" * 80)
    print("DEMO 3: Permanent Failure (Not Retryable)")
    print("=" * 80 + "\n")

    engine = WorkflowEngine()

    # Create and queue
    print("[1] Creating workflow...")
    workflow = engine.create_workflow(
        tenant_id="demo_tenant",
        user_id="demo_user",
        input_data={"source_id": "notebooklm_src_demo"},
    )
    print(f"    ✓ Created: {workflow.id}\n")

    engine.queue_workflow(workflow)
    engine.start_processing(workflow)
    print("[2] Started processing...\n")

    # Progress
    print("[3] Generating layout...")
    engine.update_progress(workflow, "generating_layout", 40)
    print(f"    Progress: {workflow.progress_pct}%\n")

    # Fail with permanent error
    print("[4] Invalid JSON response (permanent error)...")
    parse_error = InvalidResponseError(
        "JSON parsing failed: Unexpected token 'N' at line 1, column 1"
    )
    engine.fail_workflow(workflow, parse_error, step="generating_layout")
    print(f"    ✓ Status: {workflow.status.value}\n")

    # Display error details
    print("[ERROR DETAILS]")
    api_response = workflow.to_dict()
    print(f"  Error Type: {api_response['error']['type']}")
    print(f"  Message: {api_response['error']['message']}")
    print(f"  Retryable: {api_response['error']['retryable']}\n")

    print("[USER ACTION]")
    print("  User sees: ✗ Invalid Response")
    print("  Message: 'The LLM returned invalid data. Please check your input.'")
    print("  Buttons: [Contact Support] [Cancel] [Details]")
    print("  Note: NO [Retry] button shown for permanent errors\n")


async def demo_event_streaming():
    """Demo: Event streaming (async generator)."""
    print("\n" + "=" * 80)
    print("DEMO 4: Event Streaming (Async Generator)")
    print("=" * 80 + "\n")

    engine = WorkflowEngine()

    # Create workflow
    workflow = engine.create_workflow("demo_tenant", "demo_user", {})
    engine.queue_workflow(workflow)
    engine.start_processing(workflow)
    engine.update_progress(workflow, "step_1", 30)
    engine.complete_workflow(workflow)

    # Stream events
    print("[EVENTS RECEIVED]\n")
    event_count = 0
    async for event in engine.event_stream(workflow.id):
        event_count += 1
        event_dict = event.to_dict()
        timestamp = event_dict["timestamp"]
        event_type = event_dict["event_type"]

        if event_type == "status_changed":
            print(f"[{timestamp}] STATUS CHANGED")
            print(f"  {event_dict['old_status']} → {event_dict['new_status']}")
        elif event_type == "step_progressed":
            print(f"[{timestamp}] PROGRESS")
            print(f"  Step: {event_dict['step']}")
            print(f"  Progress: {event_dict['progress_pct']}%")
        elif event_type == "artifact_created":
            print(f"[{timestamp}] ARTIFACT CREATED")
            print(f"  {event_dict['step']} (progress: {event_dict['progress_pct']}%)")
        elif event_type == "failed":
            print(f"[{timestamp}] WORKFLOW FAILED")
            print(f"  Error: {event_dict['error']['message']}")

        print()

    print(f"[TOTAL EVENTS] {event_count}\n")


async def main():
    """Run all demos."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  WORKFLOW ENGINE DEMO (T2.4)".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    print("\nDemonstrating:")
    print("  • Deterministic state machine (SUBMITTED → QUEUED → PROCESSING → COMPLETED/FAILED)")
    print("  • Progress tracking and artifact creation")
    print("  • Error classification (transient vs permanent)")
    print("  • Event emission and streaming")
    print("  • UX-friendly workflow model")
    print()

    try:
        await demo_happy_path()
        await demo_transient_failure()
        await demo_permanent_failure()
        await demo_event_streaming()

        print("=" * 80)
        print("✓ ALL DEMOS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print("\nKey Takeaways:")
        print("  • Workflow engine is deterministic (no LLM-driven state changes)")
        print("  • Errors are classified for correct UI behavior (retryable flag)")
        print("  • Events emitted in correct order for real-time UI updates")
        print("  • Artifacts collected throughout processing")
        print("  • Ready for REST API exposure (T2.5)\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
