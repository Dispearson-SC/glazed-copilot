import { render, screen } from "@testing-library/react";
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
  it("opens the copilot by default at /", async () => {
    open();
    expect(await screen.findByRole("navigation", { name: "Ventanas del copiloto" })).toBeInTheDocument();
  });

  it.each(["/alerts", "/cases", "/purchases", "/decisions", "/inventory", "/week", "/trace", "/stores/S030/trace"])(
    "sends the removed route %s to the copilot",
    async (path) => {
      open(path);
      expect(await screen.findByRole("navigation", { name: "Ventanas del copiloto" })).toBeInTheDocument();
    },
  );
});

describe("store name helper", () => {
  it("splits only on the first separator", () => {
    expect(splitStoreName("A · B · C")).toEqual(["A", "B · C"]);
    expect(splitStoreName("Solo")).toEqual(["Solo", null]);
  });
});
