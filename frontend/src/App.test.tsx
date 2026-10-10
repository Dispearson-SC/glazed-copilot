import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "./ApiContext";
import App from "./App";
import { SessionProvider } from "./SessionContext";
import { splitStoreName } from "./format";
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

describe("App routes", () => {
  it("serves the dashboard at /", async () => {
    open();
    expect(await screen.findByTestId("hero")).toBeInTheDocument();
  });

  it("serves the login at /login", async () => {
    open("/login");
    expect(await screen.findByRole("button", { name: "Entrar al resumen" })).toBeInTheDocument();
  });

  it("serves the chat at /chat", async () => {
    open("/chat");
    expect(await screen.findByTestId("chat-header")).toBeInTheDocument();
  });

  it.each(["/alerts", "/cases", "/purchases", "/decisions", "/inventory", "/week", "/trace", "/stores/S030/trace"])(
    "sends the removed route %s to the dashboard",
    async (path) => {
      open(path);
      expect(await screen.findByTestId("hero")).toBeInTheDocument();
    },
  );
});

describe("top bar title", () => {
  it("shows the full store name and the page subtitle 'Resumen' (Main.dc.html)", async () => {
    const plain = { store_id: "S030", name: "Tienda Única", format: "mall", site_id: "X", region: "N", display_name: "Tienda Única" };
    open("/", fakeApi({ listStores: async () => [plain] }));
    const bar = await screen.findByRole("banner");
    expect(await within(bar).findByText("Tienda Única")).toBeInTheDocument();
    expect(within(bar).getByText("Resumen")).toBeInTheDocument();
  });

  it("splits only on the first separator", () => {
    expect(splitStoreName("A · B · C")).toEqual(["A", "B · C"]);
    expect(splitStoreName("Solo")).toEqual(["Solo", null]);
  });
});

describe("App shell", () => {
  it("shows the store display name in the top bar with the sign-in link", async () => {
    open();
    const bar = await screen.findByRole("banner");
    expect(await within(bar).findByText("Aeropuerto Norte · Glazed Centro")).toBeInTheDocument();
    expect(within(bar).getByText("Resumen")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Iniciar sesión" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("link", { name: "Cambiar sucursal" })).toBeNull();
  });

  it("marks the current page in the bottom navigation", async () => {
    open("/");
    expect(await screen.findByRole("link", { name: /Resumen/, current: "page" })).toHaveAttribute("href", "/");
  });

  it("the design's Chat entry opens /chat", async () => {
    open("/");
    await screen.findByRole("navigation", { name: "Navegación principal" });
    expect(screen.getByRole("link", { name: /Chat/ })).toHaveAttribute("href", "/chat");
  });
});

describe("copilot route", () => {
  it("serves /copiloto with the capsule navigation and the top bar", async () => {
    open("/copiloto");
    expect(await screen.findByRole("navigation", { name: "Ventanas del copiloto" })).toBeInTheDocument();
    expect(screen.getByText("Glazed Co.")).toBeInTheDocument();
  });
});
