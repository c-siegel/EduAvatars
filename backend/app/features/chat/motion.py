"""
Avatar Body Language (Motion Markers)

Projects with motion_enabled let the LLM mark a gesture in its reply as "::name::" (e.g.
"::wave_right:: Hello!"). The markers are cut out here before the text is spoken (TTS), shown or
saved; the names travel to the browser separately, where the vendored MotionEngine
(frontend/src/vendor/motion-engine) plays them on the avatar. Markers in the text instead of tool
calls keep the gesture at its place in the sentence and cost the model only a few tokens.

Only the curated gestures in MOTIONS are recognized. Anything else that merely looks like a marker
stays in the text: C++ code such as "std::vector::size" must survive, and a gesture the model
invented then shows up in the saved transcript, which is where a teacher testing this looks.

How to use:
    system_prompt = f"{preprompt}\\n\\n{MOTION_PROMPT}"
    clean, marks = extract_motions(reply)   # clean text + where each gesture was
"""

import re
from dataclasses import dataclass

# Must match the motion dictionary the frontend registers (frontend/src/vendor/motion-engine/
# motions.json, see tests/test_motion.py), otherwise the browser drops a gesture the LLM was
# offered. The descriptions are for the LLM: when a gesture fits, not what it looks like.
MOTIONS: dict[str, str] = {
    "wave_right": "wave hello or goodbye",
    "nod_yes": "nod to agree or to confirm a correct answer",
    "shake_no": "shake your head to gently say no or point out a mistake",
    "thumbup_right": "give a thumbs up to praise good work",
    "applause": "clap to celebrate a success",
    "point": "point to stress an important idea",
    "shrug_confused": "shrug when something is unclear or depends on the situation",
    "thinking_face": "look thoughtful while you consider a question",
    "raise_eyebrows": "raise your eyebrows at a surprising or interesting fact",
    "warm_smile": "smile warmly to encourage or reassure",
}

# English on purpose, like the rest of the system-prompt scaffolding: the model replies in the
# project's language either way, and the names are identifiers, not words to translate.
MOTION_PROMPT = (
    "You appear as an animated 3D avatar and can use body language. To make a gesture, write its "
    "marker exactly as ::name:: in your reply, right where the gesture should happen, e.g. "
    '"::wave_right:: Hello!". Markers are neither spoken nor shown, so never mention them. Use at '
    "most one marker per sentence and only when it fits naturally; many replies need none. Use "
    "only these gestures:\n" + "\n".join(f"- {name}: {use}" for name, use in MOTIONS.items())
)

# Whitespace inside the colons is tolerated because models sometimes write ":: nod_yes ::".
_MARKER_RE = re.compile(r"::\s*(" + "|".join(map(re.escape, MOTIONS)) + r")\s*::", re.IGNORECASE)


@dataclass(frozen=True)
class MotionMark:
    """One gesture the LLM used: its name and the character position in the cleaned text where
    the marker stood (0 = before the first character)."""

    name: str
    offset: int

    def to_json(self) -> dict:
        return {"name": self.name, "offset": self.offset}


def extract_motions(text: str) -> tuple[str, list[MotionMark]]:
    """Cut every known marker out of `text`; return the cleaned text and the marks in order.

    The space next to a removed marker is dropped once, so "Yes ::nod_yes:: exactly" reads
    "Yes exactly" instead of carrying a double space into TTS and the transcript.
    """
    clean = ""
    marks: list[MotionMark] = []
    pos = 0
    for match in _MARKER_RE.finditer(text):
        clean += text[pos : match.start()]
        pos = match.end()
        if not clean or clean[-1].isspace():
            while pos < len(text) and text[pos] in " \t":
                pos += 1
        marks.append(MotionMark(match.group(1).lower(), len(clean)))
    clean += text[pos:]

    stripped = clean.strip()
    shift = len(clean) - len(clean.lstrip())
    return stripped, [MotionMark(m.name, min(max(m.offset - shift, 0), len(stripped))) for m in marks]
