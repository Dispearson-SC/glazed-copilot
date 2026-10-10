import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import { AuthGate, scopeStores } from "./AuthContext";
import App from "./App";
import { ApiError, type AuthUser } from "./api";
import { SessionProvider } from "./SessionContext";
import { fakeApi, store, store2 } from "./test/helpers";

const manager: AuthUser = { user_id: "u1", email: "m@x.mx", name: "Marta Gerente", role: "manager", store_ids: ["S030", "S031"] };
const admin: AuthUser = { ...manager, role: "admin", name: "Ada Admin", store_ids: [] };

function open(api: ReturnType<typeof fakeApi>, path = "/copiloto") {
  return render(
    <ApiProvider api={api}>
      <MemoryRouter initialEntries={[path]}>
        <AuthGate>
          <SessionProvider>
            <App />
          </SessionProvider>
        </AuthGate>
      </MemoryRouter>
    </ApiProvider>,
  );
}
const nav = () => screen.findByRole("navigation", { name: "Ventanas del copiloto" });
const unauth = () => new ApiError(401, "no");

async function fill(email = "m@x.mx", pw = "secreto") {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Correo del turno"), email);
  await user.type(screen.getByLabelText("Contraseña"), `${pw}{Enter}`);
}

describe("auth gate", () => {
  it("auth_required with me 200 shows the app and the user", async () => {
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: manager })) }));
    await nav();
    await userEvent.click(screen.getByRole("button", { name: "Ajustes del copiloto" }));
    expect(screen.getByText("Marta Gerente")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Cerrar sesión/ })).toBeInTheDocument();
  });

  it("auth_required with me 401 shows the login", async () => {
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => { throw unauth(); }) }));
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Ventanas del copiloto" })).toBeNull();
    expect(screen.queryByText(/Olvidaste|Volver al resumen|Recordarme/)).toBeNull();
  });

  it.each([404, 501])("auth_required with me %i treats auth as disabled", async (code) => {
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => { throw new ApiError(code, "x"); }) }));
    await nav();
  });

  it("auth_required false ignores a 401 from me and hides user UI", async () => {
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: false })), me: vi.fn(async () => { throw unauth(); }) }));
    await nav();
    expect(screen.queryByLabelText("Correo del turno")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Ajustes del copiloto" }));
    expect(screen.queryByText(/Cerrar sesión/)).toBeNull();
  });

  it("missing field or failing health means no login and no logout UI", async () => {
    open(fakeApi({ getHealth: vi.fn(async () => { throw new ApiError(0, "down"); }), me: vi.fn(async () => { throw new ApiError(404, "x"); }) }));
    await nav();
    expect(screen.queryByText(/Cerrar sesión/)).toBeNull();
  });

  it("auth_required false but me 200 still shows the user", async () => {
    open(fakeApi({ me: vi.fn(async () => ({ user: admin })) }));
    await nav();
    await userEvent.click(screen.getByRole("button", { name: "Ajustes del copiloto" }));
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
  });

  it("a network error on me shows the login with a retry", async () => {
    const me = vi.fn().mockRejectedValueOnce(new ApiError(0, "x")).mockResolvedValue({ user: manager });
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me }));
    await userEvent.click(await screen.findByRole("button", { name: "Reintentar" }));
    await nav();
  });

  it("shows a splash while checking", () => {
    open(fakeApi({ getHealth: vi.fn(() => new Promise(() => {})) }));
    expect(screen.getByRole("status", { name: "Cargando sesión" })).toBeInTheDocument();
  });
});

describe("login form", () => {
  const needLogin = (login: unknown) =>
    fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => { throw unauth(); }), login });

  it("signs in and opens the app", async () => {
    const login = vi.fn(async () => ({ user: manager }));
    open(needLogin(login));
    await fill();
    await nav();
    expect(login).toHaveBeenCalledWith({ email: "m@x.mx", password: "secreto" });
  });

  it("401 shows the generic error", async () => {
    open(needLogin(vi.fn(async () => { throw unauth(); })));
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos");
  });

  it("429 shows the rate-limit error", async () => {
    open(needLogin(vi.fn(async () => { throw new ApiError(429, "x"); })));
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiados intentos. Espera unos minutos.");
  });

  it("a network error shows the connection error", async () => {
    open(needLogin(vi.fn(async () => { throw new ApiError(0, "x"); })));
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");
  });

  it("the password can be shown and the inputs avoid iOS zoom", async () => {
    open(needLogin(vi.fn()));
    const pw = await screen.findByLabelText("Contraseña");
    expect(pw).toHaveAttribute("type", "password");
    expect(pw).toHaveAttribute("autocomplete", "current-password");
    expect(pw.className).toContain("text-[16px]");
    await userEvent.click(screen.getByRole("button", { name: "Mostrar contraseña" }));
    expect(pw).toHaveAttribute("type", "text");
  });
});

