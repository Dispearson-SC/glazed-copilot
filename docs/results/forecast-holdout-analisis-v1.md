# Pronóstico de ventas diarias: evaluación fuera de muestra (holdout) v1

**Proyecto:** Glazed Co. / SOFTEK Tienda Inteligente  
**Alcance:** pronóstico de unidades por tienda × SKU × día, entrenado solo con el primer 80 % del periodo y evaluado contra el último 20 %.  
**Código y salidas:** `data/forecast/` (CLI: `python3 -m forecast run`), tablas en `data/forecast/out/`.

## 1. Resumen ejecutivo

- **Corte verificado:** el periodo compartido de ventas e inventario es 2025-10-01 a 2026-09-30 (365 días). El 80 % son 292 días, por lo que el modelo se entrena hasta el **2026-07-19** (coincide con lo esperado). El holdout son 73 días (2026-07-20 a 2026-09-30). Ningún dato posterior al corte se usa para ajustar ni para construir variables (se verifica con una prueba de fuga, sección 8).
- **El modelo propio supera a las dos referencias** en todas las métricas principales, sobre 129 541 observaciones tienda-SKU-día sin censura (1.05 M de unidades, 2 021 series):

| Modelo | WAPE (p50) | Sesgo | MASE | Pinball q=0.74 | Cobertura p10–p90 |
|---|---:|---:|---:|---:|---:|
| **GLM Poisson (modelo propio)** | **29.8 %** | -2.5 % | **0.86** | **1.080** | 88.0 % |
| Promedio móvil 28 d por día de semana | 35.7 % | +6.6 % | 0.98 | 1.359 | 89.5 % |
| Estacional ingenuo (misma semana pasada) | 46.8 % | +15.3 % | 1.21 | 1.706 | 81.2 % |

Frente al promedio móvil, el pinball a q=0.74 baja 20.5 % y el WAPE 16.6 %; el modelo gana en las 36 tiendas evaluadas.

- **Efecto en reabasto (estimación, no medición):** con el mismo nivel de servicio (97 % de unidades surtidas), el modelo requiere unas **259 mil unidades de excedente perecedero** frente a 299 mil del promedio móvil (-13 %) y 388 mil del estacional ingenuo (-33 %).
- **Advertencia de representatividad:** la ventana de holdout (20-jul a 30-sep) es la cola del **pico de verano**; julio es el mes de mayor venta del año (2.98 M). **No es representativa del invierno** ni de temporadas con otra dinámica. Con solo 12 meses de historia el modelo no puede aprender estacionalidad anual; los resultados de este documento no deben extrapolarse a diciembre-febrero sin una nueva validación.

## 2. Datos y supuestos

| Tema | Tratamiento |
|---|---|
| Granularidad | tienda × SKU × día; 2 100 series con historia en el holdout, 2 021 pronosticables |
| Demanda | unidades vendidas sin devoluciones; días abiertos sin fila de venta se rellenan con 0 desde la primera observación de la serie |
| Tiendas cerradas | solo existen días con estado `open` en `store_calendar`. S010 (cierre 2026-07-13) no tiene filas; S017 se pronostica hasta 2026-08-20 (cierra el 21-ago) |
| Demanda censurada | día con `stockout_hours > 0` en `inventory_daily` (18.1 % de los días-serie con inventario en el holdout). Se excluyen del ajuste; en la evaluación se puntúan aparte y de forma unilateral |
| Variables conocidas de antemano | día de la semana, feriados, vacaciones escolares, promociones planeadas (profundidad de descuento y combos), formato del sitio, departamento |
| No usado | clima (no hay pronóstico disponible, se evita usar el observado) |
| Series no pronosticables | 5 515 filas / 70 977 unidades (5.8 % del holdout): sobre todo S015, abierta el 2026-07-18, sin historia (51 mil unidades) |

Supuesto relevante: el calendario de aperturas y cierres (incluido el cierre definitivo de S017) y las promociones planeadas se consideran conocidos al momento del corte.

## 3. Modelos

