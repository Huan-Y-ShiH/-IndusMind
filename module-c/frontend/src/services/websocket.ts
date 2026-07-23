/**
 * WebSocket client for IndusMind real-time alert stream.
 *
 * Connects to /ws/alerts on the gateway (proxied by Vite dev server).
 * Features: auto-reconnect with exponential backoff, heartbeat ping/pong.
 */

type AlertHandler = (data: unknown) => void;

class AlertWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private handlers: AlertHandler[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseDelay = 1000; // 1s

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/alerts`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[WS] Connected to alert stream');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      // Handle plain-text ping/pong heartbeat first (server sends raw 'ping'/'pong')
      if (typeof event.data === 'string') {
        if (event.data === 'ping') {
          this.ws?.send('pong');
          return;
        }
        if (event.data === 'pong') {
          // Server responded to our heartbeat — nothing to do
          return;
        }
        // Try to parse as JSON for structured messages
        try {
          const data = JSON.parse(event.data);
          this.handlers.forEach((h) => h(data));
        } catch {
          console.warn('[WS] Unrecognized text message:', event.data);
        }
      }
      // Binary data (ArrayBuffer, Blob) — ignored for now
    };

    this.ws.onclose = () => {
      console.log('[WS] Disconnected');
      this.stopHeartbeat();
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // stop reconnect
    this.ws?.close();
    this.ws = null;
  }

  onMessage(handler: AlertHandler): () => void {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  // ── Private ────────────────────────────────────────────────────

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000); // 30s heartbeat
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts),
      30000,
    );
    this.reconnectAttempts++;
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }
}

// Singleton
export const alertWS = new AlertWebSocket();

// ── Message types (aligned with backend ws.py) ──────────────────────

export type WsAlertMessage = {
  type: 'alert';
  event_id: string | null;
  workflow_id?: string;
  device_id: string;
  data: {
    alert_type: string;
    message: string;
    risk_level: string;
  };
  timestamp: string;
};

export type WsConnectionMessage = {
  type: 'connection';
  event_id: null;
  data: {
    message: string;
  };
  timestamp: string;
};
