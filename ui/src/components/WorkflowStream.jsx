/**
 * WorkflowStream Component
 * Displays live event stream with real-time updates and animations.
 * Supports agent_step events with semantic messages.
 */

import React, { useEffect, useRef } from 'react';

// Map agent event names to user-facing messages
function getEventMessage(evt) {
  // Handle agent_step events
  if (evt.payload?.event_name) {
    const agentMessages = {
      'agent_thinking': 'AI Agent is analyzing your request...',
      'notebooklm_extraction_started': 'AI Agent is extracting insights from NotebookLM...',
      'notebooklm_extraction_completed': 'AI Agent extracted key insights',
      'design_plan_created': 'AI Agent is planning your design...',
      'canva_design_started': 'AI Agent is creating Canva design...',
      'canva_design_created': 'AI Agent created your Canva design',
      'canva_content_partial_warning': 'Design created with partial content',
    };

    // Use message from payload or fallback to predefined message
    return evt.payload.message || agentMessages[evt.payload.event_name] || evt.payload.event_name;
  }

  // Fallback for legacy events (backwards-compatible)
  if (typeof evt.payload === 'string') {
    return evt.payload;
  }

  if (evt.payload?.step) {
    return evt.payload.step;
  }

  if (evt.payload?.new_status) {
    return `Status: ${evt.payload.new_status}`;
  }

  return 'Processing...';
}

export function WorkflowStream({ events, isConnected, isLoading }) {
  const containerRef = useRef(null);

  // Auto-scroll to latest events
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  if (!isLoading && events.length === 0) {
    return (
      <div className="stream-container empty" data-testid="event-stream">
        <p className="muted">
          No events yet. Start a workflow to see live updates here.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`stream-container ${isConnected ? 'connected' : ''}`}
      ref={containerRef}
      data-testid="event-stream"
    >
      {events.length === 0 && isLoading && (
        <div className="stream-event stream-event--loading">
          <div className="event-spinner" />
          <span>Waiting for events…</span>
        </div>
      )}

      {events.map((evt) => {
        const message = getEventMessage(evt);
        const isAgentEvent = evt.payload?.event_name;
        const metadata = evt.payload?.metadata;

        return (
          <div
            key={evt.id + evt.ts}
            className={`stream-event ${isAgentEvent ? 'stream-event--agent' : ''}`}
            data-testid="event-entry"
          >
            <div className="event-meta">
              <span className="event-time">{formatTime(evt.ts)}</span>
              {evt.payload?.progress_pct !== undefined && (
                <span className="event-progress">{evt.payload.progress_pct}%</span>
              )}
              {evt.id && <span className="event-id">{evt.id}</span>}
            </div>
            <div className="event-body">
              <p className="event-message">{message}</p>

              {/* Display agent-specific metadata */}
              {isAgentEvent && metadata && (
                <div className="event-metadata">
                  {/* NotebookLM extraction summary */}
                  {evt.payload.event_name === 'notebooklm_extraction_completed' && (
                    <div className="extraction-summary">
                      <strong>Extracted:</strong> {metadata.title}
                      <br />
                      <strong>Sections:</strong> {metadata.sections_count}
                      {metadata.first_headings && metadata.first_headings.length > 0 && (
                        <>
                          <br />
                          <strong>Headings:</strong> {metadata.first_headings.join(', ')}
                        </>
                      )}
                    </div>
                  )}

                  {/* Canva partial warning */}
                  {evt.payload.event_name === 'canva_content_partial_warning' && (
                    <div className="warning-banner">
                      ⚠️ {metadata.warning}
                    </div>
                  )}

                  {/* Design plan details */}
                  {evt.payload.event_name === 'design_plan_created' && (
                    <div className="plan-details">
                      <strong>Slides:</strong> {metadata.slide_count} | <strong>Theme:</strong> {metadata.theme}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
