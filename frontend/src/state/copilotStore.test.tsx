import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Memory } from "../data/copilot";
import { CopilotProvider, copilotReducer, initialCopilotState, useCopilot } from "./copilotStore";

const learned: Memory = { id: "l1", cat: "preferencias", icon: "school", tag: "Motivo: Precio o costo", text: "Precio o costo", src: "Rechazo · hoy · Pedido", conf: "Ajustará próximas propuestas", isNew: true };

describe("copilotReducer", () => {
  it("starts on the Agente window with no context, menu, sheet or toast", () => {
    expect(initialCopilotState).toMatchObject({ tab: "agente", day: "hoy", memFilter: "todas", alertFilter: "todas", ctx: null, menuFor: null, rejectFor: null, toast: null, accepted: 0, handled: [], learned: [], analyses: [] });
  });

  it("changes window and closes the open menu", () => {
    const s = copilotReducer({ ...initialCopilotState, menuFor: "x" }, { type: "tab", tab: "sucursal" });
    expect(s.tab).toBe("sucursal");
    expect(s.menuFor).toBeNull();
  });

  it("opens and closes the reject sheet, closing the menu", () => {
    const open = copilotReducer({ ...initialCopilotState, menuFor: "x" }, { type: "openReject", id: "x" });
    expect(open.rejectFor).toBe("x");
    expect(open.menuFor).toBeNull();
    expect(copilotReducer(open, { type: "closeReject" }).rejectFor).toBeNull();
  });

  it("toggles the menu of one card", () => {
    const a = copilotReducer(initialCopilotState, { type: "toggleMenu", id: "x" });
    expect(a.menuFor).toBe("x");
    expect(copilotReducer(a, { type: "toggleMenu", id: "x" }).menuFor).toBeNull();
    expect(copilotReducer(a, { type: "toggleMenu", id: "y" }).menuFor).toBe("y");
  });

  it("opens an analysis: switches to Agente, pins the context and records the card after the given message count", () => {
    const s = copilotReducer({ ...initialCopilotState, tab: "decisiones", menuFor: "x" }, { type: "analysis", itemId: "x", title: "Pedir pavo", mode: "analizar", at: 3 });
    expect(s.tab).toBe("agente");
    expect(s.ctx).toEqual({ id: "x", title: "Pedir pavo" });
    expect(s.menuFor).toBeNull();
    expect(s.analyses).toEqual([{ id: "an-1", itemId: "x", mode: "analizar", at: 3 }]);
  });

  it("marks an item handled; an accepted tech decision bumps the counter, an approval does not", () => {
    const a = copilotReducer(initialCopilotState, { type: "handled", id: "t1", accepted: true });
    expect(a).toMatchObject({ handled: ["t1"], accepted: 1 });
    const b = copilotReducer(a, { type: "handled", id: "a1", accepted: false });
    expect(b).toMatchObject({ handled: ["t1", "a1"], accepted: 1 });
    expect(copilotReducer(b, { type: "handled", id: "a1", accepted: false }).handled).toEqual(["t1", "a1"]);
  });

  it("prepends learned memories", () => {
    const s = copilotReducer(initialCopilotState, { type: "learned", memory: learned });
    expect(s.learned).toEqual([learned]);
  });

  it("clears the pinned context", () => {
    const s = copilotReducer({ ...initialCopilotState, ctx: { id: "x", title: "T" } }, { type: "ctx", ctx: null });
    expect(s.ctx).toBeNull();
  });

  it("sets filters and day", () => {
    expect(copilotReducer(initialCopilotState, { type: "day", day: "ayer" }).day).toBe("ayer");
    expect(copilotReducer(initialCopilotState, { type: "memFilter", value: "demanda" }).memFilter).toBe("demanda");
    expect(copilotReducer(initialCopilotState, { type: "alertFilter", value: "datos" }).alertFilter).toBe("datos");
  });
});

describe("CopilotProvider toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows a toast and clears it after 3.2 s", () => {
    const { result } = renderHook(() => useCopilot(), { wrapper: CopilotProvider });
    act(() => result.current.showToast("Aceptada"));
    expect(result.current.state.toast).toBe("Aceptada");
    act(() => void vi.advanceTimersByTime(3100));
    expect(result.current.state.toast).toBe("Aceptada");
    act(() => void vi.advanceTimersByTime(200));
    expect(result.current.state.toast).toBeNull();
  });

  it("restarts the timer when a new toast replaces the old one", () => {
    const { result } = renderHook(() => useCopilot(), { wrapper: CopilotProvider });
    act(() => result.current.showToast("uno"));
    act(() => void vi.advanceTimersByTime(3000));
    act(() => result.current.showToast("dos"));
    act(() => void vi.advanceTimersByTime(3000));
    expect(result.current.state.toast).toBe("dos");
    act(() => void vi.advanceTimersByTime(300));
    expect(result.current.state.toast).toBeNull();
  });

  it("renders children", () => {
    render(<CopilotProvider><p>hijo</p></CopilotProvider>);
    expect(screen.getByText("hijo")).toBeInTheDocument();
  });
});
