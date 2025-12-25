import { useEffect, useRef, useCallback } from "react";
import { io, Socket } from "socket.io-client";

interface UseWebSocketOptions {
  roomCode?: string;
  userId?: number;
  userName?: string;
  onRoomState?: (state: any) => void;
  onQueueUpdated?: (queue: any[]) => void;
  onVideoPlaying?: (data: any) => void;
  onPlaybackToggled?: (data: any) => void;
  onVideoSkipped?: (data: any) => void;
  onUserJoined?: (data: any) => void;
  onUserLeft?: (data: any) => void;
  onTimeSynced?: (time: number) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const socketRef = useRef<Socket | null>(null);
  const isConnectedRef = useRef(false);

  useEffect(() => {
    if (!options.roomCode || !options.userId || !options.userName) {
      return;
    }

    // Conectar ao WebSocket
    const socket = io(window.location.origin, {
      transports: ["websocket", "polling"],
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("[WebSocket] Connected");
      isConnectedRef.current = true;

      // Entrar na sala
      socket.emit("join-room", {
        roomCode: options.roomCode,
        userId: options.userId,
        userName: options.userName,
      });
    });

    socket.on("room-state", (state: any) => {
      console.log("[WebSocket] Received room state:", state);
      options.onRoomState?.(state);
    });

    socket.on("queue-updated", (queue: any[]) => {
      console.log("[WebSocket] Queue updated:", queue);
      options.onQueueUpdated?.(queue);
    });

    socket.on("video-playing", (data: any) => {
      console.log("[WebSocket] Video playing:", data);
      options.onVideoPlaying?.(data);
    });

    socket.on("playback-toggled", (data: any) => {
      console.log("[WebSocket] Playback toggled:", data);
      options.onPlaybackToggled?.(data);
    });

    socket.on("video-skipped", (data: any) => {
      console.log("[WebSocket] Video skipped:", data);
      options.onVideoSkipped?.(data);
    });

    socket.on("user-joined", (data: any) => {
      console.log("[WebSocket] User joined:", data);
      options.onUserJoined?.(data);
    });

    socket.on("user-left", (data: any) => {
      console.log("[WebSocket] User left:", data);
      options.onUserLeft?.(data);
    });

    socket.on("time-synced", (time: number) => {
      console.log("[WebSocket] Time synced:", time);
      options.onTimeSynced?.(time);
    });

    socket.on("disconnect", () => {
      console.log("[WebSocket] Disconnected");
      isConnectedRef.current = false;
    });

    socket.on("error", (error: any) => {
      console.error("[WebSocket] Error:", error);
    });

    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, [options.roomCode, options.userId, options.userName]);

  const emit = useCallback((event: string, data?: any) => {
    if (socketRef.current && isConnectedRef.current) {
      socketRef.current.emit(event, data);
    }
  }, []);

  return {
    socket: socketRef.current,
    isConnected: isConnectedRef.current,
    emit,
  };
}
