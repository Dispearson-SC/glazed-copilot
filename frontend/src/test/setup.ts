import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy*/waitFor default to 1 s, which times out on a loaded CI/dev box; assertions are unchanged.
configure({ asyncUtilTimeout: 4000 });

afterEach(() => {
  cleanup();
  try { localStorage.clear(); } catch { /* ignore */ }
});

// jsdom has no media stack: inert stand-ins keep the voice UI mounted; voice tests install fakes of their own.
if (typeof MediaRecorder === "undefined") {
  class InertRecorder {
    static isTypeSupported = () => false;
    state = "inactive";
    start() { this.state = "recording"; }
    stop() { this.state = "inactive"; }
  }
  (globalThis as unknown as { MediaRecorder: unknown }).MediaRecorder = InertRecorder;
}
if (!navigator.mediaDevices) {
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: async () => ({ getTracks: () => [] }) } });
}
Object.defineProperty(HTMLMediaElement.prototype, "play", { configurable: true, value: () => Promise.resolve() });
Object.defineProperty(HTMLMediaElement.prototype, "pause", { configurable: true, value: () => {} });
