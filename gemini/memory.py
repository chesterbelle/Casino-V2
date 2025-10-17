"""
====================================================
🧠 GeminiMemory — Memoria viva del Casino V2
====================================================

Objetivo:
---------
Guardar, purgar y portar el conocimiento empírico de cada estrategia
("votante") de reversión a la media para que Gemini pueda:
  - Estimar p̂ (winrate) por estrategia individual
  - Comparar p̂ contra p* y calcular apuesta (Kelly)
  - Purificar el consenso (apagar votantes débiles)

Diseño:
-------
• Ventana de observación deslizante por estrategia/bucket/market (memoria corta activa)
• Persistencia dual:
    - CSV: log cronológico por estrategia/bucket/símbolo/timeframe (portabilidad y auditoría)
    - JSON: snapshot resumido con winrates y conteos (carga rápida)
• API simple para integrar con Gemini y el Croupier:
    - register_vote_set(trade_id, votos)
    - finalize_trade(trade_id, win)  # aplica a TODAS las estrategias que votaron
    - get_winrate(strategy_name), get_all_stats()

Rutas (portables):
------------------
gemini/data/memory_log.csv
gemini/data/memory_state.json

Config (si existe config.py):
-----------------------------
MEMORY_WINDOW (int)       # tamaño de ventana por estrategia (default: 500)
AUTOSAVE_INTERVAL (int)   # cada cuántos trades guardar JSON (default: 10)
CSV_PATH (str)            # ruta del csv (default: "gemini/data/memory_log.csv")
STATE_PATH (str)          # ruta del json (default: "gemini/data/memory_state.json")

Notas:
------
- Cada trade puede tener múltiples estrategias “votantes”.
- Al finalizar el trade, se registra el resultado para CADA estrategia votante.
- La ventana se aplica por estrategia (cada una recuerda solo sus últimos N resultados).
- El JSON mantiene winrate y votos por estrategia para carga inmediata.
- El CSV permite auditar y migrar el “estado mental” entre máquinas.
====================================================
"""

from __future__ import annotations

import os
import json
import csv
from collections import deque, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

# ----------------------------------------------------
# Carga opcional de config del proyecto
# (usa defaults si no existe o no define los atributos)
# ----------------------------------------------------
try:
    import config
except Exception:
    config = None


def _cfg(name: str, default):
    return getattr(config, name, default) if config and hasattr(config, name) else default


# ============================
# Parámetros por defecto
# ============================
MEMORY_WINDOW: int = _cfg("MEMORY_WINDOW", 500)
AUTOSAVE_INTERVAL: int = _cfg("AUTOSAVE_INTERVAL", 10)
CSV_PATH: str = _cfg("CSV_PATH", "gemini/data/memory_log.csv")
STATE_PATH: str = _cfg("STATE_PATH", "gemini/data/memory_state.json")


