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
  currentTime = 0;
  duration = NaN;
  paused = true;
  playbackRate = 1;
  defaultPlaybackRate = 1;
  preservesPitch = false;
  private listeners: Record<string, Array<() => void>> = {};
  play = vi.fn(async () => { this.paused = false; this.emit("play"); });
  pause = vi.fn(() => { this.paused = true; this.emit("pause"); });
  addEventListener(ev: string, fn: () => void) { (this.listeners[ev] ??= []).push(fn); }
  emit(ev: string) { this.listeners[ev]?.forEach((f) => f()); }
  /** Simulates metadata arriving / playback advancing. */
  set(over: { duration?: number; currentTime?: number }, ev = "timeupdate") { Object.assign(this, over); this.emit(ev); }
  constructor() { FakeAudio.instances.push(this); }
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
  delete (window as unknown as Record<string, unknown>).speechSynthesis;
});

const mic = () => screen.queryByRole("button", { name: "Hablar con el copiloto" });
async function ready(api: ReturnType<typeof fakeApi>, chat = chatOf()) {
  const utils = render(<AgentWindow chat={chat} {...props} />, { wrapper: wrapWith(api) });
  await waitFor(() => expect(api.getVoiceConfig).toHaveBeenCalled());
  await act(async () => {});
  return utils;
}
const sendBtn = () => screen.getByRole("button", { name: /^Enviar mensaje/ });
/** Taps the mic and waits until the recorder runs. */
async function tapMic() {
  fireEvent.click(mic()!);
  await waitFor(() => expect(FakeRecorder.instances.length).toBeGreaterThan(0));
  return FakeRecorder.instances[FakeRecorder.instances.length - 1];
}
/** Records for `ms` and taps the send button. */
async function record(ms = 1500) {
  const before = FakeRecorder.instances.length;
  fireEvent.click(mic()!);
  await waitFor(() => expect(FakeRecorder.instances.length).toBe(before + 1));
  now += ms;
  fireEvent.click(sendBtn());
}

