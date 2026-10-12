# Tech Stack

Date: 12 Oct 2026

## Introduction

This document records which technology the application is built with.

## Status

The frontend and the backend are chosen. The LLMs are still open.

## The Stack

### Frontend

React. The reasons are written down in [#117](https://github.com/innergames-prototyping/innergames-prototyping/issues/117).

### Backend

Python with FastAPI.

Why:

- The simulation is Python. The pipeline writes a Python simulation of each game and runs it many times. With a Python backend that is one language and one process. Any other backend would still have to start Python for every run.
- The data formats come from one definition. The component file, the game model, the playthrough log and the results file each need a schema and validation. FastAPI is built on Pydantic, which gives the model, the validation and the JSON Schema from a single class.
- The same models describe what the LLM has to return, so structured output needs no second definition.
- Python has mature libraries for the rest of the pipeline: statistics on the simulation results, rendering PDF pages to images, and clients for the LLM providers.
- The team and future students know Python, and the development shell already provides it.

What it costs:

- Two languages: TypeScript in the frontend and Python in the backend. FastAPI generates an OpenAPI description of the API, and the frontend types are generated from that, so the two don't drift apart.
- A Windows application needs Python packaged with it.

### LLMs

To be decided.
