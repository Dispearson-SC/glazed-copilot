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

  it("serves the store picker at /login", async () => {
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
  it("falls back to the full name and the page subtitle when there is no separator", async () => {
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
  it("links only the three remaining screens in the bottom navigation (Chat became Copiloto)", async () => {
    open();
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    const links = Array.from(nav.querySelectorAll("a")).map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([["dashboardResumen", "/"], ["forumCopiloto", "/copiloto"], ["storefrontSucursal", "/login"]]);
  });

  it("shows the store display name in the top bar and links to the picker", async () => {
    open();
    const bar = await screen.findByRole("banner");
    expect(await within(bar).findByText("Aeropuerto Norte")).toBeInTheDocument();
    expect(within(bar).getByText("Glazed Centro")).toBeInTheDocument();
    expect(within(bar).queryByText("Resumen")).toBeNull();
    expect(within(bar).queryByText(/·/)).toBeNull();
    expect(screen.getByRole("link", { name: "Cambiar sucursal" })).toHaveAttribute("href", "/login");
  });

  it("marks the current page in the bottom navigation", async () => {
    open("/");
    expect(await screen.findByRole("link", { name: /Resumen/, current: "page" })).toHaveAttribute("href", "/");
  });

  it("keeps the full chat reachable at /chat even though the nav now points to the copilot", async () => {
    open("/chat");
    expect(await screen.findByTestId("chat-header")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Copiloto/ })).toHaveAttribute("href", "/copiloto");
  });
});

describe("copilot route", () => {
  it("serves /copiloto with the capsule navigation and the top bar", async () => {
    open("/copiloto");
    expect(await screen.findByRole("navigation", { name: "Ventanas del copiloto" })).toBeInTheDocument();
    expect(screen.getByText("Glazed Co.")).toBeInTheDocument();
  });
});
