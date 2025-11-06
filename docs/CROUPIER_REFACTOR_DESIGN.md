# 🎯 Diseño: Croupier como Tablero de Control

## 📋 Objetivo

Transformar el Croupier de un simple "pass-through" a un **tablero de control centralizado** que:
- Gestiona el portfolio (balance + posiciones)
- Coordina la ejecución con exchange adapters
- Provee información consolidada al resto del sistema
- Mantiene el estado del trading

---

## 🏗️ Arquitectura Actual vs Nueva

### ❌ Arquitectura Actual (v1.9.4)

```
Gemini → Croupier (pass-through) → Table/DataSource
                                      ├── BalanceManager
                                      └── PositionTracker
```

**Problemas:**
- Croupier no sabe nada del portfolio
- Balance y posiciones están en la Table
- Para consultar balance hay que ir a la Table
- Croupier es solo un router, no un "control board"

### ✅ Arquitectura Nueva (Propuesta)

```
Gemini → Croupier (Control Board) → ExchangeAdapter
           ├── PortfolioManager
           │     ├── BalanceManager
           │     └── PositionTracker
           └── ExchangeAdapter (delegate)
```

**Beneficios:**
- Croupier es el dueño del portfolio
- Cualquiera puede preguntarle el balance
- Centraliza toda la información de trading
- ExchangeAdapter solo maneja comunicación

---

## 🎨 Diseño de Componentes

### 1. PortfolioManager

**Responsabilidad:** Gestionar balance y posiciones

```python
class PortfolioManager:
    """
    Gestiona el portfolio completo del trader.

    Responsabilidades:
    - Mantener balance actual
    - Trackear posiciones abiertas
    - Calcular equity disponible
    - Validar que hay fondos suficientes
    """

    def __init__(self, initial_balance: float):
        self.balance_manager = BalanceManager(initial_balance)
        self.position_tracker = PositionTracker()

    def get_balance(self) -> float:
        """Balance disponible."""
        return self.balance_manager.balance

    def get_equity(self) -> float:
        """Equity total (balance + posiciones)."""
        return self.balance_manager.get_equity()

    def get_open_positions(self) -> List[Position]:
        """Posiciones abiertas."""
        return self.position_tracker.get_open_positions()

    def can_open_position(self, size: float) -> bool:
        """Valida si hay fondos para abrir posición."""
        return self.balance_manager.balance >= size

    def open_position(self, trade_id: str, symbol: str, side: str,
                     size: float, entry_price: float, tp: float, sl: float):
        """Registra apertura de posición."""
        self.position_tracker.open_position(...)
        self.balance_manager.reserve_funds(size)

    def close_position(self, trade_id: str, exit_price: float,
                      exit_reason: str) -> dict:
        """Cierra posición y actualiza balance."""
        position = self.position_tracker.get_position(trade_id)
        pnl = self._calculate_pnl(position, exit_price)

        self.position_tracker.close_position(trade_id, ...)
        self.balance_manager.release_funds(position.size)
        self.balance_manager.apply_pnl(pnl)

        return {"pnl": pnl, "balance": self.get_balance()}
```

### 2. Croupier Refactorizado

**Responsabilidad:** Tablero de control del trading

```python
class Croupier:
    """
    Tablero de control centralizado del Casino.

    Responsabilidades:
    - Gestionar portfolio (balance + posiciones)
    - Coordinar ejecución con exchange
    - Proveer información consolidada
    - Validar órdenes antes de ejecutar
    """

    def __init__(self, exchange_adapter, initial_balance: float):
        self.logger = logging.getLogger("Croupier")
        self.portfolio = PortfolioManager(initial_balance)
        self.exchange = exchange_adapter

    # === API Pública: Información ===

    def get_balance(self) -> float:
        """Balance disponible."""
        return self.portfolio.get_balance()

    def get_equity(self) -> float:
        """Equity total."""
        return self.portfolio.get_equity()

    def get_open_positions(self) -> List[Position]:
        """Posiciones abiertas."""
        return self.portfolio.get_open_positions()

    def get_portfolio_state(self) -> dict:
        """Estado completo del portfolio."""
        return {
            "balance": self.get_balance(),
            "equity": self.get_equity(),
            "open_positions": len(self.get_open_positions()),
            "positions": self.get_open_positions()
        }

    # === API Pública: Ejecución ===

    def execute_order(self, order: dict) -> dict:
        """
        Ejecuta una orden de trading.

        Flujo:
        1. Validar orden
        2. Verificar fondos disponibles
        3. Delegar ejecución al exchange
        4. Actualizar portfolio con resultado
        5. Retornar resultado normalizado
        """
        # 1. Validar
        self._validate_order(order)

        # 2. Verificar fondos (si no es ghost)
        if not order.get("ghost", False):
            if not self.portfolio.can_open_position(order["size"]):
                return self._insufficient_funds_result(order)

        # 3. Delegar a exchange
        result = self.exchange.execute_order(order)

        # 4. Actualizar portfolio (si no es ghost)
        if not order.get("ghost", False):
            self._update_portfolio(order, result)

        # 5. Retornar con info de portfolio
        result["balance"] = self.get_balance()
        result["equity"] = self.get_equity()

        return result

    # === Métodos Privados ===

    def _validate_order(self, order: dict):
        """Valida que la orden tenga todos los campos requeridos."""
        required = ("symbol", "side", "size", "take_profit", "stop_loss")
        for field in required:
            if field not in order:
                raise ValueError(f"Orden incompleta: falta '{field}'")

    def _update_portfolio(self, order: dict, result: dict):
        """Actualiza portfolio basado en resultado de ejecución."""
        if result.get("status") == "opened":
            self.portfolio.open_position(
                trade_id=order["trade_id"],
                symbol=order["symbol"],
                side=order["side"],
                size=order["size"],
                entry_price=result["entry_price"],
                tp=order["take_profit"],
                sl=order["stop_loss"]
            )
        elif result.get("status") == "closed":
            self.portfolio.close_position(
                trade_id=order["trade_id"],
                exit_price=result["exit_price"],
                exit_reason=result.get("exit_reason", "unknown")
            )
```

