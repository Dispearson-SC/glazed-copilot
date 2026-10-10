const ESCAPED_THINK_TAG = /&lt;(\/?(?:mm:)?think)&gt;/gi;
const THINK_BLOCK = /<(mm:)?think>[\s\S]*?<\/(?:mm:)?think>/gi;
const STRAY_THINK_TAG = /<\/?(?:mm:)?think>/gi;

/** Removes model "thinking" markup (raw or HTML-escaped) from a reply before it is displayed. */
export function sanitizeReply(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(ESCAPED_THINK_TAG, "<$1>")
    .replace(THINK_BLOCK, "")
    .replace(STRAY_THINK_TAG, "")
    .trim();
}
