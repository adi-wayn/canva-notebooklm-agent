/**
 * AgentInput Component
 * Conversational input for workflow creation.
 * Replaces the old form-based interface with a chat-like experience.
 */

import React, { useState, useMemo } from 'react';

const defaultConfig = {
  prompt: 'Generate a summary and key insights',
  source_id: 'demo-source',
};

export function AgentInput({ onSubmit, isLoading, tenantId, userId }) {
  const [configText, setConfigText] = useState(
    JSON.stringify(defaultConfig, null, 2)
  );
  const [expandConfig, setExpandConfig] = useState(false);

  const configError = useMemo(() => {
    try {
      JSON.parse(configText || '{}');
      return '';
    } catch (err) {
      return 'Invalid JSON in config';
    }
  }, [configText]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (configError) return;

    const config = JSON.parse(configText || '{}');
    onSubmit(config);
  };

  return (
    <form className="agent-input" onSubmit={handleSubmit} data-testid="agent-input-form">
      <div className="input-area">
        <div className="input-field">
          <label htmlFor="prompt-input" className="input-label">
            What would you like the agent to do?
          </label>
          <textarea
            id="prompt-input"
            className="input-textarea"
            placeholder="e.g., Analyze this document and extract key topics..."
            value={
              configText
                ? (() => {
                    try {
                      return JSON.parse(configText)?.prompt || '';
                    } catch {
                      return '';
                    }
                  })()
                : ''
            }
            onChange={(e) => {
              try {
                const config = JSON.parse(configText || '{}');
                config.prompt = e.target.value;
                setConfigText(JSON.stringify(config, null, 2));
              } catch {
                setConfigText(e.target.value);
              }
            }}
            data-testid="prompt-input"
            disabled={isLoading}
          />
        </div>

        <div className="input-actions">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!!configError || isLoading}
            data-testid="submit-workflow-btn"
          >
            {isLoading ? 'Starting…' : 'Start'}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setExpandConfig(!expandConfig)}
            title="Advanced configuration"
          >
            {expandConfig ? '▼' : '⚙️'} Config
          </button>
        </div>
      </div>

      {expandConfig && (
        <div className="config-panel">
          <label htmlFor="config-json" className="input-label">
            Configuration (JSON)
          </label>
          <textarea
            id="config-json"
            className="input-textarea config-textarea"
            value={configText}
            onChange={(e) => setConfigText(e.target.value)}
            data-testid="config-input"
            disabled={isLoading}
          />
          {configError && <p className="error-message">{configError}</p>}
          <p className="helper-text">
            This is passed to your backend. Adjust source_id, prompt, or other parameters as needed.
          </p>
        </div>
      )}
    </form>
  );
}
