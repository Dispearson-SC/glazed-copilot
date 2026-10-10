import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy*/waitFor default to 1 s, which times out on a loaded CI/dev box; assertions are unchanged.
configure({ asyncUtilTimeout: 4000 });

afterEach(() => {
  cleanup();
  try { localStorage.clear(); } catch { /* ignore */ }
});
