import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, useEffect, useState, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import { SessionProvider, useSession } from "./SessionContext";
import { caseA, fakeApi } from "./test/helpers";
import type { Case } from "./types";
import { pickCase, useCurrentCase } from "./useCurrentCase";

const D = "2026-07-19";
const mk = (id: string, over: Partial<Case> = {}): Case => ({ ...caseA, case_id: id, ...over });

describe("pickCase", () => {
  it("prefers the explicit id, then live at the default date, then any live, then the first", () => {
    const old = mk("old", { mode: "sandbox", sim_today: "2026-03-01" });
    const sandbox = mk("sb", { mode: "sandbox", sim_today: D });
    const liveOther = mk("lo", { sim_today: "2026-05-01" });
    const liveDef = mk("ld", { sim_today: D });
    expect(pickCase([old, sandbox, liveOther, liveDef], "old", D)?.case_id).toBe("old");
    expect(pickCase([old, sandbox, liveOther, liveDef], "", D)?.case_id).toBe("ld");
    expect(pickCase([old, sandbox, liveOther], "", D)?.case_id).toBe("lo");
    expect(pickCase([sandbox], "", D)?.case_id).toBe("sb");
    expect(pickCase([], "", D)).toBeNull();
  });

  it("picks the earliest created_at among several default-date live cases", () => {
    const b = mk("b", { sim_today: D, created_at: "2026-07-01T10:00:00Z" });
    const a = mk("z", { sim_today: D, created_at: "2026-07-01T09:00:00Z" });
    expect(pickCase([b, a], "", D)?.case_id).toBe("z");
  });
});

function Show() {
  const { currentCase } = useCurrentCase("S030");
  return <p data-testid="out">{currentCase?.case_id ?? "none"}</p>;
}

function Prefer({ id, children }: { id: string; children: ReactNode }) {
  const { setCaseId } = useSession();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setCaseId(id, "S030");
    setReady(true);
  }, [id, setCaseId]);
  return ready ? <>{children}</> : null;
}

const mount = (api: ReturnType<typeof fakeApi>, prefer = "", strict = false) => {
  const tree = (
    <ApiProvider api={api}>
      <SessionProvider>
        {prefer ? <Prefer id={prefer}><Show /></Prefer> : <Show />}
      </SessionProvider>
    </ApiProvider>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
};

describe("useCurrentCase default simulation date", () => {
  it("creates exactly one live case at the default date when missing, and uses it", async () => {
    const created = mk("new", { sim_today: D, title: `Demo ${D}` });
    let made = false;
    const api = fakeApi({
      listCases: vi.fn(async () => (made ? [caseA, created] : [caseA])),
      createCase: vi.fn(async () => {
        made = true;
        return created;
      }),
    });
    mount(api, "", true);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("new"));
    expect(api.createCase).toHaveBeenCalledTimes(1);
    expect(api.createCase).toHaveBeenCalledWith({ store_id: "S030", sim_today: D, mode: "live", title: `Demo ${D}` });
  });

  it("does not create when a live case at the default date exists", async () => {
    const api = fakeApi({ listCases: vi.fn(async () => [caseA, mk("ld", { sim_today: D })]) });
    mount(api);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("ld"));
    expect(api.createCase).not.toHaveBeenCalled();
  });

  it("does not create when the session has an explicit case", async () => {
    const api = fakeApi();
    mount(api, "c1");
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("c1"));
    expect(api.createCase).not.toHaveBeenCalled();
  });

  it("after creating, re-lists and picks deterministically if another tab created one too", async () => {
    const mine = mk("m2", { sim_today: D, created_at: "2026-07-01T10:00:01Z" });
    const theirs = mk("m1", { sim_today: D, created_at: "2026-07-01T10:00:00Z" });
    let made = false;
    const api = fakeApi({
      listCases: vi.fn(async () => (made ? [mine, theirs] : [])),
      createCase: vi.fn(async () => {
        made = true;
        return mine;
      }),
    });
    mount(api);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("m1"));
  });

  it("falls back to the old pick when creation fails", async () => {
    const api = fakeApi({ createCase: vi.fn(async () => { throw new Error("boom"); }) });
    mount(api);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("c1"));
  });
});

describe("useCurrentCase per-store choice", () => {
  const a1 = mk("a1", { store_id: "S030", sim_today: D, created_at: "2026-07-19T08:00:00Z" });
  const a2 = mk("a2", { store_id: "S030", sim_today: D, created_at: "2026-07-19T09:00:00Z" });
  const b1 = mk("b1", { store_id: "S031", sim_today: D, created_at: "2026-07-19T08:00:00Z" });
  const b2 = mk("b2", { store_id: "S031", sim_today: D, created_at: "2026-07-19T09:00:00Z" });

  function Harness() {
    const [store, setStore] = useState("S030");
    const { setCaseId } = useSession();
    const { currentCase } = useCurrentCase(store);
    return (
      <>
        <p data-testid="out">{currentCase?.case_id ?? "none"}</p>
        <button onClick={() => setCaseId("a2", "S030")}>choose a2</button>
        <button onClick={() => setStore("S031")}>to B</button>
        <button onClick={() => setStore("S030")}>to A</button>
      </>
    );
  }

  it("a case chosen in store A does not hide the remembered case of store B, and A's choice comes back", async () => {
    localStorage.setItem("glazed.caseId.S031", "b2");
    const api = fakeApi({ listCases: vi.fn(async (q: { store_id: string }) => (q.store_id === "S030" ? [a1, a2] : [b1, b2])) });
    render(
      <ApiProvider api={api}>
        <SessionProvider>
          <Harness />
        </SessionProvider>
      </ApiProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("a1"));
    await userEvent.click(screen.getByText("choose a2"));
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("a2"));
    await userEvent.click(screen.getByText("to B"));
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("b2"));
    await userEvent.click(screen.getByText("to A"));
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("a2"));
  });
});
