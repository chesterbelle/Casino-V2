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
    WINDOW_SIZE, MIN_SUPPORT,
    APPROVAL_MIN_SAMPLES (nuevo, por defecto 500),
    MODE (para permitir GHOST en backtest)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime

import config
from .memory import GeminiMemory
from .bucket_manager import BucketManager

try:
    from scipy.stats import beta as scipy_beta  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    scipy_beta = None

from statistics import NormalDist


# =========================================================
# Utilidades y parámetros por defecto seguros
# =========================================================
APPROVAL_MIN_SAMPLES = getattr(config, "MIN_SUPPORT", 20)  # mínimo para aprobar un bucket
KELLY_FRACTION = getattr(config, "KELLY_FRACTION", 1.0)

R = getattr(config, "TAKE_PROFIT", 0.01)  # ganancia objetivo (proporción)
L = getattr(config, "STOP_LOSS", 0.01)    # pérdida objetivo (proporción)
# Umbral crítico de acierto p* (para R:R asimétrico): p* = L / (L + R)
P_STAR = L / (L + R)
# “b” para Kelly odds: b = R/L
B = R / L
ALPHA_PRIOR = float(getattr(config, "BAYES_ALPHA", 1.0))
BETA_PRIOR = float(getattr(config, "BAYES_BETA", 1.0))
CREDIBILITY_THRESHOLD = float(getattr(config, "BAYES_CREDIBILITY_THRESHOLD", 0.6))
LOWER_CREDIBLE_PERCENTILE = float(getattr(config, "BAYES_LOWER_PERCENTILE", 0.1))

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


