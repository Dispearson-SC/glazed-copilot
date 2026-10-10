# Glazed Co. – Análisis de estado (baseline)

Periodo 2025-10-01 a 2026-09-30. Scripts SQL/Python en `scratchpad/analysis/`; dataset no modificado.
Convención: **[S]** = cifra que depende de un supuesto (ver sección "Supuestos").

## 0. Cifras ancla (datos limpios)
| Métrica | Valor |
|---|---|
| Ventas netas | **$26.27 M** (raw sin limpiar: $26.43 M, +0.6 %) |
| Unidades / transacciones / footfall | 5.43 M / 3.25 M / 30.8 M (KPIs) |
| Descuento total | $534.9 k (2.0 % del bruto): promos $465 k + lealtad sin promo $69.9 k (13 %) |
| Ticket medio / UPT / conversión | $8.09 / 1.67 / ~10 % (transacciones/footfall) |
| Tiendas con ventas | 38 (en `stores.csv` hay 40 filas) |
| SKUs que realmente venden | 127 (el maestro tiene 991 únicos) |
Validación cruzada: tras deduplicar y limpiar, sum(sales_daily) coincide con `store_daily_kpis` en 12,539 de 12,784 tienda-día (98 %) y $26.27 M vs $26.28 M. Los KPIs sirven como "oráculo" de control.

