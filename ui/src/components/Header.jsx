/**
 * Header Component
 * Branding and connection status indicator.
 */

import React from 'react';

export function Header({ agentState, isConnected }) {
  const stateLabel = {
    idle: 'Ready',
    thinking: 'Thinking…',
    processing: 'Processing…',
    complete: 'Complete',
    error: 'Error',
  }[agentState] || 'Ready';

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <h1 className="header-title">Notebook LM Agent</h1>
          <p className="header-subtitle">Interactive workflow exploration</p>
        </div>
        <div className={`state-pill state-${agentState}`} data-testid="agent-state">
          {stateLabel}
          {isConnected && <span className="pulse" />}
        </div>
      </div>
    </header>
  );
}