1. **Estacional ingenuo:** valor de la misma semana-día más reciente sin censura (últimos 28 días).
2. **Promedio móvil 28 d por día de semana:** media de los últimos cuatro mismos días de la semana sin censura.
3. **GLM Poisson propio:** `log μ = nivel de la serie + efectos compartidos`. Los efectos compartidos son día de la semana × tipo de sitio, día de la semana × departamento, feriado, vacaciones escolares × tipo de sitio y promoción planeada. El nivel de cada serie se estima con una vida media de 7 días (sigue el nivel reciente) y los coeficientes con toda la ventana de entrenamiento. La vida media se eligió con un backtest dentro del entrenamiento (origen = corte menos 73 días), nunca con el holdout; ganó el valor más corto de la rejilla, por lo que es un límite conocido (sección 7).
4. **Cuantiles:** cada modelo recibe cuantiles aditivos por nivel de pronóstico, calibrados con ese mismo backtest. Se entregan p10, p20, p50, p60, p74, p80, p85 y p90; `forecast` es el p50. Además se publican la media `mu` y la dispersión binomial negativa `alpha` por fila, y la rejilla `calibration_grid.csv` permite calcular **cualquier cuantil** con `forecast.calibration.quantile(mu, grid, q)`. La calibración se centra (se elimina la deriva media del backtest) porque esa deriva es propia de la ventana; la variante sin centrar se reporta como sensibilidad en la sección 7.

## 4. Resultados

Todas las cifras de precisión usan días sin censura. Pinball a q=0.74 es la métrica primaria (razón crítica de reorden); menor es mejor.

### 4.1 Por formato de tienda

| Formato | Modelo propio WAPE | Prom. móvil | Ingenuo | Sesgo propio | Pinball 0.74 propio / prom. móvil | Cob. p10–p90 |
|---|---:|---:|---:|---:|---:|---:|
| Full Counter | 26.2 % | 32.2 % | 44.4 % | -1.2 % | 1.506 / 1.908 | 87.6 % |
| Express Kiosk | 33.2 % | 39.1 % | 48.5 % | -5.1 % | 0.875 / 1.111 | 88.4 % |
| Shop-in-Shop | 34.0 % | 39.7 % | 50.3 % | -2.4 % | 0.882 / 1.084 | 87.9 % |

### 4.2 Por clase de vida útil

| Clase | Filas | Unidades | WAPE propio | Prom. móvil | Ingenuo | Sesgo propio | Pinball 0.74 propio | Cob. p10–p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 día | 11 061 | 51 192 | 35.1 % | 38.2 % | 43.9 % | -9.1 % | 0.686 | 90.2 % |
| 2–3 días | 53 494 | 458 393 | 26.9 % | 30.5 % | 35.5 % | -5.0 % | 1.006 | 89.4 % |
| 4–5 días | 2 973 | 6 913 | 49.8 % | 52.7 % | 61.3 % | -15.1 % | 0.504 | 89.9 % |
| No perecedero | 62 013 | 538 433 | 31.5 % | 39.7 % | 56.6 % | +0.4 % | 1.241 | 86.3 % |

Los perecederos de 1 día tienen sesgo negativo (el modelo se queda corto 9 %) y es donde más pesa la censura (24 % de sus días-serie con inventario tienen quiebre).

### 4.3 Por categoría (WAPE; modelo propio / prom. móvil / ingenuo)

| Categoría | Unidades | Propio | Prom. móvil | Ingenuo |
|---|---:|---:|---:|---:|
| Coffee & Tea | 417 249 | 29.2 % | 38.9 % | 58.2 % |
| Bakery | 264 045 | 27.0 % | 29.8 % | 35.4 % |
| Sandwiches | 206 098 | 28.0 % | 32.2 % | 36.1 % |
| Specialty Beverage | 78 284 | 40.9 % | 43.4 % | 51.5 % |
| Grab & Go | 39 442 | 31.6 % | 36.2 % | 43.6 % |
| Packaged Beverage | 39 685 | 33.0 % | 37.4 % | 45.7 % |
| Produce | 4 398 | 43.1 % | 46.4 % | 52.7 % |
| Souvenir & Merch | 3 115 | 84.1 % | 87.4 % | 104.3 % |
| Sweet Snacks | 2 515 | 61.6 % | 63.8 % | 76.4 % |
| Catering | 100 | 116.9 % | 107.4 % | 157.4 % |

### 4.4 Por semana de horizonte (desde el corte)

