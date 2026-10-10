import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, renderPage } from "../test/helpers";
import DashboardPage from "./DashboardPage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <DashboardPage />);

/** Main.dc.html, element by element. */
describe("Main (/) matches Main.dc.html", () => {
  it("top bar: logo, store name, 'Resumen', Notificaciones button and the Iniciar sesión link", async () => {
    open();
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByRole("img", { name: /Logo/ })).toBeInTheDocument();
    expect(await within(bar).findByText("Aeropuerto Norte · Glazed Centro")).toBeInTheDocument();
    expect(within(bar).getByText("Resumen")).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: "Notificaciones" })).toBeInTheDocument();
    expect(within(bar).getByRole("link", { name: "Iniciar sesión" })).toHaveAttribute("href", "/login");
  });

  it("live badge, clock, title and date line", async () => {
    open();
    expect(await screen.findByText("En vivo • Sin datos")).toBeInTheDocument();
    expect(screen.getByTestId("sim-clock")).toHaveTextContent("Sin datos");
    expect(screen.getByRole("heading", { name: "Resumen de hoy" })).toBeInTheDocument();
    expect(screen.getByText("Domingo, 1 De Marzo 2026")).toBeInTheDocument();
  });

  it("hero: sales, delta vs ayer, design caption, daily goal and progress", async () => {
    open();
    const hero = await screen.findByTestId("hero");
    expect(within(hero).getByText("Ventas de hoy")).toBeInTheDocument();
    expect(await within(hero).findByText("$733.91")).toBeInTheDocument();
    expect(within(hero).getByTestId("hero-delta")).toHaveTextContent("vs ayer");
    expect(within(hero).getByText("Corte parcial estimado del salón y pedidos en mostrador")).toBeInTheDocument();
    expect(within(hero).getByText("Meta diaria: Sin datos")).toBeInTheDocument();
    expect(within(hero).getByTestId("hero-progress")).toHaveTextContent("Sin datos");
  });

  it("computes the delta against yesterday's day summary", async () => {
    const getDaySummary = vi.fn(async (_c: string, date?: string) => ({
      store_id: "S030", date: date ?? "", as_of: "2026-03-01", totals: { net_sales: date === "2026-02-28" ? 500 : 600, transactions: 10, units_sold: 20 }, top_skus: [],
    }));
    open(fakeApi({ getDaySummary }));
    expect(await screen.findByTestId("hero-delta")).toHaveTextContent("+20% vs ayer");
    expect(getDaySummary).toHaveBeenCalledWith("c1", "2026-02-28");
  });

  it("three metric cards", async () => {
    open();
    await screen.findByTestId("metric-transactions");
    expect(screen.getByTestId("metric-transactions")).toHaveTextContent("Pedidos realizados");
    expect(screen.getByTestId("metric-avg-ticket")).toHaveTextContent("Ticket promedio");
    expect(screen.getByTestId("metric-units")).toHaveTextContent("Items vendidos");
  });

  it("'Actividad de hoy': hourly chart structure with 'Sin datos' (the backend has no hourly data)", async () => {
    open();
    const section = (await screen.findByRole("heading", { name: "Actividad de hoy" })).closest("section")!;
    expect(within(section).getByText("Distribución de ingresos y afluencia por hora")).toBeInTheDocument();
    expect(within(section).getByText("Intervalo 2h")).toBeInTheDocument();
    expect(within(section).getByTestId("activity-pill")).toHaveTextContent("Sin datos");
    for (const h of ["07h", "09h", "11h", "13h", "15h", "17h", "19h"]) expect(within(section).getByText(h)).toBeInTheDocument();
    expect(within(section).getByText("Pico registrado (mañana)")).toBeInTheDocument();
    expect(within(section).getByText("Turno actual")).toBeInTheDocument();
  });

  it("'Favoritos de hoy': heading, subtitle, Top 3 and the three product cards", async () => {
    open();
    expect(await screen.findByRole("heading", { name: "Favoritos de hoy" })).toBeInTheDocument();
    expect(screen.getByText("Bebidas con mayor rotación en barra")).toBeInTheDocument();
    expect(screen.getByText("Top 3")).toBeInTheDocument();
    expect(await screen.findByTestId("top-product-1")).toHaveTextContent("50 Donut Holes");
    expect(screen.getByTestId("top-product-3")).toBeInTheDocument();
    expect(screen.queryByTestId("top-product-4")).toBeNull();
  });

  it("report and close-shift buttons (disabled: no backend route) and the sync line", async () => {
    open();
    expect(await screen.findByRole("button", { name: /Descargar reporte del día \(PDF\)/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Cerrar turno de caja/ })).toBeDisabled();
    expect(await screen.findByText(/Última sincronización automática hace \d+ min/)).toBeInTheDocument();
  });

  it("floating chat: the FAB opens the 'Chat del turno' panel with its design parts", async () => {
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    expect(within(panel).getByText("Chat del turno")).toBeInTheDocument();
    expect(within(panel).getByText("Sin agente conectado")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Cerrar chat" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "¿Cómo van las ventas?" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Dame el ticket promedio" })).toBeInTheDocument();
    expect(within(panel).getByLabelText("Escribe un mensaje")).toHaveAttribute("placeholder", "Escribe un mensaje…");
    expect(within(panel).getByRole("link", { name: /Abrir chat completo/ })).toHaveAttribute("href", "/chat");
  });

  it("bottom navigation: exactly Resumen, Pedidos, Productos, Chat, Ajustes", async () => {
    open();
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual(["dashboardResumen", "receipt_longPedidos", "local_cafeProductos", "chatChat", "tuneAjustes"]);
    expect(within(nav).getByRole("link", { name: /Resumen/ })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /Chat/ })).toHaveAttribute("href", "/chat");
  });

  it("has none of the legacy elements", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("hero");
    for (const legacy of [/Fecha simulada/, /Cambiar de sucursal/, /Modelo de proyección/, /Preguntar al asistente/, /Ventas por día/, /Proyección/, /Lo que viene/, /Lo que se pierde/, /abiertas/, /Datos al /, /Copiloto/, /Intervalo 1 día/, /vs promedio/]) {
      expect(screen.queryByText(legacy)).toBeNull();
    }
    expect(screen.queryByRole("link", { name: /Copiloto/ })).toBeNull();
    expect(api.getForecast).not.toHaveBeenCalled();
  });
});
