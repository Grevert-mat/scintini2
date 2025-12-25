import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, publicProcedure, router } from "../_core/trpc";
import {
  createRoom,
  getRoomByCode,
  getRoomById,
  addToQueue,
  getQueueForRoom,
  removeFromQueue,
  reorderQueue,
  clearQueue,
  addToHistory,
  getPlayHistory,
  addParticipant,
  removeParticipant,
  getRoomParticipants,
  updateRoomPlayback,
} from "../db";
import { searchKaraokeVideos, getVideoDetails, getEmbedUrl } from "../youtube";
import { nanoid } from "nanoid";

export const karaokeRouter = router({
  // Criar uma nova sala de karaokê
  createRoom: protectedProcedure
    .input(z.object({ name: z.string().min(1).max(255) }))
    .mutation(async ({ ctx, input }) => {
      const roomCode = nanoid(8).toUpperCase();
      const room = await createRoom(input.name, ctx.user.id, roomCode);
      
      // Adicionar criador como participante
      await addParticipant(room.id, ctx.user.id);

      return {
        id: room.id,
        roomCode: room.roomCode,
        name: room.name,
        createdAt: room.createdAt,
      };
    }),

  // Entrar em uma sala existente
  joinRoom: protectedProcedure
    .input(z.object({ roomCode: z.string().length(8) }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      // Adicionar como participante
      await addParticipant(room.id, ctx.user.id);

      return {
        id: room.id,
        roomCode: room.roomCode,
        name: room.name,
        isActive: room.isActive,
      };
    }),

  // Obter informações da sala
  getRoom: publicProcedure
    .input(z.object({ roomCode: z.string().length(8) }))
    .query(async ({ input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        return null;
      }

      const queue = await getQueueForRoom(room.id);
      const participants = await getRoomParticipants(room.id);

      return {
        id: room.id,
        roomCode: room.roomCode,
        name: room.name,
        isActive: room.isActive,
        currentVideoId: room.currentVideoId,
        currentVideoTitle: room.currentVideoTitle,
        currentVideoThumbnail: room.currentVideoThumbnail,
        isPlaying: room.isPlaying,
        currentTime: room.currentTime,
        queue: queue.map(s => ({
          id: s.id,
          videoId: s.videoId,
          title: s.title,
          artist: s.artist,
          thumbnail: s.thumbnail,
          duration: s.duration,
          addedBy: s.addedBy,
          position: s.position,
        })),
        participants: participants.length,
      };
    }),

  // Sair de uma sala
  leaveRoom: protectedProcedure
    .input(z.object({ roomCode: z.string().length(8) }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      await removeParticipant(room.id, ctx.user.id);
      return { success: true };
    }),

  // Buscar vídeos de karaokê
  searchKaraoke: publicProcedure
    .input(z.object({ query: z.string().min(1).max(255) }))
    .query(async ({ input }) => {
      try {
        const videos = await searchKaraokeVideos(input.query);
        
        // Obter detalhes adicionais (duração)
        const videosWithDetails = await Promise.all(
          videos.slice(0, 10).map(async (video) => {
            const details = await getVideoDetails(video.videoId);
            return {
              videoId: video.videoId,
              title: video.title,
              artist: video.channelTitle,
              thumbnail: video.thumbnail,
              duration: details?.duration || 0,
            };
          })
        );

        return videosWithDetails;
      } catch (error: any) {
        // Propagar a mensagem de erro específica
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error.message || "Erro desconhecido ao buscar vídeos.",
        });
      }
    }),

  // Adicionar música à fila
  addToQueue: protectedProcedure
    .input(z.object({
      roomCode: z.string().length(8),
      videoId: z.string(),
      title: z.string(),
      artist: z.string().optional(),
      thumbnail: z.string(),
      duration: z.number().optional(),
    }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      const song = await addToQueue(
        room.id,
        input.videoId,
        input.title,
        input.artist,
        input.thumbnail,
        input.duration,
        ctx.user.id
      );

      return {
        id: song.id,
        videoId: song.videoId,
        title: song.title,
        artist: song.artist,
        thumbnail: song.thumbnail,
        duration: song.duration,
        position: song.position,
      };
    }),

  // Obter fila de uma sala
  getQueue: publicProcedure
    .input(z.object({ roomCode: z.string().length(8) }))
    .query(async ({ input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        return [];
      }

      const queue = await getQueueForRoom(room.id);
      return queue.map(s => ({
        id: s.id,
        videoId: s.videoId,
        title: s.title,
        artist: s.artist,
        thumbnail: s.thumbnail,
        duration: s.duration,
        addedBy: s.addedBy,
        position: s.position,
      }));
    }),

  // Remover música da fila
  removeFromQueue: protectedProcedure
    .input(z.object({
      roomCode: z.string().length(8),
      queueId: z.number(),
    }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      await removeFromQueue(input.queueId);
      return { success: true };
    }),

  // Reordenar fila
  reorderQueue: protectedProcedure
    .input(z.object({
      roomCode: z.string().length(8),
      queueId: z.number(),
      newPosition: z.number(),
    }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      await reorderQueue(room.id, input.queueId, input.newPosition);
      return { success: true };
    }),

  // Limpar fila
  clearQueue: protectedProcedure
    .input(z.object({ roomCode: z.string().length(8) }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      await clearQueue(room.id);
      return { success: true };
    }),

  // Atualizar estado de reprodução
  updatePlayback: protectedProcedure
    .input(z.object({
      roomCode: z.string().length(8),
      videoId: z.string(),
      title: z.string(),
      thumbnail: z.string(),
      isPlaying: z.boolean(),
      currentTime: z.number(),
    }))
    .mutation(async ({ ctx, input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        throw new Error("Sala não encontrada");
      }

      await updateRoomPlayback(
        room.id,
        input.videoId,
        input.title,
        input.thumbnail,
        input.isPlaying,
        input.currentTime
      );

      return { success: true };
    }),

  // Obter histórico de reprodução
  getHistory: publicProcedure
    .input(z.object({ roomCode: z.string().length(8), limit: z.number().default(50) }))
    .query(async ({ input }) => {
      const room = await getRoomByCode(input.roomCode);
      if (!room) {
        return [];
      }

      const history = await getPlayHistory(room.id, input.limit);
      return history.map(h => ({
        id: h.id,
        videoId: h.videoId,
        title: h.title,
        artist: h.artist,
        addedBy: h.addedBy,
        playedAt: h.playedAt,
      }));
    }),

  // Obter URL de embed do YouTube
  getEmbedUrl: publicProcedure
    .input(z.object({ videoId: z.string() }))
    .query(({ input }) => {
      return getEmbedUrl(input.videoId);
    }),
});
