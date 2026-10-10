import { describe, expect, it } from "vitest";
import { sanitizeReply } from "./sanitize";

describe("sanitizeReply", () => {
  it("returns clean text untouched", () => {
    expect(sanitizeReply("Pide 40 donas hoy.")).toBe("Pide 40 donas hoy.");
  });
  it("strips complete <think> blocks, multiline", () => {
    expect(sanitizeReply("<think>razono\nmucho</think>Pide 40.")).toBe("Pide 40.");
  });
  it("strips <mm:think> blocks", () => {
    expect(sanitizeReply("<mm:think>x</mm:think>Hola")).toBe("Hola");
  });
  it("strips a stray closing tag", () => {
    expect(sanitizeReply("Hola</think>")).toBe("Hola");
    expect(sanitizeReply("Hola</mm:think> mundo")).toBe("Hola mundo");
  });
  it("strips HTML-escaped forms", () => {
    expect(sanitizeReply("Hola&lt;/mm:think&gt;")).toBe("Hola");
    expect(sanitizeReply("&lt;think&gt;secreto&lt;/think&gt;Listo")).toBe("Listo");
  });
  it("is case-insensitive and trims", () => {
    expect(sanitizeReply("  <THINK>a</THINK>  Listo \n")).toBe("Listo");
  });
  it("handles empty and nullish input", () => {
    expect(sanitizeReply("")).toBe("");
    expect(sanitizeReply(null)).toBe("");
    expect(sanitizeReply(undefined)).toBe("");
  });
});
