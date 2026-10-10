import { describe, expect, it, vi } from "vitest";
import type { Api } from "../api";
import * as src from "./copilot";

const api = {} as Api;

describe("data sources the backend does not serve yet", () => {
  it("answers 'soon' without calling the API", async () => {
    const spy = vi.fn();
    const probe = new Proxy({}, { get: () => spy }) as unknown as Api;
    const calls = await Promise.all([
      src.fetchIssueAnalysis(probe, "c1", "i1"),
      src.fetchForecastMetric(probe, "c1", "traffic"),
      src.fetchInventoryStatus(probe, "c1"),
      src.fetchMemories(probe, "c1"),
      src.fetchAutonomyLog(probe, "c1"),
      src.revertAutonomy(probe, "c1", "x"),
      src.fetchAgentsStatus(probe),
      src.fetchTurnProgress(probe, "c1", "t1"),
      src.fetchInboxCounts(probe, "c1"),
    ]);
    for (const c of calls) expect(c).toEqual({ status: "soon" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("prefixes the chat context into the text until POST /messages accepts a context field", () => {
    expect(src.chatContextText("Analiza: Pedir pavo", { issueId: "S030|x|1", title: "Pedir pavo", mode: "analizar" })).toBe(
      "Contexto: Pedir pavo (S030|x|1).\nAnaliza: Pedir pavo",
    );
    expect(src.chatContextText("hola", null)).toBe("hola");
  });

  it("exposes an alert's agent as unknown until the API carries agent_id", () => {
    expect(src.alertAgent({ alert_id: "a" } as never)).toBeNull();
    expect(api).toBeDefined();
  });
});
