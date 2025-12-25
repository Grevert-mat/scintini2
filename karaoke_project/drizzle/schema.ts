import { int, mysqlEnum, mysqlTable, text, timestamp, varchar, boolean, json } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  youtubeAccessToken: text("youtubeAccessToken"), // YouTube OAuth token
  youtubeRefreshToken: text("youtubeRefreshToken"), // YouTube refresh token
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * Salas/Sessões de karaokê
 * Cada sala pode ter múltiplos usuários conectados simultaneamente
 */
export const karaokeRooms = mysqlTable("karaoke_rooms", {
  id: int("id").autoincrement().primaryKey(),
  roomCode: varchar("roomCode", { length: 8 }).notNull().unique(), // Código curto para compartilhamento
  name: varchar("name", { length: 255 }).notNull(),
  createdBy: int("createdBy").notNull(), // ID do usuário que criou
  isActive: boolean("isActive").default(true).notNull(),
  currentVideoId: varchar("currentVideoId", { length: 255 }), // ID do vídeo em reprodução
  currentVideoTitle: varchar("currentVideoTitle", { length: 500 }),
  currentVideoThumbnail: text("currentVideoThumbnail"), // URL da thumbnail
  isPlaying: boolean("isPlaying").default(false).notNull(),
  currentTime: int("currentTime").default(0).notNull(), // Tempo em segundos
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type KaraokeRoom = typeof karaokeRooms.$inferSelect;
export type InsertKaraokeRoom = typeof karaokeRooms.$inferInsert;

/**
 * Fila de músicas em cada sala
 */
export const songQueue = mysqlTable("song_queue", {
  id: int("id").autoincrement().primaryKey(),
  roomId: int("roomId").notNull(), // Referência à sala
  videoId: varchar("videoId", { length: 255 }).notNull(), // ID do vídeo YouTube
  title: varchar("title", { length: 500 }).notNull(), // Título da música
  artist: varchar("artist", { length: 255 }), // Artista/Cantor
  thumbnail: text("thumbnail"), // URL da thumbnail
  duration: int("duration"), // Duração em segundos
  addedBy: int("addedBy").notNull(), // ID do usuário que adicionou
  position: int("position").notNull(), // Posição na fila (0 = próxima)
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type SongQueue = typeof songQueue.$inferSelect;
export type InsertSongQueue = typeof songQueue.$inferInsert;

/**
 * Histórico de músicas reproduzidas
 */
export const playHistory = mysqlTable("play_history", {
  id: int("id").autoincrement().primaryKey(),
  roomId: int("roomId").notNull(),
  videoId: varchar("videoId", { length: 255 }).notNull(),
  title: varchar("title", { length: 500 }).notNull(),
  artist: varchar("artist", { length: 255 }),
  addedBy: int("addedBy").notNull(),
  playedAt: timestamp("playedAt").defaultNow().notNull(),
});

export type PlayHistory = typeof playHistory.$inferSelect;
export type InsertPlayHistory = typeof playHistory.$inferInsert;

/**
 * Participantes de uma sala
 */
export const roomParticipants = mysqlTable("room_participants", {
  id: int("id").autoincrement().primaryKey(),
  roomId: int("roomId").notNull(),
  userId: int("userId").notNull(),
  joinedAt: timestamp("joinedAt").defaultNow().notNull(),
  lastActivity: timestamp("lastActivity").defaultNow().notNull(),
});

export type RoomParticipant = typeof roomParticipants.$inferSelect;
export type InsertRoomParticipant = typeof roomParticipants.$inferInsert;
