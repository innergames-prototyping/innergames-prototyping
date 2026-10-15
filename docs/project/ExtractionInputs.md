# Extraction Inputs

Date: 14 Oct 2026

## Goal

The extraction skill (`.claude/skills/extract-game-components`) turns a game's files into `rules.txt` and `components.json`. Today it only accepts PDFs. The user should be able to drop any mix of files into the frontend and not have to think about formats: PDFs, docx, plain text and individual asset images (one card or tile per file). Photos of physical components are out of scope.

## Direction

Conversion is deterministic Python; the model only decides what each piece is and reads what exists only as pixels.

`extract.py render` accepts any dropped file and converts by extension, so the backend and the agent use one command and the agent always starts from the same inventory: page images, exact text sources and asset images.

| Input | Conversion |
|---|---|
| PDF | Unchanged: page images and text layer through poppler |
| docx | Unzip: text in order from `word/document.xml` (including tables and text boxes), images from `word/media/`. No LibreOffice; old `.doc` is refused |
| txt / md | Used as is |
| PNG / JPG / WebP | Each file is a one-page document |
| zip | Unpacked first, then its contents are handled as above |

Exact text (txt, md, the text of a docx) goes straight into the rules without reading or voting. That is cheaper and keeps typos without effort. If the same rulebook arrives in two formats, the exact-text one wins.

## What changes in the skill

- **What an image file is.** One asset, a sheet of assets, a back, or a rules page. The agent decides this per file, as it now decides per PDF page.
- **Pairing fronts and backs.** Matching by file-name pattern assumes tidy names. The config needs an explicit pairing (or "these fronts share this back") that the agent chooses from names and images.
- **Counts.** A folder of assets usually has one image per design, not per copy. The skill must say where the count comes from (the rules, the file name, the image) and which wins.
- **Text sources in the rules.** The agent still decides what is rules (not credits or adverts) and where each text source sits among the PDF regions.
- **Images inside a docx have no page position.** Components pictured there are the same open question as components pictured in a rulebook: do they count as shown in the files?

## Order

1. Image files as one-page documents (nearly free).
2. Exact text sources (covers txt, md and docx text).
3. Images from docx.
4. Explicit front/back pairing and counts for asset images.

Each step is tested on at least one real game, with repeated runs as in the earlier extraction tests.
