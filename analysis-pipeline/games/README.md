# Game extractions

Output of the extraction skill for five games. Each folder holds:

- `rules.md`: the rulebook as text, transcribed as printed (typos kept).
- `components.json`: every physical component (cards, tiles, tokens, pieces) with the values printed on it, in the format of `components.schema.json`.

| Folder | Game |
|---|---|
| `7-wonders-duel` | 7 Wonders Duel Solo |
| `bottom-line` | The Bottom Line (older skill version: components the rules name but no file shows are in a `not_in_files` list instead of in `items`) |
| `catan-with-items` | Catan: pictured components read from the rulebook images, the rest from the counts in the rules |
| `catan-items-as-rules` | Catan: every component built from the counts in the rules (`"from_rules": true`) |
| `stratego` | Stratego (rulebook only, so every component comes from the rules) |
