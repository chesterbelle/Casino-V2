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
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    import config
except ImportError:
    # Fallback for when config is in core/
    import os
    import sys

    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import config
    except ImportError:
        # Last resort: import from core
        from core import config

from .bucket_manager import BucketManager
from .decision_logger import DecisionLogger
from .memory import GeminiMemory

try:
    from scipy.stats import beta as scipy_beta  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    scipy_beta = None

from statistics import NormalDist

# =========================================================
# Utilidades y parámetros por defecto seguros
# =========================================================
APPROVAL_MIN_SAMPLES = getattr(config, "MIN_SUPPORT", 20)
KELLY_FRACTION = getattr(config, "KELLY_FRACTION", 1.0)

R_GROSS = getattr(config, "TAKE_PROFIT", 0.01)
L_GROSS = getattr(config, "STOP_LOSS", 0.01)
FEES = 2 * getattr(config, "COMMISSION_RATE", 0.0)
SLIPPAGE = getattr(config, "SLIPPAGE_DEFAULT", 0.0)
COST = FEES + SLIPPAGE
R_NET = max(0.0, R_GROSS - COST)
L_NET = L_GROSS + COST

if R_NET <= 0 or (R_NET + L_NET) <= 0:
    P_STAR = 1.0
    B = 0.0
else:
    P_STAR = L_NET / (L_NET + R_NET)
    B = R_NET / L_NET if L_NET > 0 else 0.0
ALPHA_PRIOR = float(getattr(config, "BAYES_ALPHA", 1.0))
BETA_PRIOR = float(getattr(config, "BAYES_BETA", 1.0))
CREDIBILITY_THRESHOLD = float(getattr(config, "BAYES_CREDIBILITY_THRESHOLD", 0.6))
LOWER_CREDIBLE_PERCENTILE = float(getattr(config, "BAYES_LOWER_PERCENTILE", 0.1))


# =========================================================
# Dataclasses de decisión
# =========================================================
@dataclass
class Decision:
    """Decision completa (legacy) - incluye orden construida"""

    action: str  # "BET" | "GHOST" | "SKIP"
    side: Optional[str]  # "LONG" | "SHORT" | None
    order: Optional[dict]  # Orden estandarizada o None
    reason: str  # explicación breve
    trade_id: Optional[str]  # id para correlacionar con memory/log


@dataclass
class Verdict:
    """
    Verdict de validación probabilística (nuevo).

    Separa la validación (Gemini) del sizing (Player).
    Contiene toda la información para que un Player decida cuánto apostar.
    """

    trade_id: Optional[str]  # id del trade potencial
    side: Optional[str]  # "LONG" | "SHORT" | None (None = conflict)
    reason: str  # razón de la decisión
    metrics: List[ParticipantMetrics]  # métricas de todos los participantes
    participants: List[Participant]  # participantes que votaron
    meta: Dict  # metadata (timestamp, symbol, timeframe)


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


