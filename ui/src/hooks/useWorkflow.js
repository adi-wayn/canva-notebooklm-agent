/**
 * useWorkflow Hook
 * Manages workflow lifecycle (create, fetch, retry, cancel).
 */

import { useState, useCallback } from 'react';
import { api } from '../lib/api';

export function useWorkflow() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [workflowError, setWorkflowError] = useState(null);

  const create = useCallback(async (tenantId, userId, config) => {
    setIsSubmitting(true);
    setWorkflowError(null);
    try {
      const workflow = await api.createWorkflow(tenantId, userId, config);
      return workflow;
    } catch (err) {
      setWorkflowError(err.message);
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const fetch = useCallback(async (workflowId, tenantId) => {
    setWorkflowError(null);
    try {
      const workflow = await api.getWorkflow(workflowId, tenantId);
      return workflow;
    } catch (err) {
      setWorkflowError(err.message);
      throw err;
    }
  }, []);

  const retry = useCallback(async (workflowId, tenantId) => {
    setIsRetrying(true);
    setWorkflowError(null);
    try {
      const workflow = await api.retryWorkflow(workflowId, tenantId);
      return workflow;
    } catch (err) {
      setWorkflowError(err.message);
      throw err;
    } finally {
      setIsRetrying(false);
    }
  }, []);

  const cancel = useCallback(async (workflowId, tenantId) => {
    setIsCancelling(true);
    setWorkflowError(null);
    try {
      const workflow = await api.cancelWorkflow(workflowId, tenantId);
      return workflow;
    } catch (err) {
      setWorkflowError(err.message);
      throw err;
    } finally {
      setIsCancelling(false);
    }
  }, []);

  return {
    create,
    fetch,
    retry,
    cancel,
    isSubmitting,
    isRetrying,
    isCancelling,
    workflowError,
    setWorkflowError,
  };
}
