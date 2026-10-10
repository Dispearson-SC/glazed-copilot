import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { alertA, fakeApi, renderPage } from "../test/helpers";
import HomePage from "./HomePage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <HomePage />);

describe("HomePage", () => {
  it("offers stores by display name", async () => {
    open();
    expect(await screen.findByRole("option", { name: "Aeropuerto Norte · Glazed Centro" })).toBeInTheDocument();
  });

  it("shows both losses side by side: waste and lost sales as a range", async () => {
    open();
    const waste = await screen.findByTestId("loss-waste");
    const lost = screen.getByTestId("loss-lost-sales");
    expect(within(waste).getByText("$310.50")).toBeInTheDocument();
    expect(within(lost).getByText("$180.25")).toBeInTheDocument();
    expect(within(lost).getByText("$100.00 – $260.00")).toBeInTheDocument();
    expect(screen.getByText(/2026-02-15/)).toBeInTheDocument();
  });

  it("builds a semaphore from open alerts by severity", async () => {
    const api = fakeApi({
      listAlerts: async () => [
        { ...alertA, alert_id: "a1", severity_usd: 600 },
        { ...alertA, alert_id: "a2", severity_usd: 200 },
        { ...alertA, alert_id: "a3", severity_usd: 20 },
        { ...alertA, alert_id: "a4", severity_usd: 900, state: "resuelta" },
      ],
    });
    open(api);
    await waitFor(() => expect(screen.getByTestId("sem-red")).toHaveTextContent("1"));
    expect(screen.getByTestId("sem-yellow")).toHaveTextContent("1");
    expect(screen.getByTestId("sem-green")).toHaveTextContent("1");
  });

  it("links to purchases and alerts", async () => {
    open();
    expect(await screen.findByRole("link", { name: "Ver compras" })).toHaveAttribute("href", "/stores/S030/purchases");
    expect(screen.getByRole("link", { name: "Ver alertas" })).toHaveAttribute("href", "/alerts");
  });

  it("shows an error state when kpis fail", async () => {
    open(fakeApi({ getKpis: async () => { throw new Error("sin kpis"); } }));
    expect(await screen.findByRole("alert")).toHaveTextContent("sin kpis");
  });

  it("shows an empty state without a case", async () => {
    open(fakeApi({ listCases: async () => [] }));
    expect(await screen.findByText("Sin caso activo para esta sucursal")).toBeInTheDocument();
  });
});
