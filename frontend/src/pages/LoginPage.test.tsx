import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "../ApiContext";
import { SessionProvider, useSession } from "../SessionContext";
import { caseA, fakeApi, store2 } from "../test/helpers";
import LoginPage from "./LoginPage";

function Probe() {
  const s = useSession();
  return <p data-testid="home">{`home:${s.storeId}:${s.caseId}`}</p>;
}

const open = (api = fakeApi()) =>
  render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Probe />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );

describe("LoginPage (store and case picker)", () => {
  it("has no credential fields", async () => {
    open();
    await screen.findByRole("option", { name: "Aeropuerto Norte · Glazed Centro" });
    expect(screen.queryByLabelText(/contraseña|correo/i)).toBeNull();
  });

  it("lists stores by display name and the cases of the chosen store", async () => {
    const api = fakeApi({
      listCases: async (q: { store_id?: string }) =>
        q.store_id === "S031" ? [{ ...caseA, case_id: "c9", store_id: "S031", title: "Caso norte" }] : [caseA],
    });
    open(api);
    await screen.findByRole("option", { name: "Caso uno" });
    await userEvent.selectOptions(screen.getByLabelText("Sucursal"), "S031");
    expect(await screen.findByRole("option", { name: "Caso norte" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Plaza Sur · Glazed Norte" })).toBeInTheDocument();
    expect(store2.store_id).toBe("S031");
  });

  it("preselects the live case at the default simulation date", async () => {
    const api = fakeApi({
      listCases: async () => [caseA, { ...caseA, case_id: "cd", title: "Demo", sim_today: "2026-07-19" }],
    });
    open(api);
    await screen.findByRole("option", { name: "Demo" });
    expect(screen.getByLabelText("Caso")).toHaveValue("cd");
  });

  it("stores the choice in the session and goes home", async () => {
    open();
    await screen.findByRole("option", { name: "Caso uno" });
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByTestId("home")).toHaveTextContent("home:S030:c1");
  });

  it("shows an error when stores cannot be loaded", async () => {
    open(fakeApi({ listStores: async () => { throw new Error("sin red"); } }));
    expect(await screen.findByRole("alert")).toHaveTextContent("sin red");
  });
});