describe("tap-to-talk (MiniMax STT)", () => {
  it("one tap starts recording: Escuchando with timer, cancel X, mic pressed, send enabled", async () => {
    await ready(fakeApi());
    expect(sendBtn()).toBeDisabled();
    await tapMic();
    expect(await screen.findByText(/Escuchando… 0:00/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar grabación" })).toBeInTheDocument();
    expect(mic()).toHaveAttribute("aria-pressed", "true");
    const send = screen.getByRole("button", { name: "Enviar mensaje de voz" });
    expect(send).toBeEnabled();
    expect(FakeRecorder.instances[0].mimeType).toBe("audio/webm;codecs=opus");
    now += 3000;
    expect(await screen.findByText(/Escuchando… 0:03/)).toBeInTheDocument();
  });

  it("requests the mic and primes the shared audio element synchronously inside the mic tap", async () => {
    await ready(fakeApi());
    fireEvent.click(mic()!);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(FakeAudio.instances).toHaveLength(1);
    expect(FakeAudio.instances[0].play).toHaveBeenCalledTimes(1);
    expect(FakeAudio.instances[0].src).toMatch(/^data:audio\/wav/);
  });

  it("send transcribes and sends the text as a voice message; the mic tracks are already stopped", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "¿Qué pido hoy?" })) });
    const chat = chatOf();
    await ready(api, chat);
    await record(2000);
    expect(screen.queryByRole("button", { name: "Cancelar grabación" })).toBeNull();
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("¿Qué pido hoy?", { voice: true }));
    const [blob, name] = (api.transcribe as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(name).toBe("voice.webm");
    expect(trackStop).toHaveBeenCalled();
    expect(trackStop.mock.invocationCallOrder[0]).toBeLessThan((api.transcribe as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0]);
  });

  it("shows Transcribiendo… with send disabled while the request is in flight", async () => {
    let release!: (v: { text: string }) => void;
    const api = fakeApi({ transcribe: vi.fn(() => new Promise<{ text: string }>((r) => { release = r; })) });
    await ready(api);
    await record();
    expect(await screen.findByText("Transcribiendo…")).toBeInTheDocument();
    expect(sendBtn()).toBeDisabled();
    await act(async () => release({ text: "hola" }));
    await waitFor(() => expect(screen.queryByText("Transcribiendo…")).toBeNull());
  });

  it("tapping the mic again discards the recording and sends nothing", async () => {
    const api = fakeApi();
    const chat = chatOf();
    await ready(api, chat);
    await tapMic();
    fireEvent.click(mic()!);
    expect(screen.queryByText(/Escuchando/)).toBeNull();
    expect(mic()).toHaveAttribute("aria-pressed", "false");
    expect(trackStop).toHaveBeenCalled();
    expect(api.transcribe).not.toHaveBeenCalled();
    expect(chat.send).not.toHaveBeenCalled();
  });

  it("the cancel X discards the recording and sends nothing", async () => {
    const api = fakeApi();
    const chat = chatOf();
    await ready(api, chat);
    await tapMic();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar grabación" }));
    expect(screen.queryByText(/Escuchando/)).toBeNull();
    expect(trackStop).toHaveBeenCalled();
    expect(api.transcribe).not.toHaveBeenCalled();
    expect(chat.send).not.toHaveBeenCalled();
  });

  it("auto-stops at max_seconds and sends as if send were tapped", async () => {
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ max_seconds: 0.1 })), transcribe: vi.fn(async () => ({ text: "largo" })) });
    const chat = chatOf();
    await ready(api, chat);
    await tapMic();
    now += 5000;
    await waitFor(() => expect(chat.send).toHaveBeenCalledWith("largo", { voice: true }));
  });

  it("language_suspect puts the text in the composer, does not send, and a later send is a voice turn", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "hola buenos dias", language_suspect: true })) });
    const chat = chatOf();
    await ready(api, chat);
    await record();
    const box = screen.getByLabelText("Mensaje para el copiloto") as HTMLInputElement;
    await waitFor(() => expect(box.value).toBe("hola buenos dias"));
    expect(chat.send).not.toHaveBeenCalled();
    expect(await screen.findByText("Revisa el texto antes de enviarlo")).toBeInTheDocument();
    expect(box).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(chat.send).toHaveBeenCalledWith("hola buenos dias", { voice: true });
  });

  it("language_suspect: clearing the composer drops the voice flag", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "hola", language_suspect: true })) });
    const chat = chatOf();
    await ready(api, chat);
    await record();
    const box = screen.getByLabelText("Mensaje para el copiloto") as HTMLInputElement;
    await waitFor(() => expect(box.value).toBe("hola"));
    fireEvent.change(box, { target: { value: "" } });
    fireEvent.change(box, { target: { value: "otro mensaje" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(chat.send).toHaveBeenCalledWith("otro mensaje", undefined);
  });

  it("an empty transcript is not sent and shows a toast", async () => {
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "  " })) });
    const chat = chatOf();
    await ready(api, chat);
    await record();
    expect(await screen.findByText("No te escuché, intenta de nuevo")).toBeInTheDocument();
    expect(chat.send).not.toHaveBeenCalled();
  });

  it("a 400 shows the audio message; 502 and network errors show the retry message", async () => {
    const transcribe = vi.fn()
      .mockRejectedValueOnce(new ApiError(400, "audio vacío"))
      .mockRejectedValueOnce(new ApiError(502, "down"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await ready(fakeApi({ transcribe }));
    await record();
    expect(await screen.findByText(/No se pudo procesar el audio/)).toBeInTheDocument();
    await record();
    expect(await screen.findByText("No se pudo transcribir, intenta de nuevo")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Transcribiendo…")).toBeNull());
    await record();
    await waitFor(() => expect(transcribe).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(mic()).toHaveAttribute("aria-pressed", "false"));
  });

  it.each([
    ["audio/mp4", "voice.m4a"],
    ["audio/ogg;codecs=opus", "voice.ogg"],
  ])("prefers %s over webm", async (mime, file) => {
    FakeRecorder.isTypeSupported.mockImplementation((m) => m === mime || m === "audio/webm;codecs=opus");
    const api = fakeApi({ transcribe: vi.fn(async () => ({ text: "hola" })) });
    await ready(api);
    await record();
    await waitFor(() => expect(api.transcribe).toHaveBeenCalled());
    expect(FakeRecorder.instances[0].mimeType).toBe(mime);
    expect((api.transcribe as ReturnType<typeof vi.fn>).mock.calls[0][1]).toBe(file);
    FakeRecorder.reset();
  });

  it("shows a clear message when the microphone permission is denied", async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    await ready(fakeApi());
    fireEvent.click(mic()!);
    expect(await screen.findByText("Permite el micrófono para hablar con el copiloto")).toBeInTheDocument();
    expect(screen.queryByText(/Escuchando/)).toBeNull();
  });

  it("stops the stream when unmounted mid-recording", async () => {
    const { unmount } = await ready(fakeApi());
    await tapMic();
    unmount();
    expect(trackStop).toHaveBeenCalled();
  });
});

