"""Core verification components used to build a CoSim environment."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import cocotb
from cocotb.handle import HierarchyObject
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge, Timer

from .transaction import BaseTransaction


class BaseModel(ABC):
    """Base class for software reference models.

    A reference model consumes transactions from ``input_queue``, computes the
    expected result, and pushes it into ``expected_queue`` for scoreboard
    comparison.
    """

    def __init__(
        self,
        input_queue: Queue,
        expected_queue: Queue,
        name: str = "ReferenceModel",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.input_queue = input_queue
        self.expected_queue = expected_queue
        self._task = cocotb.start_soon(self.run(*args, **kwargs))
        self.log.debug("======== %s initialized ========", self.name)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        """Continuously translate input transactions into expected results."""

        while True:
            input_transaction = await self.input_queue.get()
            self.log.debug("[%s Input] %s", self.name, input_transaction)
            expected_transaction = self.compute(
                input_transaction,
                *args,
                **kwargs,
            )
            expected_transaction.id = input_transaction.id
            self.log.debug("[%s Output] %s", self.name, expected_transaction)
            self.expected_queue.put_nowait(expected_transaction)

    @abstractmethod
    def compute(
        self,
        input_transaction: BaseTransaction,
        *args: Any,
        **kwargs: Any,
    ) -> BaseTransaction:
        """Compute the expected result for one input transaction."""


class BaseDriver(ABC):
    """Base class for hardware drivers.

    Drivers convert transactions or commands into signal activity on the DUT.
    """

    def __init__(
        self,
        dut: HierarchyObject,
        name: str = "Driver",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.dut = dut
        self.log = logging.getLogger(f"cocotb.{name}")
        self.log.debug("======== %s initialized ========", self.name)

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> None:
        """Drive DUT signals for one transaction or command."""


class BaseMonitor(ABC):
    """Base class for hardware monitors.

    A monitor samples DUT state, converts observations into transactions, and
    publishes them to ``output_queue``. Each transaction is assigned an
    incrementing ``id`` before it is enqueued.
    """

    def __init__(
        self,
        dut: HierarchyObject,
        output_queue: Queue,
        name: str = "Monitor",
        sample_delay: int = 10,
        sample_delay_unit: str = "ns",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.dut = dut
        self.log = logging.getLogger(f"cocotb.{name}")
        self.output_queue = output_queue
        self.sample_delay = sample_delay
        self.sample_delay_unit = sample_delay_unit
        self._next_id = 0
        self._task = cocotb.start_soon(self.run(*args, **kwargs))
        self.log.debug("======== %s initialized ========", self.name)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        """Continuously sample DUT state and publish captured transactions."""

        while True:
            await Timer(self.sample_delay, unit=self.sample_delay_unit)
            transaction = await self.sample(*args, **kwargs)
            if transaction is not None:
                transaction.id = self._next_id
                self._next_id += 1
                self.output_queue.put_nowait(transaction)
                self.log.debug("[%s Sample] %s", self.name, transaction)
            await RisingEdge(self.dut.clk)

    @abstractmethod
    async def sample(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[BaseTransaction]:
        """Sample DUT state and return a transaction when one is available."""


class BaseScoreboard(ABC):
    """Base class for scoreboards.

    A scoreboard consumes actual and expected transactions and tracks how many
    comparisons match or mismatch.
    """

    def __init__(
        self,
        actual_queue: Queue,
        expected_queue: Queue,
        name: str = "Scoreboard",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.log = logging.getLogger(f"cocotb.{name}")
        self.actual_queue = actual_queue
        self.expected_queue = expected_queue
        self.match_count = 0
        self.mismatch_count = 0
        self._task = cocotb.start_soon(self.run(*args, **kwargs))
        self.log.debug("======== %s initialized ========", self.name)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        """Continuously fetch and compare actual and expected transactions."""

        while True:
            actual_transaction = await self.actual_queue.get()
            expected_transaction = await self.expected_queue.get()
            self.log.debug("[%s Actual] %s", self.name, actual_transaction)
            self.log.debug("[%s Expected] %s", self.name, expected_transaction)
            self.compare(
                actual_transaction,
                expected_transaction,
                *args,
                **kwargs,
            )

    def compare(
        self,
        actual_transaction: BaseTransaction,
        expected_transaction: BaseTransaction,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Compare one actual transaction with one expected transaction."""

        if actual_transaction == expected_transaction:
            self.match_count += 1
            self.log.debug("[%s] MATCH count=%d", self.name, self.match_count)
            return True

        self.mismatch_count += 1
        self.log.debug(
            "[%s] MISMATCH count=%d",
            self.name,
            self.mismatch_count,
        )
        return False
