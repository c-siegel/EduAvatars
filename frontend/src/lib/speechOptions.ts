// Sprachauswahl fürs Konfigurator (Screen 1e) — steuert NICHT die Lipsync-Qualität (die kommt
// audio-basiert aus HeadAudio, unabhängig von der Sprache, siehe TalkingHeadAvatar), sondern den
// Sprachhinweis für Spracherkennung (STT) und die Antwortsprache des Avatars. Labels leben in den
// i18n-Locale-Dateien (configurator.step2.spokenLanguageOptions.<value>), nicht hier, da diese
// Datei kein React-Component ist und t() nicht aufrufen kann.
export const SPOKEN_LANGUAGE_VALUES = ["de", "en"] as const;
