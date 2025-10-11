## Mitigación ante Buckets Desconocidos (`UNKNOWN`)

### Contexto
Durante el backtest reciente se observó que, cuando los `features` consolidados no contienen los campos esperados por `BucketManager` (por ejemplo `bbw`, `range_score`, hora válida), el clasificador cae en el bucket `UNKNOWN`. En ese escenario Gemini sigue procesando la señal y podría generar apuestas con estimaciones mal condicionadas, degradando la credibilidad estadística del sistema.

### Cambio propuesto
Implementar un guard-rail en `Gemini.evaluate_signals` para abortar cualquier apuesta (retornar `GHOST`) cuando alguno de los participantes derive de un bucket `UNKNOWN`. La regla debe ser explícita:

1. Al extraer `Participant`s, si `participant.bucket == "UNKNOWN"`, descartar inmediatamente la señal.
2. Opcional: loggear un warning con `symbol`, `timeframe` y `contributors` para facilitar el diagnóstico.

Esto asegura que solo se ejecuten trades cuando el contexto fue correctamente clasificado, manteniendo la coherencia con la política de “apagar totalmente” ante falta de edge o soporte insuficiente.
