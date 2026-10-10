import { describe, expect, it } from "vitest";
import { parseTraceMessage } from "./parseTraceMessage";

const CLIPPED_REQ = '{"kind": "request", "parts": [{"content": "¿Qué deberíamos pedir mañana y por qu…';
const CLIPPED_RESP = '{"kind": "response", "parts": [{"id": null, "content": "I\'ll consult to glazed_present f…';
const CLIPPED_TOOL = '{"kind": "request", "parts": [{"content": "<untrusted-tool-output>\\n## S030 · Pl…';

describe("parseTraceMessage", () => {
  it("passes plain text through", () => {
    expect(parseTraceMessage("hola")).toEqual({ text: "hola", truncated: false, untrusted: false });
  });
  it("reads content from a valid envelope, joining string parts", () => {
    const env = JSON.stringify({ kind: "response", parts: [{ id: null, content: "Pide 40\n<think>x</think>" }, { tool_name: "t", args: {} }, { content: "ok" }] });
    expect(parseTraceMessage(env)).toMatchObject({ text: "Pide 40\n\nok", truncated: false, untrusted: false });
  });
  it("extracts content from a clipped request and flags truncation", () => {
    const r = parseTraceMessage(CLIPPED_REQ);
    expect(r.text).toBe("¿Qué deberíamos pedir mañana y por qu…");
    expect(r.truncated).toBe(true);
    expect(r.untrusted).toBe(false);
  });
  it("extracts content from a clipped response", () => {
    const r = parseTraceMessage(CLIPPED_RESP);
    expect(r.text).toBe("I'll consult to glazed_present f…");
    expect(r.truncated).toBe(true);
  });
  it("flags clipped tool output as untrusted", () => {
    const r = parseTraceMessage(CLIPPED_TOOL);
    expect(r.untrusted).toBe(true);
    expect(r.text.startsWith("<untrusted-tool-output>\n## S030")).toBe(true);
  });
  it("flags valid envelopes carrying tool output as untrusted", () => {
    const env = JSON.stringify({ kind: "request", parts: [{ content: "<untrusted-tool-output>x" }] });
    expect(parseTraceMessage(env).untrusted).toBe(true);
  });
  it("unescapes \\n \\\" \\\\ and \\uXXXX, tolerating a missing closing quote and a dangling escape", () => {
    const clipped = '{"kind": "response", "parts": [{"content": "a\\nb \\"q\\" c\\\\d \\u00e9 \\u00';
    expect(parseTraceMessage(clipped).text).toBe('a\nb "q" c\\d é');
  });
  it("sanitizes thinking markup", () => {
    const env = JSON.stringify({ kind: "response", parts: [{ content: "<think>x</think>Listo</mm:think>" }] });
    expect(parseTraceMessage(env).text).toBe("Listo");
  });
  it("returns empty text for an envelope without string content", () => {
    expect(parseTraceMessage('{"kind": "response", "parts": [{"tool_name": "x"}]}').text).toBe("");
  });
});
