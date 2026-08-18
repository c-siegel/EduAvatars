// Generischer Standard-Preprompt (Screen 1e, Schritt "Verhalten") — wird einmalig eingesetzt,
// solange das Feld noch leer ist, und lässt sich jederzeit über "Auf Standard zurücksetzen"
// wiederherstellen. Keine Interpolation aus anderen Schritten mehr: die Lehrkraft passt den Text
// direkt an, statt ihn aus Voreinstellungen generieren zu lassen.
export const DEFAULT_PREPROMPT =
  "Du bist ein hilfreicher, KI-gestützter Lernassistent.\n\n" +
  "Antworte kindgerecht, geduldig und ermutigend. Wenn du etwas nicht weißt, sag das ehrlich, " +
  "anstatt zu raten.";
