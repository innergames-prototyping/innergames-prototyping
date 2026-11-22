"""HTTP API of the extraction: start a run with uploaded files, follow it, fetch its files.

The `RunManager` lives in `request.app.state.runs` (set in `app/main.py`).
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.datastructures import UploadFile as FormFile

from ..analysis.session import AnalysisError, Steering
from .runs import (
    AnalysisRequest,
    Checkpoint,
    CheckpointASteering,
    RunBusyError,
    RunEvent,
    RunManager,
    RunNotFoundError,
    RunNotWaitingError,
    RunStatus,
)
from .workspace import ExtractionError

router = APIRouter(prefix="/api/extractions", tags=["extractions"])
runs_router = APIRouter(prefix="/api/runs", tags=["runs"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def _runs(request: Request) -> RunManager:
    return request.app.state.runs


def _not_found(run_id: str) -> HTTPException:
    return HTTPException(404, f"no extraction {run_id!r}")


def refused_files(uploads: list[tuple[str, bytes]]) -> list[str]:
    """The names of the uploads that are not a PDF (starting with `%PDF-`), png or jpg."""
    refused = []
    for name, data in uploads:
        suffix = Path(name).suffix.lower()
        is_pdf = suffix == ".pdf" and data.startswith(b"%PDF-")
        if not is_pdf and suffix not in IMAGE_SUFFIXES:
            refused.append(name)
    return refused


@router.post("", status_code=201)
async def start_extraction(request: Request, files: list[UploadFile]) -> RunStatus:
    uploads = [(Path(f.filename or "").name, await f.read()) for f in files]
    if refused := refused_files(uploads):
        raise HTTPException(
            400, f"Only PDF (a real PDF), PNG and JPG files are accepted. Refused: {refused}"
        )
    try:
        return _runs(request).start(dict(uploads))
    except RunBusyError as e:
        raise HTTPException(409, str(e)) from e
    except ExtractionError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
async def list_extractions(request: Request) -> list[RunStatus]:
    return _runs(request).list_runs()


@router.get("/{run_id}")
async def get_extraction(request: Request, run_id: str) -> RunStatus:
    try:
        return _runs(request).get(run_id)
    except RunNotFoundError as e:
        raise _not_found(run_id) from e


@router.get("/{run_id}/events")
async def get_events(
    request: Request, run_id: str, after: Annotated[int, Query(ge=0)] = 0
) -> list[RunEvent]:
    try:
        return _runs(request).events(run_id, after)
    except RunNotFoundError as e:
        raise _not_found(run_id) from e


@router.get("/{run_id}/files/{path:path}")
async def get_file(request: Request, run_id: str, path: str) -> FileResponse:
    try:
        file = _runs(request).workspace(run_id).resolve(path)
    except RunNotFoundError as e:
        raise _not_found(run_id) from e
    except ExtractionError as e:
        raise HTTPException(404, f"no file {path!r}") from e
    if not file.is_file():
        raise HTTPException(404, f"no file {path!r}")
    return FileResponse(file)


@router.post("/{run_id}/cancel")
async def cancel_extraction(request: Request, run_id: str) -> RunStatus:
    try:
        return _runs(request).cancel(run_id)
    except RunNotFoundError as e:
        raise _not_found(run_id) from e


class AnalysisStart(BaseModel):
    source_run: str
    timings: dict[str, Any] | None = None
    focus: dict[str, Any] | None = None
    verify: list[Checkpoint] = []


class CheckpointBBody(BaseModel):
    timings: dict[str, Any] | None = None
    focus: dict[str, Any] | None = None
    answers: list[str] = []
    note: str = ""


def _designer_json(name: str, text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(422, f"{name} is not valid JSON") from e
    if not isinstance(data, dict):
        raise HTTPException(422, f"{name} must be a JSON object")
    return data


@runs_router.post("", status_code=201)
async def start_run(
    request: Request,
    files: list[UploadFile],
    timings: Annotated[str | None, Form()] = None,
    focus: Annotated[str | None, Form()] = None,
    verify: Annotated[list[Checkpoint] | None, Form()] = None,
) -> RunStatus:
    """Starts one run: extraction, then analysis."""
    analysis = AnalysisRequest(_designer_json("timings", timings), _designer_json("focus", focus))
    uploads = [(Path(f.filename or "").name, await f.read()) for f in files]
    if refused := refused_files(uploads):
        raise HTTPException(
            400, f"Only PDF (a real PDF), PNG and JPG files are accepted. Refused: {refused}"
        )
    try:
        return _runs(request).start(dict(uploads), analysis, verify)
    except RunBusyError as e:
        raise HTTPException(409, str(e)) from e
    except AnalysisError as e:
        raise HTTPException(422, str(e)) from e
    except ExtractionError as e:
        raise HTTPException(400, str(e)) from e


@runs_router.post("/analysis", status_code=201)
async def start_analysis(request: Request, body: AnalysisStart) -> RunStatus:
    """Starts a run that does only the analysis, on an earlier run's extraction results."""
    try:
        return _runs(request).start_analysis(
            body.source_run, AnalysisRequest(body.timings, body.focus), body.verify
        )
    except RunNotFoundError as e:
        raise _not_found(body.source_run) from e
    except RunBusyError as e:
        raise HTTPException(409, str(e)) from e
    except AnalysisError as e:
        raise HTTPException(422, str(e)) from e


async def _steering(request: Request) -> CheckpointASteering | Steering | None:
    """Empty body: approve. Multipart: replaced files (A). JSON: numbers, answers, note (B)."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        rules, components = form.get("rules"), form.get("components")
        if not isinstance(rules, FormFile) and not isinstance(components, FormFile):
            raise HTTPException(422, "send a rules or components file")
        return CheckpointASteering(
            await rules.read() if isinstance(rules, FormFile) else None,
            await components.read() if isinstance(components, FormFile) else None,
        )
    raw = await request.body()
    if not raw.strip():
        return None
    try:
        body = CheckpointBBody.model_validate_json(raw)
    except ValueError as e:
        raise HTTPException(422, "the body does not match the checkpoint B format") from e
    return Steering(body.timings, body.focus, tuple(body.answers), body.note)


@runs_router.post("/{run_id}/continue")
async def continue_run(request: Request, run_id: str) -> RunStatus:
    """Empty body approves the checkpoint; a body steers the run."""
    steering = await _steering(request)
    try:
        return _runs(request).continue_run(run_id, steering)
    except RunNotFoundError as e:
        raise _not_found(run_id) from e
    except (RunBusyError, RunNotWaitingError) as e:
        raise HTTPException(409, str(e)) from e
    except AnalysisError as e:
        raise HTTPException(422, str(e)) from e


runs_router.add_api_route("", list_extractions, methods=["GET"])
runs_router.add_api_route("/{run_id}", get_extraction, methods=["GET"])
runs_router.add_api_route("/{run_id}/events", get_events, methods=["GET"])
runs_router.add_api_route("/{run_id}/files/{path:path}", get_file, methods=["GET"])
runs_router.add_api_route("/{run_id}/cancel", cancel_extraction, methods=["POST"])
