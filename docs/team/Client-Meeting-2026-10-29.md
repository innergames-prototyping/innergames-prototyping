# Client Meeting 29 Oct 2026

**Attendees:** Luc, Amelie

## 1. Demo

- Luc showed the breakthrough in the extraction step: the script now gives back the context and rules the orchestrator needs. The AI has nothing left to do once the script has been made.
- Amelie went through her simulation pipeline and the results it produced.

## 2. Client feedback

**On the pipeline**

- The client liked that the AI doesn't need to do anything once the script is created.
- Move times should go in as in-between steps, as assumed variables the user enters.
- On the results, because it was a game he was unfamiliar with: "Looks usable, but it's difficult to say."

**On what the output should focus on**

- Usable feedback matters most. Finding every little point matters less.
- The goal isn't games that can't be exploited at all. The focus is playability: how many rounds a game takes and other soft characteristics.
- Spending weeks making a game perfect against exploits isn't worth it. "Okay" is enough.
- Focus on actionable output.

**On data storage**

- Look into using SQLite as the data store instead of JSON.

## 3. Action points for next meeting

1. Run the pipeline on a game the client actually made, so he can judge whether the results are right.
2. Present with a PowerPoint.
3. Look into SQLite as a replacement for the JSON data store.
