import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { ApiProvider } from "../ApiContext";
import { ApiError } from "../api";
import { buildPendingItems } from "../data/copilot";
import Toast from "../components/copilot/Toast";
import AgentWindow from "../components/copilot/AgentWindow";
import { CopilotProvider, useCopilot } from "../state/copilotStore";
import { pendingA } from "../test/copilotFixtures";
import { fakeApi } from "../test/helpers";
import type { ChatMessage } from "../chatHistory";
import type { VoiceConfig } from "../types";
import type { useChat } from "../useChat";
import { stripMarkdown } from "./markdown";

const items = buildPendingItems(pendingA, "2026-07-19");
const props = { caseId: "c1", items, pendingLine: "x", onApprove: () => {}, onReject: () => {} };
const cfg = (over: Partial<VoiceConfig> = {}): VoiceConfig => ({ enabled: true, stt: true, tts: true, voice_id: "v", max_seconds: 60, ...over });

type Chat = ReturnType<typeof useChat>;
const chatOf = (over: Partial<Chat> = {}): Chat => ({
  messages: [], status: "idle", stillRunning: false, progress: [], proposals: [], decisionError: null,
  send: vi.fn(async () => {}), retry: vi.fn(async () => {}), decide: vi.fn(async () => {}), ...over,
}) as Chat;

// --- fakes -------------------------------------------------------------------------------------------------
class FakeRecorder {
  static instances: FakeRecorder[] = [];
  static isTypeSupported = vi.fn((m: string) => m === "audio/webm;codecs=opus");
  static reset = () => FakeRecorder.isTypeSupported.mockImplementation((m: string) => m === "audio/webm;codecs=opus");
  state = "inactive";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor(public stream: unknown, opts?: { mimeType?: string }) {
    this.mimeType = opts?.mimeType ?? "";
    FakeRecorder.instances.push(this);
  }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["abc"]) });
    this.onstop?.();
  }
}

class FakeAudio {
  static instances: FakeAudio[] = [];
  src = "";
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  play = vi.fn(async () => {});
  pause = vi.fn();
  constructor() { FakeAudio.instances.push(this); }
}

class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = "";
  continuous = false;
  interimResults = false;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  abort = vi.fn();
  stop = vi.fn(() => this.onend?.());
  constructor() { FakeRecognition.instances.push(this); }
  say(text: string) { this.onresult?.({ results: [{ isFinal: true, 0: { transcript: text } }] }); }
}

let now = 1_000_000;
const trackStop = vi.fn();
const getUserMedia = vi.fn();

function ToastProbe() {
  const { state } = useCopilot();
  return <Toast text={state.toast} />;
}
const wrapWith = (api: ReturnType<typeof fakeApi>) => ({ children }: { children: ReactNode }) => (
  <ApiProvider api={api}>
    <CopilotProvider>
      {children}
      <ToastProbe />
    </CopilotProvider>
  </ApiProvider>
);

beforeEach(() => {
  now = 1_000_000;
  vi.spyOn(Date, "now").mockImplementation(() => now);
  FakeRecorder.instances = [];
  FakeAudio.instances = [];
  FakeRecognition.instances = [];
  trackStop.mockClear();
  getUserMedia.mockReset().mockImplementation(async () => ({ getTracks: () => [{ stop: trackStop }] }));
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal("Audio", FakeAudio);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  URL.createObjectURL = vi.fn(() => "blob:voice");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete (window as unknown as Record<string, unknown>).SpeechRecognition;
  delete (window as unknown as Record<string, unknown>).speechSynthesis;
});

const mic = () => screen.queryByRole("button", { name: "Hablar con el copiloto" });
async function ready(api: ReturnType<typeof fakeApi>, chat = chatOf()) {
  const utils = render(<AgentWindow chat={chat} {...props} />, { wrapper: wrapWith(api) });
  await waitFor(() => expect(api.getVoiceConfig).toHaveBeenCalled());
  await act(async () => {});
  return utils;
}
/** Hold the mic for `ms` and release. */
async function hold(ms = 1500) {
  const m = mic()!;
  fireEvent.pointerDown(m, { button: 0 });
  await waitFor(() => expect(FakeRecorder.instances.length + FakeRecognition.instances.length).toBeGreaterThan(0));
  now += ms;
  fireEvent.pointerUp(m);
}

