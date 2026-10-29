---
name: extract-game-components
description: Extract a tabletop game's rules text and every physical component (cards, tiles, tokens, boards, sheets) from its PDF files into rules.txt and a game-agnostic components.json. Components the rules name that no file shows are added as entries too. Use when asked to transcribe or extract a game's rulebook and components from PDFs. Extraction only - no analysis.
---

# Extract a game's rules and components from PDFs

Turn the game PDFs the user names into two files:

- `results/rules.txt`: the rules, transcribed verbatim.
- `results/components.json`: every kind of physical component the game uses, and each different
  piece once with how many there are, in the format of `export.schema.json` (next to this file).
  `assemble` derives it from `work/components.json`, which lists every item on its own with where it
  came from, in the format of `components.schema.json`: every item the files show, plus every item
  the rules name that no file shows (see Round 3).

This is **extraction only**: record what is printed, exactly as printed. Don't explain, summarise,
model or critique the game, and don't resolve ambiguities.

**Never fix spelling, typos or grammar.** A later analysis stage looks for exactly these errors, so a
misspelling that you or a reader silently corrects is lost to it. A corrected typo is an extraction
error, just like a misread value.

## How the work is split

`extract.py` (next to this file) does everything mechanical and all the bulk reading. It cuts out
every item, groups pixel-identical copies into designs, reads every design and every rules region
with independent, tool-less model calls (each sees one item or one region), re-reads until every
value and word has a majority, flags what doesn't, runs consistency checks, and assembles and
validates the output.

Your job is the judgment: the layout, the fields, checking the overlays, and resolving what the
script flags. **Don't read component values yourself, and don't open item crops in bulk**: each image
you open costs more than dozens of script reads. Open only previews, overlays, contact sheets and
flagged crops. Don't hand work to subagents; the script already parallelises the reading.

**Never delete, move or edit reads** (`work/reads`, `work/rules/reads`) to get a different vote. When
readers disagree, decide from the image and record an override; if the image doesn't settle it,
leave it unresolved.

Run the script as `<this skill's directory>/extract.py <command>` from the working directory. It
starts its own nix-shell, so the first run takes a while. It works in `./work/` and reads
`work/config.json`, which you write (format at the end). `extract.py -h` lists the commands.

## Keep turns few

Every turn re-sends the whole conversation, so the number of turns drives your cost more than
anything else. Work in the five rounds below. Chain script commands with `&&` in one call, open all
the images a round needs in one turn as parallel Read calls, make each config change as one edit,
and don't print files you just wrote or that the script already summarises.

## Round 1: Survey

Run `extract.py render <pdf> <pdf> ...`, then open every `work/preview/*.png` in one turn. Decide what
each page is: rulebook, component sheet (fronts), backs of a sheet, board, or something else. Duplex
backs are usually mirrored left to right. `work/text/` has the PDF text layer, which is often broken
in image-exported PDFs; use it at most as a cross-check.

## Round 2: Layout and regions

Write `work/config.json` with everything except `kinds` and `rules_items`: `game`, `sources`, `layouts`
(one per component page) and `rules_regions`. Run `extract.py crop && extract.py group && extract.py
preview` (only `preview` when there are no component pages), then open in one turn every output listed
below. Fix and re-run until all are right.

**Items.** The default `segment` method finds every separate object on a page, drops thin lines (cut
lines, crop marks), and cuts each item out with its own shape. `row` follows vertical position
(offset hex rows count as rows), `col` the order within the row. Check:

- `work/preview/items_<page>.png`: exactly one red box per item; no missed items, boxes around two
  items, or items split in two.
- `work/contact/<page>.png`: the cut-out items, labelled `r<row>c<col>` **above** each thumbnail.
  Nothing clipped, and text upright.

Fix problems through the layout:

- Items split in two: raise `merge` (joining distance in pixels, default 4).
- Neighbours merged: lower `merge` or raise `line_width` (default 8). For items printed edge to edge,
  use `"method": "grid"` with cut lines from `extract.py lines <pdf stem>_p<page>` (`xs`/`ys`), or
  `box`, `rows` and `cols`. For irregular layouts, or touching items such as tiles on a photo, use
  `"method": "boxes"` with one page-fraction box per item.
- Junk (logos, page furniture): add its `r<row>c<col>` to `skip`. Every separate printed piece is a
  component, including filler or marker cards. A piece whose text reads like rules, such as a
  reference or summary card, is still a component.
- Sideways items: `rotate` (degrees clockwise) for the page, `rotate_items` per item or row
  (`{"r3c2": 0, "r5": 90}`). Readers all misread sideways symbols the same way (a sideways minus looks
  like a zero), so voting can't catch it.

**Designs.** `group` puts pixel-identical fronts into one design; any small local difference keeps
them apart. Check `work/contact/designs_*.png` and `work/contact/backs.png`. Extra designs are
harmless.

**Rules regions.** What belongs in `rules.txt`:

