You are writing the viewer-facing slide and the speaker notes for one page of a technical course.

The slide is what the audience sees. The speaker notes are for the instructor.
The narration script is already written and must NOT be duplicated in the slide.

Return ONLY a JSON object with this shape:

{
  "slide": 3,
  "title": "Short page title",
  "slide_markdown": "Markdown/HTML body for the slide, excluding the title",
  "zh_sub": "One concise Simplified Chinese translation of the key idea, or empty string",
  "technical_check": "The one premise most likely to be stated incorrectly on this page"
}

Rules:
- Keep slide_markdown under 1200 characters. Prefer short bullets, one equation,
  one diagram reference, or one code block.
- No `$...$` math delimiters. Use HTML <sub>/<sup> and Unicode symbols.
- Do not put speaker notes, timing, or stage directions in slide_markdown.
- zh_sub is a viewer-facing Chinese summary, not a word-for-word translation of
  the narration.
- technical_check is a short caution for the instructor.
- Return JSON only.
