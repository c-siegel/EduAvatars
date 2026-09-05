import type { TalkingHead } from "@met4citizen/talkinghead";

// HeadAudio (frontend/public/headaudio/, siehe ATTRIBUTION.md) berechnet Lipsync-Visemes in
// Echtzeit direkt aus dem abgespielten Audiosignal — unabhängig von Sprache/TTS-Anbieter, ohne
// Wort-Timestamps. Ersetzt TalkingHeads eigenen text-basierten Viseme-Pfad (der Wort-Timing
// bräuchte, das litellm.speech() nicht liefert). Setup entspricht 1:1 dem offiziellen
// Integrationsbeispiel aus der HeadAudio-Doku.
//
// Bekannte Einschränkung: das einzige vortrainierte Modell (model-en-mixed.bin) wurde nur auf
// englischen Stimmen trainiert — für Deutsch unverifiziert.

interface HeadAudioNodeLike extends AudioNode {
  loadModel(url: string): Promise<void>;
  update(): void;
  onvalue: (key: string, value: number) => void;
}

// Vite blockiert im Dev-Server jeden import(), der (auch dynamisch/nicht statisch analysierbar)
// durch seine Transform-Middleware läuft und auf eine Datei unter public/ zeigt ("This file is in
// /public ... should not be imported from source code"), selbst mit @vite-ignore — das unterdrückt
// nur die Analyse-Warnung, nicht diese Laufzeit-Sperre. new Function(...) erzeugt einen echten,
// nativen Browser-import() außerhalb von Vites Modulgraph, den die Middleware nie zu Gesicht
// bekommt — verifiziert per Playwright gegen den echten Dev-Server.
const nativeImport = new Function("specifier", "return import(specifier)") as (
  specifier: string,
) => Promise<{ HeadAudio: new (context: AudioContext, options: Record<string, unknown>) => HeadAudioNodeLike }>;

export async function attachHeadAudio(head: TalkingHead): Promise<void> {
  await head.audioCtx.audioWorklet.addModule("/headaudio/headworklet.mjs");
  // Laufzeit-URL unter public/, kein Vite-Modulgraph-Eintrag (kein npm-Paket vorhanden, siehe
  // ATTRIBUTION.md). Klasse heißt "HeadAudio" (verifiziert im Quellcode) — die HeadAudio-Doku
  // selbst spricht generisch von einem "audio worklet node", das ist kein exakter Klassenname.
  // Fertig aufgelöste URL statt "/headaudio/headaudio.mjs": Code aus new Function(...) hat keine
  // eigene Skript-URL, und Firefox löst ein dynamisches import() darin gegen eine file://-Basis auf
  // statt gegen die Dokument-Basis. Der Browser bricht dann mit "Content at https://… may not load
  // or link to file:///…" ab — Chromium (und damit die Playwright-Verifikation oben) und WebKit
  // nehmen die Dokument-Basis und waren davon nie betroffen. Eine absolute URL lässt dem Browser
  // gar keine Basis mehr zu wählen.
  const { HeadAudio } = await nativeImport(new URL("/headaudio/headaudio.mjs", location.origin).href);
  const headaudio: HeadAudioNodeLike = new HeadAudio(head.audioCtx, {
    parameterData: { vadGateActiveDb: -40, vadGateInactiveDb: -60 },
  });
  await headaudio.loadModel("/headaudio/model-en-mixed.bin");
  head.audioSpeechGainNode.connect(headaudio);
  headaudio.onvalue = (key, value) => {
    Object.assign(head.mtAvatar[key], { newvalue: value, needsUpdate: true });
  };
  head.opt.update = headaudio.update.bind(headaudio);
}
