# 📊 COMPARACIÓN: Testing vs Backtest

**Fecha:** 2025-11-05 10:04:33

---

## 💰 BALANCE

| Métrica | Testing | Backtest | Diferencia |
|---------|---------|----------|------------|
| Balance Inicial | $4,732.24 | $10,000.00 | $+5,267.76 (+111.32%) |
| Balance Final | $2,922.91 | $10,003.02 | $+7,080.11 (+242.23%) ❌ |
| Net PnL | $-1,809.33 | $+3.32 | $+1,812.65 |

## 📈 ACTIVIDAD DE TRADING

| Métrica | Testing | Backtest | Diferencia |
|---------|---------|----------|------------|
| Velas Procesadas | 10 | 60 | +50 ⚠️ |
| Señales Detectadas | 3 | 4 | +1 ❌ |
| Órdenes Ejecutadas | 3 | 2 | -1 ✅ |
| Trades Cerrados | 0 | 2 | +2 ⚠️ |

## 🎲 PROGRESIÓN PAROLI

| Vela | Testing Step | Backtest Step | Status |
|------|--------------|---------------|--------|
| 0 | 0 | 0 | ✅ |
| 10 | 0 | 0 | ✅ |
| 20 | 0 | 0 | ✅ |
| 30 | 0 | 0 | ✅ |
| 40 | 0 | 0 | ✅ |
| 50 | 0 | 0 | ✅ |

## 📋 RESUMEN

### 🚨 Problemas Identificados:

- ❌ **Señales diferentes:** Testing=3, Backtest=4
- ❌ **Balance final difiere >10%:** +242.23%

## 💡 RECOMENDACIONES

⚠️ **Requiere investigación:**

1. Verificar que sensores usan mismos datos en ambos modos
3. Verificar cálculo de TP/SL y fees

---

*Generado automáticamente por compare_results.py*
