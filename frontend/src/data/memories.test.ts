import { describe, expect, it } from "vitest";
import { alertsA, integrityA, memoriesA } from "../test/copilotFixtures";
import { buildMemories, buildWarnings, filterMemories, filterWarnings } from "./copilot";

describe("buildMemories", () => {
  const all = buildMemories(memoriesA);

  it("maps the backend memories in the order served (newest first), with the design's categories", () => {
    expect(all.map((m) => [m.id, m.cat])).toEqual([
      ["rej-7d7ee16b9f3a", "preferencias"], ["dec-3c379580f251", "proveedores"], ["bb-1", "demanda"], ["bb-2", "eventos"],
    ]);
  });

  it("flags only memories created in the last 24 hours as 'Nuevo aprendizaje'", () => {
    expect(all.map((m) => Boolean(m.isNew))).toEqual([true, false, false, false]);
  });

  it("writes source, case count and verification from backend fields", () => {
    expect(all[0]).toMatchObject({ tag: "Preferencia del gerente", icon: "person", src: "Motivo de rechazo · 10/10", conf: "1 caso · sin verificar" });
    expect(all[1]).toMatchObject({ tag: "Proveedor", icon: "local_shipping", src: "Registro de decisiones · 09/10", conf: "3 casos · verificada" });
    expect(all[2].src).toBe("Experiencia de la sucursal · 01/10");
    expect(all[3]).toMatchObject({ tag: "Evento", conf: "1 caso · verificada" });
  });

  it("filters by category and by search text", () => {
    expect(filterMemories(all, "proveedores", "").map((m) => m.id)).toEqual(["dec-3c379580f251"]);
    expect(filterMemories(all, "todas", "bacon").map((m) => m.id)).toEqual(["rej-7d7ee16b9f3a"]);
    expect(filterMemories(all, "todas", "  ")).toHaveLength(4);
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
