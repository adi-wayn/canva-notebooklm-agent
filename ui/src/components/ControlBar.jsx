/**
 * ControlBar Component
 * Actions for workflow management (retry, cancel, refresh, load).
 */

import React from 'react';

export function ControlBar({
  canRetry,
  canCancel,
  onRetry,
  onCancel,
  onRefresh,
  onLoadWorkflow,
  isRetrying,
  isCancelling,
  activeWorkflowId,
}) {
  return (
    <div className="control-bar">
      <div className="control-group">
        {activeWorkflowId && (
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onRefresh}
              title="Refresh workflow state from server"
            >
              🔄 Refresh
            </button>

            <button
              type="button"
              className="btn btn-success"
              onClick={onRetry}
              disabled={!canRetry || isRetrying}
              data-testid="retry-btn"
            >
              {isRetrying ? 'Retrying…' : '🔁 Retry'}
            </button>

            <button
              type="button"
              className="btn btn-danger"
              onClick={onCancel}
              disabled={!canCancel || isCancelling}
              data-testid="cancel-btn"
            >
              {isCancelling ? 'Cancelling…' : '⏹ Cancel'}
            </button>
          </>
        )}
      </div>

      <div className="control-group">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onLoadWorkflow}
          title="Load an existing workflow by ID"
        >
          📂 Load Workflow
        </button>
      </div>
    </div>
  );
}
