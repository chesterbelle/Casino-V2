# Changelog

## 2025-10-12 — Integración modalidad Oscar Grind

- Se añadió un paquete `oscar/` con los componentes exclusivos del modo Oscar:
  - `range_sensor.py`: sensor de rango autónomo reutilizando la lógica del bot Range Grinder.
  - `oscar_grind_machine.py`: state machine del método Oscar Grind para gestionar sesiones y sizing.
  - `oscar_trader.py`: orquestador que combina sensor + state machine y delega órdenes al croupier.
  - `session.py`: loop de backtest que reproduce el flujo del casino usando Oscar en lugar de Gemini.
- Se amplió `main.py` para habilitar el modo Oscar cuando `ENABLE_OSCAR_MODE=True`, manteniendo el flujo Gemini original como opción por defecto.
- `config.py` incorporó la bandera `ENABLE_OSCAR_MODE` y parámetros `OSCAR_*` para ajustar unidades y límites del método.
- Documentación interna actualizada explicando cómo activar el modo Oscar y mantener la modularidad con el pipeline existente.
- TableBacktest ahora lee el perfil de exchange para diferenciar fees de entrada/salida, aplicar slippage dinámico según tamaño y volatilidad, cobrar funding proporcional al tiempo en posición y simular liquidaciones por margen; los reportes muestran comisiones, funding y liquidaciones acumuladas.
