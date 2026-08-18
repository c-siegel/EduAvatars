// Sprachauswahl fürs Konfigurator (Screen 1e) — steuert NICHT die Lipsync-Qualität (die kommt
// audio-basiert aus HeadAudio, unabhängig von der Sprache, siehe TalkingHeadAvatar), sondern den
// Sprachhinweis für Spracherkennung (STT) und die Antwortsprache des Avatars.
export const SPOKEN_LANGUAGE_OPTIONS = [
  { value: "de", label: "Deutsch" },
  { value: "en", label: "Englisch" },
] as const;
