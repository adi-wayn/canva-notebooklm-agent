import React, { useState, useEffect } from "react";
import "./ConnectionStatus.css";

export function ConnectionStatus() {
  const [canvaStatus, setCanvaStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);

  // Check Canva connection status on mount
  useEffect(() => {
    checkConnectionStatus();
  }, []);

  const checkConnectionStatus = async () => {
    try {
      setLoading(true);
      const tenantId = "demo-tenant";
      const userId = "test-user";

      const response = await fetch(`/api/v1/auth/canva/status?user_id=${userId}`, {
        headers: {
          "X-Tenant-ID": tenantId,
        },
      });
      const data = await response.json();
      setCanvaStatus(data);
    } catch (error) {
      console.error("Error checking connection status:", error);
      setCanvaStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  const handleConnectCanva = () => {
    setConnecting(true);
    // Direct redirect for OAuth
    const tenantId = "demo-tenant";
    const userId = "test-user";
    window.location.href = `/api/v1/auth/canva/authorize?user_id=${userId}&tenant_id=${tenantId}`;
  };

  const handleDisconnectCanva = async () => {
    if (!window.confirm("Are you sure you want to disconnect Canva?")) {
      return;
    }

    try {
      setLoading(true);
      const response = await fetch("/api/v1/auth/canva/disconnect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": "demo-tenant",
        },
        body: JSON.stringify({ user_id: "test-user" })
      });

      if (response.ok) {
        setCanvaStatus({ connected: false });
      }
    } catch (error) {
      console.error("Error disconnecting Canva:", error);
    } finally {
      setLoading(false);
    }
  };

  // Check for OAuth callback parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("success") && params.get("success") === "canva_connected") {
      // Clear URL and refresh status
      window.history.replaceState({}, document.title, window.location.pathname);
      checkConnectionStatus();
    }
    if (params.has("error")) {
      const error = params.get("error");
      console.error("OAuth error:", error);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  if (loading) {
    return <div className="connection-status loading">Loading...</div>;
  }

  return (
    <div className="connection-status">
      {canvaStatus?.connected ? (
        <div className="connected">
          <div className="status-icon">✓</div>
          <div className="status-info">
            <div className="status-label">Canva Connected</div>
            <div className="account-email">{canvaStatus.account_email}</div>
          </div>
          <button
            className="disconnect-btn"
            onClick={handleDisconnectCanva}
            title="Disconnect from Canva"
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="disconnected">
          <div className="status-icon">○</div>
          <div className="status-info">
            <div className="status-label">Connect Canva</div>
            <div className="status-hint">
              Connect your Canva account to create designs
            </div>
          </div>
          <button
            className="connect-btn"
            onClick={handleConnectCanva}
            disabled={connecting}
          >
            {connecting ? "Connecting..." : "Connect"}
          </button>
        </div>
      )}
    </div>
  );
}