describe("session", () => {
  it("a later 401 returns to the login", async () => {
    const api = fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: manager })) });
    open(api);
    await nav();
    const cb = (api.setOnUnauthorized as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]).filter(Boolean).pop();
    cb();
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
  });

  it("logout calls the API and shows the login", async () => {
    const api = fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: manager })) });
    open(api);
    await nav();
    await userEvent.click(screen.getByRole("button", { name: "Ajustes del copiloto" }));
    await userEvent.click(screen.getByRole("menuitem", { name: /Cerrar sesión/ }));
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
    expect(api.logout).toHaveBeenCalled();
  });
});

describe("store scoping", () => {
  it("filters the list for a manager", async () => {
    const one = { ...manager, store_ids: ["S031"] };
    const two = { ...manager, store_ids: ["S030", "S031"] };
    const api = fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: two })), listStores: vi.fn(async () => [store, store2, { ...store, store_id: "S099", display_name: "Otra · Tienda" }]) });
    open(api);
    await userEvent.click(await screen.findByRole("button", { name: "Cambiar sucursal" }));
    const dlg = await screen.findByRole("dialog", { name: "Elegir sucursal" });
    await waitFor(() => expect(dlg.querySelectorAll("li button").length).toBe(2));
    expect(dlg).not.toHaveTextContent("Otra · Tienda");
    expect(one.store_ids).toHaveLength(1);
  });

  it("a single store is read-only", async () => {
    const one = { ...manager, store_ids: ["S031"] };
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: one })) }));
    await nav();
    expect(screen.queryByRole("button", { name: "Cambiar sucursal" })).toBeNull();
  });

  it("admins see every store", async () => {
    open(fakeApi({ getHealth: vi.fn(async () => ({ auth_required: true })), me: vi.fn(async () => ({ user: admin })) }));
    await userEvent.click(await screen.findByRole("button", { name: "Cambiar sucursal" }));
    const dlg = await screen.findByRole("dialog", { name: "Elegir sucursal" });
    await waitFor(() => expect(dlg.querySelectorAll("li button").length).toBe(2));
  });
});

describe("scopeStores fails closed for managers", () => {
  const stores = [{ store_id: "S001" }, { store_id: "S002" }] as Parameters<typeof scopeStores>[0];
  it("a manager with no assigned stores sees none", () => {
    expect(scopeStores(stores, { user_id: "u", email: "m@x", name: "M", role: "manager", store_ids: [] })).toEqual([]);
  });
  it("an admin with an empty list sees all stores", () => {
    expect(scopeStores(stores, { user_id: "a", email: "a@x", name: "A", role: "admin", store_ids: [] })).toHaveLength(2);
  });
  it("a manager sees only the assigned stores", () => {
    expect(scopeStores(stores, { user_id: "u", email: "m@x", name: "M", role: "manager", store_ids: ["S002"] }).map((s) => s.store_id)).toEqual(["S002"]);
  });
});

