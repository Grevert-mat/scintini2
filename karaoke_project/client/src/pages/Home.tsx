import { useState } from "react";
import { useLocation } from "wouter";
import { trpc } from "@/lib/trpc";
import { useAuth } from "@/_core/hooks/useAuth";
import { Music, Play, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { getLoginUrl } from "@/const";

export default function Home() {
  const [, setLocation] = useLocation();
  const { user, isAuthenticated, loading } = useAuth();
  const [roomCode, setRoomCode] = useState("");
  const [roomName, setRoomName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const createRoomMutation = trpc.karaoke.createRoom.useMutation();
  const joinRoomMutation = trpc.karaoke.joinRoom.useMutation();

  const handleCreateRoom = async () => {
    if (!roomName.trim()) {
      toast.error("Digite um nome para a sala");
      return;
    }

    setIsCreating(true);
    try {
      const room = await createRoomMutation.mutateAsync({ name: roomName });
      toast.success("Sala criada com sucesso!");
      setLocation(`/remote?room=${room.roomCode}`);
    } catch (error) {
      toast.error("Erro ao criar sala");
    } finally {
      setIsCreating(false);
    }
  };

  const handleJoinRoom = async () => {
    if (!roomCode.trim()) {
      toast.error("Digite um código de sala");
      return;
    }

    try {
      await joinRoomMutation.mutateAsync({ roomCode: roomCode.toUpperCase() });
      toast.success("Entrou na sala!");
      setLocation(`/remote?room=${roomCode.toUpperCase()}`);
    } catch (error) {
      toast.error("Sala não encontrada ou erro ao entrar");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-white">Carregando...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="text-center">
          <Music className="w-16 h-16 mx-auto mb-6 text-purple-400" />
          <h1 className="text-4xl font-bold text-white mb-2">Karaokê YouTube</h1>
          <p className="text-slate-300 mb-8 max-w-md">
            Controle uma tela de karaokê com seu celular. Busque músicas, crie filas e divirta-se com amigos!
          </p>
          <Button
            onClick={() => window.location.href = getLoginUrl()}
            className="bg-purple-600 hover:bg-purple-700 text-white px-8 py-3 text-lg"
          >
            Entrar com Manus
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col">
      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700 p-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <Music className="w-8 h-8 text-purple-400" />
            <h1 className="text-3xl font-bold text-white">Karaokê YouTube</h1>
          </div>
          <p className="text-slate-300">Bem-vindo, {user?.name}!</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="max-w-2xl w-full grid md:grid-cols-2 gap-6">
          {/* Create Room */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-purple-500 transition">
            <div className="flex items-center gap-3 mb-4">
              <Play className="w-6 h-6 text-purple-400" />
              <h2 className="text-xl font-bold text-white">Criar Sala</h2>
            </div>
            <p className="text-slate-300 text-sm mb-4">
              Crie uma nova sala de karaokê, busque músicas e compartilhe o código com seus amigos
            </p>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Nome da sala (ex: Festa do João)"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-purple-500"
              />
              <Button
                onClick={handleCreateRoom}
                disabled={isCreating || !roomName.trim()}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white"
              >
                {isCreating ? "Criando..." : "Criar Sala"}
              </Button>
            </div>
          </div>

          {/* Join Room */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-purple-500 transition">
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-6 h-6 text-purple-400" />
              <h2 className="text-xl font-bold text-white">Entrar em Sala</h2>
            </div>
            <p className="text-slate-300 text-sm mb-4">
              Digite o código de uma sala para se conectar e controlar a reprodução
            </p>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Código da sala (ex: ABC12345)"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                onKeyPress={(e) => e.key === "Enter" && handleJoinRoom()}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 uppercase"
              />
              <Button
                onClick={handleJoinRoom}
                disabled={!roomCode.trim()}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white"
              >
                Entrar na Sala
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-slate-800 border-t border-slate-700 p-4 text-center">
        <p className="text-slate-400 text-sm">
          © 2025 Karaokê YouTube - Divirta-se cantando!
        </p>
      </div>
    </div>
  );
}
