# MotionEngine: Attribution

`MotionEngine.js`, `OverlayManager.js` and `utils.js` come from
[lhupyn/motion-engine](https://github.com/lhupyn/motion-engine) (MIT, see `LICENSE`), commit
`bd780a19e10d1cc5736a77946b04e08d658d5bf8` (v0.3.0). The avatar uses them for the gestures the
LLM marks in its replies (see `backend/app/features/chat/motion.py`).

Vendored instead of installed: the package is only published on GitHub, not on npm, so a pinned
copy keeps builds independent of that repository.

Changes against upstream:

- `MotionEngine.js`: the FaceMirror (webcam + MediaPipe) and empathic-reaction API is removed,
  together with its import, so no webcam or MediaPipe code ends up in the bundle. Nothing else is
  changed. `FaceMirror.js` and `MotionStudio.js` are not included.
- `motions.json`: only the ten gestures offered to the LLM (keep it in sync with `MOTIONS` in
  `backend/app/features/chat/motion.py`; a backend test checks this), without the FaceMirror
  `_detect`/`_react` fields. The definitions themselves are unchanged from upstream.
