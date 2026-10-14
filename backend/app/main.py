import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import extraction

app = FastAPI(title="InnerGames prototyping")


def summary(job: extraction.Job) -> dict:
    return {
        "id": job.id,
        "state": job.state,
        "pdfs": job.pdfs,
        "activity": job.activity,
        "seconds": round((job.finished or time.time()) - job.started),
        "results": job.results() if job.state != "running" else [],
        "result": job.result,
        "cost_usd": job.cost_usd,
    }


def get_job(job_id: str) -> extraction.Job:
    if job_id not in extraction.jobs:
        raise HTTPException(404, f"No extraction with id {job_id}")
    return extraction.jobs[job_id]


@app.post("/api/extractions")
async def create_extraction(files: list[UploadFile]) -> dict:
    pdfs, rejected = {}, []
    for f in files:
        name = Path(f.filename or "").name
        data = await f.read()
        if name.lower().endswith(".pdf") and data.startswith(b"%PDF-"):
            pdfs[name] = data
        else:
            rejected.append(name or "(unnamed file)")
    if rejected:
        raise HTTPException(400, f"Not a PDF: {', '.join(rejected)}")
    return summary(extraction.start(pdfs))


@app.get("/api/extractions/{job_id}")
def read_extraction(job_id: str) -> dict:
    return summary(get_job(job_id))


@app.get("/api/extractions/{job_id}/results/{name}")
def read_result(job_id: str, name: str) -> FileResponse:
    job = get_job(job_id)
    if name not in job.results():
        raise HTTPException(404, f"{name} is not a result of extraction {job_id}")
    return FileResponse(job.dir / "results" / name)
