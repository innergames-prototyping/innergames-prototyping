# Client Meeting 4 Nov 2026

**Attendees:** Luc, Amelie, Youri (online)

## 1. Presentation

- The team presented the project with a PowerPoint.
- Amelie went through her simulation pipeline. It simulates player characters (chatty, distracted, focused), and every action has a minimum and maximum time the user enters.
- Arien seemed engaged during Amelie's part.
- In hindsight, we didn't step back to explain what the goal of the project is.

## 2. Client feedback

**On the simulation**

- The character types differ from the player types that matter for competitive games.
- Suggest default action times for ease of use, and decide which distribution to draw them from.
- Find a cheap way to add and remove seed variables.
- Keep play time realistic. In playtests the fastest group took 30 minutes and the slowest 2 hours; that range is the starting point.
- Human interaction takes far more time than the game steps themselves. In a digital game, tapping the screen goes very fast.

**On what the output should answer**

- Games are always played by humans first. A realistic scenario for play time and other measures matters more than exploits, which only matter for competitive games.
- "Is the game as we designed it a pleasant, workable experience?"
- "Is it boring the second time?" How much variation is there, and how often can you play it before it stops being interesting?
- How often do players die at the points where they can, and is that too often or not often enough?
- Results must be actionable, e.g. what to change to make the game much harder or much easier.
- The output itself is fine.

**On the application**

- It should be failsafe; it doesn't have to be foolproof.
- Think about what the user enters when running it.
- If a PDF has a text layer, use it alongside image reading as a backup.
- The main process is in place, and the client said we can be proud of that.
- The client asked what needs to be done to make it work "good enough".

## 3. Action points

1. Share the list of calculated measures with the client so he can say what to keep or drop. The current list looks okay.
2. Add suggested default action times and choose a distribution for them.
3. Make seed variables cheap to add and remove.
4. Use the playtest range of 30 minutes to 2 hours to check that simulated play times are realistic.
5. Use a PDF's text layer when it has one.
6. Open the next presentation by explaining the goal of the project.