## 1. Auditoría de calidad de datos
| Tabla | Problema | Conteo | Tratamiento sugerido |
|---|---|---|---|
| sales_daily | Fechas en 3 formatos (`YYYY-MM-DD`, `DD-Mon-YY`, `MM/DD/YYYY`) | 301 filas no ISO | Parseo multi-formato (asumir MM/DD) |
| sales_daily | store_id con variantes (`s001`, `S001 `, `S0001`) | 200 filas | `upper(trim)` + normalizar a `S###` |
| sales_daily | sku con variantes (`sku-`, `SKU100003`, espacios) | 504 filas | normalizar a `SKU-######` |
| sales_daily | Duplicados exactos (fecha,tienda,sku) | 3,004 filas sobrantes ($131.6 k); 4 claves con unidades distintas | Conservar 1ª; revisar los 4 conflictos |
| sales_daily | units_sold nulo | 102 | Reconstruir `round(gross/price)` |
| sales_daily | units_sold negativo (net negativo) | 152 (-$7.9 k) | Tratar como devoluciones; excluir de demanda |
| sales_daily | Outliers de unidades (x10; p.ej. 870 uds con gross de 87) | 30 (>200 uds) | Reconstruir con gross/price |
| sales_daily | gross ≠ units×price | 671 | Confiar en gross/net; recalcular units |
| sales_daily | net ≠ gross − discount; discount > gross | 180 / 181 | Recalcular net = gross − discount (descuento acotado) |
| sales_daily | SKUs huérfanos aleatorios (SKU-7xxxxx) | 400 filas ($19.1 k) | Excluir (no están en KPIs) |
| sales_daily | SKU-100040 sin maestro de productos | 6,557 filas, **$407 k (1.5 %)** | Completar maestro (probable alta omitida) |
| sales_daily | promo_id `PR999` inexistente | 60 filas | Tratar como sin promo |
| sales_daily | Ventas antes de apertura / en ventanas de cierre | 119 + 197 = 316 filas ($9.9 k); sin fila KPI | Excluir |
| stores | Duplicado S039 = S004; S040 con site `ST99` huérfano | 2 filas | Eliminar; mapear S039→S004 |
| stores | opening_time nulo/`#N/A` | 5 tiendas (S011,S012,S013,S033,S034) | Inferir con closing_time − open_hours |
| stores | Nombres con espacios/mayúsculas inconsistentes | 9 | `trim` + normalizar |
| stores | Apertura posterior a primeras ventas (S005, S015, S023, S024, S025) | 5 tiendas | Respetar `opened_date` |
| products | SKUs duplicados con atributos distintos (costo/categoría/nombre) | 37 filas extra (991 únicos) | Regla de supervivencia (costo no nulo, categoría canónica) |
| products | SKU en minúsculas/espacios | varios | Normalizar |
| products | category con casing y valores cruzados (Beverage/Bakery, etc.) | ~30 filas | Mapa canónico por departamento |
| products | unit_cost nulo / 0 | 40 nulos / 151 ceros (descontinuados + 7 vendidos) | Imputar desde costo mediano de PO o ratio por depto **[S]** |
| products | descontinuado antes de lanzamiento | varias | Validar fechas |
| barcodes | Código compartido por 2 SKUs; SKUs sin maestro | 30 filas / 52 filas | Resolver unicidad |
| prices | Moneda `USD`,`Usd`,`usd`,`US$`,`USD ` | 98 filas no estándar | Normalizar a USD |
| prices | Fechas mixtas; effective_to < effective_from | 84 / 61 | Parsear; invalidar |
| prices | price_id duplicado | 40 | Deduplicar |
| prices | Tienda huérfana (S099, S120…) | 39 | Excluir |
| prices | Precio ≤0/nulo; >$15 (p.ej. 20, 0) | 73 / 141 | Invalidar |
| prices | Vigencias solapadas / dos vigentes abiertas | 68 pares / 57 pares | Quedarse con la de `effective_from` más reciente |
| prices | Cobertura | 254 SKUs, 41 "tiendas"; 23,306 ventas sin precio de lista; 10,372 con precio ≠ lista | Usar precio observado en ventas |
| inventory_daily | Duplicados exactos | 500 | Deduplicar |
| inventory_daily | sku en minúsculas | 300 | Normalizar |
| inventory_daily | Identidad closing = opening+recv−sold−exp−dmg rota | 2,195 (0.44 %): 393 closing<0, 40 fraccionarios, 1,762 otros (±1..10) | Marcar; recalcular closing |
| inventory_daily | opening ≠ closing día previo | 2,594 pares | Marcar discontinuidades |
| inventory_daily | stockout_hours > 24 | 60 (hasta 60 h) | Cap a open_hours |
| inventory_daily | Filas en días de tienda cerrada/no abierta | 4,546 (1,797 con recepción: 20.5 k uds) | Excluir |
| inventory_daily | Mermas (expired) en SKUs no perecederos | 374 | Revisar maestro |
| inventory_daily | Arranque en frío 2025-10-01 (opening=0) | primeros días | Excluir semana 1 de stockout |
| purchase_orders | po_id duplicado con cantidades distintas | 100 | Conservar 1ª; revisar |
| purchase_orders | expected_date nula | 100 | Imputar order+lead time estándar |
| purchase_orders | received_date < order_date | 60 | Invalidar fecha |
| purchase_orders | qty_received > qty_ordered | 74 | Cap |
| purchase_orders | qty_ordered ≤0 / unit_cost 0 | 27 / 6,566 | Imputar costo |
| purchase_orders | Entregadas sin received_date | 78 | Marcar |
| purchase_orders | Entregada con recibido < pedido (status debía ser Short-shipped) | 65 | Reclasificar |
| purchase_orders | supplier_id `SUP99` huérfano / ≠ maestro | 50 | Corregir por maestro |
| purchase_orders | Sin estado `Cancelled` (aparece solo en README); 1,179 In transit | – | Informativo |
| store_daily_kpis | Duplicados (tienda,fecha) | 25 | Deduplicar |
| store_daily_kpis | footfall nulo / 0 con transacciones | 50 / 30 | Imputar vía modelo; excluir de conversión |
| store_daily_kpis | transactions > footfall | 70 | Excluir de conversión |
| store_daily_kpis | staff_hours ≤0 / =999 | 28 / 12 | Excluir (centinela) |
| store_daily_kpis | units < transactions; ticket fuera de $2–$40 | 40 / 40 | Excluir |
| store_daily_kpis | Días faltantes dentro de ventana abierta | 46 | Imputar o ignorar |
| promotions | PR003 end < start (2025-11-19 < 11-24); ventas hasta 12-24 | 1 | Corregir a 2025-12-24 **[S]** |
| promotions | PR013 "Mystery Promo" sin ninguna venta etiquetada | 1 | Sin ejecución: sirve de placebo |
| calendar | `quarter_idx` incoherente (valor 3 abarca todo el año) | 365 | Recalcular |
| KPI vs ventas | Días con ventas ≠ KPI (>$0.5) tras limpieza | 245 (1.9 %) | Reconciliar |

## 2. Panorama de negocio
**Por región**
| Región | Net $ | Tiendas | $/tienda |
|---|---|---|---|
| Northeast | 14.13 M (54 %) | 15 | 942 k |
| Southwest | 3.22 M | 4 | 805 k |
| Midwest | 2.54 M | 5 | 508 k |
| Mountain | 2.23 M | 4 | 558 k |
| Southeast | 2.08 M | 6 | 347 k |
| Northwest / Pacific / S.Central | 0.82 / 0.70 / 0.54 M | 2/1/1 | – |

