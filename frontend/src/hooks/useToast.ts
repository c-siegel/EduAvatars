import { useState } from "react";

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  return { message, show: setMessage, dismiss: () => setMessage(null) };
}
