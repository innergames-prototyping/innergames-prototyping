"""HTTP API of the extraction: start a run with uploaded files, follow it, fetch its files.

The `RunManager` lives in `request.app.state.runs` (set in `app/main.py`).
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from .runs import RunBusyError, RunEvent, RunManager, RunNotFoundError, RunStatus
from .workspace import ExtractionError

router = APIRouter(prefix="/api/extractions", tags=["extractions"])

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
    return _runs(request).list()


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
