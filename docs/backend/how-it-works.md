# How It Works

What happens to a board game from the moment you upload it until you get the results. The technical version is in [Pipeline Flow](./pipeline-flow.md).

```mermaid
flowchart TD
    upload["You upload the game<br/>rulebook, cards and board as PDFs or photos<br/>optional: numbers you already know, such as the play time"]

    subgraph extraction["Part 1: Extraction - reading the game"]
        look["The AI looks through every page"]
        cut["It cuts out each card, tile and board"]
        read["It reads the rules and every component<br/>several times, and keeps the answer most reads agree on"]
        list["Result: the rules text<br/>and a list of all components"]
        look --> cut --> read --> list
    end

    checkA{"Did you ask to check<br/>the work in between?"}
    approveA["You check the rules and the component list<br/>approve them, or upload a corrected version"]

    subgraph analysis["Part 2: Analysis - playing the game"]
        understand["The AI writes down how the game works<br/>and estimates how long a game takes"]
        checkB{"Did you ask to check<br/>the work in between?"}
        approveB["You check what the AI understood<br/>approve it, or add numbers, answers and notes"]
        build["The AI builds a computer version of the game"]
        play["The computer plays the game many times"]
        understand --> checkB
        checkB -- yes --> approveB --> build
        checkB -- no --> build
        build --> play
    end

    report["You get the report<br/>play time, balance, problems found,<br/>questions for the designer and what the AI had to assume"]

    upload --> look
    list --> checkA
    checkA -- yes --> approveA --> understand
    checkA -- no --> understand
    play --> report

    classDef person fill:#fff4d6,stroke:#c98a00,color:#000
    class upload,approveA,approveB,report person
```

The yellow boxes are the moments where a person takes part. All other steps run on their own.

- **Checking in between is optional.** When you start, you choose if the run stops for you. If you do not choose this, the run goes from upload to report without a stop.
- **You can stop a run at any time.**
- **A finished run can be played back**, so you can see what the AI did step by step.
