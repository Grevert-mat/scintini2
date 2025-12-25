import { describe, expect, it, beforeEach } from "vitest";
import { appRouter } from "./routers";
import type { TrpcContext } from "./_core/context";

type AuthenticatedUser = NonNullable<TrpcContext["user"]>;

function createAuthContext(userId: number = 1, userName: string = "Test User"): { ctx: TrpcContext } {
  const user: AuthenticatedUser = {
    id: userId,
    openId: `test-user-${userId}`,
    email: `test${userId}@example.com`,
    name: userName,
    loginMethod: "manus",
    role: "user",
    createdAt: new Date(),
    updatedAt: new Date(),
    lastSignedIn: new Date(),
  };

  const ctx: TrpcContext = {
    user,
    req: {
      protocol: "https",
      headers: {},
    } as TrpcContext["req"],
    res: {
      clearCookie: () => {},
    } as TrpcContext["res"],
  };

  return { ctx };
}

describe("Karaoke Router", () => {
  describe("createRoom", () => {
    it("should create a new karaoke room", async () => {
      const { ctx } = createAuthContext(1, "Room Creator");
      const caller = appRouter.createCaller(ctx);

      const room = await caller.karaoke.createRoom({ name: "Test Room" });

      expect(room).toBeDefined();
      expect(room.name).toBe("Test Room");
      expect(room.roomCode).toBeDefined();
      expect(room.roomCode).toHaveLength(8);
      expect(room.id).toBeDefined();
    });

    it("should reject empty room name", async () => {
      const { ctx } = createAuthContext(1, "Room Creator");
      const caller = appRouter.createCaller(ctx);

      try {
        await caller.karaoke.createRoom({ name: "" });
        expect.fail("Should have thrown an error");
      } catch (error: any) {
        expect(error.message).toContain("Too small");
      }
    });
  });

  describe("searchKaraoke", () => {
    it("should search for karaoke videos", async () => {
      const { ctx } = createAuthContext();
      const caller = appRouter.createCaller(ctx);

      const results = await caller.karaoke.searchKaraoke({ query: "Imagine" });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      const firstResult = results[0];
      expect(firstResult).toHaveProperty("videoId");
      expect(firstResult).toHaveProperty("title");
      expect(firstResult).toHaveProperty("thumbnail");
      expect(firstResult.title.toLowerCase()).toContain("karaoke");
    });

    it("should reject empty search query", async () => {
      const { ctx } = createAuthContext();
      const caller = appRouter.createCaller(ctx);

      try {
        await caller.karaoke.searchKaraoke({ query: "" });
        expect.fail("Should have thrown an error");
      } catch (error: any) {
        expect(error.message).toContain("Too small");
      }
    });
  });

  describe("getEmbedUrl", () => {
    it("should return correct embed URL for video", async () => {
      const { ctx } = createAuthContext();
      const caller = appRouter.createCaller(ctx);

      const url = await caller.karaoke.getEmbedUrl({ videoId: "dQw4w9WgXcQ" });

      expect(url).toBe("https://www.youtube.com/embed/dQw4w9WgXcQ?enablejsapi=1");
    });
  });

  describe("Queue Management", () => {
    it("should add song to queue", async () => {
      const { ctx } = createAuthContext(1, "Queue Manager");
      const caller = appRouter.createCaller(ctx);

      // Create a room first
      const room = await caller.karaoke.createRoom({ name: "Queue Test Room" });

      // Add to queue
      const queueItem = await caller.karaoke.addToQueue({
        roomCode: room.roomCode,
        videoId: "dQw4w9WgXcQ",
        title: "Never Gonna Give You Up - Karaoke",
        artist: "Rick Astley",
        thumbnail: "https://example.com/thumb.jpg",
        duration: 213,
      });

      expect(queueItem).toBeDefined();
      expect(queueItem.videoId).toBe("dQw4w9WgXcQ");
      expect(queueItem.title).toBe("Never Gonna Give You Up - Karaoke");
      expect(queueItem.position).toBe(0);
    });

    it("should get queue for room", async () => {
      const { ctx } = createAuthContext(1, "Queue Manager");
      const caller = appRouter.createCaller(ctx);

      // Create a room
      const room = await caller.karaoke.createRoom({ name: "Get Queue Test Room" });

      // Add multiple songs
      await caller.karaoke.addToQueue({
        roomCode: room.roomCode,
        videoId: "video1",
        title: "Song 1 - Karaoke",
        artist: "Artist 1",
        thumbnail: "https://example.com/thumb1.jpg",
      });

      await caller.karaoke.addToQueue({
        roomCode: room.roomCode,
        videoId: "video2",
        title: "Song 2 - Karaoke",
        artist: "Artist 2",
        thumbnail: "https://example.com/thumb2.jpg",
      });

      // Get queue
      const queue = await caller.karaoke.getQueue({ roomCode: room.roomCode });

      expect(Array.isArray(queue)).toBe(true);
      expect(queue.length).toBe(2);
      expect(queue[0]?.title).toBe("Song 1 - Karaoke");
      expect(queue[1]?.title).toBe("Song 2 - Karaoke");
    });

    it("should remove song from queue", async () => {
      const { ctx } = createAuthContext(1, "Queue Manager");
      const caller = appRouter.createCaller(ctx);

      // Create a room and add a song
      const room = await caller.karaoke.createRoom({ name: "Remove Queue Test Room" });
      const queueItem = await caller.karaoke.addToQueue({
        roomCode: room.roomCode,
        videoId: "video1",
        title: "Song 1 - Karaoke",
        artist: "Artist 1",
        thumbnail: "https://example.com/thumb1.jpg",
      });

      // Remove from queue
      await caller.karaoke.removeFromQueue({
        roomCode: room.roomCode,
        queueId: queueItem.id,
      });

      // Verify it's removed
      const queue = await caller.karaoke.getQueue({ roomCode: room.roomCode });
      expect(queue.length).toBe(0);
    });
  });

  describe("Room Management", () => {
    it("should join an existing room", async () => {
      const { ctx: creatorCtx } = createAuthContext(1, "Room Creator");
      const { ctx: joinerCtx } = createAuthContext(2, "Room Joiner");

      const creatorCaller = appRouter.createCaller(creatorCtx);
      const joinerCaller = appRouter.createCaller(joinerCtx);

      // Create room
      const room = await creatorCaller.karaoke.createRoom({ name: "Join Test Room" });

      // Join room
      const joinedRoom = await joinerCaller.karaoke.joinRoom({ roomCode: room.roomCode });

      expect(joinedRoom).toBeDefined();
      expect(joinedRoom.roomCode).toBe(room.roomCode);
      expect(joinedRoom.name).toBe("Join Test Room");
    });

    it("should get room information", async () => {
      const { ctx } = createAuthContext(1, "Room Creator");
      const caller = appRouter.createCaller(ctx);

      // Create room
      const room = await caller.karaoke.createRoom({ name: "Info Test Room" });

      // Get room info
      const roomInfo = await caller.karaoke.getRoom({ roomCode: room.roomCode });

      expect(roomInfo).toBeDefined();
      expect(roomInfo?.name).toBe("Info Test Room");
      expect(roomInfo?.roomCode).toBe(room.roomCode);
      expect(roomInfo?.isActive).toBe(true);
      expect(Array.isArray(roomInfo?.queue)).toBe(true);
    });
  });
});
