You are writing an English narration script for one page of a technical course.

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
      "text": "English narration sentence(s).",
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
