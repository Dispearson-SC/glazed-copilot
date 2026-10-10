import { describe, expect, it } from "vitest";
import { ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchInventory, branchKpis, hoySummary, orderPlanA } from "../test/copilotFixtures";
import { buildDayView, isPlaceholder, buildInventoryRows, buildScheduled } from "./copilot";

const input = { asOf: "2026-07-19", forecast: branchForecast, ayer: ayerSummary, hoy: hoySummary, kpis: branchKpis, expiring: branchExpiring };

describe("buildDayView", () => {
  it("Ayer: expected from the forecast, real from the day summary, compared with the same-weekday average", () => {
    const v = buildDayView("ayer", input);
    expect(v).toMatchObject({
      title: "Así cerró ayer", date: "Sábado, 18 de julio de 2026", expected: "$654.45", range: "$540 – $791", real: "$849.20",
      realNote: "+25% vs promedio mismo día", conf: "Pronóstico cerrado",
    });
    expect(v.weather).toMatchObject({ tag: "observado", temp: "37° / 29°", text: "Lluvia 4.6 mm", icon: "rainy" });
    expect(v.traffic).toEqual({ value: "734", caption: "visitas" });
    expect(v.orders).toEqual({ label: "Pedidos", value: "105" });
    expect(v.ticket.value).toBe("$8.09");
    expect(v.conversion.value).toBe("14.3%");
    expect(v.context).toBe("Sábado · vacaciones escolares");
  });

  it("Hoy: expected only; real sales are never shown, whatever the day summary carries", () => {
    const v = buildDayView("hoy", input);
    expect(v).toMatchObject({ title: "Hoy en la sucursal", expected: "$868.54", range: "$700 – $1,101", real: "Pendiente", realNote: "Se registra al cierre", conf: "Pronóstico" });
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

  it("shows the expected waste of the day from /expiring and the 7-day lost sales from /kpis", () => {
    const hoy = buildDayView("hoy", input);
    expect(hoy.waste).toEqual({ label: "Merma esperada", value: "Disponible pronto", sub: "a costo" });
    const manana = buildDayView("manana", input);
    expect(manana.waste).toEqual({ label: "Merma esperada", value: "$12.25", sub: "a costo · $11 – $15" });
    expect(manana.lost).toEqual({ label: "Venta perdida (7 días)", value: "$534.62", sub: "$75 – $691 · por falta de producto" });
    expect(buildDayView("ayer", input).waste).toEqual({ label: "Merma real", value: "Sin datos", sub: "Últimos 7 días: $1,202.09" });
  });
});

describe("buildDayView with /outlook", () => {
  const outlook = {
    days: [
      { date: "2026-07-19", net_sales: { low: 700, mid: 900, high: 1100 }, transactions: { mid: 118.4 }, ticket: { mid: 7.6 }, expected_waste_usd: { low: 5, mid: 8, high: 11 }, expected_lost_sales_usd: { low: 10, mid: 20, high: 30 }, weather: null },
    ],
  };
  it("prefers the outlook for Hoy and fills orders, ticket, waste and lost sales", () => {
    const v = buildDayView("hoy", { ...input, outlook });
    expect(v).toMatchObject({ expected: "$900.00", range: "$700 – $1,100" });
    expect(v.orders.value).toBe("118");
    expect(v.ticket.value).toBe("$7.60");
    expect(v.waste).toEqual({ label: "Merma esperada", value: "$8.00", sub: "a costo · $5 – $11" });
    expect(v.lost).toEqual({ label: "Venta perdida esperada", value: "$20.00", sub: "$10 – $30 · por falta de producto" });
    expect(v.weather.text).toBe("Sin pronóstico");
  });
  it("keeps 'Disponible pronto' for a day the outlook does not cover", () => {
    expect(buildDayView("manana", { ...input, outlook }).orders.value).toBe("Disponible pronto");
  });
});

describe("same-weekday baseline when the forecast has no point for the day", () => {
  it("shows the backend's same-weekday average for Ayer and Hoy instead of an empty range", () => {
    expect(buildDayView("ayer", { ...input, forecast: null }).baseline).toBe("Promedio mismo día (7 sem): $677.87");
    expect(buildDayView("hoy", { ...input, forecast: null }).baseline).toBe("Promedio mismo día (7 sem): $700.00");
    expect(buildDayView("manana", { ...input, forecast: null }).baseline).toBeNull();
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

describe("buildScheduled", () => {
  it("lists late and expected placed orders, skipping received ones and supplier schedule rows", () => {
    const rows = buildScheduled(branchDeliveries, 4);
    expect(rows).toEqual([
      { what: "Vasos 12 oz · 40", who: "Pioneer Merch & Packaging", when: "jue 16", status: "Atrasado", tone: "warn" },
      { what: "Southwestern Veggie Burrito · 10", who: "Summit Frozen Foods", when: "mar 21", status: "Colocado", tone: "ok" },
    ]);
  });
});
