import { describe, expect, it } from "vitest";
import { searchKaraokeVideos } from "./youtube";

describe("YouTube API Integration", () => {
  it("should search for karaoke videos successfully", async () => {
    const results = await searchKaraokeVideos("Imagine");
    
    expect(results).toBeDefined();
    expect(Array.isArray(results)).toBe(true);
    expect(results.length).toBeGreaterThan(0);
    
    // Verify structure of results
    if (results.length > 0) {
      const firstResult = results[0];
      expect(firstResult).toHaveProperty("videoId");
      expect(firstResult).toHaveProperty("title");
      expect(firstResult).toHaveProperty("thumbnail");
      expect(firstResult.title.toLowerCase()).toContain("karaoke");
    }
  }, { timeout: 10000 });
});
