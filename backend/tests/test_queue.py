import asyncio

from app.extraction import tools
from app.extraction.queue import MAX_FAILURES, ReadTarget, run_reads
from app.extraction.reader import RecordedReader


class CountingTarget(ReadTarget):
    """Wants `wanted` reads; a read raises when `broken`."""

    def __init__(self, wanted: int, broken: bool = False):
        super().__init__()
        self.wanted = wanted
        self.broken = broken
        self.reads = 0

    def next_reads(self):
        if self.reads >= self.wanted:
            return []
        return [self._read]

    async def _read(self):
        if self.broken:
            raise ValueError("bug in a read")
        self.reads += 1


def test_a_failing_target_does_not_stop_the_others():
    good, bad = CountingTarget(3), CountingTarget(3, broken=True)

    asyncio.run(run_reads([bad, good], parallel=2))

    assert good.reads == 3
    assert bad.failures == MAX_FAILURES


def test_an_unexpected_error_in_a_tool_becomes_a_tool_error(ws, monkeypatch):
    def crash(_ws):
        raise ValueError("boom")

    monkeypatch.setattr(tools.cost, "cost_report", crash)
    reader = RecordedReader(lambda *_: None)

    output = asyncio.run(tools.call_tool(ws, reader, None, "cost", {}))

    assert output.startswith("ERROR: cost failed unexpectedly")
