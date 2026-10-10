import { useEffect, useState, type FormEvent } from "react";
import { useApi } from "../ApiContext";
import { ApiError, type AuthUser, type DemoUser } from "../api";

const pill =
  "gc-field flex items-center gap-2 rounded-full border border-surface-container bg-surface px-4 py-3 focus-within:border-secondary focus-within:ring-2 focus-within:ring-on-tertiary-container/40";
const control = "min-w-0 flex-1 border-0 bg-transparent p-0 font-body-md text-[16px] text-on-surface outline-none placeholder:text-on-surface-variant/60";

function messageFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "Correo o contraseña incorrectos";
    if (e.status === 429) return "Demasiados intentos. Espera unos minutos.";
    if (e.status === 0) return "No se pudo conectar";
  }
  return "No se pudo conectar";
}

/** Login.dc.html. The page keeps the URL it was opened at; the gate returns to the app there once the session exists. */
export default function LoginPage({ onLogin, demo = false, loadFailed = false, onRetry }: { onLogin: (u: AuthUser) => void; demo?: boolean; loadFailed?: boolean; onRetry?: () => void }) {
  const api = useApi();
  const [users, setUsers] = useState<DemoUser[] | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [demoError, setDemoError] = useState("");
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    if (!demo) {
      setUsers(null);
      return;
    }
    let live = true;
    api.getDemoUsers().then(
      (u) => live && setUsers(Array.isArray(u) && u.length ? u : null),
      () => live && setUsers(null),
    );
    return () => {
      live = false;
    };
  }, [api, demo]);

  const picker = !!users;
  const formVisible = !picker || formOpen;

  async function pick(u: DemoUser) {
    if (pending) return;
    setDemoError("");
    setPending(u.email);
    try {
      const { user } = await api.demoLogin(u.email);
      onLogin(user);
    } catch (err) {
      setDemoError(err instanceof ApiError && err.status === 401 ? "Ese usuario ya no está disponible" : "No se pudo conectar");
      setPending(null);
    }
  }
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const f = e.currentTarget.elements as unknown as Record<string, HTMLInputElement>;
    const email = (f.email?.value ?? "").trim();
    const password = f.password?.value ?? "";
    if (!email || !password) {
      setError("Correo o contraseña incorrectos");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const { user } = await api.login({ email, password });
      onLogin(user);
    } catch (err) {
      setError(messageFor(err));
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface font-body-md text-body-md text-on-surface">
      <header className="fixed inset-x-0 top-0 z-40 bg-surface/[.85] pt-safe backdrop-blur-xl shadow-[0_1px_8px_rgba(75,48,37,.04)]">
        <div className="mx-auto flex h-16 max-w-[640px] items-center px-4">
          <div className="flex items-center gap-2">
            <img alt="Logo Glazed Co." src="/Logo.png" className="h-8 w-8 rounded-full object-contain" />
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm tracking-tight text-primary">Glazed Co.</span>
              <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">Copiloto</span>
            </div>
          </div>
        </div>
      </header>
      <main className="px-4 pb-24 pt-20">
        <div className="mx-auto flex w-full max-w-[480px] flex-col gap-4">
          <section className="relative overflow-hidden rounded-[20px] bg-primary-container p-6 text-white shadow-xl shadow-primary-container/20">
            <div aria-hidden="true" className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-secondary-container/10 blur-2xl"></div>
            <div aria-hidden="true" className="pointer-events-none absolute -bottom-12 -left-12 h-40 w-40 rounded-full bg-on-tertiary-container/10 blur-2xl"></div>
            <div className="relative z-10 flex flex-col gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-tertiary-fixed-dim">
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">coffee_maker</span>
              </div>
              <h1 className="m-0 font-headline-lg text-headline-lg tracking-tight">Pasa detrás de la barra</h1>
              <p className="m-0 font-body-md text-body-md text-surface-variant">Ingresa con tu cuenta de turno para ver el resumen de hoy.</p>
            </div>
          </section>
          {picker && (
            <section aria-label="Modo demo" className="rounded-[18px] border border-surface-container bg-white p-6 shadow-sm shadow-primary/5">
              <h2 className="m-0 font-headline-md text-headline-md tracking-tight text-primary" style={{ fontFamily: '"Playfair Display", serif' }}>Modo demo</h2>
              <p className="m-0 mt-1 font-body-md text-body-md text-on-surface-variant">Elige un usuario para entrar</p>
              <ul className="m-0 mt-4 flex list-none flex-col gap-3 p-0">
                {users!.map((u) => {
                  const loading = pending === u.email;
                  const stores = u.store_ids.length === 0 ? "Todas las sucursales" : u.store_ids.map((id) => `Sucursal ${id}`).join(", ");
                  const role = u.role === "admin" ? "Administrador" : "Gerente";
                  return (
                    <li key={u.email}>
                      <button
                        type="button"
                        aria-label={`Entrar como ${u.name}, ${role}`}
                        aria-busy={loading}
                        disabled={!!pending}
                        onClick={() => void pick(u)}
                        className="flex min-h-[44px] w-full items-center gap-3 rounded-[16px] border border-surface-container bg-surface px-4 py-3 text-left transition-all active:scale-[0.98] disabled:opacity-60"
                      >
                        <span aria-hidden="true" className="material-symbols-outlined text-[24px] text-secondary">{loading ? "hourglass_top" : u.role === "admin" ? "admin_panel_settings" : "storefront"}</span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="font-body-md text-body-md font-semibold text-on-surface">{loading ? "Entrando…" : u.name}</span>
                          <span className="font-label-sm text-label-sm text-on-surface-variant">{role}</span>
                          <span className="font-label-sm text-label-sm text-on-surface-variant">{stores}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {demoError && (
                <p role="alert" className="m-0 mt-3 rounded-[14px] border border-error/20 bg-error-container/40 px-4 py-2.5 font-body-md text-body-md text-on-error-container">
                  {demoError}
                </p>
              )}
              <button
                type="button"
                aria-expanded={formOpen}
                aria-controls="login-form"
                onClick={() => setFormOpen((v) => !v)}
                className="mt-4 min-h-[44px] w-full rounded-full bg-transparent px-3 font-body-md text-body-md font-semibold text-secondary underline underline-offset-2"
              >
                Entrar con correo y contraseña
              </button>
            </section>
          )}
          {formVisible && (
          <section id="login-form" className="rounded-[18px] border border-surface-container bg-white p-6 shadow-sm shadow-primary/5">
            {loadFailed && (
              <div role="alert" className="mb-4 flex items-center justify-between gap-2 rounded-[14px] border border-error/20 bg-error-container/40 px-4 py-2.5 text-on-error-container">
                <span>No se pudo conectar</span>
                <button type="button" onClick={onRetry} className="min-h-[44px] rounded-full bg-transparent px-3 font-semibold text-secondary underline underline-offset-2">
                  Reintentar
                </button>
              </div>
            )}
            <form className="m-0 flex flex-col gap-4" onSubmit={submit} noValidate>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="login-email" className="font-label-md text-label-md text-on-surface">Correo del turno</label>
                <div className={pill}>
                  <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">mail</span>
                  <input id="login-email" name="email" type="email" autoComplete="email" placeholder="turno@glazed.mx" className={control} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="login-password" className="font-label-md text-label-md text-on-surface">Contraseña</label>
                <div className={pill}>
                  <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">lock</span>
                  <input id="login-password" name="password" type={show ? "text" : "password"} autoComplete="current-password" placeholder="Escribe tu contraseña" className={control} />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-pressed={show}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-transparent p-0 text-on-surface-variant"
                  >
                    <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{show ? "visibility_off" : "visibility"}</span>
                  </button>
                </div>
              </div>
              {error && (
                <p role="alert" className="m-0 rounded-[14px] border border-error/20 bg-error-container/40 px-4 py-2.5 font-body-md text-body-md text-on-error-container">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-full bg-secondary px-4 py-3.5 font-body-md text-body-md font-semibold text-white shadow-md shadow-secondary/20 transition-all active:scale-[0.98] disabled:opacity-60"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{busy ? "hourglass_top" : "login"}</span>
                {busy ? "Verificando…" : "Entrar"}
              </button>
            </form>
          </section>
          )}
          <p className="m-0 text-center font-label-sm text-label-sm text-on-surface-variant">Al entrar aceptas el uso operativo del resumen de turno.</p>
        </div>
      </main>
    </div>
  );
}
