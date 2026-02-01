/**
 * WorkflowHistory Component
 * Displays a list of recent workflows with filtering and loading
 */

import React, { useState, useEffect } from 'react';
import '../styles/WorkflowHistory.css';

export function WorkflowHistory({ tenantId, onSelectWorkflow, currentWorkflowId }) {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all'); // all, completed, failed, processing
  const [error, setError] = useState(null);

  useEffect(() => {
    if (tenantId) {
      loadWorkflows();
    }
  }, [tenantId, filter]);

  const loadWorkflows = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const url = `${baseUrl}/api/v1/workflows?tenant_id=${encodeURIComponent(tenantId)}&limit=20`;
      
      const response = await fetch(url, {
        headers: {
          'X-Tenant-ID': tenantId,
        },
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch workflows: ${response.statusText}`);
      }
      
      const data = await response.json();
      let filtered = data.workflows || [];
      
      // Apply filter
      if (filter !== 'all') {
        filtered = filtered.filter(wf => wf.status.toLowerCase() === filter.toLowerCase());
      }
      
      setWorkflows(filtered);
    } catch (err) {
      console.error('Failed to load workflows:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadWorkflows();
  };

  if (error) {
    return (
      <div className="workflow-history">
        <div className="history-header">
          <h3 className="history-title">📋 Recent Workflows</h3>
        </div>
        <div className="history-error">
          <p>❌ Failed to load workflows</p>
          <button onClick={handleRefresh} className="history-retry-btn">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="workflow-history">
      <div className="history-header">
        <h3 className="history-title">📋 Recent Workflows</h3>
        <button onClick={handleRefresh} className="history-refresh-btn" title="Refresh">
          🔄
        </button>
      </div>

      <div className="history-filters">
        {['all', 'completed', 'processing', 'failed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`history-filter-btn ${filter === f ? 'active' : ''}`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="history-list">
        {loading ? (
          <div className="history-loading">
            <div className="loading-spinner"></div>
            <p>Loading workflows...</p>
          </div>
        ) : workflows.length === 0 ? (
          <div className="history-empty">
            <p className="empty-icon">🔍</p>
            <p className="empty-text">No workflows found</p>
            <p className="empty-hint">Create a workflow to get started</p>
          </div>
        ) : (
          workflows.map(workflow => (
            <WorkflowItem
              key={workflow.id}
              workflow={workflow}
              isActive={workflow.id === currentWorkflowId}
              onClick={() => onSelectWorkflow(workflow.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function WorkflowItem({ workflow, isActive, onClick }) {
  const statusColors = {
    'SUBMITTED': 'status-submitted',
    'QUEUED': 'status-queued',
    'PROCESSING': 'status-processing',
    'COMPLETED': 'status-completed',
    'FAILED': 'status-failed',
    'CANCELLED': 'status-cancelled',
  };

  const statusColor = statusColors[workflow.status] || 'status-default';
  
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      className={`workflow-item ${isActive ? 'active' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
    >
      <div className="workflow-item-header">
        <span className={`workflow-status-badge ${statusColor}`}>
          {workflow.status}
        </span>
        <span className="workflow-item-time">
          {formatDate(workflow.created_at)}
        </span>
      </div>
      
      <div className="workflow-item-body">
        <p className="workflow-item-id">
          {workflow.id}
        </p>
        {workflow.config && workflow.config.description && (
          <p className="workflow-item-desc">
            {workflow.config.description}
          </p>
        )}
      </div>
      
      {workflow.progress_pct !== undefined && (
        <div className="workflow-item-progress">
          <div
            className="workflow-progress-bar"
            style={{ width: `${workflow.progress_pct}%` }}
          ></div>
        </div>
      )}
    </div>
  );
}