**Tipo de sitio / formato**: Airport 19.9 M (31 tiendas, 643 k c/u); Rail 4.48 M (4, 1.12 M c/u); Bus 1.28 M; Resort 0.58 M. Full Counter 13.2 M (13 tiendas, 1.02 M c/u); Express Kiosk 6.75 M (13, 520 k); Shop-in-Shop 6.31 M (12, 526 k). Owned 10.2 M vs Concession 16.0 M.

**Departamento**: Beverage 45.7 %, Bakery 31.2 %, Food 18.2 %, Grab&Go 2.5 %, desconocido 1.5 %, Merch 0.8 %. Categorías: Coffee & Tea $8.98 M, Bakery $8.13 M, Sandwiches $4.78 M, Specialty Bev $1.77 M, Packaged Bev $1.05 M.

**Tiendas** (ventas/día): top S029 ($5,532, Full Counter NE aeropuerto), S014 (4,778), S012 (4,446), S009 (3,848), S028 (3,327). Bottom: S030 ($678), S018 (790), S019 (822), S036 (900), S027 (940).

**Estacionalidad**: mensual (M$) oct 1.71, nov 1.94, dic 2.14, ene 1.79, feb 1.64, mar 2.16, abr 2.09, may 2.37, jun 2.67, **jul 2.98 (pico)**, ago 2.63, sep 2.15. Día de semana (neto/tienda-día): Vie $2,241 > Jue 2,154 > Mar 2,131 > Lun 2,093 > Dom 2,022 > Mié 1,996 > **Sáb 1,755 (-22 % vs Vie)**.

**Efecto calendario** (índice vs promedio de la misma tienda y día de semana): feriado +5.2 % ventas / +8.7 % footfall; vacaciones escolares (sin feriado) +25 % ventas (1.152 vs 0.918) y +17 % footfall. Feriados: Pre-July 4th +54 %, Memorial Weekend +28 %, Pre-Christmas +25 %, Pre-Thanksgiving +24 %, Donut Day +24 %; caídas: New Year's Day -24 %, Christmas Day -22 %, Thanksgiving -19 %, Easter -19 %.

**Ciclo de vida**: nuevas S023 (2025-11-10), S025 (2026-01-04), S024 (2026-03-10), S005 (2026-04-29), S015 (2026-07-18, ya a $3.2 k/día); cierres definitivos S010 (2026-07-13) y S017 (2026-08-21); cierres temporales: S006 19 d, S021 31 d, S031 31 d, S036 20 d, S037 23 d. Ventas perdidas por cierres temporales ≈ 124 tienda-días.

## 3. Promociones
Uplift = DiD: (unidades in-scope / unidades control sin promo) en ventana de promo vs ±28 días (excluye días contaminados por otras promos). Margen con costo **[S]**. Entre paréntesis rango con ventana ±14 d (robustez). PR001 no tiene pre-baseline y PR011 no tiene post-baseline: baja confianza.
| Promo | Tipo / % | Esperado | Uplift real (±28d) | Costo desc. | Efecto margen neto [S] |
|---|---|---|---|---|---|
| PR001 Fall Flavors | %Off 10 Bev | 18 | +15 (n/c) | $97.2 k | -$6 k |
| PR002 Bakery Dozen | Bundle 15 | 30 | **-11** (-8) | $55.4 k | **-$103 k** |
| PR003 Holiday Merch | %Off 20 | 45 | +1.5 (+15) | $4.5 k | -$4 k |
| PR004 NY Breakfast | Bundle 12 Sandwich | 25 | **+25** (+24) | $33.9 k | +$7 k |
| PR005 Valentine | %Off 15 Bakery | 30 | +1 (+11) | $26.6 k | -$30 k |
| PR006 Spring Iced | %Off 10 C&T | 15 | +11 (+14) | $51.0 k | -$9 k |
| PR007 Travel G&G | %Off 10 | 20 | +19 (+19) | $1.8 k | +$0.4 k |
| PR008 Donut Day | %Off 25 | 60 | **+35** (+35) | $8.8 k | -$3.6 k |
| PR009 Summer Iced | %Off 15 C&T | 25 | **+30** (+28) | $100.8 k | **+$26 k** |
| PR010 Back to Routine | %Off 10 Sandwich | 15 | +8 (+8) | $33.4 k | -$12 k |
| PR011 Coffee Day | %Off 20 C&T | 30 | -4 (+24) | $17.4 k | -$20 k |
| PR012 NE Winter | %Off 10 C&T (NE) | 12 | +16 (+6) | $27.3 k | +$4 k |
| PR013 Mystery | sin ejecutar | 20 | +14 (+6.5) sin descuento | $2.3 k lealtad | placebo |
Lecturas: (a) PR013 (nunca aplicada) muestra +6 a +14 % de deriva estacional en Bakery en abril: el ruido/estacionalidad del método es de ±10 pts, así que solo PR004, PR007, PR008, PR009 superan claramente el piso. (b) 8 de 12 promos quedan por debajo del uplift esperado; las de descuento ≥15 % en Bakery (PR002, PR005) destruyen margen. (c) Mejor ROI: Bundle de sandwiches y "Summer Iced Coffee" (verano, +footfall). (d) Sumando, promos con efecto neto negativo = -$188 k [S] sobre $294 k de descuento; positivas = +$37 k. (e) Descuento por lealtad sin promo: 20,634 filas, 5 % y 10 %, $69.9 k = 13 % del descuento total.
Aplicación de promos: 100 % de filas in-scope etiquetadas (todas las tiendas/ SKUs del alcance). PR004/PR010/PR002/PR008: algunas filas fuera de categoría por maestro sucio.

