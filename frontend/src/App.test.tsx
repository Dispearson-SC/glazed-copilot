import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "./ApiContext";
import App from "./App";
import { SessionProvider } from "./SessionContext";
import { fakeApi } from "./test/helpers";

const open = (path = "/", api = fakeApi()) =>
  render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );

describe("App", () => {
  it("links all pages in the navigation", async () => {
    open();
    const nav = screen.getByRole("navigation");
    for (const [name, href] of [["Inicio", "/"], ["Alertas", "/alerts"], ["Casos", "/cases"], ["Inspector", "/trace"]] as const)
      expect(await screen.findByRole("link", { name })).toHaveAttribute("href", href);
    expect(nav).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Compras" })).toHaveAttribute("href", "/purchases");
  });

  it("renders Home at / with the simulation control in the header", async () => {
    open();
    expect(await screen.findByTestId("loss-waste")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Avanzar 1 día" })).toBeInTheDocument();
  });

  it("redirects /purchases to the store purchases screen", async () => {
    open("/purchases");
    expect(await screen.findByTestId("supplier-SUP1")).toBeInTheDocument();
  });

  it("refreshes alerts after advancing a day", async () => {
    const api = fakeApi();
    open("/alerts", api);
    await screen.findByTestId("alert-a1");
    const before = (api.listAlerts as unknown as { mock: { calls: unknown[] } }).mock.calls.length;
    await userEvent.click(await screen.findByRole("button", { name: "Avanzar 1 día" }));
    await screen.findByText(/2026-03-02/);
    await new Promise((r) => setTimeout(r, 50));
    expect((api.listAlerts as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBeGreaterThan(before);
  });
});
