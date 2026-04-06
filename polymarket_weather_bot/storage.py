"""
storage.py — Persistência de trades e sessões em SQLite.

Esquema:
  - trades: registro completo de cada operação paper/real
  - sessions: resumo de cada sessão do bot
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gerenciador de contexto para conexões
# ---------------------------------------------------------------------------

@contextmanager
def get_conn(db_path: str, persistent_conn=None):
    """
    Abre uma conexão ao banco.
    Se persistent_conn for fornecida (modo :memory:), reutiliza-a.
    """
    if persistent_conn is not None:
        yield persistent_conn
        persistent_conn.commit()
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class Storage:
    """
    Interface de alto nível para persistência de dados.
    Cria e migra o banco automaticamente.
    Suporta banco em arquivo (padrão) ou em memória (db_path=":memory:").
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.bot.db_path
        # Para :memory:, mantemos uma conexão persistente única
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _init_db(self):
        with get_conn(self.db_path, self._mem_conn) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id         TEXT UNIQUE NOT NULL,
                    token_id         TEXT NOT NULL,
                    market_name      TEXT,
                    status           TEXT NOT NULL DEFAULT 'OPEN',

                    -- Dados da entrada
                    entry_timestamp  TEXT NOT NULL,
                    entry_price      REAL NOT NULL,
                    bet_size_usd     REAL NOT NULL,
                    shares           REAL NOT NULL,
                    bankroll_before  REAL NOT NULL,

                    -- Leituras das 5 fontes (JSON serializado)
                    weather_sources  TEXT,
                    consensus_temp   REAL,
                    my_probability   REAL,
                    market_price     REAL,
                    edge             REAL,

                    -- Dados da saída (preenchidos ao fechar)
                    exit_timestamp   TEXT,
                    exit_price       REAL,
                    pnl_usd          REAL,
                    pnl_pct          REAL,
                    bankroll_after   REAL,
                    close_reason     TEXT,

                    -- Metadados
                    paper_trade      INTEGER NOT NULL DEFAULT 1,
                    notes            TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_timestamp  TEXT NOT NULL,
                    end_timestamp    TEXT,
                    starting_bankroll REAL NOT NULL,
                    ending_bankroll  REAL,
                    total_trades     INTEGER DEFAULT 0,
                    winning_trades   INTEGER DEFAULT 0,
                    losing_trades    INTEGER DEFAULT 0,
                    total_pnl        REAL DEFAULT 0.0,
                    notes            TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trades_status
                    ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_token
                    ON trades(token_id);
            """)
        logger.info("Banco de dados inicializado: %s", self.db_path)

    # ------------------------------------------------------------------
    # Operações em trades
    # ------------------------------------------------------------------

    def save_trade_open(
        self,
        trade_id: str,
        token_id: str,
        market_name: str,
        entry_price: float,
        bet_size_usd: float,
        shares: float,
        bankroll_before: float,
        weather_sources: dict,
        consensus_temp: float,
        my_probability: float,
        market_price: float,
        edge: float,
        paper_trade: bool = True,
    ) -> int:
        """Registra a abertura de uma nova posição."""
        now = datetime.now(timezone.utc).isoformat()
        with get_conn(self.db_path, self._mem_conn) as conn:
            cursor = conn.execute(
                """
                INSERT INTO trades (
                    trade_id, token_id, market_name, status,
                    entry_timestamp, entry_price, bet_size_usd, shares, bankroll_before,
                    weather_sources, consensus_temp, my_probability, market_price, edge,
                    paper_trade
                ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id, token_id, market_name,
                    now, entry_price, bet_size_usd, shares, bankroll_before,
                    json.dumps(weather_sources), consensus_temp, my_probability,
                    market_price, edge,
                    1 if paper_trade else 0,
                ),
            )
            row_id = cursor.lastrowid
        logger.info("Trade aberto salvo: %s (ID=%d)", trade_id, row_id)
        return row_id

    def save_trade_close(
        self,
        trade_id: str,
        exit_price: float,
        bankroll_after: float,
        close_reason: str,
    ) -> bool:
        """Atualiza um trade existente com os dados de fechamento."""
        with get_conn(self.db_path, self._mem_conn) as conn:
            row = conn.execute(
                "SELECT entry_price, bet_size_usd, shares FROM trades WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()

            if not row:
                logger.warning("Trade %s não encontrado para fechar.", trade_id)
                return False

            entry_price = row["entry_price"]
            shares = row["shares"]
            proceeds = shares * exit_price
            cost = row["bet_size_usd"]
            pnl_usd = proceeds - cost
            pnl_pct = (pnl_usd / cost * 100) if cost > 0 else 0.0

            now = datetime.now(timezone.utc).isoformat()
            status = "CLOSED_PROFIT" if pnl_usd >= 0 else "CLOSED_LOSS"

            conn.execute(
                """
                UPDATE trades SET
                    status          = ?,
                    exit_timestamp  = ?,
                    exit_price      = ?,
                    pnl_usd         = ?,
                    pnl_pct         = ?,
                    bankroll_after  = ?,
                    close_reason    = ?
                WHERE trade_id = ?
                """,
                (status, now, exit_price, pnl_usd, pnl_pct,
                 bankroll_after, close_reason, trade_id),
            )

        logger.info(
            "Trade fechado: %s | PnL: $%.4f (%.2f%%) | Status: %s",
            trade_id, pnl_usd, pnl_pct, status
        )
        return True

    def get_open_trades(self) -> list[dict]:
        """Retorna todas as posições abertas."""
        with get_conn(self.db_path, self._mem_conn) as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status = 'OPEN'"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trade(self, trade_id: str) -> Optional[dict]:
        """Retorna um trade específico pelo ID."""
        with get_conn(self.db_path, self._mem_conn) as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?", (trade_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_trades(self, limit: int = 100) -> list[dict]:
        """Retorna os últimos N trades."""
        with get_conn(self.db_path, self._mem_conn) as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Relatório / estatísticas
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Calcula estatísticas gerais de todos os trades fechados."""
        with get_conn(self.db_path, self._mem_conn) as conn:
            total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            open_trades = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='OPEN'"
            ).fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status LIKE 'CLOSED_%'"
            ).fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='CLOSED_PROFIT'"
            ).fetchone()[0]
            losses = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='CLOSED_LOSS'"
            ).fetchone()[0]
            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0) FROM trades WHERE status LIKE 'CLOSED_%'"
            ).fetchone()[0]

        win_rate = (wins / closed * 100) if closed > 0 else 0.0
        return {
            "total_trades": total,
            "open_positions": open_trades,
            "closed_trades": closed,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate_pct": round(win_rate, 2),
            "total_pnl_usd": round(total_pnl, 4),
        }

    def print_report(self):
        """Imprime um relatório formatado no console."""
        stats = self.get_stats()
        print("\n" + "=" * 55)
        print("  RELATÓRIO DE PERFORMANCE — POLYMARKET WEATHER BOT")
        print("=" * 55)
        print(f"  Total de trades:      {stats['total_trades']}")
        print(f"  Posições abertas:     {stats['open_positions']}")
        print(f"  Trades fechados:      {stats['closed_trades']}")
        print(f"  Vencedores:           {stats['winning_trades']}")
        print(f"  Perdedores:           {stats['losing_trades']}")
        print(f"  Win rate:             {stats['win_rate_pct']}%")
        print(f"  PnL total:            ${stats['total_pnl_usd']:.4f}")
        print("=" * 55)

        recent = self.get_all_trades(limit=10)
        if recent:
            print("\n  Últimos trades:")
            print(f"  {'ID':<22} {'Status':<18} {'PnL':>8} {'Banca':>10}")
            print("  " + "-" * 60)
            for t in recent:
                pnl_str = f"${t['pnl_usd']:.4f}" if t['pnl_usd'] is not None else "—"
                bank_str = f"${t['bankroll_after']:.4f}" if t['bankroll_after'] else "—"
                print(f"  {t['trade_id']:<22} {t['status']:<18} {pnl_str:>8} {bank_str:>10}")
        print()
