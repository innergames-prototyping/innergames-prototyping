"""HTTP API of the extraction: start a run with uploaded files, follow it, fetch its files.

The `RunManager` lives in `request.app.state.runs` (set in `app/main.py`).
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..analysis.session import AnalysisError
from .runs import (
    AnalysisRequest,
    RunBusyError,
    RunEvent,
    RunManager,
    RunNotFoundError,
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
) -> RunStatus:
    """Starts one run: extraction, then analysis."""
    analysis = AnalysisRequest(_designer_json("timings", timings), _designer_json("focus", focus))
    uploads = [(Path(f.filename or "").name, await f.read()) for f in files]
    if refused := refused_files(uploads):
        raise HTTPException(
            400, f"Only PDF (a real PDF), PNG and JPG files are accepted. Refused: {refused}"
        )
    try:
        return _runs(request).start(dict(uploads), analysis)
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
            body.source_run, AnalysisRequest(body.timings, body.focus)
        )
    except RunNotFoundError as e:
        raise _not_found(body.source_run) from e
    except RunBusyError as e:
        raise HTTPException(409, str(e)) from e
    except AnalysisError as e:
        raise HTTPException(422, str(e)) from e


runs_router.add_api_route("", list_extractions, methods=["GET"])
runs_router.add_api_route("/{run_id}", get_extraction, methods=["GET"])
runs_router.add_api_route("/{run_id}/events", get_events, methods=["GET"])
runs_router.add_api_route("/{run_id}/files/{path:path}", get_file, methods=["GET"])
runs_router.add_api_route("/{run_id}/cancel", cancel_extraction, methods=["POST"])
