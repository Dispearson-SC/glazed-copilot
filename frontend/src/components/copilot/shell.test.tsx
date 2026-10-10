import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AgentOrb from "./AgentOrb";
import CapsuleNav from "./CapsuleNav";
import CopilotTopBar from "./CopilotTopBar";
import Toast from "./Toast";

describe("CapsuleNav", () => {
  const tabs = ["Agente", "Decisiones", "Sucursal", "Memorias", "Alertas"];

  it("renders the five windows as real buttons with the design labels", () => {
    render(<CapsuleNav tab="agente" onChange={() => {}} badges={{}} />);
    const nav = screen.getByRole("navigation", { name: "Ventanas del copiloto" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent?.replace(/^[a-z_]+/, ""))).toEqual(tabs);
  });

  it("marks only the active window with aria-current=page", () => {
    render(<CapsuleNav tab="sucursal" onChange={() => {}} badges={{}} />);
    expect(screen.getByRole("button", { name: /Sucursal/, current: "page" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { current: "page" })).toHaveLength(1);
  });

  it("calls onChange with the tab id", async () => {
    const onChange = vi.fn();
    render(<CapsuleNav tab="agente" onChange={onChange} badges={{}} />);
    await userEvent.click(screen.getByRole("button", { name: /Memorias/ }));
    expect(onChange).toHaveBeenCalledWith("memorias");
  });

  it("shows a badge only when the count is above zero, and names it for screen readers", () => {
    render(<CapsuleNav tab="agente" onChange={() => {}} badges={{ decisiones: 12, memorias: 0, alertas: 3 }} />);
    expect(screen.getByRole("button", { name: "Decisiones, 12 pendientes" })).toHaveTextContent("12");
    expect(screen.getByRole("button", { name: "Alertas, 3 pendientes" })).toHaveTextContent("3");
    expect(screen.getByRole("button", { name: "Memorias" })).not.toHaveTextContent("0");
  });

  it("gives every tab a 44px touch target", () => {
    render(<CapsuleNav tab="agente" onChange={() => {}} badges={{}} />);
    for (const b of screen.getAllByRole("button")) expect(b.className).toMatch(/min-h-\[44px\]/);
  });
});

describe("CopilotTopBar", () => {
  it("shows the brand, the branch and an accessible settings button", async () => {
    const onSettings = vi.fn();
    render(<CopilotTopBar branch="Shop-in-Shop 1" onSettings={onSettings} />);
    const bar = screen.getByRole("banner");
    expect(within(bar).getByText("Glazed Co.")).toBeInTheDocument();
    expect(within(bar).getByText(/Copiloto · Shop-in-Shop 1/)).toBeInTheDocument();
    const btn = within(bar).getByRole("button", { name: "Ajustes del copiloto" });
    expect(btn.className).toMatch(/w-11/);
    await userEvent.click(btn);
    expect(onSettings).toHaveBeenCalled();
  });
});

describe("AgentOrb", () => {
  it("is decorative", () => {
    const { container } = render(<AgentOrb size={116} />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});

describe("Toast", () => {
  it("renders a status message and nothing when empty", () => {
    const { rerender } = render(<Toast text="Aceptada: pavo" />);
    expect(screen.getByRole("status")).toHaveTextContent("Aceptada: pavo");
    rerender(<Toast text={null} />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
