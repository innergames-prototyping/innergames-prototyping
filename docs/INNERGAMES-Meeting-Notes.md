# Meeting Notes

# Meeting with Client 1 - 15:00 17 Sept 2026

# Client Meeting — InnerGames

**Date:** 17 September 2026

**Project:** Project Pipeline

---

## 1. Client and context

InnerGames develops physical games, runs workshops, and uses its games to teach; the games are instruments of education and awareness rather than entertainment products.

## 2. Production and prototyping process

- Design starts on paper: cutting and assembling paper prototypes by hand, then moving into digital for production.

- One prototype is close to final production spec.

- Prototypes are being tested with the final target groups; the production version will be physically identical to the tested physical copy.

- Material tension raised by the client:

  - Eco paper is preferred for production models, but its colour fades easily.

  - Lamination makes a component feel like plastic, but is arguably the more eco-friendly choice because of the added durability.

- Test copies have to stay cheap, so eco stock is not used for testing rounds.

## 3. Primary subject game — "KansenKeren"

**Theme and intent**

- Latest game; the subject is the course of a life.

- Each player has a profile card and persona with a backstory: who this person is.

- The purpose of the game is to make everything positive.

- The game is designed to let players feel how bad some people's lives can be. The stated aims are spreading awareness and empathy for the elderly.

**Mechanics**

- Each persona has aspects, represented by dots that are distributed across the board.

- A persona can hold good situations or problems — money trouble, family trouble, and so on.

- Turn loop: throw the dice, move the pawn.

- Landing on red forces the player to add another red somewhere else on the board.

- The educational core is the justification step: the player has to explain the causal link, e.g. why the financial aspect went red because the social aspect went red.

- On landing, a red dot can be swapped to green and a green dot to red.

- The game is finished when the persona has all green dots (good ending) or all red dot (bad ending). Once the whole board is filled, play continues.

**Format**

- Multiplayer and collaborative.

- Not a complex game, but there are a lot of permutations.

- Target average play length: one hour.

- Intended for use in classes.

**The designers' open problem**

- They cannot currently work out how long it takes to reach all green or all red. This is the question being handed to us.

## 4. Second game - "Sociality"

- Structured more like a written story.

- Design principle for both games: playable without any theoretical knowledge of the subject matter.

- Stated objective: players should actually finish the game.

- Only two games are currently suited to this kind of product testing.

## 5. The assignment

- Produce an estimate of, for example, the chance that a player finishes the game within one hour.

- The client wants actionable solutions.

- The board will be used in classes.

- The hour is an objective, but extensive testing is needed to keep sessions within that span.

- Deliverable expectation: an MVP, and a general solution rather than one hard-wired to a single game.

- Optimisation focus: the outcome has to be valuable, since the tool will not be used much.

## 6. Constraints and acceptance criteria

- Acceptable deviation in total play time: no more than 5% above or below the target time. This is the goal the client asked us to aim for, not a hard pass/fail requirement.

- The acceptable figure differs per game — 5% is not a universal rule.

## 7. Legal and IP

- No NDA. Protection rests on copyright and model rights.

- No secrets: every aspect of the games may be discussed openly.

- The prohibition is on copying the design and the gameplay.

- All usage must be for studies only.

- AI use is approved by the client.

- Licence: the software must be proprietary, All Rights Reserved. The GitHub repository must be private.

- Portfolio use is permitted.

## 8. Technical and delivery constraints

- The delivery platform must be easy for future university students to pick up.

- No heavy servers. It must be cheap and testable by students.

- Budget is a consideration specifically with regard to AI token usage.

**Required features**

- The system has to state its assumptions.

- The system then has to show the details behind a result.

- The system could be visual — this would be nice to have.

- The system needs to output accumulated simulated information.

## 9. Process, collaboration and data

- Sprint deliverable: a presentation at the end of each sprint.

- Meeting cadence: a visit once a week at the start of the semester, then once per sprint.

- The games may be taken off-site for testing and fact-checking.

- Testing may be benchmarked against other board games of similar complexity. The bar should be there but should not be set very high; Catan is extremely flexible, whereas the InnerGames titles are relatively simple.

- Testing data will be needed, because people do not find everything. Access to existing testing data would be useful; the client will try to find some but is uncertain whether any exists.

---

# Group Meeting 13:00 1 Oct 2026

## 1. Process Chart

- We would draft a process chart on a whiteboard in order to begin to flesh out a full understanding of our project.

- We had based the chart off earlier ideation from the Github Issues Repo and prior discussions.

- Amilie would pen the bulk of the chart and would pitch it to Luc and Ralph. Both Students would give their own opinions and criticisms.

- Luc would end up finding a whole in the Chart and suggest we add a Cache, which turned into a Profile system.

## 2. Division of Responsibilities

- Amilie, Luc and Ralph discussed how to divide group responsibilities with the process chart in mind. We had to assume what our 4th member would want to do since he was sick.

- We discussed and decided to give UI Responsibilities to Ralph, Amilie would work on the Simulation and Analysis segments, Luc would work on the file conversion segment and Yoeri would work on the LLM optimisation and set up sides.

- The full specifics of each responsibility was detailed in a separate document.

## 3. Misc Report

- We discussed we’d work out the technical issues and agreed on discarding the CLI UI and move straight to wireframing a proper WebUI since a CLI UI would be too clunky for deployment and testing.

- We additionally outlined the three research documents we needed to get published before next week. This was as follows: Competitor Research, System Research & LLM Research. Amilie would take the first two and Ralph would do the final one.

- Ralph would agree to get a wireframe out by the end of the week and Luc would additionally agree to produce a full process chart, bullet point the competitor research.

## 4. Follow Up Discussion

- Following end of the meeting Amilie and Luc got to work on documentation and formalising the process diagram. However some issues came up with optimisation.
- Luc made the point on LLMs being over used and the pipeline being too janky and not smooth.
- Amilie and Luc had lengthy debate and discussion over the pipeline structure. Both eventually settled into an agreement by dividing up previously straight simulation & analysis pipeline into segmented optional tabs that could be ran to save on tokens.
- Simulation would be removed from LLM workload and script would be run locally to be injected into local widgets.
- Analysis could be prompted by User if deemed necessary.
- LLM "Blackbox" would be one seamless process to the user but under the hood go through a multi step check internally.
- We ended up redrawing the latter half of the process chart and getting it pictured.

# Group Meeting 15:00 8th Oct 2026

## 1. Discussion of Workload

- Weekend work isn't expected.
- Everyone must claim 1 Github issue and talked about how they worked at it or how they thought about it at the end of next Monday.
- When working on parts of the application that collide, students must communicate with each other and co-ordinate their research and the parts of their work that intersect with other people's work.
- Ralph to get multiple wireframes done by Thursday in order to show to the client.
- Luc to email client, teachers & fill out Feedpulse.
- Youri to send research material to Amilie.
- Amilie to document meeting & write up research document for LLM prompt size. 

## 2. Discussion of Communication

- 11am Weekly meeting with teachers
- Weekly email to client.
- At least 1 client meeting per sprint for feedback.
- Students cannot use DMs to talk to each other and must use the discord server.
