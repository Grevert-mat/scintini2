import { Server as HTTPServer } from "http";
import { initializeWebSocket } from "../websocket";

export function setupWebSocket(httpServer: HTTPServer) {
  const io = initializeWebSocket(httpServer);
  console.log("[WebSocket] Socket.IO initialized");
  return io;
}
