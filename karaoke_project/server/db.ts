import { eq, and, desc } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { InsertUser, users, karaokeRooms, songQueue, playHistory, roomParticipants, KaraokeRoom, SongQueue, PlayHistory } from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: ReturnType<typeof drizzle> | null = null;

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

// ============= Karaoke Rooms Functions =============

export async function createRoom(name: string, userId: number, roomCode: string): Promise<KaraokeRoom> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  const result = await db.insert(karaokeRooms).values({
    name,
    createdBy: userId,
    roomCode,
    isActive: true,
  });

  const rooms = await db.select().from(karaokeRooms).where(eq(karaokeRooms.roomCode, roomCode)).limit(1);
  return rooms[0]!;
}

export async function getRoomByCode(roomCode: string): Promise<KaraokeRoom | undefined> {
  const db = await getDb();
  if (!db) return undefined;

  const result = await db.select().from(karaokeRooms).where(eq(karaokeRooms.roomCode, roomCode)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getRoomById(roomId: number): Promise<KaraokeRoom | undefined> {
  const db = await getDb();
  if (!db) return undefined;

  const result = await db.select().from(karaokeRooms).where(eq(karaokeRooms.id, roomId)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function updateRoomPlayback(
  roomId: number,
  videoId: string,
  title: string,
  thumbnail: string,
  isPlaying: boolean,
  currentTime: number
) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.update(karaokeRooms)
    .set({
      currentVideoId: videoId,
      currentVideoTitle: title,
      currentVideoThumbnail: thumbnail,
      isPlaying,
      currentTime,
      updatedAt: new Date(),
    })
    .where(eq(karaokeRooms.id, roomId));
}

// ============= Song Queue Functions =============

export async function addToQueue(
  roomId: number,
  videoId: string,
  title: string,
  artist: string | undefined,
  thumbnail: string | undefined,
  duration: number | undefined,
  userId: number
): Promise<SongQueue> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  // Get the next position
  const lastSong = await db.select().from(songQueue)
    .where(eq(songQueue.roomId, roomId))
    .orderBy(desc(songQueue.position))
    .limit(1);

  const nextPosition = lastSong.length > 0 ? (lastSong[0]!.position + 1) : 0;

  const result = await db.insert(songQueue).values({
    roomId,
    videoId,
    title,
    artist,
    thumbnail,
    duration,
    addedBy: userId,
    position: nextPosition,
  });

  const songs = await db.select().from(songQueue)
    .where(and(eq(songQueue.roomId, roomId), eq(songQueue.videoId, videoId)))
    .limit(1);

  return songs[0]!;
}

export async function getQueueForRoom(roomId: number): Promise<SongQueue[]> {
  const db = await getDb();
  if (!db) return [];

  return await db.select().from(songQueue)
    .where(eq(songQueue.roomId, roomId))
    .orderBy(songQueue.position);
}

export async function removeFromQueue(queueId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.delete(songQueue).where(eq(songQueue.id, queueId));
}

export async function reorderQueue(roomId: number, queueId: number, newPosition: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  // Get all songs in the queue
  const allSongs = await getQueueForRoom(roomId);
  
  // Find the song being moved
  const songToMove = allSongs.find(s => s.id === queueId);
  if (!songToMove) throw new Error("Song not found in queue");

  // Remove the song from its current position
  const otherSongs = allSongs.filter(s => s.id !== queueId);

  // Insert it at the new position
  const reorderedSongs = [
    ...otherSongs.slice(0, newPosition),
    songToMove,
    ...otherSongs.slice(newPosition),
  ];

  // Update all positions
  for (let i = 0; i < reorderedSongs.length; i++) {
    await db.update(songQueue)
      .set({ position: i })
      .where(eq(songQueue.id, reorderedSongs[i]!.id));
  }
}

export async function clearQueue(roomId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.delete(songQueue).where(eq(songQueue.roomId, roomId));
}

// ============= Play History Functions =============

export async function addToHistory(
  roomId: number,
  videoId: string,
  title: string,
  artist: string | undefined,
  userId: number
) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.insert(playHistory).values({
    roomId,
    videoId,
    title,
    artist,
    addedBy: userId,
  });
}

export async function getPlayHistory(roomId: number, limit: number = 50): Promise<PlayHistory[]> {
  const db = await getDb();
  if (!db) return [];

  return await db.select().from(playHistory)
    .where(eq(playHistory.roomId, roomId))
    .orderBy(desc(playHistory.playedAt))
    .limit(limit);
}

// ============= Room Participants Functions =============

export async function addParticipant(roomId: number, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  // Check if already exists
  const existing = await db.select().from(roomParticipants)
    .where(and(eq(roomParticipants.roomId, roomId), eq(roomParticipants.userId, userId)))
    .limit(1);

  if (existing.length === 0) {
    await db.insert(roomParticipants).values({
      roomId,
      userId,
    });
  }
}

export async function removeParticipant(roomId: number, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.delete(roomParticipants)
    .where(and(eq(roomParticipants.roomId, roomId), eq(roomParticipants.userId, userId)));
}

export async function getRoomParticipants(roomId: number) {
  const db = await getDb();
  if (!db) return [];

  return await db.select().from(roomParticipants)
    .where(eq(roomParticipants.roomId, roomId));
}

export async function updateLastActivity(roomId: number, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  await db.update(roomParticipants)
    .set({ lastActivity: new Date() })
    .where(and(eq(roomParticipants.roomId, roomId), eq(roomParticipants.userId, userId)));
}

// Import types for export
export type { KaraokeRoom, SongQueue, PlayHistory };
