/**
 * StateIndicator Component
 * Shows workflow execution state with progress and error details.
 */

import React from 'react';

export function StateIndicator({
  snapshot,
  agentState,
  isLoading,
}) {
  if (!snapshot && !isLoading) {
    return (
      <div className="state-indicator empty">
        <p className="muted">Create a workflow to see execution state here.</p>
      </div>
    );
  }

  const progressPct = snapshot?.progress_pct || 0;
  const statusClass = snapshot?.status ? `status-${snapshot.status}` : '';

  return (
    <div className="state-indicator">
      {/* Status Badge */}
      <div className={`status-badge ${statusClass}`} data-testid="workflow-status">
        {snapshot?.status || 'Loading…'}
      </div>

      {/* Progress Bar */}
      {snapshot && (
        <div className="progress-section">
          <p className="progress-label">
            {snapshot.step || 'Initializing'}
          </p>
          <div className="progress-bar" data-testid="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="progress-percent" data-testid="progress-percent">
            {progressPct}%
          </p>
        </div>
      )}

      {/* Workflow Info */}
      {snapshot && (
        <div className="workflow-info">
          <div className="info-item">
            <span className="info-label">Workflow ID</span>
            <code data-testid="workflow-id">{snapshot.id}</code>
          </div>
          <div className="info-item">
            <span className="info-label">Tenant</span>
            <span>{snapshot.tenant_id}</span>
          </div>
          {snapshot.created_at && (
            <div className="info-item">
              <span className="info-label">Created</span>
              <span>{new Date(snapshot.created_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {snapshot?.error && (
        <div className="error-section" data-testid="workflow-error">
          <div className="error-header">
            <span className="error-type">{snapshot.error.type}</span>
            <span className="error-retryable" data-testid="error-retryable">
              {snapshot.error.retryable ? '🔄 Retryable' : '❌ Not retryable'}
            </span>
          </div>
          <p className="error-message">{snapshot.error.message}</p>
        </div>
      )}

      {/* Artifacts */}
      {snapshot?.status === 'COMPLETED' && (
        <div className="artifacts-section" data-testid="workflow-artifacts">
          <h3>Artifacts</h3>
          {snapshot.artifacts && snapshot.artifacts.length > 0 ? (
            <ul className="artifacts-list">
              {snapshot.artifacts.map((artifact) => (
                <li key={artifact.name} className="artifact-item">
                  <span className="artifact-icon">📎</span>
                  <div className="artifact-details">
                    <span className="artifact-name">{artifact.name}</span>
                    <span className="artifact-type">{artifact.content_type}</span>
                  </div>
                  {artifact.url && (
                    <a href={artifact.url} target="_blank" rel="noreferrer" className="artifact-link">
                      View
                    </a>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No artifacts generated</p>
          )}
        </div>
      )}
    </div>
  );
}
