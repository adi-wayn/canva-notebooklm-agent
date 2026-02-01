/**
 * useWorkflowState Hook
 * Manages workflow state, status changes, and derived UI properties.
 */

import { useState, useCallback, useMemo } from 'react';
import {
  getAgentState,
  isTerminalStatus,
  canRetry,
  canCancel,
} from '../lib/stateHelpers';

export function useWorkflowState() {
  const [snapshot, setSnapshot] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const agentState = useMemo(() => {
    if (!snapshot) return 'idle';
    return getAgentState(snapshot.status, !!snapshot.error);
  }, [snapshot]);

  const canRetryWorkflow = useMemo(() => {
    if (!snapshot) return false;
    return canRetry(snapshot.status, snapshot.error);
  }, [snapshot]);

  const canCancelWorkflow = useMemo(() => {
    if (!snapshot) return false;
    return canCancel(snapshot.status);
  }, [snapshot]);

  const isTerminal = useMemo(() => {
    if (!snapshot) return false;
    return isTerminalStatus(snapshot.status);
  }, [snapshot]);

  const updateFromEvent = useCallback((event) => {
    if (!event?.payload) return;

    setSnapshot((prev) => {
      const next = { ...(prev || {}) };
      const { payload } = event;

      if (payload.old_status || payload.new_status) {
        next.status = payload.new_status || payload.old_status || next.status;
      }
      if (payload.step !== undefined) next.step = payload.step;
      if (typeof payload.progress_pct === 'number')
        next.progress_pct = payload.progress_pct;
      if (payload.error) next.error = payload.error;
      if (payload.artifacts) next.artifacts = payload.artifacts;

      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setSnapshot(null);
    setError(null);
  }, []);

  return {
    snapshot,
    setSnapshot,
    isLoading,
    setIsLoading,
    error,
    setError,
    agentState,
    canRetryWorkflow,
    canCancelWorkflow,
    isTerminal,
    updateFromEvent,
    reset,
  };
}
