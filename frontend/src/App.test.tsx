import { render, screen } from "@testing-library/react";
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

describe("App shell", () => {
  it("links only the three remaining screens in the bottom navigation", async () => {
    open();
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    const links = Array.from(nav.querySelectorAll("a")).map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([["dashboardResumen", "/"], ["chatChat", "/chat"], ["storefrontSucursal", "/login"]]);
  });

  it("shows the store display name in the top bar and links to the picker", async () => {
    open();
    const bar = await screen.findByRole("banner");
    expect(await screen.findByText("Aeropuerto Norte · Glazed Centro", { selector: "header span" })).toBeInTheDocument();
    expect(bar).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cambiar sucursal" })).toHaveAttribute("href", "/login");
  });

  it("marks the current page in the bottom navigation", async () => {
    open("/chat");
    expect(await screen.findByRole("link", { name: /Chat/, current: "page" })).toHaveAttribute("href", "/chat");
  });
});
