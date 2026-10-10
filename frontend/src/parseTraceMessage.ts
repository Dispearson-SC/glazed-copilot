import { sanitizeReply } from "./sanitize";

export interface ParsedTraceMessage {
  /** Sanitized, human-readable text ("" when the envelope carries no string content). */
  text: string;
  /** The envelope was clipped by the backend, so the text is incomplete. */
  truncated: boolean;
  /** A peer/tool result injected as a request; never a user message. */
  untrusted: boolean;
}

const ENVELOPE_HEAD = /^\s*\{\s*"kind"/;
const FIRST_CONTENT = /"content"\s*:\s*"((?:[^"\\]|\\[\s\S])*)\\?(?:"|$)/;
const ESCAPE = /\\(u[0-9a-fA-F]{4}|[\s\S])/g;
const SIMPLE: Record<string, string> = { n: "\n", t: "\t", r: "\r", b: "\b", f: "\f" };
const UNTRUSTED = "<untrusted-tool-output>";

function unescapeJson(s: string): string {
  return s
    .replace(/\\u[0-9a-fA-F]{0,3}$/, "") // dangling partial unicode escape at the clip point
    .replace(ESCAPE, (_, c: string) => (c[0] === "u" && c.length === 5 ? String.fromCharCode(parseInt(c.slice(1), 16)) : (SIMPLE[c] ?? c)));
}

/** Turns a trace message payload (plain text or a serialized, possibly clipped, pydantic-ai envelope) into display text. */
export function parseTraceMessage(raw: string): ParsedTraceMessage {
  let content = raw;
  let truncated = false;
  if (ENVELOPE_HEAD.test(raw)) {
    try {
      const env = JSON.parse(raw) as { parts?: Array<{ content?: unknown }> };
      content = (env.parts ?? [])
        .map((p) => p?.content)
        .filter((c): c is string => typeof c === "string")
        .join("\n");
    } catch {
      truncated = true;
      const m = FIRST_CONTENT.exec(raw);
      content = m ? unescapeJson(m[1]) : "";
    }
  }
  const untrusted = content.trimStart().startsWith(UNTRUSTED);
  return { text: sanitizeReply(content), truncated, untrusted };
}