describe("push-to-talk (backend STT)", () => {
  it("hold then release transcribes and sends the text as a normal message", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "¿Qué pido hoy?" })) });
    const chat = chatOf();
    await ready(api, chat);
    fireEvent.pointerDown(mic()!, { button: 0 });
    expect(await screen.findByText(/Escuchando… 0:00/)).toBeInTheDocument();
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(1));
    expect(FakeRecorder.instances[0].mimeType).toBe("audio/webm;codecs=opus");
    now += 2000;
    fireEvent.pointerUp(mic()!);
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("¿Qué pido hoy?", undefined));
    const [blob, name] = (api.transcribe as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(name).toBe("voice.webm");
    expect(trackStop).toHaveBeenCalled();
  });

  it("prefers audio/mp4 over webm (the provider rejects webm)", async () => {
    FakeRecorder.isTypeSupported.mockImplementation((m) => m === "audio/mp4" || m === "audio/webm;codecs=opus");
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "hola" })) });
    await ready(api);
    await hold();
    await waitFor(() => expect(api.transcribe).toHaveBeenCalled());
    expect((api.transcribe as ReturnType<typeof vi.fn>).mock.calls[0][1]).toBe("voice.m4a");
    FakeRecorder.reset();
  });

  it("prefers audio/ogg;codecs=opus when supported and names the file .ogg", async () => {
    FakeRecorder.isTypeSupported.mockImplementation(() => true);
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "hola" })) });
    await ready(api);
    await hold();
    await waitFor(() => expect(api.transcribe).toHaveBeenCalled());
    expect(FakeRecorder.instances[0].mimeType).toBe("audio/ogg;codecs=opus");
    expect((api.transcribe as ReturnType<typeof vi.fn>).mock.calls[0][1]).toBe("voice.ogg");
    FakeRecorder.reset();
  });

  it("a 400 from transcribe shows a toast and keeps using the backend (no Web Speech fallback)", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    const api = fakeApi({ transcribe: vi.fn(async () => { throw new ApiError(400, "audio vacío"); }) });
    await ready(api);
    await hold();
    expect(await screen.findByText(/No se pudo procesar el audio/)).toBeInTheDocument();
    await hold();
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(2));
    expect(FakeRecognition.instances).toHaveLength(0);
  });

  it("cancels a hold shorter than 0.5 s without calling the backend", async () => {
    const api = fakeApi();
    const chat = chatOf();
    await ready(api, chat);
    await hold(100);
    expect(await screen.findByText("Mantén presionado el micrófono para hablar")).toBeInTheDocument();
    expect(api.transcribe).not.toHaveBeenCalled();
    expect(chat.send).not.toHaveBeenCalled();
    expect(trackStop).toHaveBeenCalled();
  });

  it("cancels when the pointer leaves the button", async () => {
    const api = fakeApi();
    await ready(api);
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(1));
    fireEvent.pointerLeave(mic()!);
    expect(screen.queryByText(/Escuchando/)).toBeNull();
    now += 2000;
    fireEvent.pointerUp(mic()!);
    expect(api.transcribe).not.toHaveBeenCalled();
  });

  it("cancels when the pointer slides far away (touch keeps the pointer captured)", async () => {
    const api = fakeApi();
    await ready(api);
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(1));
    fireEvent.pointerMove(mic()!, { clientX: 400, clientY: 400 });
    expect(screen.queryByText(/Escuchando/)).toBeNull();
    expect(api.transcribe).not.toHaveBeenCalled();
  });

  it("auto-stops at max_seconds", async () => {
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ max_seconds: 0.1 })), transcribe: vi.fn(async () => ({ text: "largo" })) });
    const chat = chatOf();
    await ready(api, chat);
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(1));
    now += 5000;
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("largo", undefined));
  });

  it("shows a clear message when the microphone permission is denied", async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    await ready(fakeApi());
    fireEvent.pointerDown(mic()!, { button: 0 });
    expect(await screen.findByText("Permite el micrófono para hablar con el copiloto")).toBeInTheDocument();
    expect(screen.queryByText(/Escuchando/)).toBeNull();
  });

  it("does not send an empty transcript", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "  " })) });
    const chat = chatOf();
    await ready(api, chat);
    await hold();
    expect(await screen.findByText("No te escuché; intenta de nuevo")).toBeInTheDocument();
    expect(chat.send).not.toHaveBeenCalled();
  });

  it("uses Web Speech after a transcribe error", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    const api = fakeApi({ transcribe: vi.fn(async () => { throw new ApiError(503, "cuota"); }) });
    const chat = chatOf();
    await ready(api, chat);
    await hold();
    expect(await screen.findByText(/dictado del navegador/)).toBeInTheDocument();
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecognition.instances).toHaveLength(1));
    FakeRecognition.instances[0].say("hola");
    now += 1500;
    fireEvent.pointerUp(mic()!);
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("hola", undefined));
    expect(FakeRecognition.instances[0].lang).toBe("es-MX");
  });

  it("stops the stream when unmounted mid-hold", async () => {
    const { unmount } = await ready(fakeApi());
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecorder.instances).toHaveLength(1));
    unmount();
    expect(trackStop).toHaveBeenCalled();
  });
});

describe("Web Speech and availability", () => {
  it("uses Web Speech when the config is disabled", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ enabled: false, stt: false, tts: false })) });
    const chat = chatOf();
    await ready(api, chat);
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecognition.instances).toHaveLength(1));
    FakeRecognition.instances[0].say("desde el navegador");
    now += 1500;
    fireEvent.pointerUp(mic()!);
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("desde el navegador", undefined));
    expect(FakeRecorder.instances).toHaveLength(0);
  });

  it("uses Web Speech when the config request fails", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => { throw new ApiError(404, "nf"); }) });
    await ready(api);
    fireEvent.pointerDown(mic()!, { button: 0 });
    await waitFor(() => expect(FakeRecognition.instances).toHaveLength(1));
  });

  it("hides the mic when stt is off and the browser has no Web Speech", async () => {
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ stt: false })) });
    await ready(api);
    await waitFor(() => expect(mic()).toBeNull());
  });
});