describe("mic availability", () => {
  it("is shown while the config loads and when stt is on", async () => {
    await ready(fakeApi());
    expect(mic()).not.toBeNull();
  });

  it("is hidden when stt is off", async () => {
    await ready(fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ stt: false })) }));
    await waitFor(() => expect(mic()).toBeNull());
  });

  it("is hidden without MediaRecorder", async () => {
    vi.stubGlobal("MediaRecorder", undefined);
    await ready(fakeApi());
    expect(mic()).toBeNull();
  });

  it("is hidden without getUserMedia", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {} });
    await ready(fakeApi());
    expect(mic()).toBeNull();
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
      await record();
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

  it("primes the shared element on the mic tap and the send tap, then reuses it for playback after the mic is released", async () => {
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const api = fakeApi();
    await converse(api, true);
    await waitFor(() => expect(FakeAudio.instances[0].src).toBe("blob:voice"));
    const a = FakeAudio.instances[0];
    expect(FakeAudio.instances).toHaveLength(1);
    // mic tap and send tap prime with the silent clip; the last play call is the reply
    await waitFor(() => expect(a.play.mock.calls.length).toBeGreaterThanOrEqual(3));
    const [firstPrime, secondPrime] = a.play.mock.invocationCallOrder;
    expect(secondPrime).toBeGreaterThan(firstPrime);
    // tracks stopped before any reply playback
    expect(trackStop.mock.invocationCallOrder[0]).toBeLessThan(a.play.mock.invocationCallOrder.at(-1)!);
    await waitFor(() => expect(info).toHaveBeenCalledWith("[voice] tts path:", "minimax", "ok"));
    expect(info.mock.calls.filter((c) => c[0] === "[voice] tts path:")).toHaveLength(1);
  });

  it("a typed send and the speaker button prime the shared element too", async () => {
    const chat = chatOf({ messages: [user, reply] });
    await ready(fakeApi(), chat);
    fireEvent.change(screen.getByLabelText("Mensaje para el copiloto"), { target: { value: "hola" } });
    fireEvent.submit(screen.getByLabelText("Mensaje para el copiloto").closest("form")!);
    expect(FakeAudio.instances).toHaveLength(1);
    expect(FakeAudio.instances[0].play).toHaveBeenCalledTimes(1);
    expect(FakeAudio.instances[0].src).toMatch(/^data:audio\/wav/);
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    expect(FakeAudio.instances[0].play).toHaveBeenCalledTimes(2); // synchronous, before the speak request resolves
    await waitFor(() => expect(FakeAudio.instances[0].src).toBe("blob:voice"));
    expect(FakeAudio.instances).toHaveLength(1);
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

  it("typed messages send no voice flag", async () => {
    const chat = chatOf();
    await ready(fakeApi(), chat);
    fireEvent.change(screen.getByLabelText("Mensaje para el copiloto"), { target: { value: "hola" } });
    fireEvent.submit(screen.getByLabelText("Mensaje para el copiloto").closest("form")!);
    expect(chat.send).toHaveBeenCalledWith("hola", undefined);
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

describe("speechSynthesis fallback voice", () => {
  const reply: ChatMessage = { id: "a1", role: "assistant", text: "Pide 40 donas", ts: "2026-07-19T14:05:09Z" };
  const user: ChatMessage = { id: "u1", role: "user", text: "hola" };
  const setup = (synth: Record<string, unknown>) => {
    vi.stubGlobal("SpeechSynthesisUtterance", class { lang = ""; rate = 1; voice: unknown = null; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(public text: string) {} });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak: vi.fn(), cancel: vi.fn(), ...synth } });
    return window.speechSynthesis.speak as ReturnType<typeof vi.fn>;
  };
  async function play(api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ tts: false })) })) {
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
  }

  it.each([
    ["es-MX", [{ lang: "en-US" }, { lang: "es-ES" }, { lang: "es-US" }, { lang: "es-MX" }], "es-MX"],
    ["es-US", [{ lang: "en-US" }, { lang: "es-ES" }, { lang: "es_US" }], "es_US"],
    ["es-*", [{ lang: "en-US" }, { lang: "es-ES" }], "es-ES"],
  ])("prefers %s", async (_n, voices, expected) => {
    const speak = setup({ getVoices: () => voices });
    await play();
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    const u = speak.mock.calls[0][0];
    expect(u.lang).toBe("es-MX");
    expect(u.voice.lang).toBe(expected);
  });

  it("never uses a non-Spanish voice: with none available it still sets lang es-MX", async () => {
    const speak = setup({ getVoices: () => [{ lang: "en-US" }] });
    await play();
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak.mock.calls[0][0].lang).toBe("es-MX");
    expect(speak.mock.calls[0][0].voice).toBeNull();
  });

  it("waits once for voiceschanged when the list is empty", async () => {
    let voices: Array<{ lang: string }> = [];
    let changed: (() => void) | undefined;
    const speak = setup({
      getVoices: () => voices,
      addEventListener: (_e: string, fn: () => void) => { changed = fn; },
      removeEventListener: vi.fn(),
    });
    await play();
    await waitFor(() => expect(changed).toBeDefined());
    expect(speak).not.toHaveBeenCalled();
    voices = [{ lang: "es-US" }];
    act(() => changed!());
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak.mock.calls[0][0].voice).toEqual({ lang: "es-US" });
  });

  it("speaks anyway when voiceschanged never fires", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const speak = setup({ getVoices: () => [], addEventListener: vi.fn(), removeEventListener: vi.fn() });
      await play();
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(speak).toHaveBeenCalledTimes(1);
      expect(speak.mock.calls[0][0].lang).toBe("es-MX");
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ["tts off", () => fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ tts: false })) }), "tts-off"],
    ["speak error", () => fakeApi({ speak: vi.fn(async () => { throw new ApiError(502, "x"); }) }), "speak-error"],
    ["play rejected", () => {
      vi.stubGlobal("Audio", class extends FakeAudio {
        constructor() { super(); this.play = vi.fn(async () => { if (this.src.startsWith("blob:")) throw new Error("NotAllowedError"); }); }
      });
      return fakeApi();
    }, "play-rejected"],
  ])("logs one speechSynthesis path line (%s) without text", async (_n, mk, reason) => {
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const speak = setup({ getVoices: () => [{ lang: "es-MX" }] });
    await play(mk());
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    const lines = info.mock.calls.filter((c) => c[0] === "[voice] tts path:");
    expect(lines).toEqual([["[voice] tts path:", "speechSynthesis", reason]]);
  });
});

