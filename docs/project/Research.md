# Research Document

## Summary

InnerGames tests a finished board game prototype by playing it with large groups of people. Testing like that is slow and it does not always catch every issue: things like exploits, games that never end or situations the rules do not cover do not always come up, which leads to poor performance when the game gets rolled out. InnerGames wants a tool which can simulate games from their rule and asset files and which can find those problems consistently, for at most €10 per analysis run.

To find out how such a tool should work, we asked the client how testing happens today, compared existing game engines (Tabletop Simulator, Ludii and OpenSpiel) and built a first version of the analysis as a claude markdown skill. We ran that skill with three frontier models on The Bottom Line, a game with a known exploit.

None of the existing engines fit: they either do not enforce rules, cannot express the discussion-driven games InnerGames makes, or add a large dependency for little gain. When testing, the models instead wrote a Python simulation of one game with a known exploit themselves, and found it in every run for €3 to €10. For The Bottom Line specifically over 3000 paired games, the player using the exploit won 68.5% of the time.

This rests on one game and a handful of runs, so it shows the approach can work, not that it finds every problem. Which model to use for each step and which player behaviours a simulation needs are still open. That said, the client does not mind prototypes going to a cloud AI provider, so proprietary AI is fully on the table.

Our advice is to create a local web tool that turns the files into a game description, checks whether the game can be modelled, has an AI write the simulation with every assumption exposed as a setting, and shows the results in a dashboard. The next iteration should test more games, compare models per step and decide the default player behaviours together with the client.

## Introduction

InnerGames creates educational board games with workshops alongside them to teach groups of people how to play. When they have rules, assets and other items finalised, they go out and give the games a test run with say 100 people to see if they can find any exploits, games that don't end, situations the rules don't cover and so on. Besides the fact these tests are really time-consuming, they often do not find every problem with the game. This means they might still be surprised when actual players go on and play the games during actual workshops. The product InnerGames is asking for is a way to digitally simulate any game based on PDFs with rules and assets to find out those bugs in advance, so early testing becomes both more efficient as well as effective.

This document goes over the constraints of the project and research we did for it. It answers five sub-questions, before giving our advice and further steps.

## Research questions

Main question: "How can a tool turn files containing assets and rules of any board game into actionable results using on-the-fly simulation and static analysis using LLMs for less than €10 per run?"

| Nr | Sub-question | Method |
| --- | --- | --- |
| 1 | How do InnerGames designers test a prototype today, and what does a result need before they trust it? | Field: interview, document analysis |
| 2 | What already exists for describing and simulating board games? | Library: literature study, available product analysis |
| 3 | Can an LLM read the files of a prototype well enough to find real problems? | Workshop: prototyping. Lab: system test |
| 4 | Which way of making a game executable fits this project best? | Workshop: prototyping, multi-criteria decision making |
| 5 | What does sending unreleased prototypes to an AI provider mean for InnerGames? | Library: literature study. Field: interview. Showroom: ethical check |

## Findings

In this section I go over each subquestion as outlined above and explain what we did to answer it and what we found.

### How do InnerGames designers test a prototype today, and what does a result need before they trust it?

We asked the stakeholder about how they test today and what log they keep of exactly what they look for and what they find. His response is that currently it's all a bit in the air. First and foremost testing happens with large groups of people as a kind of trial run, but this isn't a formal process by any means. When we asked him about prior testing data to compare against, he wasn't sure if he even had any.

### What already exists for describing and simulating board games?

#### Tabletop Simulator

Tabletop Simulator [1] is the first tool that comes to mind, but what they do is offer the tools to put pieces on a table in a certain way, and to get a PDF print of the rules. It's about facilitating playing the game, but not about enforcing rules at all. You can cheat in the game much as you can cheat in real life. Not suitable for simulating anything.

#### Ludii

Ludii [2] is a generic programming language based on lisp that is capable of modelling any strategy game in a fairly decent way. For games that have strict rules about how to proceed at each step, this actually seems quite promising. The reason we did not choose it however is because of the nature of the games InnerGames makes: many decisions and proceedings are based on discussion and arguments, which cannot be modelled in code that easily. Cards are also an afterthought and overall it's not very mature. LLMs also struggle writing Ludii [3] compared to writing python. It's something to keep in mind when the client wants to visualise the simulated game, but otherwise isn't a good fit.

#### OpenSpiel

Google Deepmind has developed another generic game engine with python bindings. That seemed most promising at first, but the problem is that this is a 300mb dependency that it's hard to justify using over writing some of the logic on the fly. The AI is still outputting most of the tokens, but has to take more into consideration as a consequence of targeting this spec. The way we currently see it is that it's on our radar if custom methods don't hold up, but it's doing most of the easy stuff, being bot play on a game that was already generated anyway.

### Can an LLM read the files of a prototype well enough to find real problems?

We tested this by giving a little bit of project context to current frontier models (tested on Opus 5, Astra 6 and Fable 5.1). We created a `SKILL.md` file that instructed the models to do the following:

