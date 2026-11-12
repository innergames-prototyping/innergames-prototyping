import io
import time

import pytest
from fake_results import PROPOSAL, write_results
from fastapi.testclient import TestClient
from PIL import Image

from app.extraction.agent import AgentResult
from app.extraction.reader import RecordedReader
from app.extraction.runs import RunManager
from app.main import create_app
from app.settings import Settings


async def fake_agent(ws, settings, reader, limits, on_event):
    on_event("tool", "render_pdfs")
    write_results(ws)
    return AgentResult("All done.", 0.5, is_error=False)


@pytest.fixture
def client(tmp_path):
    settings = Settings(tmp_path / "data", "a", "r", 2)
    runs = RunManager(settings, RecordedReader(lambda *_: PROPOSAL), fake_agent)
    with TestClient(create_app(settings, runs)) as client:
        yield client


def pdf_bytes() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (100, 140), "white").save(out, "PDF", resolution=72)
    return out.getvalue()


def wait_until_ended(client, run_id) -> dict:
    for _ in range(100):
        status = client.get(f"/api/extractions/{run_id}").json()
        if status["state"] != "running":
            return status
        time.sleep(0.05)
    raise AssertionError("the run did not end")


def test_text_file_is_refused_with_its_name_and_nothing_starts(client):
    response = client.post(
        "/api/extractions",
        files=[("files", ("notes.txt", b"hello")), ("files", ("rules.pdf", pdf_bytes()))],
    )

    assert response.status_code == 400
    assert "notes.txt" in response.json()["detail"]
    assert "rules.pdf" not in response.json()["detail"]
    assert client.get("/api/extractions").json() == []


def test_fake_pdf_is_refused(client):
    response = client.post("/api/extractions", files=[("files", ("rules.pdf", b"not a pdf"))])

    assert response.status_code == 400
    assert "rules.pdf" in response.json()["detail"]


def test_upload_runs_and_results_are_served(client):
    response = client.post("/api/extractions", files=[("files", ("rules.pdf", pdf_bytes()))])

    assert response.status_code == 201
    run_id = response.json()["id"]
    status = wait_until_ended(client, run_id)
    assert status["state"] == "done"
    assert status["files"] == ["rules.pdf"]
    assert "results/game_model_v1.json" in status["results"]
    assert client.get("/api/extractions").json()[0]["id"] == run_id

    events = client.get(f"/api/extractions/{run_id}/events").json()
    assert events[0]["kind"] == "tool"
    assert client.get(f"/api/extractions/{run_id}/events?after=1").json() == events[1:]

    rules = client.get(f"/api/extractions/{run_id}/files/results/rules.md")
    assert rules.status_code == 200
    assert rules.text.startswith("On your turn")


def test_files_endpoint_stays_inside_the_run(client):
    run_id = client.post("/api/extractions", files=[("files", ("rules.pdf", pdf_bytes()))]).json()[
        "id"
    ]
    wait_until_ended(client, run_id)

    for path in ("%2e%2e/%2e%2e/runs", "..%2f..%2fx", "%2e%2e/%2e%2e/%2e%2e/etc/passwd", "work"):
        assert client.get(f"/api/extractions/{run_id}/files/{path}").status_code == 404


def test_unknown_run_is_404(client):
    for url in ("", "/events", "/files/a.txt"):
        assert client.get(f"/api/extractions/20260101-000000-abcd{url}").status_code == 404
    assert client.post("/api/extractions/20260101-000000-abcd/cancel").status_code == 404


def test_second_run_while_running_is_409(tmp_path):
    import asyncio

    settings = Settings(tmp_path / "data", "a", "r", 2)
    gates = []

    async def slow_agent(ws, settings, reader, limits, on_event):
        gate = asyncio.Event()
        gates.append(gate)
        await gate.wait()
        return AgentResult("ok", 0, is_error=False)

    runs = RunManager(settings, RecordedReader(lambda *_: PROPOSAL), slow_agent)
    with TestClient(create_app(settings, runs)) as client:
        first = client.post("/api/extractions", files=[("files", ("a.png", b"x"))])
        second = client.post("/api/extractions", files=[("files", ("b.png", b"x"))])
        client.post(f"/api/extractions/{first.json()['id']}/cancel")
        status = wait_until_ended(client, first.json()["id"])

    assert first.status_code == 201
    assert second.status_code == 409
    assert status["state"] == "cancelled"
