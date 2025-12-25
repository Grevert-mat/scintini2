import { useEffect, useState } from "react";
import { useSearchParams } from "wouter";
import { trpc } from "@/lib/trpc";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuth } from "@/_core/hooks/useAuth";
import {
  Music,
  Search,
  Plus,
  Trash2,
  GripVertical,
  Copy,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";

export default function Remote() {
  const [searchParams] = useSearchParams();
  const roomCode = searchParams.get("room") || "";
  const { user, logout } = useAuth();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [queue, setQueue] = useState<any[]>([]);
  const [currentSong, setCurrentSong] = useState<any>(null);
  const [showLogs, setShowLogs] = useState(false);

  const { data: logs } = trpc.logs.getErrorLogs.useQuery(undefined, {
    enabled: showLogs,
  });

  // Queries
  const { data: roomData } = trpc.karaoke.getRoom.useQuery(
    { roomCode },
    { enabled: !!roomCode }
  );

  const addToQueueMutation = trpc.karaoke.addToQueue.useMutation();
  const removeFromQueueMutation = trpc.karaoke.removeFromQueue.useMutation();
  const leaveRoomMutation = trpc.karaoke.leaveRoom.useMutation();

  // WebSocket
  const { emit } = useWebSocket({
    roomCode,
    userId: user?.id || 0,
    userName: user?.name || "Guest",
    onRoomState: (state) => {
      if (state.currentVideoId) {
        setCurrentSong({
          videoId: state.currentVideoId,
          title: state.currentVideoTitle,
          thumbnail: state.currentVideoThumbnail,
        });
      }
      if (state.queue) {
        setQueue(state.queue);
      }
    },
    onQueueUpdated: (newQueue) => {
      setQueue(newQueue);
    },
    onVideoPlaying: (data) => {
      setCurrentSong({
        videoId: data.videoId,
        title: data.title,
        thumbnail: data.thumbnail,
      });
    },
    onVideoSkipped: (data) => {
      if (data.nextSong) {
        setCurrentSong({
          videoId: data.nextSong.videoId,
          title: data.nextSong.title,
          thumbnail: data.nextSong.thumbnail,
        });
      }
      setQueue(data.queue);
    },
  });

  // Buscar karaokês
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const utils = trpc.useUtils();
      const results = await utils.karaoke.searchKaraoke.fetch({ query: searchQuery });
      setSearchResults(results);
    } catch (error: any) {
      console.error("[Remote] Erro ao buscar músicas:", error);
      const errorMessage = error?.message || "Erro ao buscar músicas";
      toast.error(errorMessage);
    } finally {
      setIsSearching(false);
    }
  };

  // Adicionar à fila
  const handleAddToQueue = async (song: any) => {
    if (!roomCode) return;

    try {
      await addToQueueMutation.mutateAsync({
        roomCode,
        videoId: song.videoId,
        title: song.title,
        artist: song.artist,
        thumbnail: song.thumbnail,
        duration: song.duration,
      });

      // Emitir via WebSocket
      emit("add-to-queue", { roomCode, song });
      toast.success("Música adicionada à fila!");
      setSearchResults([]);
      setSearchQuery("");
    } catch (error: any) {
      console.error("[Remote] Erro ao adicionar música:", error);
      toast.error(error?.message || "Erro ao adicionar música");
    }
  };

  // Remover da fila
  const handleRemoveFromQueue = async (queueId: number) => {
    if (!roomCode) return;

    try {
      await removeFromQueueMutation.mutateAsync({ roomCode, queueId });
      emit("remove-from-queue", { roomCode, queueId });
      toast.success("Música removida da fila");
    } catch (error: any) {
      console.error("[Remote] Erro ao remover música:", error);
      toast.error(error?.message || "Erro ao remover música");
    }
  };

  // Copiar código da sala
  const handleCopyRoomCode = () => {
    navigator.clipboard.writeText(roomCode);
    toast.success("Código da sala copiado!");
  };

  // Sair da sala
  const handleLeaveRoom = async () => {
    if (!roomCode) return;

    try {
      await leaveRoomMutation.mutateAsync({ roomCode });
      emit("leave-room", { roomCode, userId: user?.id });
      await logout();
      window.location.href = "/";
    } catch (error) {
      toast.error("Erro ao sair da sala");
    }
  };

  if (!roomCode) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="text-center">
          <Music className="w-12 h-12 mx-auto mb-4 text-purple-400" />
          <h1 className="text-2xl font-bold text-white mb-2">Karaokê YouTube</h1>
          <p className="text-slate-300">Acesse com um código de sala válido</p>
        </div>
      </div>
    );
  }

  return (
    <>
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 p-4 flex flex-col">
      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700 p-4 sticky top-0 z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Music className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-bold text-white">Karaokê</h1>
          </div>
          <Button
            onClick={handleLeaveRoom}
            variant="ghost"
            size="sm"
            className="text-red-400 hover:text-red-300"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>

        {/* Room Code */}
        <div className="flex items-center gap-2 bg-slate-700 rounded-lg p-2">
          <span className="text-sm text-slate-300 flex-1">Sala: {roomCode}</span>
          <Button
            onClick={handleCopyRoomCode}
            variant="ghost"
            size="sm"
            className="text-slate-400 hover:text-white"
          >
            <Copy className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Current Song */}
      {currentSong && (
        <div className="bg-gradient-to-r from-purple-600 to-purple-700 p-4 text-white">
          <p className="text-xs text-purple-200 mb-1">Tocando agora</p>
          <h2 className="font-bold text-lg truncate">{currentSong.title}</h2>
          {currentSong.thumbnail && (
            <img
              src={currentSong.thumbnail}
              alt={currentSong.title}
              className="w-full h-32 object-cover rounded mt-2"
            />
          )}
        </div>
      )}

      {/* Search */}
      <div className="p-4 bg-slate-800 border-b border-slate-700">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Input
              type="text"
              placeholder="Buscar karaokê..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              className="bg-slate-700 border-slate-600 text-white placeholder-slate-400"
            />
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
          </div>
          <Button
            onClick={handleSearch}
            disabled={isSearching || !searchQuery.trim()}
            className="bg-purple-600 hover:bg-purple-700"
          >
            {isSearching ? "..." : "Buscar"}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="p-4 border-b border-slate-700">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">
              Resultados ({searchResults.length})
            </h3>
            <div className="space-y-2">
              {searchResults.map((song) => (
                <div
                  key={song.videoId}
                  className="flex items-start gap-3 p-3 bg-slate-700 rounded-lg hover:bg-slate-600 transition"
                >
                  <img
                    src={song.thumbnail}
                    alt={song.title}
                    className="w-12 h-12 rounded object-cover flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white truncate">
                      {song.title}
                    </p>
                    <p className="text-xs text-slate-400 truncate">
                      {song.artist}
                    </p>
                  </div>
                  <Button
                    onClick={() => handleAddToQueue(song)}
                    size="sm"
                    variant="ghost"
                    className="text-purple-400 hover:text-purple-300 flex-shrink-0"
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Queue */}
        <div className="p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">
            Fila ({queue.length})
          </h3>
          {queue.length === 0 ? (
            <div className="text-center py-8">
              <Music className="w-8 h-8 mx-auto mb-2 text-slate-500" />
              <p className="text-slate-400 text-sm">Nenhuma música na fila</p>
            </div>
          ) : (
            <div className="space-y-2">
              {queue.map((song, idx) => (
                <div
                  key={song.id}
                  className="flex items-start gap-3 p-3 bg-slate-700 rounded-lg hover:bg-slate-600 transition"
                >
                  <GripVertical className="w-4 h-4 text-slate-500 mt-1 flex-shrink-0" />
                  <img
                    src={song.thumbnail}
                    alt={song.title}
                    className="w-12 h-12 rounded object-cover flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-400">#{idx + 1}</p>
                    <p className="text-sm font-semibold text-white truncate">
                      {song.title}
                    </p>
                    <p className="text-xs text-slate-400 truncate">
                      {song.artist}
                    </p>
                  </div>
                  <Button
                    onClick={() => handleRemoveFromQueue(song.id)}
                    size="sm"
                    variant="ghost"
                    className="text-red-400 hover:text-red-300 flex-shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Botão de Logs */}
      <button
        onClick={() => setShowLogs(true)}
        className="fixed bottom-4 right-4 p-3 bg-red-600 hover:bg-red-700 text-white rounded-full shadow-lg z-40 transition"
        title="Ver logs de erro"
      >
        <AlertCircle className="w-5 h-5" />
      </button>
    </div>

    {/* Modal de Logs */}
    <Dialog open={showLogs} onOpenChange={setShowLogs}>
      <DialogContent className="max-w-2xl max-h-96 overflow-y-auto bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white">Logs de Erro</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          {logs && logs.length > 0 ? (
            logs.map((log: any, idx: number) => (
              <div key={idx} className="bg-slate-800 p-3 rounded text-sm text-slate-200 border-l-2 border-red-500">
                <div className="font-mono text-xs text-slate-400">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </div>
                <div className="font-semibold text-red-400 mt-1">{log.message}</div>
                {log.details && (
                  <div className="text-xs text-slate-400 mt-1 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(log.details, null, 2)}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="text-slate-400 text-center py-4">Nenhum erro registrado</div>
          )}
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