- All rules text: headings, paragraphs, lists, tables, and captions next to pictures. Anything
  printed on a rules page is rules text unless listed below; when unsure, include it.
- Not text inside pictures (pictured cards, tokens, boards, decoration); readers write `[image]`.
  Exception: a pictured form or summary whose printed instructions are rules, such as a score sheet.
  Give its region a `note`, e.g. "This region is a pictured form whose printed instructions are part
  of the rules. Transcribe its numbered steps as a numbered list, with their instructions, labels and
  formulas; leave out the values written into its boxes."
- Not page furniture: page numbers, and headers, footers and credit blocks repeated on pages.
  Credits go in `game.credits`. A one-off paragraph about the game, such as who made it and why, or
  where to send feedback, is rules text, even when it names the authors.
- Not text on a component (a card, a reference card, a tile) on a component sheet: that is the
  component's `text`. Text printed on a component sheet outside every component, such as an
  assembly note, is rules text.

Add `rules_regions` in reading order, one box per column or block, as page fractions
`[x0, y0, x1, y1]`, each small enough to stay legible at 1568 px. On a page made of panels (a folded
leaflet, several pages printed on one sheet), finish each panel before the next, in the order the
panels are meant to be read, and keep numbered or counted-down sections in their printed order. Give a
region of sideways or upside-down text `rotate` (degrees clockwise that make it upright): readers,
Tesseract and proofreaders then all see it upright. Don't ask readers to turn it in a `note`; they
read turned text, but silently correct its typos. `preview` draws the regions on
`work/preview/regions_*.png`, flags printed text outside every region as **UNCOVERED**, and says
what to do with it.

## Round 3: Kinds and reading

From the design contact sheets, and full-size crops (`work/items/<key>/front.png`) of the two or
three designs that differ most within each kind, write `kinds`. One crop per kind misses values that
only some designs print, or print in another place.

- `fields` are the values printed on the item, especially those encoded as symbols: `integer` for
  counted symbols, `enum` (with `enum_values`) for colours and signs, `string` for printed values
  like "+ 3%", `list` only when nothing else fits. Title and other printed text go in no field;
  readers return `title` and `text` anyway.
- Each reader sees **one item and your text, nothing else**. The kind's `description` says how to
  recognise it; each field's says exactly where the value is printed and how to read it, e.g.
  "number of filled yellow circles in the column along the left edge; do not count hollow circles".
  Describe what is printed, never what it means in the game. When the marks in one place come in
  more than one type (colour, fill, shape), give each type its own field instead of deciding which
  ones matter.
- Describe every position (the left edge, a top corner, the strip along the bottom) on the crop as
  readers see it, `work/items/<key>/front.png`, never on the sheet. Positions turn with the item: a
  strip on the left of a sideways card runs along the top of the upright one.
- Name a field after where its value is printed (`wreath_number`, `token_numbers`), not after what
  it means (`victory_points`): readers fill a meaning-named field with whatever printed number seems
  to fit. When the same sort of mark (a number, a colour) appears in more than one place, say which
  place the field reads and which to ignore. For a colour, say which shape carries it (the fill of
  the small card symbol, not its frame or border). A value that isn't printed is null, never 0.
- `count_in_rules` and `expect` come only from numbers printed in the rules: `expect` entries look
  like `{"kind": "k", "where": {"field": "value"}, "count": 20, "distribution": {"gold": {"1": 8, "2": 12}}}`
  (`where` can also filter on `title`). Both count the files' items plus `rules_items`.

**Components the rules name that no file shows** still belong in `components.json`. For every
component the rules give a number for, compare it with what the files show (the design contact
sheets). Add the ones the files don't show to `rules_items`, one entry per group:

- `kind`: a kind in `kinds`. A sub-type the rules count separately ("2 red, 4 blue") gets its own
  entry, with the sub-type as a declared field value.
- `count`: how many the files don't show.
- `source`: the rules document and page that print the number.
- `title` and `text`: the printed name and the rules' description, verbatim, when the rules give them.
- `fields`: only values the rules state. Other declared fields come out as null.

`assemble` adds `count` items per entry, marked `"from_rules": true`. Set the kind's `count_in_rules`
to the rules' total, so the count check compares it with the files' items plus `rules_items`. Don't
add a component the rules only mention in passing or as an example, or one that belongs to another
product or edition (a full version, an expansion, an advert for the retail game), and don't guess a
count. This is only about `rules_items`: text about another product printed on a rules page is still
rules text.

Then run `extract.py read` with a 10-minute timeout on the call. It reads every design and every
rules region in one queue, many at a time, and prints the component and rules flags. `rules_items` are
not read: they are not in the files.

Each design is read once first, and each reader reports which way the text runs. A design read
sideways or upside down is not read further, and `read` ends with **ORIENTATION** lines that say which
items to turn and what to do next. Every other design is read a second time (another copy where one
exists) and gets more reads, up to 5, wherever something has no majority; then `read` runs `check`.
Changing a kind's name, description or fields makes `read` read that kind again.

