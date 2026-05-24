"""Sequence and sequencer primitives for transaction generation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import Combine


class SupportsExecute(Protocol):
    """Protocol for executors that can consume items from a sequencer."""

    name: str

    async def execute(self, item: Any) -> None:
        """Execute one queued item."""


class BaseSequence(ABC):
    """Base class for iterable transaction sequences."""

    def __init__(self, name: str = "Sequence", *args: Any, **kwargs: Any) -> None:
        self.name = name

    def __iter__(self) -> "BaseSequence":
        return self

    @abstractmethod
    def __next__(self) -> Any:
        """Return the next item and raise ``StopIteration`` when exhausted."""


class BaseSequencer(ABC):
    """Base class for sequencers that feed items to an executor."""

    def __init__(
        self,
        name: str = "Sequencer",
        max_queue_size: int = 10,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.log = logging.getLogger(f"cocotb.{self.name}")
        self.transaction_queue: Queue = Queue(max_queue_size)
        self._stop_token = object()

    async def run(
        self,
        executor: SupportsExecute,
        *sequences: BaseSequence,
    ) -> None:
        """Consume sequences and dispatch their items to the executor."""

        executor_task = cocotb.start_soon(self._run_executor(executor))
        producer_task = cocotb.start_soon(self._enqueue_sequences(*sequences))
        await Combine(executor_task, producer_task)

    async def _run_executor(self, executor: SupportsExecute) -> None:
        """Pull items from the internal queue and dispatch them."""

        while True:
            item = await self.transaction_queue.get()
            if item is self._stop_token:
                break
            await executor.execute(item)
            self.log.debug("[%s] %s executed %s", self.name, executor.name, item)

    async def _enqueue_sequences(self, *sequences: BaseSequence) -> None:
        """Iterate over every sequence and enqueue its items."""

        tasks = [
            cocotb.start_soon(self._enqueue_sequence_items(sequence))
            for sequence in sequences
        ]
        await Combine(*tasks)
        await self.transaction_queue.put(self._stop_token)

    async def _enqueue_sequence_items(self, sequence: BaseSequence) -> None:
        """Push all items from one sequence into the internal queue."""

        for item in sequence:
            await self.transaction_queue.put(item)
            self.log.debug(
                "[%s] enqueued %s from %s",
                self.name,
                item,
                getattr(sequence, "name", sequence),
            )
