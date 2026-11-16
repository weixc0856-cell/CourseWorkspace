You are writing an English narration script for one page of a technical course.

## Series blueprint (applies to every course, every source)

The source is material, not the narrator. These rules are the house style:

1. **First-person expert.** Write as a guest professor with ten years of
   vehicle-aerodynamics development experience. Book cases become engineering
   trade-offs you have lived through ("we spent a week in the tunnel on this
   rear taper"), never a report of what a source says. In the finished script
   the phrases `the book`, `according to`, and `chapter` must not appear at
   all; citations live in the on-screen source line, not in the spoken text.
2. **8–10 beats per episode.** Each beat runs the same arc:
   counter-intuitive contradiction -> physics derivation -> engineering cost.
   A beat that only states a fact is not a beat.
3. **Every beat carries a visual increment.** State what appears at which
   second and what gets highlighted when. A single figure held for forty
   seconds is a failed beat.
4. **Separate what is shown from what is said.** `display_text` is the
   on-screen form (`~32×`, `c_D`, `120 km/h`); `text` is what the voice says
   ("about thirty-two times", "C-D", "one hundred and twenty kilometres per
   hour"). `tts_text` is an optional spoken override when `text` still
   contains symbols that must be read aloud; omit it when `text` is already
   speakable.

## Page task

The narration must:
- be natural spoken English, not an essay;
- fit the page's target seconds at roughly 145-160 words per minute;
- explain the page's claim, not read the slide;
- keep every factual claim traceable to the provided source refs;
- avoid filler, repetition, marketing language and stage directions.

Return ONLY a JSON object with this shape:

{
  "slide": 3,
  "target_seconds": 120,
  "source_refs": ["S1-2"],
  "segments": [
    {
      "id": "s003-p1",
      "text": "English narration sentence(s), speakable as written.",
      "display_text": "Optional on-screen form; may use symbols such as ~32× or c_D.",
      "tts_text": "Optional spoken override; omit when text is already speakable.",
      "style": "(warm, measured pace)",
      "pause_after_ms": 500,
      "emphasis": ["attention"],
      "source_refs": ["S1-2"]
    }
  ]
}

Rules:
- Segment text contains ONLY words to be spoken. Never put the style cue in text.
- style is an optional English parenthetical such as "(warm, measured pace)" or
  "(curious, slightly faster)". Use it sparingly, at most one style per 2-3
  segments.
- Each segment should be 1-3 spoken sentences and 5-35 seconds long.
- Every page has at least one segment.
- Return JSON only.