Each rules region is also transcribed by Tesseract (OCR). A region whose first read has exactly
Tesseract's words is done; any other is read until every word has a majority and proofread in
enlarged halves for misspellings. Reads are cached per region definition, so after editing regions,
`extract.py rules` reads only the changed ones, then runs `preview` again.

## Round 4: Resolve

`check` (also run at the end of `read`) and `rules` print every flag with what to do about it:
component flags (CONFLICT, TEXT UNCERTAIN, SPELLING, DESCRIPTION, ORIENTATION, CHECK) and rules
flags (NO MAJORITY, SPELLING; region images in `work/rules/region_NN.png`). CHECK lines catch what
voting can't, because every reader can make the same mistake. Open every flagged crop and region
image in one turn, record all decisions in one config edit, and run `extract.py check && extract.py
assemble && extract.py cost`. Repeat only if something is left.

Decide every flag from the image alone. An override or rules fix records only what the image shows:
never guess, and never set a value to agree with the rules or a count check. If the image doesn't
settle it, leave it and say so in your reply.

## Round 5: Reply

`assemble` writes `work/components.json` and validates it (fix the config until it prints `VALID`),
then writes `results/rules.txt`, `results/components.json` (the same without sources, ids, notes and
confidence, identical items merged with a count, for the steps after extraction) and
`work/review.html` with each rules region beside its text. Reply with:

- the two paths, and the review page for the user to read;
- the validation result and the item count per kind, with how many of each came from `rules_items`;
- the model cost from `extract.py cost`;
- every override, fix and exclusion you made, and anything left unresolved;
- the three things you are least sure about.

## Config format (`work/config.json`)

```json
{
  "game": {"title": "<as printed>", "credits": ["<as printed>"]},
  "output": "results",
  "sources": [
    {"file": "<file>.pdf", "pages": 2, "content": "component sheet: fronts on page 1, backs on page 2",
     "layout": "10 x 11 cards, backs mirrored left to right"}
  ],
  "layouts": [
    {"file": "<file>.pdf", "page": 1, "back_page": 2, "back_mirror": "horizontal",
     "method": "segment", "merge": 4, "line_width": 8, "min_area": 0.0005,
     "rotate": 0, "rotate_items": {"r3c2": 90}, "skip": []},
    {"file": "<file>.pdf", "page": 1, "method": "grid", "xs": [0, 500, 1000], "ys": [0, 700], "inset": 4},
    {"file": "<file>.pdf", "page": 1, "method": "grid", "box": [0.05, 0.05, 0.95, 0.95], "rows": 3, "cols": 3},
    {"file": "<file>.pdf", "page": 1, "method": "boxes", "boxes": [[0.1, 0.1, 0.4, 0.3]]}
  ],
  "kinds": [
    {"id": "kind_a", "name": "<name>", "description": "<how to recognise it>",
     "fields": [{"name": "field_a", "type": "integer", "description": "<where and how to count>"},
                {"name": "field_b", "type": "enum", "enum_values": ["x", "y"], "description": "..."}],
     "count_in_rules": null, "back": "<what the back looks like>", "notes": ""}
  ],
  "rules_items": [
    {"kind": "kind_a", "count": 12, "source": {"file": "<rules>.pdf", "page": 2},
     "title": "<printed name, if the rules give one>", "text": "<rules description, verbatim, optional>",
     "fields": {"field_b": "x"}}
  ],
  "back_kinds": {},
  "expect": [],
  "separate": [],
  "overrides": {},
  "rules_regions": [{"file": "<file>.pdf", "page": 1, "box": [0.03, 0.05, 0.5, 0.5]},
                    {"file": "<file>.pdf", "page": 2, "box": [0.5, 0.6, 0.97, 0.95], "rotate": 180},
                    {"file": "<file>.pdf", "page": 2, "box": [0.03, 0.6, 0.5, 0.95], "note": "<only when needed>"}],
  "rules_fixes": [],
  "rules_excluded": [{"file": "<file>.pdf", "page": 1, "reason": "cover"},
                     {"file": "<file>.pdf", "page": 2, "box": [0.03, 0.02, 0.95, 0.05], "reason": "credits header"}],
  "extraction_notes": []
}
```

- `back_mirror`: `horizontal` (default), `vertical` or `none`. A page of backs belongs to its fronts'
  layout as `back_page`; don't list it as a layout of its own, or every back becomes an item. Leave
  out `back_page` only when a page has no backs.
- `separate`: item keys that must never be grouped with anything (use this if a group looks wrong).
- `rules_items`: one entry per group of components the rules name that the files don't show (see
  Round 3). `assemble` turns each into `count` entries in `items`. A config still using `not_in_files`
  is refused; move those names into `rules_items` with their counts.
- Pixel coordinates refer to the page renders in `work/pages/` (300 dpi by default).
