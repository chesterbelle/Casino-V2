# 📜 Protocolo de Desarrollo — Casino V2  

1. **Validación previa**  
   - Todo módulo nuevo debe incluir docstrings, tipado y logs.  
   - Cada cambio se prueba con datasets bear y bull.

2. **Estándar de intercambio**  
   - Cada feed devuelve velas en formato:  
     `{"timestamp","open","high","low","close","volume"}`  
   - Cada ejecución devuelve:  
     `{"order_id","side","entry","exit","fee","pnl","result"}`  

3. **Reglas de commits**  
   - Commit = una función o feature completa.  
   - Prefijo: `feat:`, `fix:`, `test:`, `refactor:`.  

4. **Pruebas**  
   - `pytest` en modo backtest mínimo 1000 velas.  
   - Revisión manual de equity y winrate.

5. **Versionado**  
   - Tag v5.x → Gemini Era  
   - v4.x → Legacy Range Detector