### 3. ExchangeAdapter (Simplificado)

**Responsabilidad:** Solo comunicación con exchange

```python
class ExchangeAdapter:
    """
    Adaptador para comunicación con exchange.

    Responsabilidades:
    - Ejecutar órdenes en el exchange
    - Obtener datos de mercado
    - Normalizar respuestas

    NO gestiona balance ni posiciones (eso es del Croupier).
    """

    def __init__(self, connector):
        self.connector = connector

    def execute_order(self, order: dict) -> dict:
        """
        Ejecuta orden en el exchange.

        Retorna resultado normalizado:
        {
            "status": "opened" | "closed",
            "entry_price": float,
            "exit_price": float (si closed),
            "exit_reason": str (si closed),
            "fee": float,
            "pnl": float (si closed)
        }
        """
        # Delegar al connector específico
        return self.connector.execute_order(order)

    def get_candle(self) -> dict:
        """Obtiene siguiente vela del mercado."""
        return self.connector.get_next_candle()
```

---

## 🔄 Flujo de Ejecución

### Flujo Completo

```
1. Gemini decide: "BET LONG 0.02 equity"
   ↓
2. Gemini crea orden: {symbol, side, size, tp, sl, ghost}
   ↓
3. Croupier.execute_order(orden)
   ├── Valida orden
   ├── Verifica fondos (portfolio.can_open_position)
   ├── Delega a exchange.execute_order(orden)
   ├── Actualiza portfolio con resultado
   └── Retorna resultado + balance
   ↓
4. Gemini recibe resultado con balance actualizado
```

### Consulta de Balance

```
Player pregunta: "¿Cuánto equity tengo?"
   ↓
Croupier.get_equity()
   ↓
PortfolioManager.get_equity()
   ├── balance_manager.balance
   └── position_tracker.unrealized_pnl
   ↓
Retorna equity total
```

---

## 📊 Comparación de Responsabilidades

| Componente | Antes | Después |
|------------|-------|---------|
| **Croupier** | Router simple | Control board completo |
| **BalanceManager** | En Table | En Croupier.portfolio |
| **PositionTracker** | En Table | En Croupier.portfolio |
| **ExchangeAdapter** | Todo mezclado | Solo comunicación |
| **Consultar balance** | `table.balance_manager.get_balance()` | `croupier.get_balance()` |

---

## ✅ Ventajas de la Nueva Arquitectura

1. **Centralización**
   - Todo pasa por el Croupier
   - Un solo punto para consultar estado

2. **Separación de Responsabilidades**
   - Croupier: Portfolio + Coordinación
   - ExchangeAdapter: Solo comunicación
   - PortfolioManager: Solo balance + posiciones

3. **Mejor Testabilidad**
   - Mock del ExchangeAdapter es trivial
   - PortfolioManager se puede testear aislado
   - Croupier se puede testear sin exchange real

4. **Escalabilidad**
   - Fácil agregar multi-asset (portfolio gestiona múltiples)
   - Fácil agregar risk management (en Croupier)
   - Fácil agregar reporting (Croupier tiene toda la info)

---

## 🚀 Plan de Implementación

### Fase 1: Crear PortfolioManager
- [ ] Crear `core/portfolio/portfolio_manager.py`
- [ ] Componer BalanceManager + PositionTracker
- [ ] Tests unitarios

### Fase 2: Refactorizar Croupier
- [ ] Agregar PortfolioManager al Croupier
- [ ] Implementar métodos de consulta (get_balance, get_equity)
- [ ] Actualizar execute_order para usar portfolio
- [ ] Tests unitarios

### Fase 3: Simplificar ExchangeAdapter
- [ ] Remover BalanceManager del adapter
- [ ] Remover PositionTracker del adapter
- [ ] Solo mantener lógica de comunicación
- [ ] Tests de integración

### Fase 4: Actualizar TradingSession
- [ ] Usar Croupier como fuente de verdad
- [ ] Remover accesos directos a table
- [ ] Tests end-to-end

---

## 🎯 Criterios de Éxito

- ✅ Croupier gestiona portfolio completo
- ✅ Balance se consulta via `croupier.get_balance()`
- ✅ ExchangeAdapter solo maneja comunicación
- ✅ Tests unitarios pasan
- ✅ Backward compatibility mantenida
- ✅ Código más limpio y mantenible
