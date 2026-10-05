# Reference voices

Sopro clones a voice from a short reference clip instead of having "voices" baked into the
model. This directory is where those clips live — but it ships empty on purpose: picking whose
voice becomes the product's default is a licensing and quality decision for a human, not
something to bake into a Docker image.

## What to add

One file per supported language, named `<language>.wav` (e.g. `de.wav`, `en.wav`, `fr.wav`,
`pt.wav` — the four languages sopro supports). Requirements:

- **5–20 seconds** of clear, single-speaker speech (per sopro's own README).
- Mono, any common sample rate (sopro resamples internally).
- A voice and license you have the right to ship — e.g. a recording made for this purpose, or a
  clip under a license that explicitly allows this kind of reuse. Public text-to-speech output
  (Google, Amazon, etc.) is speech, but check that service's own terms before using its output as
  a shipped reference voice.

## Where this directory is read from

In Docker, this path is bind-mounted from `${EDUAVATARS_DATA_DIR}/sopro-voices` (see
`docker/docker-compose.yml`) rather than copied into the image — so an operator can add or swap
a voice without rebuilding anything, and no audio file needs to be committed to this repo. A
language with no matching file here simply isn't available; `POST /synthesize` returns a 400 for
it (see `app/synthesis.py::UnsupportedLanguageError`).
