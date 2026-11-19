"""Runs many independent reads at once until every target is settled.

A target is one thing to read: a design, a rules region. It decides itself how many more reads
it needs from the reads it has. When a read finishes, its target is asked again right away, and
its follow-up reads go to the front of the queue. So a design is done as soon as its own reads
agree, instead of waiting for the slowest read of a round.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

Read = Callable[[], Awaitable[None]]
"""One read. It stores its own result on its target."""

MAX_FAILURES = 2


@dataclass(frozen=True)
class ReadLimits:
    min_reads: int = 2
    max_reads: int = 5
    parallel: int = 12


class ReadTarget(ABC):
    """Something that is read until its reads agree."""

    def __init__(self) -> None:
        self.busy = 0
        self.failures = 0

    @abstractmethod
    def next_reads(self) -> list[Read]:
        """The reads still needed now; [] when the target is settled."""


async def run_reads(targets: list[ReadTarget], parallel: int) -> None:
    pending: deque[tuple[ReadTarget, Read]] = deque()

    def ask(target: ReadTarget) -> list[tuple[ReadTarget, Read]]:
        if target.busy or target.failures >= MAX_FAILURES:
            return []
        reads = target.next_reads()
        target.busy += len(reads)
        return [(target, read) for read in reads]

    for target in targets:
        pending.extend(ask(target))

    running: dict[asyncio.Task, ReadTarget] = {}
    try:
        while pending or running:
            while pending and len(running) < parallel:
                target, read = pending.popleft()
                running[asyncio.create_task(read())] = target
            done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                target = running.pop(task)
                target.busy -= 1
                try:
                    task.result()
                except Exception:
                    # One failed read must not stop a run of hundreds; the target counts it and
                    # gives up after MAX_FAILURES, the others go on.
                    log.exception("read failed")
                    target.failures += 1
                pending.extendleft(reversed(ask(target)))
    finally:
        for task in running:
            task.cancel()
