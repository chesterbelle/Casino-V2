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
• Ventana de observación deslizante por estrategia (memoria corta activa)
• Persistencia dual:
    - CSV: log cronológico por estrategia (portabilidad y auditoría)
    - JSON: snapshot resumido con winrates y conteos (carga rápida)
• API simple para integrar con Gemini y el Croupier:
    - register_vote_set(trade_id, strategies_activas)
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
from typing import Dict, List, Optional, Set

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
      - Ventana por estrategia (deque de wins/losses)
      - Mapa trade_id -> set(estrategias que votaron)
      - Log CSV (histórico portable)
      - Snapshot JSON (carga rápida)

    Uso típico en el flujo:
    -----------------------
    # 🔧 PUNTO DE INTEGRACIÓN (antes de ejecutar la apuesta)
    memory.register_vote_set(trade_id, ["RSIReversion", "KeltnerReversion"])

    # ... se ejecuta el trade con el Croupier y el Feed ...

    # 🔧 PUNTO DE INTEGRACIÓN (al cerrar la apuesta)
    memory.finalize_trade(trade_id, win=True)  # o False

    p_rsi = memory.get_winrate("RSIReversion")
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
        # Conteos agregados por estrategia
        self._counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
        # Mapa de trade_id a conjunto de estrategias que votaron en ese trade
        self._trade_votes: Dict[str, Set[str]] = {}
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
                writer.writerow(["timestamp", "trade_id", "strategy", "result"])  # result: 1=WIN,0=LOSS

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
                    strategy = row["strategy"]
                    result = int(row["result"])
                    tail_per_strategy[strategy].append(result)

            # Reemplazamos ventanas por lo visto en CSV (lo más reciente)
            for strat, q in tail_per_strategy.items():
                self._windows[strat] = deque(q, maxlen=self.memory_window)
                # Los conteos totales deben mantenerse según JSON (ya que CSV puede estar truncado)
                # Si no había estado previo en JSON, aproximamos con la ventana:
                if strat not in self._counts:
                    wins = sum(q)
                    losses = len(q) - wins
                    self._counts[strat] = {"wins": wins, "losses": losses}

        except Exception as e:
            print(f"[GeminiMemory] Advertencia al calentar desde CSV: {e}")

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
    def register_vote_set(self, trade_id: str, strategies: List[str]) -> None:
        """
        Registra las ESTRATEGIAS que “votaron” en un trade antes de ejecutarse.

        Gemini debe llamar esto cuando decide jugar y conoce qué sensores (estrategias)
        justifican la entrada. Luego, al finalizar el trade, se evaluará el resultado
        para cada estrategia votante.

        :param trade_id: identificador único del trade (ej: "LTC-2025-10-10T12:30")
        :param strategies: lista de nombres de estrategias que emitieron señal
        """
        # 🔧 PUNTO DE EXTENSIÓN:
        # Si en el futuro deseas registrar también features contextuales por estrategia,
        # puedes mantener aquí un dict trade_id -> {strategy -> feature_vector}
        self._trade_votes[trade_id] = set(strategies or [])

    def finalize_trade(self, trade_id: str, win: bool) -> None:
        """
        Cierra un trade y registra el resultado para TODAS las estrategias que votaron.

        - Agrega una fila por estrategia al CSV (timestamp, trade_id, strategy, result)
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

        strategies = self._trade_votes.pop(trade_id)
        if not strategies:
            return

        ts = datetime.utcnow().isoformat()
        result_int = 1 if win else 0

        # 1) Persistencia en CSV (una fila por estrategia)
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for strat in strategies:
                    writer.writerow([ts, trade_id, strat, result_int])
        except Exception as e:
            print(f"[GeminiMemory] Error al escribir CSV: {e}")

        # 2) Actualizar memoria en caliente
        for strat in strategies:
            self._windows[strat].append(result_int)
            if win:
                self._counts[strat]["wins"] += 1
            else:
                self._counts[strat]["losses"] += 1

        # 3) Autosave periódico
        self._finalized_counter += 1
        if self._finalized_counter >= self.autosave_interval:
            self._save_state()
            self._finalized_counter = 0

    # ----------------------------------------------------
    # Consultas de estado (para Gemini)
    # ----------------------------------------------------
    def get_winrate(self, strategy_name: str) -> Optional[float]:
        """
        Devuelve p̂ (winrate) de la estrategia *en la ventana corta*.
        Si no hay suficientes datos, retorna None.

        Recomendación:
          - En Gemini, no apostar cuando p̂ is None o bajo mínimo de soporte.
        """
        window = self._windows.get(strategy_name)
        if not window:
            return None
        n = len(window)
        if n == 0:
            return None
        return sum(window) / n

    def get_window_size(self, strategy_name: str) -> int:
        """Tamaño actual de la ventana por estrategia (muestras recientes)."""
        window = self._windows.get(strategy_name)
        return len(window) if window else 0

    def get_counts(self, strategy_name: str) -> Dict[str, int]:
        """
        Conteos agregados totales (largo plazo): wins y losses acumulados.
        Útiles para diagnóstico y depuración, pero *NO* para Kelly (usa ventana).
        """
        return dict(self._counts.get(strategy_name, {"wins": 0, "losses": 0}))

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