@dataclass
class ParticipantMetrics:
    participant: Participant
    support: int
    p_hat: Optional[float]
    credibility: float
    p_conservative: float
    kelly: float
    approved: bool
    reason: str
    p_star: float
    r_net: float
    l_net: float


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
        self.decision_logger = DecisionLogger()
        # Almacenar base_meta temporalmente para make_order_from_verdict
        self._last_verdict_meta: Optional[Dict] = None

    # -----------------------------------------------------
    # API NUEVA: Validación probabilística (retorna Verdict)
    # -----------------------------------------------------
    def evaluate_signals_v2(self, signals: List[dict], equity: float) -> Verdict:
        """
        [NUEVO] Evalúa señales y retorna Verdict (solo validación).

        El Player decide el tamaño de posición basándose en el Verdict.

        Returns:
            Verdict: Contiene side, metrics, participants, meta
                    - Si Verdict.side es None → no apostar (conflict o SKIP)
                    - Si metrics vacío o no aprobados → Player no debe apostar
                    - Si hay metrics aprobados → Player puede apostar
        """
        if not signals:
            return Verdict(trade_id=None, side=None, reason="sin_señales", metrics=[], participants=[], meta={})

        # Determinar consenso de lado
        long_voters, short_voters, base_meta = self._collect_votes_by_side(signals)

        # Conflicto de lado: no apostar
        if long_voters and short_voters:
            participants = list({*long_voters, *short_voters})
            trade_id = self._make_trade_id(base_meta, side="CONFLICT")
            self.memory.register_vote_set(trade_id, self._serialize_participants(participants))
            self._last_verdict_meta = base_meta

            return Verdict(
                trade_id=trade_id,
                side=None,
                reason="conflicto_de_lado",
                metrics=[],
                participants=participants,
                meta=base_meta,
            )

        # Elegir lado
        if long_voters:
            chosen_side = "LONG"
            side_voters = long_voters
        elif short_voters:
            chosen_side = "SHORT"
            side_voters = short_voters
        else:
            return Verdict(
                trade_id=None, side=None, reason="señales_no_votantes", metrics=[], participants=[], meta=base_meta
            )

        # Calcular métricas probabilísticas
        participant_metrics = self._participant_metrics(side_voters)
        participants = [m.participant for m in participant_metrics]

        trade_id = self._make_trade_id(base_meta, side=chosen_side)
        self.memory.register_vote_set(trade_id, self._serialize_participants(participants))
        self._last_verdict_meta = base_meta

        # Determinar razón
        approved_metrics = [m for m in participant_metrics if m.approved]
        if not approved_metrics:
            reason = "sin_aprobadas"
        else:
            positive_metrics = [m for m in approved_metrics if m.kelly > 0]
            reason = "aprobado" if positive_metrics else "kelly_no_positivo"

        # Log de la decisión (para análisis)
        self._log_verdict(trade_id, chosen_side, reason, base_meta, participants, participant_metrics, equity)

        return Verdict(
            trade_id=trade_id,
            side=chosen_side,
            reason=reason,
            metrics=participant_metrics,
            participants=participants,
            meta=base_meta,
        )

    # -----------------------------------------------------
    # API LEGACY: decidir sobre un conjunto de señales
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
            chosen_side = None
            participants = list({*long_voters, *short_voters})
            trade_id = self._make_trade_id(base_meta, side="CONFLICT")
            self.memory.register_vote_set(trade_id, self._serialize_participants(participants))
            order = self._make_order(base_meta, side="LONG", size_fraction=0.0)
            decision = Decision(action="GHOST", side=None, order=order, reason="conflicto_de_lado", trade_id=trade_id)
            self._log_decision(decision, base_meta, order, participants, [], equity)
            return decision

        # Elegir lado
        if long_voters:
            chosen_side = "LONG"
            side_voters = long_voters
        elif short_voters:
            chosen_side = "SHORT"
            side_voters = short_voters
        else:
            return Decision(action="SKIP", side=None, order=None, reason="señales_no_votantes", trade_id=None)

        participant_metrics = self._participant_metrics(side_voters)
        participants = [m.participant for m in participant_metrics]

        trade_id = self._make_trade_id(base_meta, side=chosen_side)
        self.memory.register_vote_set(trade_id, self._serialize_participants(participants))

        approved_metrics = [m for m in participant_metrics if m.approved]
        positive_kelly_metrics = [m for m in approved_metrics if m.kelly > 0]

        # Por defecto, la acción es GHOST hasta que se demuestre lo contrario
        action = "GHOST"
        size_fraction = 0.0
        reason = "sin_aprobadas"

        # Condiciones para una apuesta real (BET)
        if not approved_metrics:
            reason = "sin_aprobadas"
        elif not positive_kelly_metrics:
            reason = "kelly_no_positivo"
        else:
            min_kelly = min(m.kelly for m in positive_kelly_metrics)
            if min_kelly > 0:
                action = "BET"
                size_fraction = min(min_kelly, getattr(config, "MAX_POSITION_SIZE", 0.25))
                reason = "apuesta_conservadora"
            else:
                # Este caso es raro, pero por si acaso min() diera 0
                reason = "kelly_conservador_cero"

        order = self._make_order(base_meta, side=chosen_side, size_fraction=size_fraction)
        decision = Decision(action=action, side=chosen_side, order=order, reason=reason, trade_id=trade_id)
        self._log_decision(decision, base_meta, order, participants, participant_metrics, equity)
        return decision

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
        if self.decision_logger:
            self.decision_logger.log_result(result)
        self.memory.finalize_trade(trade_id, win=win)

    # =====================================================
    # Internos — helpers
    # =====================================================
    def _collect_votes_by_side(self, signals: List[dict]) -> Tuple[List[Participant], List[Participant], dict]:
        """
        Separa votantes por lado y recoge metadatos base.
        
        Procesa señales de sensores y las clasifica en LONG o SHORT.
        Cada señal debe contener timestamp, symbol, side, y origin (estrategia).
        
        Args:
            signals: Lista de señales de sensores. Cada señal es un dict con:
                    {"timestamp": str, "symbol": str, "side": "LONG"|"SHORT",
                     "origin": str (opcional), "features": dict (opcional)}
        
        Returns:
            Tuple de (long_voters, short_voters, base_meta):
            - long_voters: Lista de Participant que votaron LONG
            - short_voters: Lista de Participant que votaron SHORT
            - base_meta: Dict con timestamp, symbol, timeframe de la primera señal
        
        Nota:
            Si origin no está presente, se infiere de features/_origin o sensor,
            o se asigna "UnknownSensor" como fallback.
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
        Infiere el nombre de la estrategia/sensor que generó la señal.
        
        Busca en múltiples campos posibles (origin, sensor, strategy, source)
        y en features/_origin como fallback.
        
        Args:
            signal: Dict con la señal del sensor
        
        Returns:
            str: Nombre de la estrategia/sensor, o "UnknownSensor" si no se encuentra
        
        Nota:
            🔧 PUNTO DE EXTENSIÓN: Si tus señales usan otro campo para el nombre,
            agrégalo a la lista de campos buscados.
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

    def _participant_metrics(self, voters: List[Participant]) -> List[ParticipantMetrics]:
        """
        Calcula métricas probabilísticas para cada participante (estrategia).
        
        Para cada participante:
        1. Obtiene p_hat (winrate) y support (tamaño de ventana) de la memoria
        2. Calcula credibilidad bayesiana: Pr(p > p_star | datos)
        3. Si credibilidad >= threshold, calcula p_conservative (percentil inferior)
        4. Calcula Kelly: f = p_conservative - (1-p_conservative)/B
        5. Aprueba si: support >= MIN_SAMPLES y kelly > 0
        
        Args:
            voters: Lista de Participant que votaron por el mismo lado
        
        Returns:
            Lista de ParticipantMetrics con todas las métricas calculadas:
            - support: número de observaciones en la ventana
            - p_hat: winrate observado
            - credibility: Pr(p > p_star | datos)
            - p_conservative: percentil inferior de la distribución posterior
            - kelly: fracción de Kelly calculada
            - approved: True si cumple criterios de aprobación
            - reason: razón de aprobación/rechazo
        
        Nota:
            Usa inferencia bayesiana con prior Beta(α, β) y posterior actualizado
            con wins y losses observados.
        """
        metrics: List[ParticipantMetrics] = []

        for participant in voters:
            if participant.bucket == "UNKNOWN" or not participant.bucket:
                metrics.append(
                    ParticipantMetrics(
                        participant=participant,
                        support=self.memory.get_window_size(participant.memory_key),
                        p_hat=self.memory.get_winrate(participant.memory_key),
                        credibility=0.0,
                        p_conservative=0.0,
                        kelly=0.0,
                        approved=False,
                        reason="bucket_unknown",
                        p_star=P_STAR,
                        r_net=R_NET,
                        l_net=L_NET,
                    )
                )
                continue

            key = participant.memory_key
            p_hat = self.memory.get_winrate(key)
            support = self.memory.get_window_size(key)

            credibility = 0.0
            p_conservative = 0.0
            kelly = 0.0
            approved = False
            reason = "insufficient_support"

            if p_hat is not None and support >= APPROVAL_MIN_SAMPLES:
                wins_est = max(0, min(support, int(round(p_hat * support))))
                losses_est = max(0, support - wins_est)

                alpha_post = ALPHA_PRIOR + wins_est
                beta_post = BETA_PRIOR + losses_est

                credibility = self._beta_prob_greater(P_STAR, alpha_post, beta_post)

                if credibility >= CREDIBILITY_THRESHOLD:
                    p_conservative = self._beta_quantile(alpha_post, beta_post, LOWER_CREDIBLE_PERCENTILE)
                    if p_conservative > P_STAR and B > 0:
                        f_raw = p_conservative - (1 - p_conservative) / B
                        kelly = max(0.0, f_raw) * KELLY_FRACTION
                        if kelly > 0:
                            approved = True
                            reason = "approved"
                        else:
                            reason = "kelly_zero"
                    else:
                        reason = "edge_not_positive"
                else:
                    reason = "credibility_low"
            else:
                reason = "insufficient_support"

            metrics.append(
                ParticipantMetrics(
                    participant=participant,
                    support=support,
                    p_hat=p_hat,
                    credibility=credibility,
                    p_conservative=p_conservative,
                    kelly=kelly,
                    approved=approved,
                    reason=reason,
                    p_star=P_STAR,
                    r_net=R_NET,
                    l_net=L_NET,
                )
            )

        return metrics

    def _make_trade_id(self, meta: dict, side: str) -> str:
        """
        Genera un ID único para el trade.
        
        Formato: {market}-{side}-{timestamp}
        Ejemplo: "BTC/USD@1m-LONG-2025-11-02T14:30:00"
        
        Args:
            meta: Dict con timestamp, symbol, timeframe
            side: "LONG" | "SHORT" | "CONFLICT"
        
        Returns:
            str: ID único del trade
        
        Nota:
            Si timestamp no está presente, usa datetime.utcnow()
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
        Construye la orden estandarizada para el Croupier/Mesa.
        
        La orden contiene toda la información necesaria para ejecutar el trade:
        symbol, side, size (fracción), take_profit, stop_loss.
        
        Args:
            meta: Dict con symbol, timeframe, timestamp
            side: "LONG" | "SHORT"
            size_fraction: Fracción del equity a arriesgar [0.0, 1.0]
                          0.0 = orden fantasma (GHOST)
                          >0.0 = orden real (BET)
        
        Returns:
            dict: Orden estandarizada con campos:
                - symbol: símbolo del activo
                - timeframe: timeframe de operación
                - timestamp: momento de la decisión
                - side: LONG o SHORT
                - size: fracción del equity (float)
                - take_profit: multiplicador de TP (ej: 1.01 = +1%)
                - stop_loss: multiplicador de SL (ej: 0.99 = -1%)
                - market: {symbol}@{timeframe} (si timeframe disponible)
        
        Nota:
            El Croupier/Mesa convierte size_fraction a monto real basado en equity.
        """
        symbol = meta.get("symbol", "UNKNOWN")
        timeframe = meta.get("timeframe", "UNKNOWN")
        order = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": meta.get("timestamp"),
            "side": side,
            "size": float(size_fraction),
            "take_profit": 1.0 + R_GROSS,
            "stop_loss": 1.0 - L_GROSS,
        }
        if timeframe and timeframe != "UNKNOWN":
            order["market"] = f"{symbol}@{timeframe}"
        return order

    def _extract_participants(self, signal: dict) -> List[Participant]:
        """
        Extrae participantes (estrategias) de una señal.
        
        Una señal puede tener múltiples contribuyentes (sensores/estrategias).
        Esta función crea un Participant por cada contribuyente.
        
        Args:
            signal: Dict con la señal. Puede contener:
                   - contributors: lista de nombres de estrategias
                   - origin/sensor/strategy: nombre único de estrategia
        
        Returns:
            Lista de Participant, uno por cada estrategia que contribuyó
        
        Nota:
            Si contributors está presente, crea un Participant por cada uno.
            Si no, crea un solo Participant inferido de la señal.
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
        Construye un Participant desde una señal.
        
        Un Participant representa una estrategia específica operando en un
        contexto específico (bucket) para un símbolo/timeframe.
        
        Args:
            signal: Dict con la señal (debe tener symbol, timeframe, features)
            origin_override: Nombre de estrategia (opcional, si no se infiere)
        
        Returns:
            Participant con strategy, bucket, symbol, timeframe
            None si hay error al identificar el bucket
        
        Nota:
            El bucket se identifica usando BucketManager.identify_bucket()
            Si falla, se asigna "UNKNOWN" como bucket.
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
        """
        Serializa participantes para GeminiMemory.
        
        Convierte objetos Participant en dicts para almacenar en memoria.
        
        Args:
            participants: Lista de Participant
        
        Returns:
            Lista de dicts con campos:
            - strategy: nombre de la estrategia
            - bucket: contexto de mercado
            - symbol: símbolo del activo
            - timeframe: timeframe de operación
            - market: {symbol}@{timeframe}
        """
        payload = []
        for p in participants:
            payload.append(
                {
                    "strategy": p.strategy,
                    "bucket": p.bucket,
                    "symbol": p.symbol,
                    "timeframe": p.timeframe,
                    "market": p.market,
                }
            )
        return payload

    def _log_decision(
        self,
        decision: Decision,
        meta: Dict,
        order: Dict,
        participants: Iterable[Participant],
        metrics: Iterable[ParticipantMetrics],
        equity: float,
    ) -> None:
        if not self.decision_logger or not decision.trade_id:
            return

        participants = list(participants)
        metrics = list(metrics)

        contributors = sorted({p.strategy for p in participants}) or []
        market = order.get("market") or (
            f"{order.get('symbol', 'UNKNOWN')}@{order.get('timeframe', 'UNKNOWN')}"
            if order.get("symbol")
            else "UNKNOWN"
        )

        if metrics:
            rows = [
                {
                    "timestamp": meta.get("timestamp"),
                    "trade_id": decision.trade_id,
                    "market": market,
                    "symbol": order.get("symbol", meta.get("symbol", "UNKNOWN")),
                    "timeframe": order.get("timeframe", meta.get("timeframe", "UNKNOWN")),
                    "side": order.get("side"),
                    "action": decision.action,
                    "reason": decision.reason,
                    "size": float(order.get("size", 0.0) or 0.0),
                    "equity": float(equity) if equity is not None else "",
                    "contributors": ",".join(contributors),
                    "strategy": m.participant.strategy,
                    "bucket": m.participant.bucket,
                    "support": m.support,
                    "p_hat": m.p_hat if m.p_hat is not None else "",
                    "credibility": m.credibility,
                    "p_conservative": m.p_conservative,
                    "kelly": m.kelly,
                    "approved": "yes" if m.approved else "no",
                    "participant_reason": m.reason,
                    "p_star": P_STAR,
                    "r_net": R_NET,
                    "l_net": L_NET,
                }
                for m in metrics
            ]
        else:
            rows = [
                {
                    "timestamp": meta.get("timestamp"),
                    "trade_id": decision.trade_id,
                    "market": market,
                    "symbol": order.get("symbol", meta.get("symbol", "UNKNOWN")),
                    "timeframe": order.get("timeframe", meta.get("timeframe", "UNKNOWN")),
                    "side": order.get("side"),
                    "action": decision.action,
                    "reason": decision.reason,
                    "size": float(order.get("size", 0.0) or 0.0),
                    "equity": float(equity) if equity is not None else "",
                    "contributors": ",".join(contributors),
                    "strategy": "",
                    "bucket": "",
                    "support": "",
                    "p_hat": "",
                    "credibility": "",
                    "p_conservative": "",
                    "kelly": "",
                    "approved": "no",
                    "participant_reason": "no_metrics",
                    "p_star": P_STAR,
                    "r_net": R_NET,
                    "l_net": L_NET,
                }
            ]

        self.decision_logger.log(rows)

    def _log_verdict(
        self,
        trade_id: str,
        side: str,
        reason: str,
        meta: Dict,
        participants: List[Participant],
        metrics: List[ParticipantMetrics],
        equity: float,
    ) -> None:
        """Log simplificado para Verdict (sin orden)"""
        if not self.decision_logger or not trade_id:
            return

        contributors = sorted({p.strategy for p in participants}) or []
        market = f"{meta.get('symbol', 'UNKNOWN')}@{meta.get('timeframe', 'UNKNOWN')}"

        if metrics:
            rows = [
                {
                    "timestamp": meta.get("timestamp"),
                    "trade_id": trade_id,
                    "market": market,
                    "symbol": meta.get("symbol", "UNKNOWN"),
                    "timeframe": meta.get("timeframe", "UNKNOWN"),
                    "side": side,
                    "action": "VERDICT",
                    "reason": reason,
                    "size": 0.0,  # Player decide esto después
                    "equity": float(equity) if equity is not None else "",
                    "contributors": ",".join(contributors),
                    "strategy": m.participant.strategy,
                    "bucket": m.participant.bucket,
                    "support": m.support,
                    "p_hat": m.p_hat if m.p_hat is not None else "",
                    "credibility": m.credibility,
                    "p_conservative": m.p_conservative,
                    "kelly": m.kelly,
                    "approved": "yes" if m.approved else "no",
                    "participant_reason": m.reason,
                    "p_star": P_STAR,
                    "r_net": R_NET,
                    "l_net": L_NET,
                }
                for m in metrics
            ]
        else:
            rows = [
                {
                    "timestamp": meta.get("timestamp"),
                    "trade_id": trade_id,
                    "market": market,
                    "symbol": meta.get("symbol", "UNKNOWN"),
                    "timeframe": meta.get("timeframe", "UNKNOWN"),
                    "side": side,
                    "action": "VERDICT",
                    "reason": reason,
                    "size": 0.0,
                    "equity": float(equity) if equity is not None else "",
                    "contributors": ",".join(contributors),
                    "strategy": "",
                    "bucket": "",
                    "support": "",
                    "p_hat": "",
                    "credibility": "",
                    "p_conservative": "",
                    "kelly": "",
                    "approved": "no",
                    "participant_reason": "no_metrics",
                    "p_star": P_STAR,
                    "r_net": R_NET,
                    "l_net": L_NET,
                }
            ]

        self.decision_logger.log(rows)

    # -----------------------------------------------------
    # API para construir órdenes desde Verdict
    # -----------------------------------------------------
    def make_order_from_verdict(self, verdict: Verdict, size_fraction: float, ghost: bool = False) -> dict:
        """
        Construye una orden desde un Verdict y un tamaño decidido por el Player.

        Args:
            verdict: Veredicto de evaluate_signals_v2()
            size_fraction: Fracción del equity a arriesgar [0, 1]
            ghost: Si True, marca como GHOST trade (shadow trading)

        Returns:
            dict: Orden estandarizada para el Croupier

        Nota:
            Si verdict.side es None (conflicto), se usa "LONG" arbitrariamente
            para construir la orden GHOST (el lado no importa en GHOST)
        """
        if not verdict:
            raise ValueError("Verdict es None")

        # Si hay conflicto (side=None), usar LONG arbitrariamente para GHOST
        side = verdict.side or "LONG"

        meta = verdict.meta or self._last_verdict_meta or {}

        order = self._make_order(meta, side, size_fraction)
        order["trade_id"] = verdict.trade_id
        order["ghost"] = ghost

        return order

    # -----------------------------------------------------
    # Bayesian helpers
    # -----------------------------------------------------
    def _beta_prob_greater(self, threshold: float, alpha: float, beta: float) -> float:
        """
        Calcula Pr(p > threshold | α, β) para distribución Beta.
        
        Usa scipy.stats.beta si está disponible, sino aproximación normal.
        
        Args:
            threshold: Valor umbral (ej: p_star)
            alpha: Parámetro α de la distribución Beta posterior
            beta: Parámetro β de la distribución Beta posterior
        
        Returns:
            float: Probabilidad de que p > threshold [0.0, 1.0]
        
        Nota:
            Esto representa la "credibilidad" de que el winrate verdadero
            es mayor que el break-even (p_star).
        """
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
        std = var**0.5 if var > 0 else 0.0
        if std == 0:
            return 1.0 if mean > threshold else 0.0
        nd = NormalDist(mean, std)
        return 1.0 - nd.cdf(threshold)

    def _beta_quantile(self, alpha: float, beta: float, percentile: float) -> float:
        """
        Calcula el cuantil de la distribución Beta.
        
        Usa scipy.stats.beta.ppf si está disponible, sino aproximación normal.
        
        Args:
            alpha: Parámetro α de la distribución Beta posterior
            beta: Parámetro β de la distribución Beta posterior
            percentile: Percentil deseado [0.0, 1.0] (ej: 0.1 = percentil 10)
        
        Returns:
            float: Valor del percentil [0.0, 1.0]
        
        Nota:
            Se usa para obtener p_conservative (estimación conservadora del winrate)
            usando el percentil inferior de la distribución posterior.
        """
        percentile = max(0.0, min(1.0, percentile))
        if scipy_beta is not None:
            return float(scipy_beta.ppf(percentile, alpha, beta))

        mean = alpha / (alpha + beta)
        var = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1))
        std = var**0.5 if var > 0 else 0.0
        if std == 0:
            return mean
        nd = NormalDist(mean, std)
        return max(0.0, min(1.0, nd.inv_cdf(percentile)))