describe("spoken replies", () => {
  const reply: ChatMessage = { id: "a1", role: "assistant", text: "**Pide** 40 donas", ts: "2026-07-19T14:05:09Z" };
  const user: ChatMessage = { id: "u1", role: "user", text: "hola" };

  /** Renders, then simulates sending (voice or typed) and the agent answering. */
  async function converse(api: ReturnType<typeof fakeApi>, voice: boolean) {
    api.transcribe = vi.fn(async () => ({ text: "hola" })) as never;
    const chat = chatOf();
    const utils = await ready(api, chat);
    if (voice) {
      await hold();
      await waitFor(() => expect(chat.send).toHaveBeenCalled());
    } else {
      fireEvent.change(screen.getByLabelText("Mensaje para el copiloto"), { target: { value: "hola" } });
      fireEvent.submit(screen.getByLabelText("Mensaje para el copiloto").closest("form")!);
      expect(chat.send).toHaveBeenCalled();
    }
    utils.rerender(<AgentWindow chat={{ ...chat, messages: [user] }} {...props} />);
    utils.rerender(<AgentWindow chat={{ ...chat, messages: [user, reply] }} {...props} />);
    return utils;
  }

  it("a reply to a voice message is spoken through the backend and plays on the shared audio element", async () => {
    const api = fakeApi();
    await converse(api, true);
    await waitFor(() => expect(api.speak).toHaveBeenCalledWith("**Pide** 40 donas"));
    expect(api.speak).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(FakeAudio.instances.at(-1)!.src).toBe("blob:voice"));
    const a = FakeAudio.instances[0];
    expect(FakeAudio.instances).toHaveLength(1);
    await waitFor(() => expect(a.play).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Detener lectura" })).toBeInTheDocument();
    act(() => a.onended?.());
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:voice");
    expect(screen.queryByRole("button", { name: "Detener lectura" })).toBeNull();
  });

  it("shows 'Preparando voz…' while the speak request is in flight", async () => {
    let release!: (b: Blob) => void;
    const api = fakeApi({ speak: vi.fn(() => new Promise<Blob>((r) => { release = r; })) });
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    expect(await screen.findByText("Preparando voz…")).toBeInTheDocument();
    await act(async () => release(new Blob(["x"])));
    await waitFor(() => expect(screen.queryByText("Preparando voz…")).toBeNull());
    expect(screen.getByText(/Hablando/)).toBeInTheDocument();
  });

  it("a typed message is never read aloud", async () => {
    const api = fakeApi();
    await converse(api, false);
    await act(async () => {});
    expect(api.speak).not.toHaveBeenCalled();
  });

  it("the speaker button plays on demand and a second press stops", async () => {
    const api = fakeApi();
    await ready(api, chatOf({ messages: [user, reply] }));
    const btn = screen.getByRole("button", { name: "Escuchar respuesta" });
    fireEvent.click(btn);
    await waitFor(() => expect(api.speak).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(btn).toHaveAttribute("aria-pressed", "true"));
    fireEvent.click(btn);
    await waitFor(() => expect(btn).toHaveAttribute("aria-pressed", "false"));
    expect(FakeAudio.instances[0].pause).toHaveBeenCalled();
  });

  it("tapping the orb stops the reading", async () => {
    await ready(fakeApi(), chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    fireEvent.click(await screen.findByRole("button", { name: "Detener lectura" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Detener lectura" })).toBeNull());
  });

  it("uses speechSynthesis when tts is off, without markdown", async () => {
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal("SpeechSynthesisUtterance", class { lang = ""; voice: unknown = null; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(public text: string) {} });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak, cancel, getVoices: () => [{ lang: "en-US" }, { lang: "es-MX" }] } });
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ tts: false })) });
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    const u = speak.mock.calls[0][0];
    expect(u.text).toBe("Pide 40 donas");
    expect(u.lang).toBe("es-MX");
    expect(u.voice).toEqual({ lang: "es-MX" });
    expect(api.speak).not.toHaveBeenCalled();
  });

  it("falls back to speechSynthesis when the speak request fails", async () => {
    const speak = vi.fn();
    vi.stubGlobal("SpeechSynthesisUtterance", class { lang = ""; onend = null; onerror = null; constructor(public text: string) {} });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak, cancel: vi.fn(), getVoices: () => [] } });
    const api = fakeApi({ speak: vi.fn(async () => { throw new ApiError(502, "tts down"); }) });
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
  });
});

describe("stripMarkdown", () => {
  it("removes common markup", () => {
    expect(stripMarkdown("# Título\n- **uno** y `dos`\n[enlace](http://x)\n```\ncode\n```")).toBe("Título uno y dos enlace");
  });
});