| Semana | Propio | Prom. móvil | Ingenuo | Sesgo propio | Cob. p10–p90 |
|---:|---:|---:|---:|---:|---:|
| 1 | 25.7 % | 27.6 % | 34.3 % | -11.0 % | 90.1 % |
| 2 | 25.1 % | 27.7 % | 36.7 % | -7.3 % | 90.3 % |
| 3 | 25.3 % | 28.7 % | 38.8 % | -2.0 % | 91.1 % |
| 4 | 27.6 % | 30.9 % | 41.5 % | +1.5 % | 90.0 % |
| 5 | 29.7 % | 34.0 % | 45.8 % | +4.3 % | 89.4 % |
| 6 | 27.2 % | 31.0 % | 41.5 % | +1.5 % | 90.1 % |
| 7 | 30.1 % | 40.6 % | 53.0 % | -3.7 % | 87.6 % |
| 8 | 32.9 % | 42.3 % | 55.5 % | -5.8 % | 85.6 % |
| 9 | 36.3 % | 49.0 % | 62.6 % | -3.1 % | 84.4 % |
| 10 | 38.2 % | 51.8 % | 65.8 % | -1.1 % | 83.9 % |
| 11 (parcial, 3 días) | 40.3 % | 41.9 % | 55.7 % | +5.2 % | 81.5 % |

El error crece con el horizonte, pero mucho más despacio que en las referencias: en las semanas 7–10 las referencias pierden entre 10 y 28 puntos de WAPE frente al modelo.

### 4.5 Día de la semana y promociones

- El WAPE por día de la semana está en 28.8–31.4 % (sábado el más alto, 31.4 %; es también el día de menor volumen).
- Días con promoción activa (PR010 y PR011, 8 265 filas, 6 % de las observaciones): WAPE 30.9 % y sesgo +3.5 %, frente a 29.7 % y -3.0 % sin promoción. El modelo aprende el efecto de promociones pasadas y lo aplica a las futuras según su profundidad; la ventaja sobre el promedio móvil se reduce en esas filas (34.5 %), así que la confianza en días con promoción nueva debe ser menor.

### 4.6 Por tienda

El WAPE del modelo propio va de 22.6 % (S029) a 48.0 % (S030); la mediana es 32.0 %. Las tiendas grandes se pronostican mejor: S029 22.6 %, S009 23.1 %, S014 25.0 %, S012 29.0 %. Las más débiles son tiendas pequeñas (S030, S027, S033, S021, S019, S036), con 9–16 mil unidades en el holdout. El detalle está en `metrics_by_store.csv`.

### 4.7 Calibración de los cuantiles

Probabilidad observada de que la demanda quede en o por debajo del cuantil (días sin censura; incluye empates en cero):

| Cuantil | p10 | p20 | p50 | p60 | p74 | p80 | p85 | p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Observado | 17.0 % | 22.9 % | 51.2 % | 62.5 % | 78.0 % | 84.7 % | 89.3 % | 93.9 % |

Los cuantiles altos están bien calibrados y ligeramente conservadores (p74 cubre 78 %; la banda p10–p90 cubre 88 % frente al 80 % nominal). Los cuantiles bajos quedan altos porque hay muchos días con venta cero y la banda no puede bajar de cero. Para reorden esto es el lado seguro; para detectar anomalías a la baja, p10 y p20 no son sensibles.

### 4.8 Días con quiebre (censurados)

En días con quiebre la venta observada solo es un piso de la demanda. Se puntúa de forma unilateral: el pronóstico cubre si p74 ≥ venta; estar por encima no cuenta como error.

| Modelo | Días censurados | Cobertura unilateral p74 | Pinball unilateral p74 |
|---|---:|---:|---:|
| GLM Poisson | 15 614 | 88.7 % | 0.187 |
| Prom. móvil 28 d | 15 614 | 91.5 % | 0.148 |
| Estacional ingenuo | 15 614 | 91.2 % | 0.190 |

En SKUs de 1 día de vida el p74 del modelo solo cubre 71.2 % de las ventas en días de quiebre, y en Bakery 76.7 %, Packaged Beverage 76.4 %: ahí el modelo subestima justo cuando el stock ya se acabó. Es la zona donde hay que mirar primero para la regla de reorden. El promedio móvil, que suele estar por encima de lo vendido, puntúa mejor aquí; en los días sin quiebre ocurre lo contrario.

## 5. Estimación de impacto en reorden (supuestos explícitos)

Simulación diaria de reposición hasta un nivel objetivo S, por serie, solo en días sin censura (donde la venta equivale a la demanda).

- Cada día se repone hasta S; no se acredita inventario sobrante.
- Venta perdida = max(0, demanda − S). Sobrante = max(0, S − demanda).
- Merma estimada = sobrante de SKUs perecederos (vida útil de 1 a 5 días); el sobrante de no perecederos se acumula como sobreinventario pero no se cuenta como merma.
- Valor de venta perdida con el precio mediano del entrenamiento; costo de merma con el costo unitario del maestro (40 % del precio cuando falta).

