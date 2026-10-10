import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AnalysisCard from "../components/copilot/AnalysisCard";
import { buildPendingItems } from "../data/copilot";
import { agentsA, alertsA, memoriesA, pendingA, inventoryWithStatus, branchForecast, hoySummary, ayerSummary } from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

function gate<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}
const julyCase = { ...caseA, sim_today: "2026-07-19" };
const base = (over = {}) =>
  fakeApi({
    listCases: async () => [julyCase],
    listProposals: async () => [],
    getAgentsStatus: async () => ({ connected: true, agents: agentsA }),
    getPending: async () => pendingA,
    getMemories: async () => memoriesA,
    listAlerts: async () => alertsA,
    listIssues: async () => [],
    ...over,
  });
const go = async (a: ReturnType<typeof base>, tab: string) => {
  renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
  await userEvent.click(await screen.findByRole("button", { name: new RegExp(`^${tab}`) }));
};
const busy = (name: RegExp) => screen.queryByRole("status", { name });
const NOT_YET = [/Sin datos/, /Disponible pronto/, /Nada pendiente/, /Sin advertencias/, /Aún no hay memorias/];
const expectNoVerdict = () => {
  for (const re of NOT_YET) expect(screen.queryByText(re)).toBeNull();
};

describe("skeleton placeholders", () => {
  it("Decisiones: loading → skeleton → data", async () => {
    const g = gate<typeof pendingA>();
    await go(base({ getPending: () => g.promise }), "Decisiones");
    const sk = await screen.findByRole("status", { name: /Cargando decisiones/ });
    expect(sk).toHaveAttribute("aria-busy", "true");
    expectNoVerdict();
    await act(async () => g.resolve(pendingA));
    expect(await screen.findByText(/Omitir el pedido de 12 Croiss-Ant Donuts/)).toBeInTheDocument();
    expect(busy(/Cargando decisiones/)).toBeNull();
  });

  it("Decisiones: loading → skeleton → empty", async () => {
    const g = gate<typeof pendingA>();
    await go(base({ getPending: () => g.promise }), "Decisiones");
    await screen.findByRole("status", { name: /Cargando decisiones/ });
    await act(async () => g.resolve({ ...pendingA, approvals: [], technical: [] }));
    expect(await screen.findByText("Nada pendiente de tu opinión por ahora.")).toBeInTheDocument();
    expect(busy(/Cargando decisiones/)).toBeNull();
  });

  it("Alertas: loading → skeleton → data, and → empty", async () => {
    const g = gate<typeof alertsA>();
    await go(base({ listAlerts: () => g.promise }), "Alertas");
    const sk = await screen.findByRole("status", { name: /Cargando advertencias/ });
    expect(sk).toHaveAttribute("aria-busy", "true");
    expectNoVerdict();
    await act(async () => g.resolve([]));
    expect(await screen.findByText("Sin advertencias por ahora")).toBeInTheDocument();
    expect(busy(/Cargando advertencias/)).toBeNull();
  });

  it("Memorias: loading → skeleton → data, and → empty", async () => {
    const g = gate<typeof memoriesA>();
    await go(base({ getMemories: () => g.promise }), "Memorias");
    const sk = await screen.findByRole("status", { name: /Cargando memorias/ });
    expect(sk).toHaveAttribute("aria-busy", "true");
    expectNoVerdict();
    await act(async () => g.resolve(memoriesA));
    expect(await screen.findByText(/Aprobaste omitir/)).toBeInTheDocument();
    expect(busy(/Cargando memorias/)).toBeNull();
  });

  it("Memorias: a loaded empty list says so only after loading", async () => {
    await go(base({ getMemories: async () => [] }), "Memorias");
    expect(await screen.findByText(/Aún no hay memorias/)).toBeInTheDocument();
    expect(busy(/Cargando memorias/)).toBeNull();
  });

  it("Sucursal: skeleton while the sources load, then the cards", async () => {
    const g = gate<typeof inventoryWithStatus>();
    await go(
      base({
        getInventory: () => g.promise,
        getForecast: async () => branchForecast,
        getDaySummary: async (_c: string, d?: string) => (d === "2026-07-18" ? ayerSummary : hoySummary),
      }),
      "Sucursal",
    );
    const sk = await screen.findByRole("status", { name: /Cargando sucursal/ });
    expect(sk).toHaveAttribute("aria-busy", "true");
    expectNoVerdict();
    await act(async () => g.resolve(inventoryWithStatus));
    expect(await screen.findByRole("heading", { name: "Hoy en la sucursal" })).toBeInTheDocument();
    expect(busy(/Cargando sucursal/)).toBeNull();
  });

  it("Agente: chat history skeleton until the stored turns arrive", async () => {
    const g = gate<never[]>();
    renderPage(base({ listTurns: () => g.promise }), "/copiloto", "/copiloto", <CopilotPage />);
    const sk = await screen.findByRole("status", { name: /Cargando conversación/ });
    expect(sk).toHaveAttribute("aria-busy", "true");
    await act(async () => g.resolve([{ turn_id: "t1", ts: "2026-07-19T08:00:00Z", user_text: "Hola", reply: "Buenas", status: "done" }] as never));
    expect(await screen.findByText("Hola")).toBeInTheDocument();
    expect(busy(/Cargando conversación/)).toBeNull();
  });

  it("Agente: no history → no skeleton, no verdict text either", async () => {
    renderPage(base({ listTurns: async () => [] }), "/copiloto", "/copiloto", <CopilotPage />);
    await screen.findByRole("heading", { name: "¿Qué decidimos hoy?" });
    await vi.waitFor(() => expect(busy(/Cargando conversación/)).toBeNull());
  });

  it("the analysis card shows a skeleton while the analysis loads", () => {
    const [item] = buildPendingItems(pendingA, "2026-07-19");
    render(<AnalysisCard item={item} analysis={{ status: "loading" }} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("status", { name: /Cargando análisis/ })).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText("Cargando análisis…")).toBeNull();
  });
});
