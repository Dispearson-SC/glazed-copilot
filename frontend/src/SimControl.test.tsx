import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import SimControl from "./SimControl";
import { caseA, fakeApi, renderPage } from "./test/helpers";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <SimControl />);

describe("SimControl", () => {
  it("shows the simulated date of the current case", async () => {
    open();
    expect(await screen.findByText(/2026-03-01/)).toBeInTheDocument();
  });

  it("advances one day and shows the new date", async () => {
    const api = fakeApi();
    open(api);
    await userEvent.click(await screen.findByRole("button", { name: "Avanzar 1 día" }));
    expect(api.advance).toHaveBeenCalledWith("c1", 1);
    expect(await screen.findByText(/2026-03-02/)).toBeInTheDocument();
  });

  it("prefers a live case", async () => {
    const api = fakeApi({ listCases: async () => [{ ...caseA, case_id: "sb", mode: "sandbox" }, caseA] });
    open(api);
    await userEvent.click(await screen.findByRole("button", { name: "Avanzar 1 día" }));
    await waitFor(() => expect(api.advance).toHaveBeenCalledWith("c1", 1));
  });

  it("shows an empty state without cases", async () => {
    open(fakeApi({ listCases: async () => [] }));
    expect(await screen.findByText("Sin caso activo")).toBeInTheDocument();
  });

  it("shows an error if advancing fails", async () => {
    open(fakeApi({ advance: async () => { throw new Error("nope"); } }));
    await userEvent.click(await screen.findByRole("button", { name: "Avanzar 1 día" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nope");
  });
});
