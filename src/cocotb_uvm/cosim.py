"""Top-level environment containers for CoSim-based verification."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, TypeAlias

from cocotb.handle import HierarchyObject
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge

from .components import BaseDriver, BaseModel, BaseMonitor, BaseScoreboard

ModuleSpec: TypeAlias = tuple[str, type[Any], dict[str, Any]]


class CoSimBase(ABC):
    """Base class for a module-level co-simulation environment.

    A ``CoSimBase`` instance owns the reference model, driver, monitors, and
    scoreboard associated with one DUT block. It exposes a uniform
    ``execute()`` entry point for UT and ST flows.
    """

    def __init__(
        self,
        dut: HierarchyObject,
        reference_model_cls: type[BaseModel],
        driver_cls: type[BaseDriver],
        input_monitor_cls: type[BaseMonitor],
        output_monitor_cls: type[BaseMonitor],
        scoreboard_cls: type[BaseScoreboard],
        mode: str = "hw",
        level: str = "ut",
        name: str = "CoSimBase",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.mode = self._validate_mode(mode)
        self.level = self._validate_level(level)
        if self.level == "st" and self.mode == "sw":
            raise RuntimeError(
                f"{self.name} cannot run in software mode during system testing."
            )

        self.dut = dut
        self.log = logging.getLogger(f"cocotb.{name}")
        self.input_queue: Queue = Queue()
        self.actual_queue: Queue = Queue()
        self.expected_queue: Queue = Queue()
        self.reference_model = reference_model_cls(
            self.input_queue,
            self.expected_queue,
        )
        self.driver = driver_cls(self.dut)
        self.input_monitor = input_monitor_cls(self.dut, self.input_queue)
        self.output_monitor = output_monitor_cls(self.dut, self.actual_queue)
        self.scoreboard = scoreboard_cls(self.actual_queue, self.expected_queue)
        self.executed_count = 0
        self.log.debug("******** %s initialized ********", self.name)

    @staticmethod
    def _validate_mode(mode: str) -> str:
        if mode not in {"hw", "sw"}:
            raise ValueError(f"Invalid mode '{mode}'. Expected 'hw' or 'sw'.")
        return mode

    @staticmethod
    def _validate_level(level: str) -> str:
        if level not in {"ut", "st"}:
            raise ValueError(f"Invalid level '{level}'. Expected 'ut' or 'st'.")
        return level

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        """Dispatch one execution request according to the selected level."""

        if self.level == "ut":
            await self.execute_unit_test(*args, **kwargs)
            if self.mode == "sw":
                self.scoreboard.match_count += 1
        else:
            await self.execute_system_test(*args, **kwargs)
        self.executed_count += 1

    @abstractmethod
    async def execute_unit_test(self, *args: Any, **kwargs: Any) -> None:
        """Drive one unit-test operation."""

    @abstractmethod
    async def execute_system_test(self, *args: Any, **kwargs: Any) -> None:
        """Drive one system-test operation."""

    async def wait_for_completion(self) -> None:
        """Wait until all executed operations have been compared."""

        while self.scoreboard.match_count + self.scoreboard.mismatch_count != self.executed_count:
            await RisingEdge(self.dut.clk)

    def report(self) -> None:
        """Log a PASS/FAIL summary for this module environment."""

        if self.success:
            self.log.info(
                "[%s REPORT] PASS, executed %d operations",
                self.name,
                self.executed_count,
            )
            return

        self.log.info(
            "[%s REPORT] FAIL, executed %d operations, %d mismatches",
            self.name,
            self.executed_count,
            self.scoreboard.mismatch_count,
        )

    def teardown(self) -> None:
        """Stop background tasks created by the environment components."""

        self.reference_model._task.cancel()
        self.input_monitor._task.cancel()
        self.output_monitor._task.cancel()
        self.scoreboard._task.cancel()
        self.log.debug("[%s] teardown", self.name)

    @property
    def success(self) -> bool:
        """Return ``True`` when every executed operation matched."""

        return (
            self.scoreboard.match_count == self.executed_count
            and self.scoreboard.mismatch_count == 0
        )


class CoSimWrapperBase(ABC):
    """Base class for wrapper environments that manage multiple modules."""

    def __init__(
        self,
        dut: HierarchyObject,
        module_specs: list[ModuleSpec],
        level: str = "ut",
        name: str = "CoSimWrapperBase",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.dut = dut
        self.name = name
        self.level = CoSimBase._validate_level(level)
        self.log = logging.getLogger(f"cocotb.{name}")
        self.modules: dict[str, Any] = {}

        for module_name, module_cls, module_config in module_specs:
            self.modules[module_name] = module_cls(*args, **module_config, **kwargs)

        if self.level == "st":
            for module in self.modules.values():
                if isinstance(module, CoSimBase) and module.mode == "sw":
                    raise RuntimeError(
                        f"{module.name} cannot run in software mode inside "
                        f"{self.name} system testing."
                    )

        self.log.debug(
            "******** %s initialized with level=%s ********",
            self.name,
            self.level,
        )

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        """Dispatch one execution request according to the selected level."""

        if self.level == "ut":
            await self.execute_unit_test(*args, **kwargs)
        else:
            await self.execute_system_test(*args, **kwargs)

    @abstractmethod
    async def execute_unit_test(self, *args: Any, **kwargs: Any) -> None:
        """Route one unit-test operation."""

    @abstractmethod
    async def execute_system_test(self, *args: Any, **kwargs: Any) -> None:
        """Route one system-test operation."""

    async def wait_for_completion(self) -> None:
        """Wait for every managed module to finish scoreboard comparison."""

        for module in self.modules.values():
            await module.wait_for_completion()

    def report(self) -> None:
        """Log a report for every managed module."""

        for module in self.modules.values():
            module.report()

    def teardown(self) -> None:
        """Tear down every managed module."""

        for module in self.modules.values():
            module.teardown()
        self.log.debug("[%s] teardown", self.name)

    @property
    def success(self) -> bool:
        """Return ``True`` when every managed module passed."""

        return all(module.success for module in self.modules.values())
