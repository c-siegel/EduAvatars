import { useLayoutEffect, type RefObject } from "react";

/** Grows a textarea to fit its content as the user types, capped at maxHeightPx (becomes internally
 * scrollable beyond that) — re-measures whenever `value` or `maxHeightPx` change. Shared by the
 * chat composer and the inline message-edit textarea (see pages/PublicChat/index.tsx and
 * components/ChatBubble/ChatBubble.tsx). */
export function useAutoResizeTextarea(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
  maxHeightPx: number | undefined,
) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Shrink first — otherwise scrollHeight only ever reports the box's current (possibly too
    // large) height back, and a deleted line would never make it shrink again.
    el.style.height = "auto";
    const max = maxHeightPx && maxHeightPx > 0 ? maxHeightPx : Infinity;
    const next = Math.min(el.scrollHeight, max);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  }, [ref, value, maxHeightPx]);
}
