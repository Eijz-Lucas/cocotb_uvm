"""Utility helpers shared across cocotb_uvm modules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from cocotb.triggers import First, RisingEdge, Timer, ValueChange


def always_sample_next(
    time: int = 10,
    unit: str = "ns",
) -> Callable[[Callable[..., Awaitable[None]]], Callable[..., Awaitable[None]]]:
    """Decorate a monitor coroutine to sample one cycle ahead.

    This helper is intended for simulators where cocotb observes updated
    register values on the same edge that triggered the coroutine. The wrapped
    coroutine waits for ``time``/``unit``, executes the sampling logic, and
    then advances to the next rising clock edge.
    """

    def decorator(
        func: Callable[..., Awaitable[None]],
    ) -> Callable[..., Awaitable[None]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> None:
            instance = args[0] if args else None
            if instance is None:
                raise ValueError("The wrapped coroutine must be bound to an instance.")

            while True:
                await Timer(time, unit=unit)
                await func(*args, **kwargs)
                await RisingEdge(instance.dut.clk)

        return wrapper

    return decorator


async def connect_check(signal_0: Any, signal_1: Any) -> None:
    """Assert that two signals remain equal throughout simulation."""

    while True:
        await First(ValueChange(signal_0), ValueChange(signal_1))
        assert signal_0.value == signal_1.value, (
            f"{signal_0} is not equal to {signal_1}"
        )