## 4. Inventario
Cobertura: inventory_daily solo 89 SKUs (60 % de unidades vendidas, $16.0 M de ventas).
**Merma** (expired+damaged): 912.8 k uds = **21.9 % de lo recibido**; costo **$1.19 M** (99 % caducidad); a precio de venta ≈ **$4.97 M**. Por categoría: Bakery 31.3 % ($1.015 M), Sandwiches 8.5 % ($128 k), Grab&Go 13.5 % ($33 k). Por vida útil: 1 día 46.5 %, 2 días 24 %, 3 días 9.3 %. Por formato: Shop-in-Shop 30.7 %, Express Kiosk 27.6 %, Full Counter 13.5 %. Recibido/vendido perecederos: 1.31 (bakery 1.46; vida 1 día 1.87). Peores tiendas: S030 (57 %, $68 k), S027 (48.5 %), S019 (44 %), S021 (44 %), S022 (43 %, $59 k). Mejores: S029 5.0 %, S014 6.3 %, S015 8.1 %.
**Quiebres**: 20.3 % de las filas SKU-tienda-día con quiebre (media 13.4 h cuando ocurre); 14.5 % de horas abiertas. Ventas perdidas estimadas **$1.4 M (solo quiebres parciales) a $3.5 M (todos)** [S]; margen $2.6 M en el caso alto. Por categoría: Sandwiches $2.06 M, Bakery $1.06 M. Tiendas: S029 $420 k, S014 $257 k, S017 $181 k, S038 $178 k, S012 $172 k. Paradoja: las tiendas de alto tráfico (Full Counter) quiebran más (S017/S015/S029 ~38 % de filas perecederas) mientras los kioscos/shop-in-shop tiran más.
**Waste + stockout simultáneo**: de 1,212 pares tienda-SKU perecederos, 383 tienen merma ≥10 % y quiebre ≥10 % de los días (204 con ≥20 %/≥15 %): merma $431 k y venta perdida $444 k [S]. Correlación merma-quiebre entre pares = -0.55 (trade-off de política de reposición).
**Días de cobertura** (cierre/ventas diarias): Bakery 0.7 d, Sandwiches 0.8 d, Grab&Go 1.6 d, Coffee&Tea/Packaged ~3.9 d, Merch 12.8 d.
**Proveedores** (6 de 8 con OC; SUP07/SUP08 sin pedidos):
| Proveedor | Líneas | Fill real / contrato | On-time real / contrato | Lead time real / estándar |
|---|---|---|---|---|
| SUP01 Northfield (Bakery) | 158.5 k | 99.5 / 95 | 93.0 / 93 | 1.12 / 1 |
| SUP02 Coastal (Pkg Bev) | 9.3 k | 99.5 / 97 | 95.2 / 95 | 3.08 / 3 |
| SUP03 Summit (Food) | 62.0 k | 98.4 / 92 | 89.9 / 90 | 2.17 / 2 |
| SUP04 Riverbend (G&G) | 25.6 k | 98.9 / 94 | 92.2 / 92 | 1.14 / 1 |
| SUP05 Pioneer (Merch) | 1.6 k | 98.1 / 88 | 86.1 / 85 | 7.24 / 7 |
| SUP06 Evergreen (Coffee) | 4.3 k | 99.3 / 96 | 94.1 / 94 | 4.11 / 4 |
Conclusión: los proveedores cumplen contrato (fill 98-99.5 %, 92 % a tiempo, retraso medio <0.25 d, 1.4 % de líneas con faltante = 37 k uds). **La merma no es problema de proveedor sino de política de pedido** (pedido por múltiplos de case_size de 12 en kioscos de baja demanda; recibido/vendido 1.5x). Sin variación mensual apreciable.

