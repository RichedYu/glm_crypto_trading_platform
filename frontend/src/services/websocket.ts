export interface WebSocketMessage {
  event_type: string;
  [key: string]: any;
}

class WebSocketService {
  private url: string;
  private socket: WebSocket | null = null;
  private subscribers: Map<string, ((data: any) => void)[]> = new Map();
  private reconnectInterval: number = 3000;
  private maxReconnectAttempts: number = 5;
  private reconnectAttempts: number = 0;

  constructor() {
    this.url =
      import.meta.env.VITE_WS_URL || "ws://localhost:8001/ws/market-data";
    this.connect();
  }

  private connect() {
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log("[WS] Connected");
      this.reconnectAttempts = 0;
    };

    this.socket.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        const { event_type, ...data } = message;
        this.notifySubscribers(event_type, data);
      } catch (error) {
        console.error("[WS] Failed to parse message", error);
      }
    };

    this.socket.onclose = () => {
      console.log("[WS] Disconnected");
      this.attemptReconnect();
    };

    this.socket.onerror = (error) => {
      console.error("[WS] Error", error);
      this.socket?.close();
    };
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(() => {
        console.log(
          `[WS] Reconnecting... (${this.reconnectAttempts + 1}/${
            this.maxReconnectAttempts
          })`
        );
        this.reconnectAttempts++;
        this.connect();
      }, this.reconnectInterval);
    } else {
      console.error("[WS] Max reconnect attempts reached");
    }
  }

  private notifySubscribers(eventType: string, data: any) {
    // 精确匹配
    if (this.subscribers.has(eventType)) {
      this.subscribers.get(eventType)?.forEach((callback) => callback(data));
    }

    // 同时也支持通配符订阅 (暂未实现复杂通配符，简单支持 'all')
    if (this.subscribers.has("all")) {
      this.subscribers
        .get("all")
        ?.forEach((callback) => callback({ eventType, data }));
    }
  }

  public subscribe(
    eventType: string,
    callback: (data: any) => void
  ): () => void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, []);
    }
    this.subscribers.get(eventType)?.push(callback);

    return () => {
      const callbacks = this.subscribers.get(eventType);
      if (callbacks) {
        this.subscribers.set(
          eventType,
          callbacks.filter((cb) => cb !== callback)
        );
      }
    };
  }
}

export const wsService = new WebSocketService();
