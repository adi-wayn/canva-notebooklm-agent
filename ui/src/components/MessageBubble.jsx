/**
 * MessageBubble Component
 * Displays user or agent messages in chat-style format
 */

import React from 'react';
import '../styles/MessageBubble.css';

export function MessageBubble({ type = 'agent', children, timestamp, thinking = false }) {
  const className = `message-bubble message-${type}`;
  
  return (
    <div className={className}>
      <div className="message-header">
        <span className="message-author">
          {type === 'user' ? '👤 You' : '🤖 AI Agent'}
        </span>
        {timestamp && (
          <span className="message-time">
            {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
      
      <div className="message-content">
        {thinking ? (
          <div className="thinking-indicator">
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
