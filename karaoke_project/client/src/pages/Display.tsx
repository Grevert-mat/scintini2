import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "wouter";
import { trpc } from "@/lib/trpc";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuth } from "@/_core/hooks/useAuth";
import { Music, Volume2, VolumeX, Play, Pause, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";

interface YouTubePlayer {
  playVideo: () => void;
  pauseVideo: () => void;
  stopVideo: () => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  getVideoData: () => { video_id: string };
  mute: () => void;
  unMute: () => void;
}

export default function Display() {
  const [searchParams] = useSearchParams();
  const roomCode = searchParams.get("room") || "";
  const { user } = useAuth();

  const [currentVideo, setCurrentVideo] = useState<any>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [queue, setQueue] = useState<any[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const playerRef = useRef<YouTubePlayer | null>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const timeUpdateIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Carregar dados da sala
  const { data: roomData } = trpc.karaoke.getRoom.useQuery(
    { roomCode },
    { enabled: !!roomCode }
  );

  // WebSocket
  const { emit } = useWebSocket({
    roomCode,
    userId: user?.id || 0,
    userName: user?.name || "Guest",
    onRoomState: (state) => {
      if (state.currentVideoId) {
        setCurrentVideo({
          videoId: state.currentVideoId,
          title: state.currentVideoTitle,
          thumbnail: state.currentVideoThumbnail,
        });
        setIsPlaying(state.isPlaying);
        setCurrentTime(state.currentTime);
      }
      if (state.queue) {
        setQueue(state.queue);
      }
    },
    onVideoPlaying: (data) => {
      setCurrentVideo({
        videoId: data.videoId,
        title: data.title,
        thumbnail: data.thumbnail,
      });
      setIsPlaying(true);
      setCurrentTime(0);
    },
    onPlaybackToggled: (data) => {
      setIsPlaying(data.isPlaying);
      setCurrentTime(data.currentTime);
    },
    onQueueUpdated: (newQueue) => {
      setQueue(newQueue);
    },
    onVideoSkipped: (data) => {
      if (data.nextSong) {
        setCurrentVideo({
          videoId: data.nextSong.videoId,
          title: data.nextSong.title,
          thumbnail: data.nextSong.thumbnail,
        });
        setCurrentTime(0);
        setIsPlaying(true);
      }
      setQueue(data.queue);
    },
  });

  // Inicializar YouTube IFrame API
  useEffect(() => {
    if (!window.YT) {
      const tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      const firstScriptTag = document.getElementsByTagName("script")[0];
      firstScriptTag?.parentNode?.insertBefore(tag, firstScriptTag);
    }

    window.onYouTubeIframeAPIReady = () => {
      console.log("[YouTube] IFrame API ready");
    };
  }, []);

  // Criar player quando temos vídeo e container
  useEffect(() => {
    if (!currentVideo?.videoId || !playerContainerRef.current) return;

    if (!window.YT?.Player) {
      console.log("[YouTube] Waiting for YT.Player...");
      return;
    }

    // Limpar player anterior
    if (playerRef.current) {
      try {
        playerRef.current.stopVideo();
      } catch (e) {
        console.log("[YouTube] Error stopping previous video");
      }
    }

    playerContainerRef.current.innerHTML = "";

    const player = new window.YT.Player(playerContainerRef.current, {
      height: "100%",
      width: "100%",
      videoId: currentVideo.videoId,
      playerVars: {
        autoplay: isPlaying ? 1 : 0,
        controls: 1,
        modestbranding: 1,
        rel: 0,
        showinfo: 0,
      },
      events: {
        onReady: (event: any) => {
          playerRef.current = event.target;
          console.log("[YouTube] Player ready");
          if (isPlaying) {
            event.target.playVideo();
          }
        },
        onStateChange: (event: any) => {
          const state = event.data;
          if (state === window.YT.PlayerState.ENDED) {
            handleSkip();
          }
        },
      },
    });
  }, [currentVideo?.videoId]);

  // Sincronizar tempo
  useEffect(() => {
    if (!playerRef.current || !isPlaying) return;

    timeUpdateIntervalRef.current = setInterval(() => {
      try {
        const time = playerRef.current?.getCurrentTime?.() || 0;
        setCurrentTime(time);
        emit("sync-time", { roomCode, currentTime: time });
      } catch (e) {
        console.log("[YouTube] Error getting current time");
      }
    }, 1000);

    return () => {
      if (timeUpdateIntervalRef.current) {
        clearInterval(timeUpdateIntervalRef.current);
      }
    };
  }, [isPlaying, roomCode, emit]);

  // Play/Pause
  const handlePlayPause = () => {
    if (!playerRef.current) return;

    const newIsPlaying = !isPlaying;
    if (newIsPlaying) {
      playerRef.current.playVideo();
    } else {
      playerRef.current.pauseVideo();
    }

    setIsPlaying(newIsPlaying);
    emit("toggle-playback", { roomCode, isPlaying: newIsPlaying, currentTime });
  };

  // Skip
  const handleSkip = () => {
    const nextSong = queue[0];
    if (nextSong) {
      emit("skip-video", { roomCode, nextSong });
    }
  };

  // Mute/Unmute
  const handleMute = () => {
    if (!playerRef.current) return;

    if (isMuted) {
      playerRef.current.unMute();
    } else {
      playerRef.current.mute();
    }
    setIsMuted(!isMuted);
  };

  if (!roomCode) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Music className="w-16 h-16 mx-auto mb-4 text-purple-400" />
          <h1 className="text-3xl font-bold text-white mb-2">Karaokê YouTube</h1>
          <p className="text-slate-300">Acesse com um código de sala válido</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col">
      {/* Player Container */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full h-full max-w-6xl bg-black rounded-lg overflow-hidden shadow-2xl">
          <div
            ref={playerContainerRef}
            className="w-full h-full"
            style={{ aspectRatio: "16 / 9" }}
          />
        </div>
      </div>

      {/* Controls and Info */}
      <div className="bg-slate-800 border-t border-slate-700 p-6">
        {/* Current Song Info */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-2">
            {currentVideo?.title || "Aguardando música..."}
          </h2>
          <p className="text-slate-300">
            {currentTime.toFixed(0)}s / Código da sala: {roomCode}
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 mb-6">
          <Button
            onClick={handlePlayPause}
            variant="default"
            size="lg"
            className="bg-purple-600 hover:bg-purple-700"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5" />
            ) : (
              <Play className="w-5 h-5" />
            )}
          </Button>

          <Button
            onClick={handleSkip}
            variant="outline"
            size="lg"
            disabled={queue.length === 0}
          >
            <SkipForward className="w-5 h-5" />
          </Button>

          <Button
            onClick={handleMute}
            variant="ghost"
            size="lg"
          >
            {isMuted ? (
              <VolumeX className="w-5 h-5" />
            ) : (
              <Volume2 className="w-5 h-5" />
            )}
          </Button>
        </div>

        {/* Next Songs */}
        {queue.length > 0 && (
          <div className="bg-slate-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">
              Próximas músicas ({queue.length})
            </h3>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {queue.slice(0, 3).map((song, idx) => (
                <div
                  key={song.id}
                  className="flex items-center gap-3 p-2 bg-slate-600 rounded"
                >
                  <span className="text-sm font-semibold text-purple-400 min-w-6">
                    #{idx + 1}
                  </span>
                  <span className="text-sm text-white truncate">
                    {song.title}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}
