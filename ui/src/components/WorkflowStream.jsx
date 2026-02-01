/**
 * WorkflowStream Component
 * Displays live event stream with real-time updates and animations.
 */

import React, { useEffect, useRef } from 'react';

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

      {events.map((evt) => (
        <div
          key={evt.id + evt.ts}
          className="stream-event"
          data-testid="event-entry"
        >
          <div className="event-meta">
            <span className="event-time">{formatTime(evt.ts)}</span>
            {evt.id && <span className="event-id">{evt.id}</span>}
          </div>
          <div className="event-body">
            {typeof evt.payload === 'object' ? (
              <pre>{JSON.stringify(evt.payload, null, 2)}</pre>
            ) : (
              <p>{evt.payload}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