@dataclass(frozen=True)
class Participant:
    strategy: str
    bucket: str
    symbol: str
    timeframe: str

    @property
    def market(self) -> str:
        return f"{self.symbol}@{self.timeframe}" if self.timeframe != "UNKNOWN" else self.symbol

    @property
    def memory_key(self) -> str:
        return f"{self.market}|{self.bucket}|{self.strategy}"


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

    def __init__(self, memory: Optional[GeminiMemory] = None, bucket_manager: Optional[BucketManager] = None):
        self.logger = logging.getLogger("Gemini")
        self.memory = memory or GeminiMemory()
        self.bucket_manager = bucket_manager or BucketManager(
            window=getattr(config, "WINDOW_SIZE", 120),
            min_support=getattr(config, "MIN_SUPPORT", 20),
        )

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
            voters_for_training = self._serialize_participants(list({*long_voters, *short_voters}))
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
        voters_payload = self._serialize_participants(approved + unapproved)
        self.memory.register_vote_set(trade_id, voters_payload)  # registramos TODOS para entrenar

        # Si no hay aprobadas o ningún Kelly positivo → GHOST (entrena sin afectar capital)
        if (len(approved) == 0) or (len(kellys) == 0):
            order = self._make_order(base_meta, side=chosen_side, size_fraction=0.0)
            reason = "sin_aprobadas" if len(approved) == 0 else "kelly_no_positivo"
            return Decision(action="GHOST", side=chosen_side, order=order, reason=reason, trade_id=trade_id)

        # Tomar el Kelly más conservador (mínimo > 0)
        min_kelly = max(0.0, min(kellys))
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
    def _collect_votes_by_side(self, signals: List[dict]) -> Tuple[List[Participant], List[Participant], dict]:
        """
        Separa votantes por lado y recoge metadatos base (timestamp/symbol).
        Asume que cada señal trae: {"timestamp","symbol","side","origin" o derivable}
        - origin (nombre de estrategia) se infiere de 'features/_origin' o 'sensor' si existe,
          de lo contrario se asigna "UnknownSensor".
        """
        long_voters: List[Participant] = []
        short_voters: List[Participant] = []
        seen_long: Set[str] = set()
        seen_short: Set[str] = set()

        # Base meta (de la primera señal)
        base_meta = {
            "timestamp": signals[0].get("timestamp"),
            "symbol": signals[0].get("symbol", "UNKNOWN"),
            "timeframe": signals[0].get("timeframe", "UNKNOWN"),
        }

        for s in signals:
            side = s.get("side", "").upper()
            participants = self._extract_participants(s)
            if not participants:
                continue

            for participant in participants:
                key = participant.memory_key
                if side == "LONG":
                    if key not in seen_long:
                        long_voters.append(participant)
                        seen_long.add(key)
                elif side == "SHORT":
                    if key not in seen_short:
                        short_voters.append(participant)
                        seen_short.add(key)

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

    def _kelly_by_strategy(self, voters: List[Participant]) -> Tuple[List[float], List[Participant], List[Participant]]:
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
        approved: List[Participant] = []
        unapproved: List[Participant] = []

        for participant in voters:
            key = participant.memory_key
            p_hat = self.memory.get_winrate(key)
            n_obs = self.memory.get_window_size(key)

            if p_hat is None or n_obs < APPROVAL_MIN_SAMPLES:
                unapproved.append(participant)
                continue

            wins_est = max(0, min(n_obs, int(round(p_hat * n_obs))))
            losses_est = max(0, n_obs - wins_est)

            alpha_post = ALPHA_PRIOR + wins_est
            beta_post = BETA_PRIOR + losses_est

            credibility = self._beta_prob_greater(P_STAR, alpha_post, beta_post)
            if credibility < CREDIBILITY_THRESHOLD:
                unapproved.append(participant)
                continue

            p_conservative = self._beta_quantile(alpha_post, beta_post, LOWER_CREDIBLE_PERCENTILE)

            if p_conservative <= P_STAR:
                approved.append(participant)
                continue

            f_raw = p_conservative - (1 - p_conservative) / B
            f_adj = max(0.0, f_raw) * KELLY_FRACTION

            if f_adj > 0:
                kellys_positive.append(f_adj)
            approved.append(participant)

        return kellys_positive, approved, unapproved

    def _make_trade_id(self, meta: dict, side: str) -> str:
        """
        Genera un ID único para el trade basado en timestamp, símbolo y lado.
        """
        ts = meta.get("timestamp")
        sym = meta.get("symbol", "UNKNOWN")
        tf = meta.get("timeframe", "UNKNOWN")
        if not ts:
            ts = datetime.utcnow().isoformat()
        market = f"{sym}@{tf}" if tf and tf != "UNKNOWN" else sym
        return f"{market}-{side}-{ts}"

    def _make_order(self, meta: dict, side: str, size_fraction: float) -> dict:
        """
        Construye la orden estandarizada para enviar al Croupier/Mesa.
        size_fraction ∈ [0,1] — fracción del equity (el Croupier/mesa convertirá a monto).
        """
        symbol = meta.get("symbol", "UNKNOWN")
        timeframe = meta.get("timeframe", "UNKNOWN")
        order = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": meta.get("timestamp"),
            "side": side,
            "size": float(size_fraction),
            "take_profit": 1.0 + R,
            "stop_loss": 1.0 - L,
        }
        if timeframe and timeframe != "UNKNOWN":
            order["market"] = f"{symbol}@{timeframe}"
        return order

    def _extract_participants(self, signal: dict) -> List[Participant]:
        """
        Devuelve la lista de participantes (uno por estrategia contribuyente) para una señal.
        """
        participants: List[Participant] = []
        contributors = signal.get("contributors")

        if contributors and isinstance(contributors, (list, tuple)):
            for origin in contributors:
                participant = self._make_participant(signal, origin_override=str(origin))
                if participant:
                    participants.append(participant)
        else:
            participant = self._make_participant(signal)
            if participant:
                participants.append(participant)

        return participants

    def _make_participant(self, signal: dict, origin_override: Optional[str] = None) -> Optional[Participant]:
        """
        Construye el participante (estrategia + bucket + símbolo/timeframe) asociado a una señal.
        """
        origin = origin_override or self._infer_origin(signal)
        symbol = signal.get("symbol", "UNKNOWN")
        timeframe = signal.get("timeframe", "UNKNOWN")
        try:
            bucket = self.bucket_manager.identify_bucket(signal)
        except Exception as exc:
            self.logger.debug(f"[Gemini] Bucket inválido para {origin}: {exc}")
            bucket = "UNKNOWN"
        return Participant(strategy=origin, bucket=bucket, symbol=symbol, timeframe=timeframe)

    def _serialize_participants(self, participants: List[Participant]) -> List[Dict[str, str]]:
        """Convierte los participantes en payload para GeminiMemory."""
        payload = []
        for p in participants:
            payload.append({
                "strategy": p.strategy,
                "bucket": p.bucket,
                "symbol": p.symbol,
                "timeframe": p.timeframe,
                "market": p.market,
            })
        return payload

    # -----------------------------------------------------
    # Bayesian helpers
    # -----------------------------------------------------
    def _beta_prob_greater(self, threshold: float, alpha: float, beta: float) -> float:
        """Pr(p > threshold | alpha, beta). Usa scipy si está disponible; fallback normal."""
        threshold = max(0.0, min(1.0, threshold))
        if threshold <= 0.0:
            return 1.0
        if threshold >= 1.0:
            return 0.0
        if scipy_beta is not None:
            return float(1.0 - scipy_beta.cdf(threshold, alpha, beta))

        # Normal approximation fallback
        mean = alpha / (alpha + beta)
        var = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1))
        std = var ** 0.5 if var > 0 else 0.0
        if std == 0:
            return 1.0 if mean > threshold else 0.0
        nd = NormalDist(mean, std)
        return 1.0 - nd.cdf(threshold)

    def _beta_quantile(self, alpha: float, beta: float, percentile: float) -> float:
        """Obtiene el cuantil inferior de la distribución Beta."""
        percentile = max(0.0, min(1.0, percentile))
        if scipy_beta is not None:
            return float(scipy_beta.ppf(percentile, alpha, beta))

        mean = alpha / (alpha + beta)
        var = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1))
        std = var ** 0.5 if var > 0 else 0.0
        if std == 0:
            return mean
        nd = NormalDist(mean, std)
        return max(0.0, min(1.0, nd.inv_cdf(percentile)))
