/**
 * ArtifactRenderer Component
 * Renders workflow artifacts with type-specific formatting and actions
 */

import React, { useState } from 'react';
import '../styles/ArtifactRenderer.css';

export function ArtifactRenderer({ artifacts = [] }) {
  if (!artifacts || artifacts.length === 0) {
    return null;
  }

  return (
    <div className="artifacts-container">
      <h3 className="artifacts-title">📦 Generated Artifacts</h3>
      <div className="artifacts-list">
        {artifacts.map((artifact, index) => (
          <ArtifactCard key={artifact.id || index} artifact={artifact} />
        ))}
      </div>
    </div>
  );
}

function ArtifactCard({ artifact }) {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    try {
      const textToCopy = artifact.content || artifact.url || artifact.text || JSON.stringify(artifact);
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };
  
  const handleDownload = () => {
    const content = artifact.content || artifact.text || JSON.stringify(artifact, null, 2);
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = artifact.name || `artifact-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  const handleOpenInCanva = () => {
    if (artifact.url) {
      window.open(artifact.url, '_blank', 'noopener,noreferrer');
    }
  };
  
  return (
    <div className="artifact-card">
      <div className="artifact-header">
        <div className="artifact-icon">{getArtifactIcon(artifact.type)}</div>
        <div className="artifact-info">
          <h4 className="artifact-name">{artifact.name || 'Unnamed Artifact'}</h4>
          <p className="artifact-type">{getArtifactLabel(artifact.type)}</p>
        </div>
      </div>
      
      <div className="artifact-body">
        {renderArtifactContent(artifact)}
      </div>
      
      <div className="artifact-actions">
        <button
          onClick={handleCopy}
          className="artifact-action-btn"
          title="Copy to clipboard"
        >
          {copied ? '✓ Copied!' : '📋 Copy'}
        </button>
        
        {(artifact.content || artifact.text) && (
          <button
            onClick={handleDownload}
            className="artifact-action-btn"
            title="Download file"
          >
            ⬇️ Download
          </button>
        )}
        
        {artifact.type === 'canva_design' && artifact.url && (
          <button
            onClick={handleOpenInCanva}
            className="artifact-action-btn artifact-action-primary"
            title="Open in Canva"
          >
            🎨 Open in Canva
          </button>
        )}
        
        {artifact.type === 'link' && artifact.url && (
          <a
            href={artifact.url}
            target="_blank"
            rel="noopener noreferrer"
            className="artifact-action-btn artifact-action-primary"
          >
            🔗 Open Link
          </a>
        )}
      </div>
    </div>
  );
}

function getArtifactIcon(type) {
  const icons = {
    'canva_design': '🎨',
    'text': '📄',
    'link': '🔗',
    'notebook': '📚',
    'audio': '🎵',
    'image': '🖼️',
    'document': '📝',
  };
  return icons[type] || '📦';
}

function getArtifactLabel(type) {
  const labels = {
    'canva_design': 'Canva Design',
    'text': 'Text Document',
    'link': 'External Link',
    'notebook': 'NotebookLM Summary',
    'audio': 'Audio File',
    'image': 'Image',
    'document': 'Document',
  };
  return labels[type] || 'Generic Artifact';
}

function renderArtifactContent(artifact) {
  switch (artifact.type) {
    case 'canva_design':
      return (
        <div className="artifact-preview">
          {artifact.thumbnail ? (
            <img src={artifact.thumbnail} alt="Design preview" className="artifact-thumbnail" />
          ) : (
            <div className="artifact-placeholder">🎨 Canva Design</div>
          )}
          {artifact.description && <p className="artifact-description">{artifact.description}</p>}
        </div>
      );
      
    case 'text':
      return (
        <div className="artifact-text-content">
          <pre className="artifact-text-pre">{artifact.content || artifact.text}</pre>
        </div>
      );
      
    case 'link':
      return (
        <div className="artifact-link-content">
          <a href={artifact.url} target="_blank" rel="noopener noreferrer" className="artifact-link">
            {artifact.url}
          </a>
          {artifact.description && <p className="artifact-description">{artifact.description}</p>}
        </div>
      );
      
    case 'notebook':
      return (
        <div className="artifact-notebook-content">
          <p className="artifact-description">
            {artifact.description || 'NotebookLM summary generated'}
          </p>
          {artifact.url && (
            <a href={artifact.url} target="_blank" rel="noopener noreferrer" className="artifact-link">
              View in NotebookLM →
            </a>
          )}
        </div>
      );
      
    default:
      return (
        <div className="artifact-generic-content">
          {artifact.description && <p className="artifact-description">{artifact.description}</p>}
          {artifact.content && (
            <pre className="artifact-text-pre">{
              typeof artifact.content === 'string' 
                ? artifact.content 
                : JSON.stringify(artifact.content, null, 2)
            }</pre>
          )}
        </div>
      );
  }
}