**Resultados del holdout (1.05 M de unidades de demanda observable):**

| Política | Venta perdida (uds) | Nivel de servicio | Merma (uds) | Valor venta perdida | Costo merma |
|---|---:|---:|---:|---:|---:|
| Prom. móvil 28 d, sin colchón (práctica simple) | 107 062 | 89.9 % | 112 538 | $513 k | $136 k |
| GLM, objetivo p60 | 117 784 | 88.8 % | 90 415 | $563 k | $112 k |
| **GLM, objetivo p74** | **60 298** | **94.3 %** | 164 345 | **$284 k** | $201 k |
| GLM, objetivo p85 | 28 127 | 97.3 % | 275 746 | $126 k | $334 k |
| Prom. móvil, objetivo p74 | 49 239 | 95.3 % | 215 649 | $230 k | $260 k |
| Ingenuo, objetivo p74 | 68 147 | 93.5 % | 233 639 | $320 k | $282 k |

**Comparación con el mismo nivel de servicio (97 %)**, barriendo el cuantil de cada modelo:

| Modelo | Merma estimada (uds) | Costo de merma |
|---|---:|---:|
| GLM Poisson | 259 363 | $314 k |
| Prom. móvil 28 d | 299 409 | $360 k |
| Estacional ingenuo | 387 994 | $468 k |

Lectura: pasar de la práctica simple (promedio móvil sin colchón) a GLM p74 reduce la venta perdida estimada 44 % (de $513 k a $284 k de ingreso) a cambio de 52 mil unidades más de merma ($65 k de costo). A servicio igual, el modelo reduce la merma 13 % frente al promedio móvil. Son órdenes de magnitud de una simulación simplificada (sin lead time, pedido mínimo, caja ni transferencias), no un ahorro garantizado. El valor de venta perdida es ingreso, no margen.

El nivel de servicio observado del negocio en el holdout ya tiene quiebres: 18.1 % de los días-serie con inventario reportan horas de quiebre.

## 6. Dónde el modelo es bueno y dónde no

**Bueno (confianza alta a media):**
- Tiendas de alto volumen y formato Full Counter (WAPE 22–29 %).
- Coffee & Tea, Bakery y Sandwiches, que concentran 84 % del volumen (WAPE 27–29 %).
- Perecederos de 2–3 días (WAPE 26.9 %), la clase más grande en unidades perecederas.
- Horizonte de 1 a 6 semanas (WAPE 25–30 %); la banda p10–p90 cubre cerca de 90 %.
- Cuantiles altos (p74 a p90) para decisiones de reorden.

**Débil (confianza baja):**
- Merch, Souvenir, Catering, Sweet Snacks y Produce: volúmenes bajos y patrón intermitente (WAPE 43–117 %). Conviene tratarlos con reglas de mínimos/máximos, no con el pronóstico.
- Tiendas nuevas o sin historia (S015: 51 mil unidades del holdout sin pronóstico) y tiendas pequeñas (WAPE 40–48 %).
- Perecederos de 1 día con quiebre: subestima demanda cuando se agota el producto.
- Semanas 7–11 del horizonte (WAPE 30–40 %) y días con promoción que el modelo no ha visto.
- Los SKUs sin cobertura de inventario (sección 7).

## 7. Riesgos y limitaciones