describe("player bar", () => {
  const reply: ChatMessage = { id: "a1", role: "assistant", text: "**Pide** 40 donas", ts: "2026-07-19T14:05:09Z" };
  const user: ChatMessage = { id: "u1", role: "user", text: "hola" };
  const bar = () => screen.queryByRole("group", { name: "Reproductor de voz" });
  async function play(api = fakeApi()) {
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    await waitFor(() => expect(bar()).not.toBeNull());
    const a = FakeAudio.instances[0];
    await waitFor(() => expect(a.play).toHaveBeenCalled());
    return a;
  }

  it("appears on play with slider, time and speed; hides on ended", async () => {
    const a = await play();
    expect(screen.getByLabelText("Posición del audio")).toBeInTheDocument();
    expect(screen.getByLabelText("Velocidad de reproducción")).toHaveTextContent("1×");
    expect(screen.getByLabelText("Tiempo")).toHaveTextContent("0:00 / --:--"); // duration unknown until metadata
    act(() => a.set({ duration: 75, currentTime: 5 }, "loadedmetadata"));
    expect(screen.getByLabelText("Tiempo")).toHaveTextContent("0:05 / 1:15");
    act(() => a.onended?.());
    expect(bar()).toBeNull();
  });

  it("copes with an Infinity duration", async () => {
    const a = await play();
    act(() => a.set({ duration: Infinity }, "durationchange"));
    expect(screen.getByLabelText("Posición del audio")).toBeDisabled();
    expect(screen.getByLabelText("Tiempo")).toHaveTextContent("0:00 / --:--");
  });

  it("seeking sets currentTime", async () => {
    const a = await play();
    act(() => a.set({ duration: 60 }, "loadedmetadata"));
    fireEvent.change(screen.getByLabelText("Posición del audio"), { target: { value: "30" } });
    expect(a.currentTime).toBe(30);
  });

  it("pause and resume toggle the audio", async () => {
    const a = await play();
    fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
    expect(a.pause).toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Reanudar" }));
    expect(a.play).toHaveBeenCalledTimes(3); // prime, playback, resume
    expect(bar()).not.toBeNull();
  });

  it("speed cycles, sets playbackRate, persists and applies to later playbacks", async () => {
    const a = await play();
    const speed = screen.getByLabelText("Velocidad de reproducción");
    const seen: string[] = [];
    for (let i = 0; i < 5; i++) {
      fireEvent.click(speed);
      seen.push(speed.textContent ?? "");
    }
    expect(seen).toEqual(["1.25×", "1.5×", "2×", "0.75×", "1×"]);
    fireEvent.click(speed);
    expect(a.playbackRate).toBe(1.25);
    expect(a.preservesPitch).toBe(true);
    expect(localStorage.getItem("glazed.voice.rate")).toBe("1.25");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar reproductor" }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    await waitFor(() => expect(bar()).not.toBeNull());
    expect(a.playbackRate).toBe(1.25);
    expect(screen.getByLabelText("Velocidad de reproducción")).toHaveTextContent("1.25×");
  });

  it("close stops playback and hides the bar", async () => {
    const a = await play();
    fireEvent.click(screen.getByRole("button", { name: "Cerrar reproductor" }));
    expect(a.pause).toHaveBeenCalled();
    expect(bar()).toBeNull();
    expect(screen.queryByRole("button", { name: "Detener lectura" })).toBeNull();
  });

  it("speechSynthesis fallback has no slider but keeps speed and stop; speed restarts the utterance", async () => {
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal("SpeechSynthesisUtterance", class { lang = ""; rate = 1; voice: unknown = null; onend: (() => void) | null = null; onerror: (() => void) | null = null; constructor(public text: string) {} });
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak, cancel, getVoices: () => [] } });
    const api = fakeApi({ getVoiceConfig: vi.fn(async () => cfg({ tts: false })) });
    await ready(api, chatOf({ messages: [user, reply] }));
    fireEvent.click(screen.getByRole("button", { name: "Escuchar respuesta" }));
    await waitFor(() => expect(bar()).not.toBeNull());
    expect(screen.queryByLabelText("Posición del audio")).toBeNull();
    fireEvent.click(screen.getByLabelText("Velocidad de reproducción"));
    expect(speak).toHaveBeenCalledTimes(2);
    expect(speak.mock.calls[1][0].rate).toBe(1.25);
    expect(bar()).not.toBeNull(); // the cancelled utterance must not stop the player
    fireEvent.click(screen.getByRole("button", { name: "Cerrar reproductor" }));
    expect(bar()).toBeNull();
  });
});

describe("stripMarkdown", () => {
  it("removes common markup", () => {
    expect(stripMarkdown("# Título\n- **uno** y `dos`\n[enlace](http://x)\n```\ncode\n```")).toBe("Título uno y dos enlace");
  });
});
