#!/bin/sh
# Downloads the on-device speech-to-text (STT) model that visitors' browsers load in the public
# chat (Parakeet Redux, see frontend/src/lib/parakeetStt.ts), verifies it, and stores a gzipped
# copy of every file next to it.
#
# Why self-hosted and pre-compressed: the model is ~380 MB raw, but its weights are ternary
# (-1/0/+1) packed into 4-bit blocks, so gzip shrinks the download to ~170 MB without changing a
# single weight. Hugging Face's CDN only serves the raw files. Caddy serves the .gz variant to
# every browser that accepts gzip (`file_server { precompressed gzip }` in docker/Caddyfile),
# so the compression work happens once here instead of on every request.
#
# Usage:
#   scripts/fetch-stt-model.sh                              # dev: writes ./models (served by Vite)
#   scripts/fetch-stt-model.sh "$EDUAVATARS_DATA_DIR/models"  # production: the volume Caddy mounts
#
# Safe to re-run: files whose checksum already matches are not downloaded again.

set -eu

TARGET_ROOT="${1:-$(dirname "$0")/../models}"
# Bump VERSION together with REVISION — the version is part of every URL, and Caddy and the
# browser's Cache API both keep a file under the same URL indefinitely.
VERSION="v1"
REPO="mrfakename/parakeet-redux-ONNX"
REVISION="0f1264f3ce3bcdab31eac2f04cdd5b720eb5fda7"
TARGET="$TARGET_ROOT/parakeet-redux/$VERSION"

# file name, sha256
FILES="
preprocessor.onnx 3de5742f5780fc8615c1d883a2a60e28621ff13d2e20d24d76e94b9e4168445f
vad-model.onnx 18dfbe344307f9eda4735d4da1fe1cd6e3be27055a6c25b4a4a2e6fe0bffde50
decoder_joint-model.int8.onnx a3d6e48bddd218743c486e0b2f3263c0e0e2f8d42785dd1e86d18a4bfc5fd79d
encoder-model.onnx ade2c65c188776b3662db620a553ab82ac7e9ca11a7be6b696bcc5190f75382e
vocab.txt d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d
"

for tool in curl sha256sum gzip; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }
done

mkdir -p "$TARGET"

echo "$FILES" | while read -r name sha; do
  [ -n "$name" ] || continue
  file="$TARGET/$name"
  if [ -f "$file" ] && echo "$sha  $file" | sha256sum -c --status; then
    echo "ok        $name"
  else
    echo "download  $name"
    curl -fL --retry 3 -o "$file.part" "https://huggingface.co/$REPO/resolve/$REVISION/$name"
    if ! echo "$sha  $file.part" | sha256sum -c --status; then
      rm -f "$file.part"
      echo "Checksum mismatch for $name — refusing to install it." >&2
      exit 1
    fi
    mv "$file.part" "$file"
    rm -f "$file.gz"
  fi
  if [ ! -f "$file.gz" ]; then
    echo "gzip      $name"
    gzip -9 -k -f "$file"
  fi
done

# The frontend reads raw (uncompressed) sizes from here for its progress bar: with gzip transfer
# encoding, the Content-Length header carries the *compressed* size while the browser hands the
# page decompressed bytes, so the header alone can't say how far along the download is.
size() { wc -c < "$TARGET/$1" | tr -d ' '; }
cat > "$TARGET/manifest.json" <<EOF
{
  "version": "$VERSION",
  "source": "https://huggingface.co/$REPO/tree/$REVISION",
  "sampleRate": 16000,
  "files": {
    "preprocessor": { "path": "preprocessor.onnx", "bytes": $(size preprocessor.onnx) },
    "vad": { "path": "vad-model.onnx", "bytes": $(size vad-model.onnx) },
    "decoder": { "path": "decoder_joint-model.int8.onnx", "bytes": $(size decoder_joint-model.int8.onnx) },
    "encoder": { "path": "encoder-model.onnx", "bytes": $(size encoder-model.onnx) },
    "vocab": { "path": "vocab.txt", "bytes": $(size vocab.txt) }
  }
}
EOF
gzip -9 -k -f "$TARGET/manifest.json"

echo "Done: $TARGET"
du -ch "$TARGET"/*.gz | tail -1 | sed 's/total/transfer size (gzip)/'