1. **Representatividad estacional.** El holdout es el final del pico de verano. La estacionalidad anual no es estimable con 12 meses. En 2026 el modelo ya mostró sesgo de -11 % en la semana 1 y +4 % en la 5, de modo que los cambios de régimen (fin de vacaciones escolares el 31-ago) se absorben solo parcialmente.
2. **Cobertura de inventario.** `inventory_daily` cubre 89 de los 127 SKUs que se venden. Los otros 38 no tienen señal de quiebre: no se puede marcar censura, su demanda observada puede estar subestimada y sus métricas no son comparables (el 42.7 % de las unidades del holdout corresponde a SKUs sin inventario). El WAPE es 30.8 % en filas sin cobertura frente a 28.9 % con cobertura.
3. **Cierres y aperturas.** S010 (cerrada 2026-07-13) no se pronostica; S017 se pronostica hasta el 20-ago; S015 abrió el 18-jul y no tiene historia. Se asume que las fechas de cierre son conocidas de antemano.
4. **Promociones.** Las promociones del holdout (PR010 y PR011) no existen en el entrenamiento; su efecto se extrapola a partir de la profundidad del descuento. PR009 termina el último día de entrenamiento y su efecto aún se arrastra en el nivel reciente.
5. **Vida media en el límite de la rejilla.** El valor más corto probado (7 días) ganó el backtest; puede haber margen con ventanas aún más cortas, a costa de mayor ruido. No se ajustó con el holdout.
6. **Sensibilidad al centrado de cuantiles.** Sin centrar la calibración, el p50 hereda la deriva alcista del backtest (febrero-julio): WAPE 35.0 % y sesgo +17.4 % en el holdout, con cobertura p10–p90 de 80.3 % y pinball 0.74 de 1.300 (todavía mejor que las referencias, 1.76 y 1.92 en esa misma corrida). Se eligió el centrado a priori por principio (la ubicación la da el modelo, la dispersión el backtest), pero la decisión se tomó después de ver ese efecto; conviene reconfirmarla con la siguiente ventana. Ejecutar con `--no-center` reproduce la variante.
7. **Ventaja en variables conocidas.** Las referencias no usan calendario, vacaciones ni promociones; parte de la ganancia del modelo viene de esas variables, no solo del método.
8. **Datos.** Las limitaciones de `data_quality.md` aplican (por ejemplo, 586 filas con bruto distinto de unidades × precio y 144 productos sin costo).

## 8. Verificación de no fuga

- Prueba automática: el pronóstico completo no cambia cuando se corrompen todas las ventas, banderas de censura y marcas de inventario posteriores al corte.
- El ajuste rechaza datos con fecha mayor al corte; el backtest de calibración usa solo el entrenamiento.
- En la corrida real, `run_meta.json` registra `forecast_invariant_to_post_cutoff_actuals = true` y fecha máxima de entrenamiento 2026-07-19.

## 9. Cómo usarlo en el copiloto y la interfaz

**Reorden.** Usar el p74 como objetivo de pedido por defecto (razón crítica ≈ 0.74), con sensibilidad en p60 y p85 (columnas ya incluidas) o cualquier otro cuantil con la rejilla. Para SKUs de 1 día con quiebre reciente, subir un nivel (p80–p85) o marcar el cálculo como de baja confianza.

**Confianza ganada, no declarada.** Mostrar junto a cada recomendación la métrica histórica de su segmento (WAPE y cobertura de banda de ese formato × clase × horizonte) y un nivel:

| Nivel | Criterio sugerido (según este holdout) |
|---|---|
| Alta | Categorías Coffee & Tea / Bakery / Sandwiches, perecederos 2–3 d o no perecederos, tiendas de alto volumen, horizonte ≤ 6 semanas, SKU con cobertura de inventario |
| Media | Horizonte 7–10 semanas, formatos Express Kiosk y Shop-in-Shop, días con promoción |
| Baja | Perecederos de 1 día con quiebre reciente, SKUs sin inventario, tiendas nuevas o pequeñas, Merch / Catering / Sweet Snacks, promociones inéditas |

**Vista pronóstico contra real.** Graficar la banda p10–p90 con la venta observada, marcar los días censurados con un símbolo distinto (la venta es un piso, no la demanda) y no contarlos como errores cuando el pronóstico queda por encima. Mostrar el sesgo reciente por tienda para detectar deriva.

**Ciclo de vida.** Reentrenar al menos semanalmente con nivel de serie de vida media corta; guardar la métrica de cada ventana para ver si la confianza se sostiene; excluir tiendas en cierre y marcar tiendas con menos de 28 días de historia como sin pronóstico propio.

**Pendientes sugeridos.** (1) Ampliar `inventory_daily` a los 38 SKUs sin cobertura para detectar quiebres; (2) validar de nuevo con un periodo de invierno cuando haya datos; (3) añadir una regla de mínimos/máximos para ítems intermitentes; (4) incorporar clima observado solo cuando exista un pronóstico confiable.

## 10. Reproducción

```
cd data/forecast
pip3 install --target .deps -r ../requirements-dev.txt
PYTHONPATH=.deps:. python3 -m pytest -q
PYTHONPATH=.deps:. python3 -m forecast run --clean ../clean --out out
```

Salidas: `out/forecast_holdout.parquet` (columnas `model, store_id, sku, date, forecast, mu, p10, p20, p50, p60, p74, p80, p85, p90, alpha, actual, censored, inv_covered`), `metrics_*.csv`, `business_*.csv`, `calibration_grid.csv`, `nb_alpha_table.csv`, `run_meta.json`. El parquet no se versiona (se regenera en unos 3.5 minutos).
