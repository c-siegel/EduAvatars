import { useCallback, useState } from "react";

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  // Stable across renders (unlike a plain arrow function, which would be a new reference every
  // render): Toast's own auto-dismiss effect depends on this function's identity, so a fresh one
  // on every parent re-render (e.g. the Configurator re-rendering from ongoing draft edits) would
  // restart its timer each time — an actively-typing teacher might never see the toast dismiss
  // on its own.
  const dismiss = useCallback(() => setMessage(null), []);
  return { message, show: setMessage, dismiss };
}
