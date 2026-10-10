import { describe, expect, it } from "vitest";
import { alertsA, historyA, integrityA, suppliersA } from "../test/copilotFixtures";
import { buildMemories, buildWarnings, filterMemories, filterWarnings, type Memory } from "./copilot";

const learned: Memory = { id: "l", cat: "preferencias", icon: "school", tag: "Motivo: Precio o costo", text: "Precio o costo", src: "Rechazo · hoy · X", conf: "Ajustará próximas propuestas", isNew: true };

describe("buildMemories", () => {
  const all = buildMemories({ history: historyA, suppliers: suppliersA, learned: [learned] });

  it("puts new learnings first, then decisions, then supplier facts; skips pending decisions", () => {
    expect(all[0]).toBe(learned);
    expect(all.map((m) => m.id)).toEqual(["l", "dec-d1", "dec-d2", "dec-d3", "sup-SUP03"]);
  });

  it("turns a rejection into a manager preference quoting the reason", () => {
    expect(all[1]).toMatchObject({ cat: "preferencias", tag: "Motivo de rechazo", text: "«Prefiero quedarme corto»", src: "Rechazo · Omitir pedido · SKU-100473" });
  });

  it("turns approvals into demand or event memories by issue kind", () => {
    expect(all[2]).toMatchObject({ cat: "demanda", tag: "Decisión aprobada", text: "Aprobaste: Omitir pedido de SKU-100502." });
    expect(all[3]).toMatchObject({ cat: "eventos" });
  });

  it("states supplier performance with backend numbers only", () => {
    expect(all[4]).toMatchObject({
      cat: "proveedores", tag: "Proveedor", text: "Summit Frozen Foods: 90.1% a tiempo, entrega real de 2.17 días y surte el 99.9%.",
      src: "Desempeño de proveedores · 180 días", conf: "667 pedidos",
    });
  });

  it("filters by category and by search text", () => {
    expect(filterMemories(all, "proveedores", "").map((m) => m.id)).toEqual(["sup-SUP03"]);
    expect(filterMemories(all, "todas", "summit").map((m) => m.id)).toEqual(["sup-SUP03"]);
    expect(filterMemories(all, "todas", "  ")).toHaveLength(5);
  });
});

describe("buildWarnings", () => {
  const w = buildWarnings({ alerts: alertsA, integrity: integrityA });

  it("maps open alerts to operation warnings and integrity issues to data warnings", () => {
    expect(w.map((x) => [x.id, x.cat, x.toneLabel])).toEqual([
      ["al1", "operacion", "Seguimiento"], ["al2", "operacion", "Seguimiento"], ["al3", "operacion", "Seguimiento"],
      ["S030|orphan_sku|SKU-7xxxxx", "datos", "Datos"],
    ]);
  });

  it("writes Spanish titles and bodies from the structured fields", () => {
    expect(w[0]).toMatchObject({ title: "Exceso de inventario: 12 Croiss-Ant Donuts", body: "Merma estimada de $687.40.", time: "11/03" });
    expect(w[1].title).toBe("Efecto de calendario: School break");
    expect(w[2].title).toBe("Acción aprobada sin ejecutar");
    expect(w[3]).toMatchObject({ title: "Ventas sin producto en el catálogo", body: "Exposición de $14,537.12.", time: "19/07" });
  });

  it("never claims an agent or an automatic action", () => {
    expect(w.every((x) => x.agent === null && !x.revertible)).toBe(true);
    expect(filterWarnings(w, "auto")).toEqual([]);
    expect(filterWarnings(w, "datos")).toHaveLength(1);
    expect(filterWarnings(w, "todas")).toHaveLength(4);
  });
});
