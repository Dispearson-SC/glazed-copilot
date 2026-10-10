import { describe, expect, it } from "vitest";
import { inventoryMany, ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchInventory, hoySummary, inventoryWithStatus, metricForecasts, orderPlanA, outlookA, outlookFull } from "../test/copilotFixtures";
import { buildDayView, isPlaceholder, buildInventoryRows, buildScheduled } from "./copilot";

const input = { asOf: "2026-07-19", forecast: branchForecast, ayer: ayerSummary, hoy: hoySummary, expiring: branchExpiring };

describe("buildDayView", () => {
  it("Ayer: expected from the forecast, real from the day summary, compared with the same-weekday average", () => {
    const v = buildDayView("ayer", input);
    expect(v).toMatchObject({
      title: "Así cerró ayer", date: "Sábado, 18 de julio de 2026", expected: "$654.45", range: "$540 – $791", real: "$849.20",
      realNote: "+25% vs promedio mismo día", conf: "Pronóstico cerrado",
    });
    expect(v.weather).toMatchObject({ tag: "observado", temp: "37° / 29°", text: "Lluvia 4.6 mm", icon: "rainy" });
    expect(v.traffic).toEqual({ value: "734", caption: "visitas esperadas" });
    expect(v.orders).toEqual({ label: "Pedidos esperados", value: "105" });
    expect(v.ticket.value).toBe("$8.09");
    expect(v.conversion.value).toBe("14.3%");
    expect(v.context).toBe("Sábado · vacaciones escolares");
  });

  it("Hoy: expected only; real sales are never shown, whatever the day summary carries", () => {
    const v = buildDayView("hoy", input);
    expect(v).toMatchObject({ title: "Hoy en la sucursal", expected: "$868.54", range: "$700 – $1,101", real: "Pendiente", realNote: "Se registra al cierre", conf: "Pronóstico Sin datos" });
    expect(JSON.stringify(v)).not.toContain("1,135");
    expect(JSON.stringify(v)).not.toContain("1135");
    expect(v.weather).toMatchObject({ tag: "pronóstico", temp: "Sin pronóstico", text: "Sin pronóstico" });
    expect(v.traffic).toEqual({ value: "Disponible pronto", caption: "visitas esperadas" });
    expect(v.orders).toEqual({ label: "Pedidos esperados", value: "Disponible pronto" });
    expect(v.context).toBe("Domingo · vacaciones escolares");
  });

  it("Mañana: forecast of the next day, weather permanently 'Sin pronóstico', no calendar facts", () => {
    const v = buildDayView("manana", input);
    expect(v).toMatchObject({ title: "Mañana en la sucursal", expected: "$833.39", range: "$682 – $1,060", real: "Pendiente", realNote: "Día futuro", context: "Lunes" });
    expect(v.weather.text).toBe("Sin pronóstico");
  });

  it("says 'Sin datos' when the forecast has no point for the day", () => {
    const v = buildDayView("manana", { ...input, forecast: null });
    expect(v.expected).toBe("Sin datos");
    expect(v.range).toBeNull();
  });

  it("shows the expected waste of the day from /expiring; lost sales need the outlook and Ayer's waste is unknown", () => {
    const hoy = buildDayView("hoy", input);
    expect(hoy.waste).toEqual({ label: "Merma esperada", value: "Disponible pronto", sub: "a costo" });
    const manana = buildDayView("manana", input);
    expect(manana.waste).toEqual({ label: "Merma esperada", value: "$12.25", sub: "a costo · $11 – $15" });
    expect(manana.lost).toEqual({ label: "Venta perdida esperada", value: "Disponible pronto", sub: "por falta de producto" });
    expect(buildDayView("ayer", input).waste).toEqual({ label: "Merma esperada", value: "Sin datos", sub: "a costo · real" });
    expect(buildDayView("ayer", input).lost.value).toBe("Disponible pronto");
  });
});

describe("buildDayView with /outlook", () => {
  const outlook = {
    days: [
      { date: "2026-07-19", net_sales: { low: 700, mid: 900, high: 1100 }, transactions: { mid: 118.4 }, avg_ticket: { mid: 7.6 }, expected_waste_usd: { low: 5, mid: 8, high: 11 }, expected_lost_sales_usd: { low: 10, mid: 20, high: 30 }, weather: null },
    ],
  };
  it("prefers the outlook for Hoy and fills orders, ticket, waste and lost sales", () => {
    const v = buildDayView("hoy", { ...input, outlook });
    expect(v).toMatchObject({ expected: "$900.00", range: "$700 – $1,100" });
    expect(v.orders.value).toBe("118");
    expect(v.ticket.value).toBe("$7.60");
    expect(v.waste).toEqual({ label: "Merma esperada", value: "$8.00", sub: "a costo · $5 – $11" });
    expect(v.lost).toEqual({ label: "Venta perdida esperada", value: "$10 – $30", sub: "por falta de producto" });
    expect(v.weather.text).toBe("Sin pronóstico");
  });
  it("says 'Sin datos' for a day the outlook does not cover (the route is deployed)", () => {
    expect(buildDayView("manana", { ...input, outlook }).orders.value).toBe("Sin datos");
  });
});

