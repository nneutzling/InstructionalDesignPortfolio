# Instructional Design Portfolio — Nicole Neutzling

Static portfolio site, ready for GitHub Pages.

- `index.html` — portfolio page (case studies, process, skills, contact)
- `support.js` — runtime the page needs; keep it next to `index.html`
- `images/` — screenshots and profile watermark
- `assets/shader-banner.js` — animated ShaderGradient background for the "Let's work together" banner (source in `tools/shader-banner/`)
- `courses/` — hosted eLearning modules, one folder each, linked from the case studies
  - `alpine-club/` — Alpine Club of Canada Trip Leader Guide, standalone web export (public)
  - `bow-valley/` — Mountains of the Bow Valley, web rebuild of the Storyline interaction (public)
  - `peak-pmp-sample/` — 8-question public sample of the Peak PMP baseline quiz (full banks stay private)
  - `larch-salmon-game/` — Swim Upstream game from the Larch & Lichen sockeye lesson (copied from the Larch & Lichen repo)
  - `larch-life-cycle/` — Sockeye life cycle explorer from the same lesson (copied from the Larch & Lichen repo)
  - `ipac-refresher-game/` — IPAC Routine Practices scenario game (unpublished prototype, cleared for portfolio use)

To refresh the two Larch pages after the lesson changes, run `tools/extract-larch.py` (usage at the top of the file) and copy any new `audio-*.mp4` into `courses/larch-life-cycle/lesson-assets/`.

REDP, PHSA and IPAC are client work: show them with screenshots and video only, never the course files.

## Adding a course

1. Create `courses/<course-name>/` and upload the unzipped web output into it.
2. In `index.html`, add a link to that case study's `links` list:
   `{ type: 'live', label: 'Open the course', url: 'courses/<course-name>/index.html' }`
   (for a Storyline publish the start page is usually `story.html`).
