"""Test rápido del cálculo de cantidad"""

# Simular el cálculo
notional_size = 25.0  # USD
price = 97.94  # USD/LTC
precision = 0.01  # step size

quantity = notional_size / price
print(f"Cantidad inicial: {quantity}")

# Método ANTERIOR (incorrecto)
quantity_old = round(quantity, int(precision))  # round(0.255, 0) = 0.0
print(f"Método anterior (incorrecto): {quantity_old}")

# Método NUEVO (correcto)
if precision < 1:
    quantity_new = round(quantity / precision) * precision
    print(f"Método nuevo (correcto): {quantity_new}")
    print(f"  - quantity / precision = {quantity / precision}")
    print(f"  - round(...) = {round(quantity / precision)}")
    print(f"  - ... * precision = {round(quantity / precision) * precision}")
