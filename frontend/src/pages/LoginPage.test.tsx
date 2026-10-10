import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "../ApiContext";
import { SessionProvider } from "../SessionContext";
import { fakeApi } from "../test/helpers";
import LoginPage from "./LoginPage";

const open = (api = fakeApi()) =>
  render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p data-testid="home">resumen</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );

/** Login.dc.html, element by element. */
describe("Login (/login) matches Login.dc.html", () => {
  it("header: logo, name, 'Resumen', Notificaciones and Iniciar sesión", async () => {
    open();
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByRole("img", { name: /Logo/ })).toBeInTheDocument();
    expect(within(bar).getByText("Resumen")).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: "Notificaciones" })).toBeInTheDocument();
    expect(within(bar).getByRole("link", { name: "Iniciar sesión" })).toBeInTheDocument();
  });

  it("hero card: coffee_maker icon, title and subtitle", () => {
    open();
    expect(screen.getByRole("heading", { name: "Pasa detrás de la barra" })).toBeInTheDocument();
    expect(screen.getByText("Ingresa con tu cuenta de turno para ver el resumen de hoy.")).toBeInTheDocument();
    expect(screen.getByText("coffee_maker")).toBeInTheDocument();
  });

  it("form: email and password fields with their icons, placeholders and the show-password toggle", async () => {
    open();
    const email = screen.getByLabelText("Correo del turno");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("placeholder", "turno@cafecentral.mx");
    const pw = screen.getByLabelText("Contraseña");
    expect(pw).toHaveAttribute("type", "password");
    expect(pw).toHaveAttribute("placeholder", "Escribe tu contraseña");
    const toggle = screen.getByRole("button", { name: "Mostrar contraseña" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(toggle);
    expect(pw).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Ocultar contraseña" })).toHaveAttribute("aria-pressed", "true");
  });

  it("remember checkbox (checked), forgot link, submit, divider, back link and footer note", () => {
    open();
    expect(screen.getByLabelText("Mantener el turno abierto")).toBeChecked();
    expect(screen.getByRole("link", { name: "¿Olvidaste la clave?" })).toHaveAttribute("href", "#");
    expect(screen.getByRole("button", { name: "Entrar al resumen" })).toBeEnabled();
    expect(screen.getByRole("link", { name: /Volver al resumen/ })).toHaveAttribute("href", "/resumen");
    expect(screen.getByText("Al entrar aceptas el uso operativo del resumen de turno.")).toBeInTheDocument();
  });

  it("shows the design's error for an invalid email or a short password and does not leave the page", async () => {
    open();
    await userEvent.type(screen.getByLabelText("Correo del turno"), "nope");
    await userEvent.type(screen.getByLabelText("Contraseña"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "Entrar al resumen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Revisa el correo o la contraseña e inténtalo de nuevo.");
    expect(screen.queryByTestId("home")).toBeNull();
  });

  it("verifies ('Verificando…') and then goes to the summary with a valid email and password", async () => {
    open();
    await userEvent.type(screen.getByLabelText("Correo del turno"), "turno@cafecentral.mx");
    await userEvent.type(screen.getByLabelText("Contraseña"), "clave1234");
    await userEvent.click(screen.getByRole("button", { name: "Entrar al resumen" }));
    expect(await screen.findByRole("button", { name: "Verificando…" })).toBeDisabled();
    expect(await screen.findByTestId("home", {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("has no bottom navigation and none of the legacy store/case picker", () => {
    open();
    expect(screen.queryByRole("navigation")).toBeNull();
    for (const legacy of [/Elige tu sucursal/, /Selecciona la sucursal/, /Sin credenciales/, /proxy/i]) expect(screen.queryByText(legacy)).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByLabelText("Sucursal")).toBeNull();
    expect(screen.queryByLabelText("Caso")).toBeNull();
  });
});
