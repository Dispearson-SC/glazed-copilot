import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import PageShell from "../components/PageShell";

const pill =
  "gc-field flex items-center gap-2 rounded-full border border-surface-container bg-surface px-4 py-3 focus-within:border-secondary focus-within:ring-2 focus-within:ring-on-tertiary-container/40";
const control = "flex-1 min-w-0 bg-transparent outline-none font-body-md text-body-md text-on-surface";
const BUSY_MS = 1200;

/** Login.dc.html. Access control is the reverse proxy's basic auth: the form only validates its fields, then opens the summary. */
export default function LoginPage() {
  const navigate = useNavigate();
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!busy) return;
    const id = setTimeout(() => navigate("/"), BUSY_MS);
    return () => clearTimeout(id);
  }, [busy, navigate]);

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = e.currentTarget.elements as unknown as Record<string, HTMLInputElement>;
    const email = (f.email?.value ?? "").trim();
    const pw = f.password?.value ?? "";
    if (!/.+@.+\..+/.test(email) || pw.length < 4) {
      setError(true);
      return;
    }
    setError(false);
    setBusy(true);
  }

  return (
    <PageShell nav={false} columnClass="flex flex-col w-full max-w-[480px] mx-auto gap-space-md pt-space-xs">
      <section className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20">
        <div aria-hidden="true" className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
        <div aria-hidden="true" className="absolute -left-12 -bottom-12 w-40 h-40 rounded-full bg-on-tertiary-container/10 blur-2xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col gap-space-sm">
          <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">coffee_maker</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg tracking-tight">Pasa detrás de la barra</h1>
          <p className="font-body-md text-body-md text-surface-variant">Ingresa con tu cuenta de turno para ver el resumen de hoy.</p>
        </div>
      </section>
      <section className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 border border-surface-container">
        <form className="flex flex-col gap-space-md" onSubmit={submit} noValidate>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-email" className="font-label-md text-label-md text-on-surface">Correo del turno</label>
            <div className={pill}>
              <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">mail</span>
              <input id="login-email" name="email" type="email" autoComplete="email" placeholder="turno@cafecentral.mx" className={control} />
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
                className="w-9 h-9 flex items-center justify-center rounded-full bg-transparent p-0 text-on-surface-variant"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{show ? "visibility_off" : "visibility"}</span>
              </button>
            </div>
          </div>
          {error && (
            <p role="alert" className="m-0 rounded-[14px] border border-error/20 bg-error-container/40 px-4 py-2.5 font-body-md text-body-md text-on-error-container">
              Revisa el correo o la contraseña e inténtalo de nuevo.
            </p>
          )}
          <div className="flex items-center justify-between gap-2">
            <label htmlFor="login-remember" className="flex items-center gap-2 cursor-pointer font-body-md text-body-md text-on-surface">
              <input id="login-remember" type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="w-4 h-4 m-0 accent-secondary" />
              Mantener el turno abierto
            </label>
            <a href="#" className="font-body-md text-body-md text-secondary underline underline-offset-2">¿Olvidaste la clave?</a>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full py-3.5 px-space-md bg-secondary text-surface-container-lowest font-body-md text-body-md font-semibold rounded-full flex items-center justify-center gap-2 shadow-md shadow-secondary/20 hover:bg-primary transition-all active:scale-[0.98] disabled:opacity-60"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{busy ? "hourglass_top" : "login"}</span>
            {busy ? "Verificando…" : "Entrar al resumen"}
          </button>
        </form>
        <div className="my-space-md border-t border-surface-container"></div>
        <Link
          to="/resumen"
          className="w-full py-3 px-space-md bg-surface-container-high text-primary font-body-md text-body-md font-medium rounded-full flex items-center justify-center gap-2 hover:bg-surface-variant transition-all active:scale-[0.98]"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">arrow_back</span>
          Volver al resumen
        </Link>
      </section>
      <p className="text-center font-label-sm text-label-sm text-on-surface-variant">Al entrar aceptas el uso operativo del resumen de turno.</p>
    </PageShell>
  );
}