describe("buildDayView with the metric forecasts (/forecast?metric=...) and the live /outlook", () => {
  const withMetrics = { ...input, metrics: metricForecasts };
  it("Hoy: visits, orders, ticket and conversion come from the metric forecasts", () => {
    const v = buildDayView("hoy", { ...withMetrics, outlook: outlookA });
    expect(v.traffic).toEqual({ value: "971", caption: "visitas esperadas" });
    expect(v.orders).toEqual({ label: "Pedidos esperados", value: "85" });
    expect(v.ticket.value).toBe("$9.56");
    expect(v.conversion.value).toBe("8.7%");
    expect(JSON.stringify(v)).not.toContain("965"); // today's actual visits are never shown
  });

  it("Mañana: the outlook feeds orders and ticket; metrics feed visits and conversion; waste and lost sales are ranges as served", () => {
    const v = buildDayView("manana", { ...withMetrics, outlook: outlookA });
    expect(v.traffic.value).toBe("836");
    expect(v.orders.value).toBe("86");
    expect(v.ticket.value).toBe("$9.24");
    expect(v.conversion.value).toBe("10.3%");
    expect(v.waste).toEqual({ label: "Merma esperada", value: "$0.00", sub: "a costo · $0 – $0" });
    expect(v.lost).toEqual({ label: "Venta perdida esperada", value: "$0 – $105", sub: "por falta de producto" });
    expect(v.weather.text).toBe("Sin pronóstico");
  });

  it("says 'Sin datos' (not 'Disponible pronto') when the routes answer but have no point for the day", () => {
    const v = buildDayView("hoy", { ...input, asOf: "2026-08-01", metrics: metricForecasts, outlook: outlookA });
    expect(v.traffic.value).toBe("Sin datos");
    expect(v.orders.value).toBe("Sin datos");
    expect(v.conversion.value).toBe("Sin datos");
    expect(v.waste.value).toBe("Sin datos");
  });

  it("keeps 'Disponible pronto' when the routes are unavailable (404)", () => {
    const v = buildDayView("manana", { ...input, metrics: null, outlook: null });
    expect(v.traffic.value).toBe("Disponible pronto");
    expect(v.conversion.value).toBe("Disponible pronto");
  });

  it("does not show a conversion the backend marks as not valid", () => {
    const bad = { ...metricForecasts, conversion: { ...metricForecasts.conversion, conversion_valid: false } as never };
    expect(buildDayView("manana", { ...input, metrics: bad }).conversion.value).toBe("Sin datos");
  });
});

describe("isPlaceholder", () => {
  it("recognises the honest empty values", () => {
    for (const v of ["Sin datos", "Disponible pronto", "Sin pronóstico", "Pendiente"]) expect(isPlaceholder(v)).toBe(true);
    expect(isPlaceholder("$12.00")).toBe(false);
  });
});

describe("buildInventoryRows", () => {
  it("combines on-hand, daily demand and the order-plan purchase", () => {
    const rows = buildInventoryRows(branchInventory, orderPlanA);
    expect(rows[0]).toMatchObject({ name: "Md Choc Stout C.B. Wsweet Cold Foam", now: "5", out: "3.23 /día", buy: "+10 · llega mar 21", cover: "1.5 días de cobertura", fill: 100 });
    expect(rows[1]).toMatchObject({ now: "0", buy: "—", fill: 0, cover: "0 días de cobertura" });
  });
});

describe("buildInventoryRows with the backend status", () => {
  const rows = buildInventoryRows(inventoryWithStatus, null);
  it("maps critical, watch and ok to the design's pills with the backend reason", () => {
    expect(rows.map((r) => [r.status, r.statusLabel])).toEqual([["critical", "Crítico"], ["ok", "En orden"], ["watch", "Seguimiento"]]);
    expect(rows[0].reason).toContain("se agota antes de la próxima entrega");
  });
  it("shows the forecast outflow and the scheduled delivery from the inventory itself", () => {
    expect(rows[0]).toMatchObject({ now: "0", out: "51.31 en 3 días", buy: "+40 · llega lun 20" });
    expect(rows[1]).toMatchObject({ out: "9.6 en 3 días", buy: "—" });
    expect(rows[2].buy).toBe("+12 · llega mié 22");
  });
  it("falls back to the daily average and the order plan when the status fields are missing", () => {
    const old = buildInventoryRows(branchInventory, orderPlanA);
    expect(old[0]).toMatchObject({ status: null, out: "3.23 /día", buy: "+10 · llega mar 21" });
  });
});

