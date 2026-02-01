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
  const [streamError, setStreamError] = useState(null);

  const abortRef = useRef(null);
  const decoderRef = useRef(new TextDecoder());

  const appendEvent = useCallback((event) => {
    setEvents((prev) => [...prev.slice(-199), event]);
  }, []);

  const updateSnapshot = useCallback((snapshot, event) => {
    return updateSnapshotFromEvent(snapshot, event);
  }, []);

  const closeStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const openStream = useCallback(
    async (workflowId, tenantId, lastId = null) => {
      closeStream();
      setStreamError(null);
      setIsConnected(false);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const streamResp = await api.openWorkflowStream(
          workflowId,
          tenantId,
          lastId
        );

        setIsConnected(true);
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
              if (event.id) setLastEventId(event.id);
            }

            boundary = buffer.indexOf('\n\n');
          }
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setStreamError(err.message);
        }
      } finally {
        setIsConnected(false);
        abortRef.current = null;
      }
    },
    [closeStream, appendEvent]
  );

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
    streamError,
    openStream,
    closeStream,
    appendEvent,
    updateSnapshot,
    reset,
  };
}
