# 🔧 PROPUESTA DE REFACTORIZACIÓN DETALLADA - v1.9.4

**Basado en:** ANALISIS_MODULARIDAD_v1.9.4.md
**Fecha:** 2025-11-06
**Estado:** PROPUESTA

---

## 📋 ÍNDICE

1. [Arquitectura Objetivo](#arquitectura-objetivo)
2. [Implementaciones Concretas](#implementaciones-concretas)
3. [Ejemplos de Código](#ejemplos-de-código)
4. [Plan de Migración](#plan-de-migración)

---

## 🎯 ARQUITECTURA OBJETIVO

### Nueva Estructura de Directorios

```
Casino-V2/
├── config/                      # ← NUEVO
│   ├── __init__.py
│   ├── manager.py              # ConfigManager
│   ├── schema.py               # Pydantic schemas
│   ├── validators.py           # Validadores custom
│   └── defaults.yaml           # Configuración por defecto
│
├── core/
│   ├── container.py            # ← NUEVO: DI Container
│   ├── interfaces/             # ← NUEVO: Interfaces abstractas
│   │   ├── __init__.py
│   │   ├── player.py           # BasePlayer
│   │   ├── sensor.py           # BaseSensor
│   │   └── evaluator.py        # BaseEvaluator
│   │
│   ├── trading/
│   │   ├── session.py          # TradingSession (mejorado)
│   │   ├── pipeline.py         # Pipeline (sin cambios)
│   │   ├── context.py          # TradingContext (sin cambios)
│   │   └── stages/
│   │       ├── process_signals.py
│   │       ├── evaluate.py
│   │       ├── build_order.py  # Simplificado
│   │       └── execute.py
│   │
│   ├── data_sources/           # Sin cambios mayores
│   └── session_runner.py       # ← ELIMINAR
│
├── gemini/                      # ← REFACTORIZAR
│   ├── __init__.py
│   ├── evaluator.py            # Evaluación principal (200 líneas)
│   ├── kelly.py                # Cálculo Kelly (150 líneas)
│   ├── bayesian.py             # Estadística bayesiana (200 líneas)
│   ├── verdict.py              # Construcción veredictos (100 líneas)
│   ├── memory_interface.py     # Abstracción memoria (100 líneas)
│   └── legacy/                 # Código viejo (temporal)
│       └── gemini_core.py
│
├── sensors/                     # ← REFACTORIZAR
│   ├── __init__.py
│   ├── manager.py              # Orquestador (80 líneas)
│   ├── registry.py             # Registro (50 líneas)
│   ├── executor.py             # Ejecución (60 líneas)
│   ├── consolidator.py         # Consolidación (100 líneas)
│   ├── cooldown.py             # Cooldowns (40 líneas)
│   ├── mean_reversion/
│   ├── momentum_trend_following/
│   └── volumen_flujo_capital/
│
├── players/                     # ← REFACTORIZAR
│   ├── __init__.py
│   ├── base.py                 # ← NUEVO: BasePlayer
│   ├── paroli.py               # Refactorizado
│   ├── kelly.py                # Refactorizado
│   └── martingale.py           # Futuro
│
└── utils/
    ├── symbol_normalizer.py    # ← NUEVO
    └── ...
```

---

## 💻 IMPLEMENTACIONES CONCRETAS

### 1. Sistema de Configuración

#### `config/schema.py`

```python
"""
Schemas de configuración con Pydantic.
Valida tipos y rangos automáticamente.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional

class TradingConfig(BaseModel):
    """Configuración de trading"""
    take_profit: float = Field(0.01, gt=0, le=1, description="TP como fracción")
    stop_loss: float = Field(0.01, gt=0, le=1, description="SL como fracción")
    kelly_fraction: float = Field(1.0, ge=0, le=1, description="Fracción de Kelly")
    max_leverage: int = Field(50, ge=1, le=100, description="Apalancamiento máximo")
    max_position_size: float = Field(0.25, gt=0, le=1, description="Tamaño máximo de posición")
    commission_rate: float = Field(0.0004, ge=0, le=0.01, description="Comisión por lado")
    slippage_default: float = Field(0.0005, ge=0, le=0.01, description="Slippage estimado")

    class Config:
        validate_assignment = True
        extra = "forbid"  # No permite campos extra

class GeminiConfig(BaseModel):
    """Configuración de Gemini"""
    min_support: int = Field(20, ge=1, description="Mínimo de muestras")
    approval_min_samples: int = Field(500, ge=1, description="Muestras para aprobar estrategia")
    window_size: int = Field(120, ge=1, description="Ventana de memoria")
    edge_threshold: float = Field(0.02, ge=0, le=1, description="Umbral de ventaja")

    # Bayesian
    bayes_alpha: float = Field(1.0, gt=0, description="Prior alpha")
    bayes_beta: float = Field(1.0, gt=0, description="Prior beta")
    bayes_credibility_threshold: float = Field(0.6, ge=0, le=1)
    bayes_lower_percentile: float = Field(0.1, ge=0, le=1)

class SensorConfig(BaseModel):
    """Configuración de sensores"""
    active_sensors: Dict[str, bool] = Field(default_factory=dict)
    sensor_params: Dict[str, Dict] = Field(default_factory=dict)
    sensor_cooldown_bars: int = Field(0, ge=0, description="Cooldown entre señales")
    sensor_batch_size: int = Field(5, ge=1, description="Tamaño de batch para procesamiento")

class ExchangeConfig(BaseModel):
    """Configuración de exchange"""
    exchange: str = Field("kraken", description="ID del exchange")
    testnet: bool = Field(True, description="Usar testnet")
    symbols: List[str] = Field(default_factory=lambda: ["BTC/USD"])
    timeframe: str = Field("1m", description="Timeframe de velas")

class SystemConfig(BaseModel):
    """Configuración completa del sistema"""
    mode: str = Field("backtest", regex="^(backtest|testing|live)$")
    log_level: str = Field("INFO", regex="^(DEBUG|INFO|WARNING|ERROR)$")
    seed: Optional[int] = Field(42, description="Semilla aleatoria")

    # Sub-configs
    trading: TradingConfig = Field(default_factory=TradingConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    sensors: SensorConfig = Field(default_factory=SensorConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)

    @validator("mode")
    def validate_mode(cls, v):
        if v not in ["backtest", "testing", "live"]:
            raise ValueError(f"Invalid mode: {v}")
        return v
```

#### `config/manager.py`

```python
"""
ConfigManager: Gestión centralizada de configuración.
"""
import yaml
from pathlib import Path
from typing import Any, Optional
from .schema import SystemConfig

class ConfigManager:
    """
    Gestor de configuración con validación.

    Ejemplo:
        >>> config = ConfigManager.from_yaml("config.yaml")
        >>> tp = config.trading.take_profit
        >>> print(tp)  # 0.01
    """

    def __init__(self, config_dict: dict):
        """
        Inicializar con diccionario.

        Args:
            config_dict: Configuración como dict

        Raises:
            ValidationError: Si la configuración es inválida
        """
        self.config = SystemConfig(**config_dict)

    @classmethod
    def from_yaml(cls, path: str) -> "ConfigManager":
        """Cargar desde archivo YAML"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(data)

    @classmethod
    def from_env(cls) -> "ConfigManager":
        """Cargar desde variables de entorno"""
        # TODO: Implementar
        pass

    @classmethod
    def default(cls) -> "ConfigManager":
        """Configuración por defecto"""
        return cls({})

    # Acceso conveniente a sub-configs
    @property
    def trading(self):
        return self.config.trading

    @property
    def gemini(self):
        return self.config.gemini

    @property
    def sensors(self):
        return self.config.sensors

    @property
    def exchange(self):
        return self.config.exchange

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtener valor por clave con dot notation.

        Ejemplo:
            >>> config.get("trading.take_profit")
            0.01
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default

        return value

    def to_dict(self) -> dict:
        """Exportar como diccionario"""
        return self.config.dict()

    def to_yaml(self, path: str):
        """Guardar como YAML"""
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
```

---

### 2. Dependency Injection Container

#### `core/container.py`

```python
"""
ServiceContainer: Contenedor de inyección de dependencias.
"""
from typing import Dict, Callable, Any, Optional
from config.manager import ConfigManager

class ServiceContainer:
    """
    Contenedor DI simple pero efectivo.

    Ejemplo:
        >>> container = ServiceContainer()
        >>> container.register("config", lambda c: ConfigManager.default(), singleton=True)
        >>> container.register("gemini", lambda c: Gemini(c.get("config")))
        >>> gemini = container.get("gemini")
    """

    def __init__(self):
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_flags: Dict[str, bool] = {}

    def register(
        self,
        name: str,
        factory: Callable[[" ServiceContainer"], Any],
        singleton: bool = False
    ):
        """
        Registrar factory de servicio.

        Args:
            name: Nombre del servicio
            factory: Función que crea el servicio (recibe container)
            singleton: Si True, solo se crea una instancia
        """
        self._factories[name] = factory
        self._singleton_flags[name] = singleton
        if singleton:
            self._singletons[name] = None

    def get(self, name: str) -> Any:
        """
        Obtener instancia de servicio.

        Args:
            name: Nombre del servicio

        Returns:
            Instancia del servicio

        Raises:
            KeyError: Si el servicio no está registrado
        """
        if name not in self._factories:
            raise KeyError(f"Service '{name}' not registered")

        # Singleton: retornar instancia existente o crear nueva
        if self._singleton_flags.get(name, False):
            if self._singletons[name] is None:
                self._singletons[name] = self._factories[name](self)
            return self._singletons[name]

        # Transient: crear nueva instancia cada vez
        return self._factories[name](self)

    def has(self, name: str) -> bool:
        """Verificar si servicio está registrado"""
        return name in self._factories

    def reset_singleton(self, name: str):
        """Resetear singleton (útil para tests)"""
        if name in self._singletons:
            self._singletons[name] = None


def create_container(config: ConfigManager) -> ServiceContainer:
    """
    Factory para crear container con servicios estándar.

    Args:
        config: ConfigManager ya inicializado

    Returns:
        ServiceContainer configurado
    """
    container = ServiceContainer()

    # Config (singleton)
    container.register("config", lambda c: config, singleton=True)

    # Memory (singleton)
    from gemini.memory import GeminiMemory
    container.register(
        "memory",
        lambda c: GeminiMemory(
            window_size=c.get("config").gemini.window_size,
            min_support=c.get("config").gemini.min_support
        ),
        singleton=True
    )

    # Gemini (transient - nueva instancia por sesión)
    from gemini.evaluator import GeminiEvaluator
    container.register(
        "gemini",
        lambda c: GeminiEvaluator(
            config=c.get("config"),
            memory=c.get("memory")
        )
    )

    # SensorManager (transient)
    from sensors.manager import SensorManager
    container.register(
        "sensor_manager",
        lambda c: SensorManager(config=c.get("config"))
    )

    # Players (factories)
    from players.paroli import ParoliPlayer
    from players.kelly import KellyPlayer

    container.register(
        "player:paroli",
        lambda c: ParoliPlayer(config=c.get("config"))
    )

    container.register(
        "player:kelly",
        lambda c: KellyPlayer(config=c.get("config"))
    )

    return container
```

---

### 3. BasePlayer Interface

#### `core/interfaces/player.py`

```python
"""
BasePlayer: Interfaz abstracta para players.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from config.manager import ConfigManager

@dataclass(frozen=True)
class PlayerState:
    """
    Estado inmutable del player.

    Attributes:
        step: Paso actual en progresión (0-indexed)
        unit: Unidad base de apuesta (None si no iniciada)
        metadata: Datos adicionales específicos del player
    """
    step: int = 0
    unit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_step(self, step: int) -> "PlayerState":
        """Crear nuevo estado con step actualizado"""
        return PlayerState(
            step=step,
            unit=self.unit,
            metadata=self.metadata
        )

    def with_unit(self, unit: float) -> "PlayerState":
        """Crear nuevo estado con unit actualizada"""
        return PlayerState(
            step=self.step,
            unit=unit,
            metadata=self.metadata
        )

    def with_metadata(self, **kwargs) -> "PlayerState":
        """Crear nuevo estado con metadata actualizada"""
        new_meta = {**self.metadata, **kwargs}
        return PlayerState(
            step=self.step,
            unit=self.unit,
            metadata=new_meta
        )

@dataclass(frozen=True)
class Outcome:
    """
    Resultado de un trade.

    Attributes:
        result: "WIN" o "LOSS"
        pnl: Profit/Loss monetario
        fee: Comisiones pagadas
        metadata: Datos adicionales
    """
    result: str  # "WIN" | "LOSS"
    pnl: float
    fee: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_win(self) -> bool:
        return self.result.upper() == "WIN"

    @property
    def is_loss(self) -> bool:
        return self.result.upper() == "LOSS"

class BasePlayer(ABC):
    """
    Interfaz abstracta para todos los players.

    Un Player decide CUÁNTO apostar basado en el veredicto de Gemini.

    Responsabilidades:
        - Mantener estado de progresión (Paroli, Martingale, etc.)
        - Calcular tamaño de posición
        - Actualizar estado tras resultado
        - Validar estado

    NO es responsable de:
        - Decidir SI apostar (eso es Gemini)
        - Ejecutar órdenes (eso es DataSource)
        - Detectar señales (eso es SensorManager)
    """

    def __init__(self, config: ConfigManager):
        """
        Inicializar player con configuración.

        Args:
            config: ConfigManager inyectado
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del player (ej: "Paroli", "Kelly")"""
        pass

    @property
    @abstractmethod
    def respects_gemini_verdict(self) -> bool:
        """
        Si True, solo apuesta cuando Gemini dice BET.
        Si False, apuesta en cualquier señal con side válido.

        Ejemplos:
            - Kelly: True (conservador, respeta Gemini)
            - Paroli: False (agresivo, apuesta siempre)
        """
        pass

    @abstractmethod
    def init_state(self) -> PlayerState:
        """
        Crear estado inicial.

        Returns:
            PlayerState inicial
        """
        pass

    @abstractmethod
    def calculate_size(
        self,
        verdict: Any,  # gemini.verdict.Verdict
        equity: float,
        state: PlayerState
    ) -> Optional[float]:
        """
        Calcular tamaño de posición como fracción de equity.

        Args:
            verdict: Veredicto de Gemini
            equity: Equity disponible
            state: Estado actual del player

        Returns:
            Fracción de equity a apostar (0.0-1.0) o None si no apostar

        Ejemplo:
            >>> size = player.calculate_size(verdict, 10000, state)
            >>> print(size)  # 0.04 (4% del equity)
        """
        pass

    @abstractmethod
    def handle_outcome(
        self,
        state: PlayerState,
        outcome: Outcome
    ) -> PlayerState:
        """
        Actualizar estado tras resultado de trade.

        Args:
            state: Estado actual
            outcome: Resultado del trade

        Returns:
            Nuevo estado (inmutable)
        """
        pass

    def validate_state(self, state: PlayerState) -> bool:
        """
        Validar que el estado sea válido.

        Args:
            state: Estado a validar

        Returns:
            True si válido, False si no

        Note:
            Implementación por defecto siempre retorna True.
            Override para validaciones específicas.
        """
        return True

    def prepare_state(
        self,
        state: PlayerState,
        equity: float
    ) -> tuple[PlayerState, Dict[str, Any]]:
        """
        Preparar estado antes de calcular size.

        Útil para players que necesitan calcular unit base.

        Args:
            state: Estado actual
            equity: Equity disponible

        Returns:
            (nuevo_estado, metadata)

        Note:
            Implementación por defecto retorna estado sin cambios.
        """
        return state, {}
```

---

### 4. Paroli Refactorizado

#### `players/paroli.py`

```python
"""
ParoliPlayer: Progresión positiva 1-4-8.
"""
from typing import Optional, Dict, Any
from core.interfaces.player import BasePlayer, PlayerState, Outcome
from config.manager import ConfigManager

class ParoliPlayer(BasePlayer):
    """
    Player con progresión Paroli 1x → 4x → 8x.

    Características:
        - Agresivo: apuesta en cualquier señal
        - Progresión positiva: aumenta tras victoria
        - Reinicia tras pérdida o completar ciclo
    """

    # Constantes
    BASE_DIVISOR = 250  # unit = equity / 250
    PROGRESSION = (1, 4, 8)
    LEVERAGE = 10

    def __init__(self, config: ConfigManager):
        super().__init__(config)
        self.max_position_size = config.trading.max_position_size

    @property
    def name(self) -> str:
        return "Paroli"

    @property
    def respects_gemini_verdict(self) -> bool:
        return False  # Agresivo: apuesta siempre

    def init_state(self) -> PlayerState:
        return PlayerState(step=0, unit=None)

    def prepare_state(
        self,
        state: PlayerState,
        equity: float
    ) -> tuple[PlayerState, Dict[str, Any]]:
        """Calcular unit si no existe"""
        if state.unit is None and equity > 0:
            unit = equity / self.BASE_DIVISOR
            state = state.with_unit(unit)

        metadata = {
            "paroli_unit": state.unit,
            "paroli_step": state.step,
            "paroli_multiplier": self.PROGRESSION[state.step]
        }

        return state, metadata

    def calculate_size(
        self,
        verdict: Any,
        equity: float,
        state: PlayerState
    ) -> Optional[float]:
        """Calcular tamaño según progresión Paroli"""
        # Validaciones
        if not verdict or not verdict.side:
            return None

        if equity <= 0:
            return None

        if state.unit is None or state.unit <= 0:
            return None

        # Calcular tamaño
        step = max(0, min(state.step, len(self.PROGRESSION) - 1))
        multiplier = self.PROGRESSION[step]
        position_amount = state.unit * multiplier

        # Fracción de equity
        size_fraction = position_amount / equity

        # Limitar por max_position_size
        size_fraction = min(size_fraction, self.max_position_size)

        return size_fraction if size_fraction > 0 else None

    def handle_outcome(
        self,
        state: PlayerState,
        outcome: Outcome
    ) -> PlayerState:
        """Actualizar progresión según resultado"""
        if outcome.is_win:
            # Avanzar en progresión
            next_step = state.step + 1

            # Si completó ciclo, reiniciar
            if next_step >= len(self.PROGRESSION):
                return PlayerState(step=0, unit=None)

            return state.with_step(next_step)

        # Pérdida: reiniciar
        return PlayerState(step=0, unit=None)

    def validate_state(self, state: PlayerState) -> bool:
        """Validar estado Paroli"""
        if state.step < 0 or state.step >= len(self.PROGRESSION):
            return False

        if state.unit is not None and state.unit < 0:
            return False

        return True
```

---

## 🔄 PLAN DE MIGRACIÓN

### Fase 1: Fundamentos (Sprint 1-2)

#### Semana 1: Configuración
1. Crear `config/schema.py`
2. Crear `config/manager.py`
3. Tests unitarios
4. Migrar `main.py` a usar ConfigManager

#### Semana 2: DI Container
1. Crear `core/container.py`
2. Crear factories
3. Migrar `main.py` a usar container
4. Tests de integración

---

### Fase 2: Interfaces (Sprint 3)

#### Semana 3: BasePlayer
1. Crear `core/interfaces/player.py`
2. Refactorizar `players/paroli.py`
3. Refactorizar `players/kelly.py`
4. Tests unitarios

---

### Fase 3: Refactorización Core (Sprint 4-6)

#### Semana 4-5: Gemini
1. Dividir en módulos
2. Migrar a usar ConfigManager
3. Tests unitarios

#### Semana 6: SensorManager
1. Dividir en módulos
2. Migrar a usar ConfigManager
3. Tests unitarios

---

### Fase 4: Limpieza (Sprint 7)

#### Semana 7: Eliminar Legacy
1. Eliminar `session_runner.py`
2. Migrar funcionalidad a TradingSession
3. Actualizar tests
4. Documentación

---

## ✅ CHECKLIST DE VALIDACIÓN

Antes de mergear cada fase:

- [ ] Tests unitarios pasan (>80% cobertura)
- [ ] Tests de integración pasan
- [ ] Backtest produce mismos resultados
- [ ] Testing mode funciona
- [ ] Documentación actualizada
- [ ] Code review aprobado
- [ ] Performance no degradado

---

**Próximo paso:** Revisar propuesta y comenzar Fase 1
