/**
 * useEventStream Hook
 * Manages SSE connection, event parsing, and stream lifecycle.
 */

import { useRef, useState, useCallback } from 'react';
import { api } from '../lib/api';
import { parseEventChunk, updateSnapshotFromEvent } from '../lib/eventParser';

export function useEventStream() {
  const [events, setEvents] = useState([]);
  const [lastEventId, setLastEventId] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [streamError, setStreamError] = useState(null);

  const abortRef = useRef(null);
  const decoderRef = useRef(new TextDecoder());
  const intentionalCloseRef = useRef(false);
  const configRef = useRef(null); // { workflowId, tenantId }
  const retryTimeoutRef = useRef(null);

  const appendEvent = useCallback((event) => {
    setEvents((prev) => [...prev.slice(-199), event]);
  }, []);

  const updateSnapshot = useCallback((snapshot, event) => {
    return updateSnapshotFromEvent(snapshot, event);
  }, []);

  const closeStream = useCallback(() => {
    intentionalCloseRef.current = true;
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    setIsConnected(false);
    configRef.current = null;
  }, []);

  const connect = useCallback(
    async (workflowId, tenantId, lastId = null) => {
      // Don't close explicitly here; we might be reconnecting
      // But we should ensure no duplicate streams
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;
      intentionalCloseRef.current = false;

      // Update config for retries
      configRef.current = { workflowId, tenantId };

      try {
        const streamResp = await api.openWorkflowStream(
          workflowId,
          tenantId,
          lastId
        );

        setIsConnected(true);
        setIsReconnecting(false); // Clear reconnecting state
        setStreamError(null); // Clear error on successful connect

        const { reader } = streamResp;
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoderRef.current.decode(value, { stream: true });

          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const chunk = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);

            const event = parseEventChunk(chunk);
            if (event) {
              appendEvent(event);
              if (event.id) {
                setLastEventId(event.id);
                // Update local var for retry logic if needed immediately
                lastId = event.id;
              }
            }

            boundary = buffer.indexOf('\n\n');
          }
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.warn('[EventStream] Stream error:', err);
          setStreamError(err.message);
        }
      } finally {
        setIsConnected(false);
        abortRef.current = null;

        // Auto-reconnect logic
        if (!intentionalCloseRef.current && configRef.current) {
          const { workflowId: wId, tenantId: tId } = configRef.current;
          console.log(`[EventStream] Connection lost. Reconnecting to ${wId} with lastId=${lastId}...`);
          setIsReconnecting(true);

          // Exponential backoff or simple delay
          retryTimeoutRef.current = setTimeout(() => {
            // Pass the *latest* lastEventId from state would be ideal, 
            // but inside callback we might need the ref-tracked one or the one from scope.
            // Relying on the 'lastId' variable in this scope which was updated in the loop.
            connect(wId, tId, lastId);
          }, 3000);
        }
      }
    },
    [appendEvent]
  );

  const openStream = useCallback((workflowId, tenantId, lastId = null) => {
    // Public API to start fresh
    if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
    setEvents([]);
    setLastEventId(lastId); // Initialize state
    setStreamError(null);
    setIsReconnecting(false);
    return connect(workflowId, tenantId, lastId);
  }, [connect]);

  const reset = useCallback(() => {
    closeStream();
    setEvents([]);
    setLastEventId(null);
    setStreamError(null);
  }, [closeStream]);

  return {
    events,
    lastEventId,
    isConnected,
    isReconnecting,
    streamError,
    openStream,
    closeStream,
    appendEvent,
    updateSnapshot,
    reset,
  };
}
