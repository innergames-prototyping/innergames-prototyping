# InnerGames Prototyping

A pipeline that reads a board game prototype and tests it by simulation, so a game designer finds problems before human playtesters do.

## Language

### The pipeline

**Run**:
One pass of the pipeline over one game's uploaded files, from upload to results.
_Avoid_: Job, session, extraction (for the whole pass)

**Phase**:
A part of a run with its own inputs and results. A run has two phases: extraction, then analysis.
_Avoid_: Stage, step

**Extraction**:
The phase that turns a game's PDFs and images into the rules text and the component list.
_Avoid_: Import, parsing

**Analysis**:
The phase that builds a simulation of the game from the extraction results, plays it many times and reports the findings.
_Avoid_: Simulation (for the whole phase), testing

**Checkpoint**:
A point in a run where it can wait for a person to approve or steer it before it continues. A run passes its checkpoints without waiting unless the person who starts it asks to verify.
_Avoid_: Pause, gate, review step

**Steering**:
What a person gives at a checkpoint to change how the run continues. At the checkpoint after extraction it is a corrected rules text or component list. At the checkpoint before the simulation it is extra designer numbers, answers to designer questions and a note.
_Avoid_: Feedback, correction, override

### Game knowledge

**Designer numbers**:
Values the game designer already knows, such as the play time, given to a run so it does not have to assume them. A run accepts all, some or none of them.
_Avoid_: Client numbers, parameters, settings

**Assumption**:
A value or rule the analysis had to choose because neither the rules text nor the designer numbers gave it.
_Avoid_: Guess, default

**Designer question**:
A question the analysis asks the game designer because the answer changes the results.
_Avoid_: Open question, clarification