class GeminiMemory:
    """
    Clase principal de memoria.
    Mantiene:
      - Ventana por clave (estrategia/bucket/símbolo)
      - Mapa trade_id -> lista de votantes normalizados
      - Log CSV (histórico portable)
      - Snapshot JSON (carga rápida)

    Uso típico en el flujo:
    -----------------------
    # 🔧 PUNTO DE INTEGRACIÓN (antes de ejecutar la apuesta)
    memory.register_vote_set(trade_id, [
        {"strategy": "RSIReversion", "bucket": "BBW=L|RS1|H=M", "symbol": "LTCUSDT"},
        {"strategy": "KeltnerReversion", "bucket": "BBW=L|RS1|H=M", "symbol": "LTCUSDT"},
    ])

    # ... se ejecuta el trade con el Croupier y el Feed ...

    # 🔧 PUNTO DE INTEGRACIÓN (al cerrar la apuesta)
    memory.finalize_trade(trade_id, win=True)  # o False

    p_rsi = memory.get_winrate("LTCUSDT@15min|BBW=L|RS1|H=M|RSIReversion")
    stats = memory.get_all_stats()
    """

    def __init__(
        self,
        csv_path: str = CSV_PATH,
        state_path: str = STATE_PATH,
        memory_window: int = MEMORY_WINDOW,
        autosave_interval: int = AUTOSAVE_INTERVAL,
    ):
        self.csv_path = csv_path
        self.state_path = state_path
        self.memory_window = int(memory_window)
        self.autosave_interval = int(autosave_interval)

        # Ventana por estrategia: {'RSIReversion': deque([1,0,1,...], maxlen=N)}
        self._windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.memory_window))
        # Conteos agregados por estrategia/bucket/símbolo
        self._counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
        # Mapa de trade_id a lista de votos normalizados
        self._trade_votes: Dict[str, List[Dict[str, str]]] = {}
        # Contador de finalizaciones para autosave
        self._finalized_counter: int = 0

        # Asegurar rutas/archivos
        self._ensure_dirs()
        self._load_state()   # carga JSON si existe (rápido)
        self._warm_from_csv()  # opcional: sincroniza con CSV si hace falta

    # ----------------------------------------------------
    # Inicialización y utilidades de IO
    # ----------------------------------------------------
    def _ensure_dirs(self):
        data_dir = os.path.dirname(self.csv_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        state_dir = os.path.dirname(self.state_path)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)

        # Crear CSV con cabecera si no existe
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["timestamp", "trade_id", "strategy", "bucket", "symbol", "timeframe", "market", "result"]
                )  # result: 1=WIN,0=LOSS

        # Crear JSON mínimo si no existe
        if not os.path.exists(self.state_path):
            self._save_state()

    def _load_state(self):
        """Carga snapshot resumido (winrates y conteos) desde JSON."""
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)

                strategies = state.get("strategies", {})
                for name, info in strategies.items():
                    wins = int(info.get("wins", 0))
                    losses = int(info.get("losses", 0))
                    # reconstruir ventana aproximada: repartimos wins/losses (solo para tener algo rápido)
                    window_len = min(self.memory_window, wins + losses)
                    # Heurística: rellenar con proporción wins/losses
                    if window_len > 0:
                        wr = wins / (wins + losses)
                        wins_in_window = int(round(wr * window_len))
                        losses_in_window = window_len - wins_in_window
                        self._windows[name] = deque([1]*wins_in_window + [0]*losses_in_window,
                                                    maxlen=self.memory_window)
                    self._counts[name] = {"wins": wins, "losses": losses}
        except Exception as e:
            # Si algo falla, continuamos con memoria vacía
            print(f"[GeminiMemory] Advertencia al cargar JSON: {e}")

    def _warm_from_csv(self):
        """
        Opción de “entibiar” memoria desde CSV (últimos registros por estrategia).
        Si el JSON ya se cargó, esto solo asegura que la ventana refleje lo último del CSV.
        """
        try:
            if not os.path.exists(self.csv_path):
                return
            # Leemos el CSV y tomamos solo hasta la memoria_window más reciente por estrategia
            tail_per_strategy: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.memory_window))
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    strategy = row.get("strategy", "UnknownStrategy")
                    bucket = row.get("bucket", "GLOBAL")
                    symbol = row.get("symbol", "UNKNOWN")
                    timeframe = row.get("timeframe", "UNKNOWN")
                    market = row.get("market")
                    if not market or market == "UNKNOWN":
                        market = f"{symbol}@{timeframe}" if timeframe != "UNKNOWN" else symbol
                    key = self._vote_key(strategy, bucket, market)
                    try:
                        result = int(row["result"])
                    except Exception:
                        continue
                    tail_per_strategy[key].append(result)

            # Reemplazamos ventanas por lo visto en CSV (lo más reciente)
            for key, q in tail_per_strategy.items():
                # La ventana siempre se refresca con los datos más recientes del CSV.
                self._windows[key] = deque(q, maxlen=self.memory_window)

                # Sincronizar conteos: si el CSV tiene más datos que el JSON,
                # es una fuente más fiable. Recalculamos desde la ventana.
                wins_in_window = sum(q)
                losses_in_window = len(q) - wins_in_window
                existing_total = self._counts.get(key, {}).get("wins", 0) + self._counts.get(key, {}).get("losses", 0)
                if wins_in_window + losses_in_window > existing_total:
                    self._counts[key] = {"wins": wins_in_window, "losses": losses_in_window}
                elif key not in self._counts:
                    # Si no había estado previo, usar la ventana
                    self._counts[key] = {"wins": wins_in_window, "losses": losses_in_window}

        except Exception as e:
            print(f"[GeminiMemory] Advertencia al calentar desde CSV: {e}")

    def _vote_key(self, strategy: str, bucket: str, market: str) -> str:
        """Construye clave única para estrategia contextual."""
        return f"{market}|{bucket}|{strategy}"

    def _save_state(self):
        """Guarda snapshot JSON de estadísticas por estrategia (portabilidad y carga rápida)."""
        try:
            payload = {
                "last_update": datetime.utcnow().isoformat(),
                "memory_window": self.memory_window,
                "strategies": {}
            }
            for name, cnt in self._counts.items():
                wins = int(cnt.get("wins", 0))
                losses = int(cnt.get("losses", 0))
                total = wins + losses
                wr = (wins / total) if total > 0 else None
                payload["strategies"][name] = {
                    "wins": wins,
                    "losses": losses,
                    "winrate": wr
                }

            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GeminiMemory] Error al guardar JSON: {e}")

    # ----------------------------------------------------
    # API principal (integración con Gemini/Core)
    # ----------------------------------------------------
    def register_vote_set(self, trade_id: str, votes: List[Dict[str, str]]) -> None:
        """
        Registra los votantes (estrategia + bucket + símbolo/timeframe) que participaron en un trade.

        Gemini debe llamar esto cuando decide jugar y conoce qué sensores/buckets
        justifican la entrada. Luego, al finalizar el trade, se evaluará el resultado
        para cada combinación única.

        :param trade_id: identificador único del trade (ej: "LTC-2025-10-10T12:30")
        :param votes: lista de dicts con claves {"strategy","bucket","symbol","timeframe","market"}
        """
        normalized: Dict[str, Dict[str, str]] = {}
        votes = votes or []
        for vote in votes:
            if isinstance(vote, dict):
                strategy = str(vote.get("strategy", "UnknownStrategy"))
                bucket = str(vote.get("bucket", "GLOBAL"))
                symbol = str(vote.get("symbol", "UNKNOWN"))
                timeframe = str(vote.get("timeframe", "UNKNOWN"))
                market = str(vote.get("market")) if vote.get("market") else None
            else:
                # Compatibilidad retro: listas de strings
                strategy = str(vote)
                bucket = "GLOBAL"
                symbol = "UNKNOWN"
                timeframe = "UNKNOWN"
                market = None

            if not market or market == "UNKNOWN":
                market = f"{symbol}@{timeframe}" if timeframe != "UNKNOWN" else symbol

            key = self._vote_key(strategy, bucket, market)
            normalized[key] = {
                "strategy": strategy,
                "bucket": bucket,
                "symbol": symbol,
                "timeframe": timeframe,
                "market": market,
                "key": key,
            }

        self._trade_votes[trade_id] = list(normalized.values())

    def finalize_trade(self, trade_id: str, win: bool) -> None:
        """
        Cierra un trade y registra el resultado para TODAS las estrategias que votaron.

        - Agrega una fila por estrategia/bucket/símbolo/timeframe al CSV (timestamp, trade_id, strategy, bucket, symbol, timeframe, market, result)
        - Actualiza ventana por estrategia (memoria corta)
        - Actualiza conteos (wins/losses)
        - Autosave del JSON cada N finalizaciones

        :param trade_id: id del trade previamente registrado
        :param win: True si el trade terminó en WIN, False si terminó en LOSS
        """
        if trade_id not in self._trade_votes:
            # Si no hay registro de votantes, no podemos asignar mérito/culpa
            # Se ignora silenciosamente para robustez operacional.
            return

        votes = self._trade_votes.pop(trade_id)
        if not votes:
            return

        ts = datetime.utcnow().isoformat()
        result_int = 1 if win else 0

        # 1) Persistencia en CSV (una fila por estrategia)
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for vote in votes:
                    writer.writerow([
                        ts,
                        trade_id,
                        vote["strategy"],
                        vote["bucket"],
                        vote.get("symbol", "UNKNOWN"),
                        vote.get("timeframe", "UNKNOWN"),
                        vote.get("market", "UNKNOWN"),
                        result_int,
                    ])
        except Exception as e:
            print(f"[GeminiMemory] Error al escribir CSV: {e}")

        # 2) Actualizar memoria en caliente
        for vote in votes:
            key = vote["key"]
            self._windows[key].append(result_int)
            if win:
                self._counts[key]["wins"] += 1
            else:
                self._counts[key]["losses"] += 1

        # 3) Autosave periódico
        self._finalized_counter += 1
        if self._finalized_counter >= self.autosave_interval:
            self._save_state()
            self._finalized_counter = 0

    # ----------------------------------------------------
    # Consultas de estado (para Gemini)
    # ----------------------------------------------------
    def get_winrate(self, strategy_key: str) -> Optional[float]:
        """
        Devuelve p̂ (winrate) de la estrategia *en la ventana corta*.
        Si no hay suficientes datos, retorna None.

        Recomendación:
          - En Gemini, no apostar cuando p̂ is None o bajo mínimo de soporte.
        """
        window = self._windows.get(strategy_key)
        if not window:
            return None
        n = len(window)
        if n == 0:
            return None
        return sum(window) / n

    def get_window_size(self, strategy_key: str) -> int:
        """Tamaño actual de la ventana por estrategia (muestras recientes)."""
        window = self._windows.get(strategy_key)
        return len(window) if window else 0

    def get_counts(self, strategy_key: str) -> Dict[str, int]:
        """
        Conteos agregados totales (largo plazo): wins y losses acumulados.
        Útiles para diagnóstico y depuración, pero *NO* para Kelly (usa ventana).
        """
        return dict(self._counts.get(strategy_key, {"wins": 0, "losses": 0}))

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Devuelve snapshot con estadísticas por estrategia:
            {
              "RSIReversion": {"wr_window": 0.58, "n_window": 123, "wins": 320, "losses": 250},
              ...
            }
        """
        out = {}
        for name in set(list(self._windows.keys()) + list(self._counts.keys())):
            wr = self.get_winrate(name)
            out[name] = {
                "wr_window": wr if wr is not None else None,
                "n_window": self.get_window_size(name),
                "wins": self._counts.get(name, {}).get("wins", 0),
                "losses": self._counts.get(name, {}).get("losses", 0),
            }
        return out

    # ----------------------------------------------------
    # Mantenimiento / Administración
    # ----------------------------------------------------
    def purge_to_window(self) -> None:
        """
        Fuerza la poda global (si por algún motivo el CSV fue importado con más
        registros de los que debería, esta función recorta las ventanas).
        """
        for name, q in self._windows.items():
            if q.maxlen != self.memory_window:
                self._windows[name] = deque(list(q)[-self.memory_window:], maxlen=self.memory_window)

    def save(self) -> None:
        """Guardado explícito del JSON (por ejemplo, al cierre de la app)."""
        self._save_state()

    # 🔧 PUNTO DE EXTENSIÓN:
    # Si quieres implementar un mecanismo de “purificación del consenso” (pruning),
    # podrías agregar aquí una función que devuelva un set de estrategias a desactivar
    # cuando su wr_window < umbral (p. ej. 0.53) y n_window >= MIN_SUPPORT.
    #
    # def get_strategies_to_prune(self, threshold: float, min_support: int) -> List[str]:
    #     ...
    #     return ["BollingerTouch"]
    #
    # Esta función no desactiva estrategias por sí misma (eso lo haría Gemini o el manager),
    # solo recomienda basándose en la evidencia empírica actual.
