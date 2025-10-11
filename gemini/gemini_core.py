"""
====================================================
🎩 Gemini Core — Jugador Probabilista del Casino V2
====================================================

Rol:
----
- Recibir señales de los sensores (votantes expertos).
- Seleccionar el lado (LONG/SHORT) por consenso conservador.
- Calcular p̂ (winrate) *individual por estrategia* desde GeminiMemory.
- Calcular Kelly por estrategia y elegir el *Kelly más conservador* (mínimo).
- Apuesta única por vela.
- Exigir "aprobación por muestras" antes de permitir que una estrategia apueste.
- Si NO se puede apostar, generar orden fantasma (GHOST) para *entrenamiento* igualmente.
- Registrar votantes y actualizar memoria al cierre del trade (real o fantasma).

Puntos clave:
-------------
• Aprobación por muestras (min_support_to_trade): una estrategia no puede "apostar"
  hasta que su ventana de observación tenga al menos N observaciones (ej: 500).
• Si hay señal pero nadie aprobado o no hay EV positivo, se emite GHOST para entrenar
  (el Croupier/Mesa simula sin afectar balance).
• Un solo trade por vela: si hay múltiples estrategias en el mismo lado, se usa la
  fracción de Kelly más conservadora (mínima positiva).
• Si hay conflicto de lado (LONG y SHORT al mismo tiempo), se elige GHOST (sin apuesta)
  para entrenar sin riesgo (estrictamente conservador).

Integraciones:
--------------
- GeminiMemory (gemini/memory.py):
    - register_vote_set(trade_id, strategies)
    - finalize_trade(trade_id, win: bool)
    - get_winrate(strategy_name) -> Optional[float]
    - get_window_size(strategy_name) -> int

Configuración:
--------------
Desde config.py se leen:
    TAKE_PROFIT (R), STOP_LOSS (L), KELLY_FRACTION,
    WINDOW_SIZE, MIN_SUPPORT, MAX_POSITION_SIZE (opcional),
    APPROVAL_MIN_SAMPLES (nuevo, por defecto 500),
    MODE (para permitir GHOST en backtest)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import config
from .memory import GeminiMemory


# =========================================================
# Utilidades y parámetros por defecto seguros
# =========================================================
APPROVAL_MIN_SAMPLES = getattr(config, "APPROVAL_MIN_SAMPLES", 500)  # mínimo para "aprobada"
MAX_POSITION_SIZE = getattr(config, "MAX_POSITION_SIZE", 0.25)       # límite superior en Kelly
KELLY_FRACTION = getattr(config, "KELLY_FRACTION", 1.0)

R = getattr(config, "TAKE_PROFIT", 0.01)  # ganancia objetivo (proporción)
L = getattr(config, "STOP_LOSS", 0.01)    # pérdida objetivo (proporción)
# Umbral crítico de acierto p* (para R:R asimétrico): p* = L / (L + R)
P_STAR = L / (L + R)
# “b” para Kelly odds: b = R/L
B = R / L

# =========================================================
# Dataclass de decisión
# =========================================================
@dataclass
class Decision:
    action: str              # "BET" | "GHOST" | "SKIP"
    side: Optional[str]      # "LONG" | "SHORT" | None
    order: Optional[dict]    # Orden estandarizada o None
    reason: str              # explicación breve
    trade_id: Optional[str]  # id para correlacionar con memory/log


class Gemini:
    """
    Núcleo de decisión de Gemini (jugador probabilista).

    Flujo por vela:
    1) Recibe lista de señales de sensores (cada elemento: dict con keys ["timestamp","symbol","side","features",...]).
    2) Consolida el lado (LONG/SHORT) de forma conservadora:
       - Si hay señales en ambos lados, NO apuesta y emite GHOST (para entrenar sin riesgo).
       - Si solo hay un lado con señales, procede con ese lado.
    3) Filtra estrategias con p̂ y tamaño de ventana >= APPROVAL_MIN_SAMPLES (aprobadas).
    4) Calcula Kelly por estrategia aprobada y toma el mínimo > 0 (conservador).
    5) Si ningún Kelly>0 o ninguna estrategia aprobada:
         - Emite GHOST (orden fantasma) para que la mesa simule y entrene igual.
       Si hay Kelly>0:
         - Emite BET con size = min_kelly, acotado por MAX_POSITION_SIZE.
    6) Antes de enviar al Croupier, registra votantes con memory.register_vote_set(trade_id, estrategias).
    """

    def __init__(self, memory: Optional[GeminiMemory] = None):
        self.logger = logging.getLogger("Gemini")
        self.memory = memory or GeminiMemory()

    # -----------------------------------------------------
    # API principal: decidir sobre un conjunto de señales
    # -----------------------------------------------------
    def evaluate_signals(self, signals: List[dict], equity: float) -> Decision:
        """
        Recibe una lista de señales de sensores y decide una única acción.
        Retorna Decision con "BET" (apuesta real), "GHOST" (simulación/entrenamiento) o "SKIP".

        Importante:
        - Siempre que haya señales válidas, se genera un trade_id y se llama
          a memory.register_vote_set(...) con las estrategias que VOTARON en el lado elegido.
        - Si no hay señales, retorna SKIP sin registro.
        """
        if not signals:
            return Decision(action="SKIP", side=None, order=None, reason="sin_señales", trade_id=None)

        # Determinar consenso de lado
        long_voters, short_voters, base_meta = self._collect_votes_by_side(signals)

        # Si hay conflicto entre LONG y SHORT, optamos por NO apostar pero entrenar (GHOST)
        if long_voters and short_voters:
            # 🔧 PUNTO DE EXTENSIÓN: podrías cambiar la regla a 'mayoría simple' en lugar de GHOST.
            chosen_side = None
            voters_for_training = list({*long_voters, *short_voters})
            trade_id = self._make_trade_id(base_meta, side="CONFLICT")
            self.memory.register_vote_set(trade_id, voters_for_training)
            order = self._make_order(base_meta, side="LONG", size_fraction=0.0)  # lado arbitrario para simulación
            return Decision(action="GHOST", side=None, order=order, reason="conflicto_de_lado", trade_id=trade_id)

        # Elegir lado
        if long_voters:
            chosen_side = "LONG"
            side_voters = long_voters
        elif short_voters:
            chosen_side = "SHORT"
            side_voters = short_voters
        else:
            return Decision(action="SKIP", side=None, order=None, reason="señales_no_votantes", trade_id=None)

        # Evaluar Kelly por estrategia aprobada (con p̂ válido y muestras suficientes)
        kellys, approved, unapproved = self._kelly_by_strategy(side_voters)

        trade_id = self._make_trade_id(base_meta, side=chosen_side)
        self.memory.register_vote_set(trade_id, approved + unapproved)  # registramos TODOS para entrenar

        # Si no hay aprobadas o ningún Kelly positivo → GHOST (entrena sin afectar capital)
        if (len(approved) == 0) or (len(kellys) == 0):
            order = self._make_order(base_meta, side=chosen_side, size_fraction=0.0)
            reason = "sin_aprobadas" if len(approved) == 0 else "kelly_no_positivo"
            return Decision(action="GHOST", side=chosen_side, order=order, reason=reason, trade_id=trade_id)

        # Tomar el Kelly más conservador (mínimo > 0) y limitarlo por MAX_POSITION_SIZE
        min_kelly = max(0.0, min(kellys))
        min_kelly = min(min_kelly, MAX_POSITION_SIZE)
        if min_kelly <= 0:
            order = self._make_order(base_meta, side=chosen_side, size_fraction=0.0)
            return Decision(action="GHOST", side=chosen_side, order=order, reason="kelly_conservador_cero", trade_id=trade_id)

        # Orden real (BET)
        order = self._make_order(base_meta, side=chosen_side, size_fraction=min_kelly)
        return Decision(action="BET", side=chosen_side, order=order, reason="apuesta_conservadora", trade_id=trade_id)

    # -----------------------------------------------------
    # API de actualización post‐trade (resultado)
    # -----------------------------------------------------
    def on_trade_result(self, trade_id: str, result: dict) -> None:
        """
        Debe llamarse cuando la mesa devuelva el resultado de la ejecución (real o fantasma).
        Espera un dict con clave "result": "WIN" | "LOSS" (y demás campos estándar).
        """
        outcome = result.get("result", "").upper()
        win = True if outcome == "WIN" else False
        self.memory.finalize_trade(trade_id, win=win)

    # =====================================================
    # Internos — helpers
    # =====================================================
    def _collect_votes_by_side(self, signals: List[dict]) -> Tuple[List[str], List[str], dict]:
        """
        Separa votantes por lado y recoge metadatos base (timestamp/symbol).
        Asume que cada señal trae: {"timestamp","symbol","side","origin" o derivable}
        - origin (nombre de estrategia) se infiere de 'features/_origin' o 'sensor' si existe,
          de lo contrario se asigna "UnknownSensor".
        """
        long_voters: List[str] = []
        short_voters: List[str] = []

        # Base meta (de la primera señal)
        base_meta = {
            "timestamp": signals[0].get("timestamp"),
            "symbol": signals[0].get("symbol", "UNKNOWN"),
        }

        for s in signals:
            side = s.get("side", "").upper()
            origin = self._infer_origin(s)

            if side == "LONG":
                long_voters.append(origin)
            elif side == "SHORT":
                short_voters.append(origin)

        # Dejar listas únicas (sin duplicados)
        long_voters = list(dict.fromkeys(long_voters))
        short_voters = list(dict.fromkeys(short_voters))

        return long_voters, short_voters, base_meta

    def _infer_origin(self, signal: dict) -> str:
        """
        Intenta inferir el nombre de la estrategia/sensor que generó la señal.
        🔧 PUNTO DE EXTENSIÓN: si tus señales traen el nombre en otra key, mapéalo aquí.
        """
        # Ejemplos de posibles campos
        for k in ("origin", "sensor", "strategy", "source"):
            if k in signal:
                return str(signal[k])
        # A veces el manager puede incluir en features
        feats = signal.get("features", {})
        if isinstance(feats, dict) and "_origin" in feats:
            return str(feats["_origin"])
        return "UnknownSensor"

    def _kelly_by_strategy(self, voters: List[str]) -> Tuple[List[float], List[str], List[str]]:
        """
        Calcula Kelly por estrategia aprobada y separa aprobadas/no-aprobadas.

        Regla de aprobación: window_size(strategy) >= APPROVAL_MIN_SAMPLES
        Kelly (asimétrico):
            b = R/L
            f* = p - (1 - p)/b
        (luego se multiplica por KELLY_FRACTION y se limita por MAX_POSITION_SIZE en el llamado)

        Retorna:
            kellys_positive: List[float]     # solo valores > 0 de estrategias aprobadas
            approved: List[str]              # estrategias con suficiente historial
            unapproved: List[str]            # estrategias para las que seguimos entrenando
        """
        kellys_positive: List[float] = []
        approved: List[str] = []
        unapproved: List[str] = []

        for strat in voters:
            p_hat = self.memory.get_winrate(strat)
            n_obs = self.memory.get_window_size(strat)

            if p_hat is None or n_obs < APPROVAL_MIN_SAMPLES:
                unapproved.append(strat)
                continue

            # Exigir EV positivo: p̂ > p*
            if p_hat <= P_STAR:
                approved.append(strat)  # está aprobada por muestras, pero sin edge → Kelly no positivo
                continue

            # Kelly asimétrico: f* = p - (1 - p)/b
            f_raw = p_hat - (1 - p_hat) / B
            f_adj = max(0.0, f_raw) * KELLY_FRACTION

            if f_adj > 0:
                kellys_positive.append(f_adj)
                approved.append(strat)
            else:
                approved.append(strat)  # aprobada, pero f = 0 por conservadurismo

        return kellys_positive, approved, unapproved

    def _make_trade_id(self, meta: dict, side: str) -> str:
        """
        Genera un ID único para el trade basado en timestamp, símbolo y lado.
        """
        ts = meta.get("timestamp")
        sym = meta.get("symbol", "UNKNOWN")
        if not ts:
            ts = datetime.utcnow().isoformat()
        return f"{sym}-{side}-{ts}"

    def _make_order(self, meta: dict, side: str, size_fraction: float) -> dict:
        """
        Construye la orden estandarizada para enviar al Croupier/Mesa.
        size_fraction ∈ [0,1] — fracción del equity (el Croupier/mesa convertirá a monto).
        """
        return {
            "symbol": meta.get("symbol", "UNKNOWN"),
            "timestamp": meta.get("timestamp"),
            "side": side,
            "size": float(size_fraction),
            "take_profit": 1.0 + R,
            "stop_loss": 1.0 - L,
        }

