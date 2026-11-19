"""Extraction: from the PDFs of a game to its rules, components and a first game model.

An agent session (Claude Agent SDK) does the judgment: what each page is, the layout, the kinds of
component, and the flags. It works only through app tools; each tool is a Python step in this
package. The bulk reading is done by many tool-less reader calls (`reader.py`) that each see one
component or one rules region.

    Round 1  Survey        render_pdfs -> view_images(previews)
    Round 2  Layout        update_config(layouts, regions) -> crop -> group -> orient -> preview
                           -> view_images(overlays), until the overlays are right
    Round 3  Kinds, read   view_images(crops) -> update_config(kinds, rules_items) -> read
    Round 4  Resolve       view_images(flagged) -> update_config(overrides) -> read_rules -> check
                           -> assemble -> cost, until no flags are left
    Round 5  Reply         final message: what was made, cost, what is unresolved
    Backend                propose_model -> validate (Pydantic) -> save game_model v1

This is a port of Luc's `extract-game-components` skill (`extract.py`).
"""