1. Read input documents and flag anything that's missing.
2. Write the rules down mentioning any ambiguity but otherwise without judging them.
3. Simulate random and greedy players in a python sim.
4. Check afterward that results can be reproduced and match the rulebook's example.
5. Report play time, game balance and any exploits.
6. Say which numbers are trustworthy.

We then let them loose on The Bottom Line, a boardgame developed by the university of Maastricht to help first year students through their Finance course. This game has a known exploit (lending as much as possible without spending nets a lot of score) as well as other smaller issues like division by zero and the fact gold can run out.

With these things in mind we ran the experiment a few times, and _we found that it could reproduce each problem flawlessly every time_. It also cost around €3-10 per run, within budget. Concretely, "the exploiting seat wins 68.5% in paired runs with the same seeds (n = 3000), and playing greedy for the exploit adds 17 minutes to a game."

It should be noted that this does not mean that we can guarantee it will find everything every time working like this, but it does mean that frontier models are already capable of work like this. We can now focus on reducing cost and ensuring quality through every run. Precision is important.

### Which way of making a game executable fits this project best?

We've discussed how we want to distribute the system, and the client wants something he can run every other month on his own. We initially settled on three options:

1. CLI, since the client is technically inclined,
2. A local (web-based) UI,
3. A website

A CLI would be the easiest to get working quickly, because we can skip any design steps and focus just on what text goes in and what goes out. A local web UI would fit a similar usecase where the user does not have to log in to anything, but would require more design work to make it convenient to use. It would also allow more options to display an eventual results dashboard, and can make interaction more intuitive. A website would mean we could distribute the product, but this isn't what the client has asked for and would require a lot more scaffolding in terms of auth and security on top of a landing page and so on.

After some internal discussion we went with a local web UI. This has the advantage of offering the team to work on UI/UX in a familiar context while also providing the nicer of the two interfaces for the client.

### What does sending unreleased prototypes to an AI provider mean for InnerGames?

InnerGames has actually said that due to the scale they work with and considering the specific target audience they have, sending any proprietary materials to Anthropic or any other AI provider isn't a big concern for them at the moment. While there are signals that in the past at least OpenAI might have trained on user input [4], they currently say they do not train on API queries and enterprise plans. We do want to test open-weight models which would allow either running on their own hardware or on rented GPU which could keep everything local, but from their point of view, this isn't a concern yet. Staying within budget is much more important comparatively.

## Conclusion

In search to answer our main question, "How can a tool turn files containing assets and rules of any board game into actionable results using on-the-fly simulation and static analysis using LLMs for less than €10 per run?", we went over 5 subquestions. We have drawn the following conclusions:

1. InnerGames' current testing methods are messy and easy to improve on, but not easy to build on because they do not have any formal method they apply.
2. Current game modeling languages or frameworks exist but don't fully fit our goals, for the time being, so we'll generate simulations fully on the fly.
3. The simplest product we could give him is the skill we made in an hour and to tell him to get a €20 claude subcription, but we think we can create a more frictionless experience. In our testing, current frontier models have been shown to perform so well that a simple claude skill as product is even on the table, though.
4. We're going with a local web-based UI over a CLI because it leaves more UI work for us and is more capable of creating a better workflow for the client through buttons and a nicer dashboard.
5. Sending proprietary game models to Anthropic or OpenAI isn't a concern at the moment.

## Advice

Current proposed workflow:

1. Interface takes PDFs, plain-text files and images,
2. Normalise these into a json with assets and a markdown file with the rules
3. Static analysis: is there a turn structure, an ending sequence. Can the game be modelled?
4. Write the game model in python with every assumption and lever encoded in the file. Provide the user with those levers so if they want to change anything, they can boolean enable certain features or change the numbers.
5. Display those levers + the results into a dashboard, updating it as the user makes changes.

There are also two other questions to answer as sub-sub questions:

1. Which AI model should we use? This will require more testing to optimize for performance as well as cost. Different models might excel at different parts of the process.
2. Which player behaviours give useful results? This will involve the stakeholder, a deeper dive into their different games and more testing again.

## References

[1] Berserk Games, "Tabletop Simulator." [Online]. Available: https://www.tabletopsimulator.com/ (accessed Oct. 5, 2026).

[2] É. Piette, D. J. N. J. Soemers, M. Stephenson, C. F. Sironi, M. H. M. Winands, and C. Browne, "Ludii – The Ludemic General Game System," in *Proc. 24th European Conference on Artificial Intelligence (ECAI 2020)*, IOS Press, 2020.

[3] T. Tanaka and E. Simo-Serra, "Grammar-based Game Description Generation using Large Language Models," *IEEE Transactions on Games*, 2024, early access. [Online]. Available: https://arxiv.org/abs/2407.17404

[4] E. Kim, "Amazon warns employees not to share confidential information with ChatGPT after seeing cases where its answer 'closely matches existing material' from inside the company," Business Insider, Jan. 2023. [Online]. Available: https://www.businessinsider.com/amazon-chatgpt-openai-warns-employees-not-share-confidential-information-microsoft-2023-1 (accessed Oct. 5, 2026).
