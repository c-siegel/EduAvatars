// Language choice for the configurator (screen 1e) — does NOT control lipsync quality (that comes
// audio-based from HeadAudio, independent of language, see TalkingHeadAvatar) but the language
// hint for speech recognition (STT) and the avatar's reply language. Labels live in the i18n
// locale files (configurator.step2.spokenLanguageOptions.<value>), not here, since this file is
// not a React component and can't call t().
export const SPOKEN_LANGUAGE_VALUES = ["de", "en"] as const;
