import { Server as HTTPServer } from "http";
import { Server as SocketIOServer, Socket } from "socket.io";
import { getDb, updateLastActivity } from "./db";

interface RoomState {
  roomId: number;
  currentVideoId?: string;
  currentVideoTitle?: string;
  currentVideoThumbnail?: string;
  isPlaying: boolean;
  currentTime: number;
  queue: any[];
}

const roomStates = new Map<string, RoomState>();
const userSockets = new Map<number, Set<string>>(); // userId -> Set of socketIds

export function initializeWebSocket(httpServer: HTTPServer) {
  const io = new SocketIOServer(httpServer, {
    cors: {
      origin: "*",
      methods: ["GET", "POST"],
    },
  });

  io.on("connection", (socket: Socket) => {
    console.log(`[WebSocket] User connected: ${socket.id}`);

    // Evento: Usuário entra em uma sala
    socket.on("join-room", async (data: { roomCode: string; userId: number; userName: string }) => {
      try {
        const { roomCode, userId, userName } = data;
        const roomId = `room:${roomCode}`;

        // Adicionar socket ao usuário
        if (!userSockets.has(userId)) {
          userSockets.set(userId, new Set());
        }
        userSockets.get(userId)!.add(socket.id);

        // Entrar na sala
        socket.join(roomId);

        // Atualizar última atividade no banco
        const db = await getDb();
        if (db) {
          // Assumindo que temos a função para obter roomId pelo roomCode
          // Por enquanto, vamos apenas registrar no mapa
        }

        // Enviar estado atual da sala para o novo usuário
        const roomState = roomStates.get(roomId) || {
          roomId: parseInt(roomCode),
          isPlaying: false,
          currentTime: 0,
          queue: [],
        };

        socket.emit("room-state", roomState);

        // Notificar outros usuários que alguém entrou
        socket.to(roomId).emit("user-joined", {
          userId,
          userName,
          timestamp: new Date(),
        });

        console.log(`[WebSocket] User ${userId} (${userName}) joined room ${roomCode}`);
      } catch (error) {
        console.error("[WebSocket] Erro ao entrar na sala:", error);
        socket.emit("error", { message: "Falha ao entrar na sala" });
      }
    });

    // Evento: Adicionar música à fila
    socket.on("add-to-queue", (data: { roomCode: string; song: any }) => {
      const { roomCode, song } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState) {
        roomState.queue.push(song);
        io.to(roomId).emit("queue-updated", roomState.queue);
        console.log(`[WebSocket] Song added to queue in room ${roomCode}`);
      }
    });

    // Evento: Remover música da fila
    socket.on("remove-from-queue", (data: { roomCode: string; queueId: number }) => {
      const { roomCode, queueId } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState) {
        roomState.queue = roomState.queue.filter((s: any) => s.id !== queueId);
        io.to(roomId).emit("queue-updated", roomState.queue);
        console.log(`[WebSocket] Song removed from queue in room ${roomCode}`);
      }
    });

    // Evento: Reordenar fila
    socket.on("reorder-queue", (data: { roomCode: string; queue: any[] }) => {
      const { roomCode, queue } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState) {
        roomState.queue = queue;
        io.to(roomId).emit("queue-updated", queue);
        console.log(`[WebSocket] Queue reordered in room ${roomCode}`);
      }
    });

    // Evento: Reproduzir vídeo
    socket.on("play-video", (data: { roomCode: string; videoId: string; title: string; thumbnail: string }) => {
      const { roomCode, videoId, title, thumbnail } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId) || {
        roomId: parseInt(roomCode),
        isPlaying: false,
        currentTime: 0,
        queue: [],
      };

      roomState.currentVideoId = videoId;
      roomState.currentVideoTitle = title;
      roomState.currentVideoThumbnail = thumbnail;
      roomState.isPlaying = true;
      roomState.currentTime = 0;

      roomStates.set(roomId, roomState);
      io.to(roomId).emit("video-playing", {
        videoId,
        title,
        thumbnail,
        timestamp: new Date(),
      });

      console.log(`[WebSocket] Video playing in room ${roomCode}: ${title}`);
    });

    // Evento: Play/Pause
    socket.on("toggle-playback", (data: { roomCode: string; isPlaying: boolean; currentTime: number }) => {
      const { roomCode, isPlaying, currentTime } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState) {
        roomState.isPlaying = isPlaying;
        roomState.currentTime = currentTime;
        io.to(roomId).emit("playback-toggled", { isPlaying, currentTime });
        console.log(`[WebSocket] Playback toggled in room ${roomCode}: ${isPlaying ? "playing" : "paused"}`);
      }
    });

    // Evento: Sincronizar tempo
    socket.on("sync-time", (data: { roomCode: string; currentTime: number }) => {
      const { roomCode, currentTime } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState) {
        roomState.currentTime = currentTime;
        io.to(roomId).emit("time-synced", currentTime);
      }
    });

    // Evento: Pular para próxima música
    socket.on("skip-video", (data: { roomCode: string; nextSong?: any }) => {
      const { roomCode, nextSong } = data;
      const roomId = `room:${roomCode}`;

      const roomState = roomStates.get(roomId);
      if (roomState && nextSong) {
        roomState.currentVideoId = nextSong.videoId;
        roomState.currentVideoTitle = nextSong.title;
        roomState.currentVideoThumbnail = nextSong.thumbnail;
        roomState.currentTime = 0;

        // Remover da fila
        roomState.queue = roomState.queue.filter((s: any) => s.id !== nextSong.id);

        io.to(roomId).emit("video-skipped", {
          nextSong,
          queue: roomState.queue,
        });

        console.log(`[WebSocket] Video skipped in room ${roomCode}`);
      }
    });

    // Evento: Usuário sai da sala
    socket.on("leave-room", (data: { roomCode: string; userId: number }) => {
      const { roomCode, userId } = data;
      const roomId = `room:${roomCode}`;

      socket.leave(roomId);

      // Remover socket do usuário
      const userSocketSet = userSockets.get(userId);
      if (userSocketSet) {
        userSocketSet.delete(socket.id);
        if (userSocketSet.size === 0) {
          userSockets.delete(userId);
        }
      }

      io.to(roomId).emit("user-left", { userId });
      console.log(`[WebSocket] User ${userId} left room ${roomCode}`);
    });

    // Evento: Desconexão
    socket.on("disconnect", () => {
      console.log(`[WebSocket] User disconnected: ${socket.id}`);

      // Limpar referências do usuário
      userSockets.forEach((socketSet, userId) => {
        if (socketSet.has(socket.id)) {
          socketSet.delete(socket.id);
          if (socketSet.size === 0) {
            userSockets.delete(userId);
          }
        }
      })
    });

    // Tratamento de erro
    socket.on("error", (error: any) => {
      console.error(`[WebSocket] Socket error: ${error}`);
    });
  });

  return io;
}

export function getRoomState(roomCode: string): RoomState | undefined {
  return roomStates.get(`room:${roomCode}`);
}

export function setRoomState(roomCode: string, state: RoomState) {
  roomStates.set(`room:${roomCode}`, state);
}
