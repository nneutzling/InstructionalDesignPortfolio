# Instructional Design Portfolio — Nicole Neutzling

Static portfolio site, ready for GitHub Pages.

- `index.html` — portfolio page (case studies, process, skills, contact)
- `support.js` — runtime the page needs; keep it next to `index.html`
- `images/` — screenshots and profile photo
- `courses/` — hosted eLearning modules, one folder each, linked from the case studies
  - `alpine-club/` — Alpine Club of Canada Trip Leader Guide, standalone web export (public)
  - `bow-valley/` — Mountains of the Bow Valley, web rebuild of the Storyline interaction (public)

REDP, PHSA and IPAC are client work: show them with screenshots and video only, never the course files.

## Adding a course

1. Create `courses/<course-name>/` and upload the unzipped web output into it.
2. In `index.html`, add a link to that case study's `links` list:
   `{ type: 'live', label: 'Open the course', url: 'courses/<course-name>/index.html' }`
   (for a Storyline publish the start page is usually `story.html`).