## 5. Personal
Datos: staff_hours medio 55.9 h/tienda-día; ventas por hora-staff $36.8; transacciones por hora-staff 4.55 (excluye 28 días ≤0 y 12 con 999).
| Formato | $/h-staff | Tx/h-staff | h/día | Personal medio en piso | Conversión | Corr(horas,tx) |
|---|---|---|---|---|---|---|
| Full Counter | 46.1 | 5.80 | 68.9 | 3.7 | 10.1 % | 0.70 |
| Express Kiosk | 33.4 | 4.16 | 44.4 | 2.6 | 10.3 % | 0.42 |
| Shop-in-Shop | 28.2 | 3.31 | 55.3 | 2.7 | 9.4 % | 0.88 |
- Mejores $/h: S014 (60.9), S012 (60.4), S015 (58.5), S029 (58.5). Peores: S030 (18.7), S019 (19.7), S018 (20.5), S020 (20.7), S034 resort (22.5), S017 (30.2 con 96 h/día).
- Correlación horas–footfall por tienda 0.46-0.94 (mediana ~0.77); con transacciones 0.34-0.85.
- **Elasticidad de horas vs demanda** (dentro de tienda): 0.29 vs transacciones, 0.42 vs footfall (debería ser ~0.8-1.0): el staffing es casi plano. Por quintiles de demanda: tx/h-staff 3.4 → 5.2 (días bajos sobre-dotados, días pico sub-dotados). Sábado: 3.96 tx/h vs viernes 4.55 (-22 % de demanda vs viernes pero solo -11 % de horas); julio 5.19 vs octubre 3.73. Conversión sube con la presión (8.6 % → 11.2 % de menor a mayor quintil), sin evidencia de pérdida visible por falta de personal.
- Sobredotación vs benchmark p75 de su formato: **144 k horas (20.5 % de 705 k)** [S]; mayores excesos S034 (63 %), S020 (53 %), S037 (51 %), S017 (45 %), S033, S018, S025. Déficit en picos ≈ 30 k h.

## 6. Oportunidades (tamaño aproximado anual, todo [S])
| # | Oportunidad | Tamaño | Módulo / señales |
|---|---|---|---|
| 1 | Reducir merma perecedera en kioscos/shop-in-shop al nivel Full Counter | $0.46 M al costo ($1.9 M a precio venta) | Inventario: demanda diaria por tienda-SKU, case_size, shelf_life, dow, feriados/escolar, on_order |
| 2 | Recuperar quiebres (30 % del perdido) en tiendas alto tráfico | $0.4–1.0 M ventas ($0.3-0.8 M margen) | Inventario: stockout_hours, tasa de venta/h, tráfico, open_hours |
| 3 | Ajustar horas a demanda (elasticidad 0.29 → ~0.8) | 25-50 % de 144 k h = $0.6-1.2 M a $17/h | Personal: footfall, tx, dow, mes, feriado, escolar, formato |
| 4 | Podar/reasignar promos con margen negativo (PR002, PR005, PR011, PR010) y concentrarse en bundles de sandwich + iced coffee verano | $0.1–0.2 M | Promo: tipo, depto, % desc, temporada, formato, uplift histórico |
| 5 | Programar promos en periodos de baja demanda (sábado, ene-feb, oct) en lugar de pico | upside no cuantificado (~$30-60 k por campaña) | Promo + calendario |
| 6 | Recomendación por tienda para lealtad: reemplazar descuento 5/10 % indiscriminado | hasta $70 k | Promo |
| 7 | Reposición para feriados/escolares (+25 % demanda, +54 % pre-July 4) | incluido en #1/#2/#3 | Calendario |
| 8 | Completar maestro (SKU-100040 = $407 k; costos) y calidad de datos | habilita todo lo anterior | Datos |
Precio: alza de ~+5 % (3-9 %) desde 2026-03-01 en casi todo el catálogo; elasticidad estimada ≈ -0.4 a -0.5 [S, indicativa].

## Supuestos
- Fechas con barras = MM/DD/YYYY. PR003 termina 2025-12-24 (última venta etiquetada).
- Costos: mediana de unit_cost de OC (>0); faltantes ⇒ ratio costo/precio mediano por depto. Margen bruto resultante 77 % (alto).
- Ventas perdidas: tasa de venta/hora en días sin quiebre × horas de quiebre (acotadas a horas abiertas) × precio neto. Quiebres de día completo pueden incluir SKU delistados (cota baja: solo parciales).
- Labor $17/h supuesto; benchmark p75 de tx/h-staff por formato.
- Uplift DiD con control = unidades no promo fuera del alcance; ruido ±10 pts (placebo PR013).