describe("demo picker", () => {
  const users = [
    { email: "admin@demo.mx", name: "Admin Demo", role: "admin" as const, store_ids: [] },
    { email: "s1@demo.mx", name: "Gerente S001", role: "manager" as const, store_ids: ["S001"] },
  ];
  const gated = (over: Record<string, unknown> = {}, demo = true) =>
    fakeApi({
      getHealth: vi.fn(async () => ({ auth_required: true, demo_login: demo })),
      me: vi.fn(async () => { throw unauth(); }),
      getDemoUsers: vi.fn(async () => users),
      ...over,
    });

  it("shows the picker with roles and stores, form collapsed", async () => {
    const api = gated();
    open(api);
    expect(await screen.findByText("Elige un usuario para entrar")).toBeInTheDocument();
    expect(screen.getByText("Todas las sucursales")).toBeInTheDocument();
    expect(screen.getByText("Sucursal S001")).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();
    expect(screen.queryByLabelText("Correo del turno")).toBeNull();
    expect(api.listStores).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Entrar con correo y contraseña" }));
    expect(screen.getByLabelText("Correo del turno")).toBeInTheDocument();
  });

  it("the hero subtitle points to today's decisions", async () => {
    open(gated());
    expect(await screen.findByText("Ingresa para ver las decisiones de hoy.")).toBeInTheDocument();
  });

  it("is hidden and the form expanded when demo_login is false or users 404", async () => {
    open(gated({}, false));
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
    expect(screen.queryByText("Elige un usuario para entrar")).toBeNull();
  });

  it("falls back to the form when demo-users 404s", async () => {
    open(gated({ getDemoUsers: vi.fn(async () => { throw new ApiError(404, "x"); }) }));
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
    expect(screen.queryByText("Elige un usuario para entrar")).toBeNull();
  });

  it("one tap logs in and enters the app", async () => {
    const demoLogin = vi.fn(async () => ({ user: manager }));
    open(gated({ demoLogin }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Gerente S001/ }));
    await nav();
    expect(demoLogin).toHaveBeenCalledWith("s1@demo.mx");
  });

  it("401 shows the unavailable message and re-enables the cards", async () => {
    open(gated({ demoLogin: vi.fn(async () => { throw unauth(); }) }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Admin Demo/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ese usuario ya no está disponible");
    expect(screen.getByRole("button", { name: /Entrar como Admin Demo/ })).toBeEnabled();
  });

  it("a network error shows the connection message", async () => {
    open(gated({ demoLogin: vi.fn(async () => { throw new ApiError(0, "x"); }) }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Admin Demo/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");
  });

  it.each([
    [404, "El modo demo está desactivado"],
    [429, "Demasiados intentos. Espera unos minutos."],
    [500, "No se pudo iniciar sesión"],
  ])("demo login %i shows its own message", async (status, text) => {
    open(gated({ demoLogin: vi.fn(async () => { throw new ApiError(status, "x"); }) }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Admin Demo/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(text);
  });

  it("a non-API error in demo login falls back to the generic message", async () => {
    open(gated({ demoLogin: vi.fn(async () => { throw new Error("boom"); }) }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Admin Demo/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo iniciar sesión");
  });

  it("a gate error with the picker shown keeps the alert and Reintentar visible, outside the collapsed form", async () => {
    let fail = true;
    const me = vi.fn(async () => { if (fail) throw new ApiError(500, "down"); throw unauth(); });
    open(gated({ me }));
    expect(await screen.findByText("Elige un usuario para entrar")).toBeInTheDocument();
    expect(screen.queryByLabelText("Correo del turno")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo conectar");
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(me).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Reintentar" })).toBeNull());
  });

  it("disables the other cards while pending", async () => {
    open(gated({ demoLogin: vi.fn(() => new Promise(() => {})) }));
    await userEvent.click(await screen.findByRole("button", { name: /Entrar como Admin Demo/ }));
    expect(screen.getByRole("button", { name: /Entrar como Gerente S001/ })).toBeDisabled();
  });

  it("logout returns to the login with the picker", async () => {
    let signed = true;
    const api = gated({ me: vi.fn(async () => { if (signed) return { user: manager }; throw unauth(); }) });
    open(api);
    await nav();
    signed = false;
    await userEvent.click(screen.getByRole("button", { name: "Ajustes del copiloto" }));
    await userEvent.click(screen.getByRole("menuitem", { name: /Cerrar sesión/ }));
    expect(await screen.findByText("Elige un usuario para entrar")).toBeInTheDocument();
  });

  it("a 401 from /stores on first load routes to the login", async () => {
    const api = fakeApi({
      getHealth: vi.fn(async () => ({ auth_required: true })),
      me: vi.fn(async () => ({ user: manager })),
      listStores: vi.fn(async () => {
        (api.setOnUnauthorized as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]).filter(Boolean).pop()?.();
        throw unauth();
      }),
    });
    open(api);
    expect(await screen.findByLabelText("Correo del turno")).toBeInTheDocument();
  });
});
