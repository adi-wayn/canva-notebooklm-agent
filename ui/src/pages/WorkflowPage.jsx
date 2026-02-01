/**
 * WorkflowPage Component
 * Client-ready AI agent interface with chat-style interaction
 */

import React, { useState } from 'react';
import { Header } from '../components/Header';
import { AgentInput } from '../components/AgentInput';
import { MessageBubble } from '../components/MessageBubble';
import { ArtifactRenderer } from '../components/ArtifactRenderer';
import { WorkflowHistory } from '../components/WorkflowHistory';
import { StateIndicator } from '../components/StateIndicator';
import { ConnectionStatus } from '../components/ConnectionStatus';
import { useWorkflow } from '../hooks/useWorkflow';
import { useWorkflowState } from '../hooks/useWorkflowState';
import { useEventStream } from '../hooks/useEventStream';

export function WorkflowPage() {
  const [tenantId, setTenantId] = useState('demo-tenant');
  const [userId, setUserId] = useState('test-user');
  const [showHistory, setShowHistory] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');

  // Workflow lifecycle management
  const workflow = useWorkflow();

  // Workflow state + derived properties
  const workflowState = useWorkflowState();

  // Event streaming
  const eventStream = useEventStream();

  const activeWorkflowId = workflowState.snapshot?.id;

  // Create workflow handler
  const handleCreateWorkflow = async (config) => {
    // Store the user's prompt for display
    setUserPrompt(config.description || config.design_id || 'New workflow request');

    workflowState.reset();
    eventStream.reset();

    try {
      const created = await workflow.create(tenantId, userId, config);
      workflowState.setSnapshot(created);
      eventStream.appendEvent({
        id: 'create',
        payload: created,
        ts: new Date().toISOString(),
      });
      await eventStream.openStream(created.id, tenantId);
    } catch (err) {
      workflowState.setError(err.message);
    }
  };

  // Load workflow from history
  const handleSelectWorkflow = async (workflowId) => {
    workflowState.reset();
    eventStream.reset();
    setShowHistory(false);

    try {
      const loaded = await workflow.fetch(workflowId, tenantId);
      workflowState.setSnapshot(loaded);
      setUserPrompt('Loaded previous workflow');
      await eventStream.openStream(workflowId, tenantId, 0);
    } catch (err) {
      workflowState.setError(err.message);
    }
  };

  // Retry handler
  const handleRetry = async () => {
    if (!activeWorkflowId) return;
    try {
      const updated = await workflow.retry(activeWorkflowId, tenantId);
      workflowState.setSnapshot(updated);
      eventStream.reset();
      await eventStream.openStream(activeWorkflowId, tenantId);
    } catch (err) {
      workflowState.setError(err.message);
    }
  };

  // Cancel handler
  const handleCancel = async () => {
    if (!activeWorkflowId) return;
    try {
      const updated = await workflow.cancel(activeWorkflowId, tenantId);
      workflowState.setSnapshot(updated);
      eventStream.closeStream();
    } catch (err) {
      workflowState.setError(err.message);
    }
  };

  // Refresh handler
  const handleRefresh = async () => {
    if (!activeWorkflowId) return;
    try {
      const updated = await workflow.fetch(activeWorkflowId, tenantId);
      workflowState.setSnapshot(updated);
    } catch (err) {
      workflowState.setError(err.message);
    }
  };

  // Update snapshot when events arrive
  React.useEffect(() => {
    if (eventStream.events.length > 0) {
      const latestEvent = eventStream.events[eventStream.events.length - 1];
      workflowState.updateFromEvent(latestEvent);
    }
  }, [eventStream.events]);

  // Hydrate artifacts from DB when workflow reaches terminal state
  // (SSE is best-effort; DB is source of truth)
  React.useEffect(() => {
    if (!activeWorkflowId) return;

    const status = workflowState.snapshot?.status;
    if (status === 'COMPLETED' || status === 'FAILED') {
      const fetchFullWorkflow = async () => {
        try {
          const fullWorkflow = await workflow.fetch(activeWorkflowId, tenantId);
          // Update local state with DB artifacts
          workflowState.setSnapshot(fullWorkflow);
        } catch (error) {
          console.error('Failed to hydrate workflow artifacts:', error);
        }
      };
      fetchFullWorkflow();
    }
  }, [workflowState.snapshot?.status, activeWorkflowId]);

  // Extract artifacts from workflow
  const artifacts = workflowState.snapshot?.artifacts || [];
  const isThinking = workflowState.agentState === 'thinking' || workflowState.agentState === 'processing';
  const hasResult = workflowState.agentState === 'complete' || workflowState.agentState === 'error';

  return (
    <div className="app-page">
      <Header
        agentState={workflowState.agentState}
        isConnected={eventStream.isConnected}
      />

      <main className="main-content">
        <div className="chat-container">
          {/* Sidebar: Workflow History */}
          <aside className={`history-sidebar ${showHistory ? 'visible' : ''}`}>
            <div className="history-sidebar-header">
              <button
                className="history-close-btn"
                onClick={() => setShowHistory(false)}
                title="Close history"
              >
                ✕
              </button>
            </div>
            <WorkflowHistory
              tenantId={tenantId}
              onSelectWorkflow={handleSelectWorkflow}
              currentWorkflowId={activeWorkflowId}
            />
          </aside>

          {/* Main Chat Area */}
          <div className="chat-main">
            {/* Top Bar */}
            <div className="chat-top-bar">
              <button
                className="history-toggle-btn"
                onClick={() => setShowHistory(!showHistory)}
                title="View history"
              >
                📋 History
              </button>
              <StateIndicator
                snapshot={workflowState.snapshot}
                agentState={workflowState.agentState}
                isLoading={workflow.isSubmitting || eventStream.isConnected}
              />
            </div>

            {/* Messages Area */}
            <div className="chat-messages">
              {!activeWorkflowId ? (
                <div className="chat-empty-state">
                  <ConnectionStatus />
                  <div className="empty-state-icon">🤖</div>
                  <h2 className="empty-state-title">AI Design Agent</h2>
                  <p className="empty-state-description">
                    I can help you create Canva designs and NotebookLM summaries.
                    Describe what you'd like to create below.
                  </p>
                </div>
              ) : (
                <>
                  {/* User's prompt */}
                  {userPrompt && (
                    <MessageBubble
                      type="user"
                      timestamp={workflowState.snapshot?.created_at}
                    >
                      {userPrompt}
                    </MessageBubble>
                  )}

                  {/* Agent thinking/processing */}
                  {isThinking && (
                    <MessageBubble
                      type="agent"
                      thinking={true}
                    />
                  )}

                  {/* Progress updates */}
                  {eventStream.events.length > 0 && workflowState.agentState === 'processing' && (
                    <MessageBubble type="agent">
                      <div className="progress-container">
                        <p className="progress-text">
                          {getCurrentStep(eventStream.events)} • {workflowState.snapshot?.progress_pct || 0}%
                        </p>
                        <div className="progress-bar-container">
                          <div
                            className="progress-bar-fill"
                            style={{ width: `${workflowState.snapshot?.progress_pct || 0}%` }}
                          ></div>
                        </div>
                      </div>
                    </MessageBubble>
                  )}

                  {/* Result message */}
                  {hasResult && (
                    <MessageBubble
                      type="agent"
                      timestamp={workflowState.snapshot?.updated_at}
                    >
                      {workflowState.agentState === 'complete' ? (
                        <div>
                          <p className="result-message">
                            ✅ <strong>Completed successfully!</strong>
                          </p>
                          <p className="result-summary">
                            I've generated {artifacts.length} artifact{artifacts.length !== 1 ? 's' : ''} for you.
                            {artifacts.length > 0 && ' Click the buttons below to view, copy, or open them.'}
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p className="result-message error-message">
                            ❌ <strong>Workflow failed</strong>
                          </p>
                          <p className="result-summary">
                            {workflowState.error || 'An unexpected error occurred.'}
                          </p>
                          {workflowState.canRetryWorkflow && (
                            <button
                              onClick={handleRetry}
                              className="retry-btn-inline"
                              disabled={workflow.isRetrying}
                            >
                              🔄 Retry Workflow
                            </button>
                          )}
                        </div>
                      )}
                    </MessageBubble>
                  )}

                  {/* Artifacts Display */}
                  {artifacts.length > 0 && (
                    <div className="artifacts-section">
                      <ArtifactRenderer artifacts={artifacts} />
                    </div>
                  )}

                  {/* Action Buttons (for running workflows) */}
                  {activeWorkflowId && workflowState.agentState === 'processing' && (
                    <div className="chat-actions">
                      <button
                        onClick={handleCancel}
                        className="action-btn action-btn-secondary"
                        disabled={workflow.isCancelling}
                      >
                        {workflow.isCancelling ? 'Cancelling...' : '⏹ Cancel'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Input Area */}
            <div className="chat-input-area">
              <AgentInput
                onSubmit={handleCreateWorkflow}
                isLoading={workflow.isSubmitting}
                tenantId={tenantId}
                userId={userId}
              />
            </div>
          </div>
        </div>

        {/* Error Toast */}
        {(workflowState.error || workflow.workflowError || eventStream.streamError) && (
          <div className="error-toast">
            <div className="error-toast-content">
              <span className="error-toast-icon">⚠️</span>
              <p className="error-toast-message">
                {workflowState.error ||
                  workflow.workflowError ||
                  eventStream.streamError}
              </p>
              <button
                className="error-toast-close"
                onClick={() => {
                  workflowState.setError(null);
                  workflow.setWorkflowError(null);
                }}
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// Helper to extract current step from events
function getCurrentStep(events) {
  if (!events || events.length === 0) return 'Starting...';

  const lastEvent = events[events.length - 1];
  const payload = lastEvent.payload || {};

  // Handle agent_step events
  if (payload.event_name) {
    const agentMessages = {
      'agent_thinking': 'Analyzing your request',
      'notebooklm_extraction_started': 'Extracting insights from NotebookLM',
      'notebooklm_extraction_completed': 'Extracted key insights',
      'design_plan_created': 'Planning your design',
      'canva_design_started': 'Creating Canva design',
      'canva_design_created': 'Canva design created',
      'canva_content_partial_warning': 'Design created with warnings',
    };

    return payload.message || agentMessages[payload.event_name] || payload.event_name;
  }

  // Legacy event handling (backwards-compatible)
  if (payload.step) {
    return capitalizeFirst(payload.step);
  }

  if (payload.event_type === 'status_changed') {
    return `Status: ${payload.new_status}`;
  }

  return 'Processing...';
}

function capitalizeFirst(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}