describe("buildScheduled", () => {
  it("lists late and expected placed orders, skipping received ones and supplier schedule rows", () => {
    const rows = buildScheduled(branchDeliveries, 4);
    expect(rows).toEqual([
      { what: "Vasos 12 oz · 40", who: "Pioneer Merch & Packaging", when: "jue 16", status: "Atrasado", tone: "warn" },
      { what: "Southwestern Veggie Burrito · 10", who: "Summit Frozen Foods", when: "mar 21", status: "Colocado", tone: "ok" },
    ]);
  });
});

describe("buildDayView with the live Wave 15 shapes (case d17217ea4550, as_of 2026-07-19)", () => {
  const outlook = {
    as_of: "2026-07-19",
    days: [
      { date: "2026-07-20", projected: true, net_sales: { low: 2622.1181, mid: 2910.9459, high: 3347.4488 }, transactions: { low: 328.3, mid: 354.5, high: 436.1 }, avg_ticket: { low: 8.32, mid: 8.69, high: 9.25 }, expected_waste_usd: { low: 6.9, mid: 6.9, high: 6.9 }, expected_lost_sales_usd: { low: 0.0, mid: 4.21, high: 198.13 }, weather: null, weather_note: "Sin pronóstico" },
    ],
  };
  const pt = (date: string, forecast: number, projected: boolean) => ({ date, forecast, p10: forecast * 0.9, p90: forecast * 1.1, baseline: forecast, actual: projected ? null : forecast, censored: false, projected });
  const mk = (metric: string, vals: [number, number]) =>
    ({ store_id: "S001", sku: null, level: "store", as_of: "2026-07-19", forecast_origin: "2026-07-19", model: "flow-weekday-8w", model_version: "", unit: "", horizon_days: 1, metric, conversion_valid: metric === "conversion" ? true : null, metrics_to_date: {}, points: [pt("2026-07-19", vals[0], false), pt("2026-07-20", vals[1], true)] }) as never;
  const metrics = { footfall: mk("footfall", [3581.5, 2996]), transactions: mk("transactions", [400, 354.5]), avg_ticket: mk("avg_ticket", [8.8, 8.69]), conversion: mk("conversion", [0.1136, 0.118]) };

  it("fills Mañana from the live outlook and metric forecasts", () => {
    const v = buildDayView("manana", { asOf: "2026-07-19", forecast: null, ayer: null, hoy: null, expiring: null, outlook, metrics });
    expect(v).toMatchObject({ expected: "$2,910.95", range: "$2,622 – $3,347", traffic: { value: "2996" }, orders: { value: "355" }, ticket: { value: "$8.69" }, conversion: { value: "11.8%" } });
    expect(v.waste.value).toBe("$6.90");
    expect(v.lost.value).toBe("$0 – $198");
  });
});

describe("buildInventoryRows closing status", () => {
  it("carries the backend sentence and keeps every row (no cap)", () => {
    const rows = buildInventoryRows(inventoryMany, null);
    expect(rows).toHaveLength(12);
    expect(rows[0].display).toBe("Agotado hoy (6.9 h sin stock) · llegan 40 mañana");
    expect(rows[0].now).toBe("0");
  });
});

describe("buildDayView with the full outlook (backtest + today + forward)", () => {
  const full = { ...input, outlook: outlookFull };
  it("Hoy: forecast and range from the is_today day, real sales stay pending, never today's actual", () => {
    const v = buildDayView("hoy", full);
    expect(v.expected).toBe("$3,605.99");
    expect(v.range).toBe("$3,256 – $3,871");
    expect(v.real).toBe("Pendiente");
    expect(v.realNote).toBe("Se registra al cierre");
    expect(JSON.stringify(v)).not.toContain("3,601");
  });
  it("Ayer: backtest forecast beside the actual with the variance, never 0", () => {
    const v = buildDayView("ayer", full);
    expect(v.expected).toBe("$2,618.95");
    expect(v.range).toBe("$2,347 – $2,900");
    expect(v.real).toBe("$849.20");
    expect(v.conf).toBe("+4% vs pronóstico");
  });
  it("Ayer: falls back to the outlook actual when the day summary is missing", () => {
    const v = buildDayView("ayer", { ...full, ayer: null });
    expect(v.real).toBe("$2,729.61");
  });
  it("Mañana: forward band", () => {
    const v = buildDayView("manana", full);
    expect(v.expected).toBe("$2,910.94");
    expect(v.range).toBe("$2,500 – $3,300");
  });
});
