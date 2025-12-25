import axios from "axios";
import { logger } from "./_core/logger";

const YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3";
const API_KEY = process.env.YOUTUBE_API_KEY;

export interface YouTubeVideo {
  videoId: string;
  title: string;
  artist?: string;
  thumbnail: string;
  duration?: number;
  channelTitle: string;
}

/**
 * Busca vídeos de karaokê no YouTube
 * Adiciona automaticamente "karaoke" ao termo de busca
 */
export async function searchKaraokeVideos(query: string, maxResults: number = 20): Promise<YouTubeVideo[]> {
  if (!API_KEY) {
    throw new Error("YOUTUBE_API_KEY não configurada");
  }

  try {
    // Adiciona "karaoke" automaticamente à busca
    const searchQuery = `${query} karaoke`;

    const response = await axios.get(`${YOUTUBE_API_BASE}/search`, {
      params: {
        part: "snippet",
        q: searchQuery,
        type: "video",
        maxResults: maxResults,
        key: API_KEY,
        order: "relevance",
        videoCategoryId: "10", // Music category
      },
    });

    const videos: YouTubeVideo[] = response.data.items.map((item: any) => ({
      videoId: item.id.videoId,
      title: item.snippet.title,
      thumbnail: item.snippet.thumbnails.medium?.url || item.snippet.thumbnails.default?.url,
      channelTitle: item.snippet.channelTitle,
    }));

    return videos;
  } catch (error: any) {
        const status = error?.response?.status;
    let errorMessage = error?.response?.data?.error?.message || error?.message || "Erro desconhecido";

    if (status === 403) {
      errorMessage = "A chave da API do YouTube está inválida ou o limite de cota foi excedido. Verifique a chave e a cota.";
    } else if (status) {
      errorMessage = `Erro HTTP ${status}: ${errorMessage}`;
    }
    logger.error("Erro ao buscar vídeos do YouTube", {
      query,
      error: errorMessage,
            status: status,
    });
    throw new Error(`Falha ao buscar vídeos de karaokê: ${errorMessage}`);
  }
}

/**
 * Obtém detalhes de um vídeo específico (incluindo duração)
 */
export async function getVideoDetails(videoId: string): Promise<YouTubeVideo | null> {
  if (!API_KEY) {
    throw new Error("YOUTUBE_API_KEY não configurada");
  }

  try {
    const response = await axios.get(`${YOUTUBE_API_BASE}/videos`, {
      params: {
        part: "snippet,contentDetails",
        id: videoId,
        key: API_KEY,
      },
    });

    if (!response.data.items || response.data.items.length === 0) {
      return null;
    }

    const item = response.data.items[0];
    const duration = parseDuration(item.contentDetails.duration);

    return {
      videoId: item.id,
      title: item.snippet.title,
      thumbnail: item.snippet.thumbnails.medium?.url || item.snippet.thumbnails.default?.url,
      channelTitle: item.snippet.channelTitle,
      duration: duration,
    };
  } catch (error: any) {
        const status = error?.response?.status;
    let errorMessage = error?.response?.data?.error?.message || error?.message || "Erro desconhecido";

    if (status === 403) {
      errorMessage = "A chave da API do YouTube está inválida ou o limite de cota foi excedido. Verifique a chave e a cota.";
    } else if (status) {
      errorMessage = `Erro HTTP ${status}: ${errorMessage}`;
    }
    logger.error("Erro ao obter detalhes do vídeo", {
      videoId,
      error: errorMessage,
    });
    return null;
  }
}

/**
 * Converte duração ISO 8601 para segundos
 * Exemplo: PT1H2M30S → 3750
 */
function parseDuration(duration: string): number {
  const match = duration.match(/PT(\d+H)?(\d+M)?(\d+S)?/);
  if (!match) return 0;

  const hours = parseInt(match[1] || "0") * 3600;
  const minutes = parseInt(match[2] || "0") * 60;
  const seconds = parseInt(match[3] || "0");

  return hours + minutes + seconds;
}

/**
 * Obtém URL de um vídeo do YouTube
 */
export function getVideoUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

/**
 * Obtém URL do embed do YouTube
 */
export function getEmbedUrl(videoId: string): string {
  return `https://www.youtube.com/embed/${videoId}?enablejsapi=1`;
}
