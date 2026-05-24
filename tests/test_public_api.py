from __future__ import annotations

import asyncio
from dataclasses import dataclass

import cocotb_uvm
import cocotb_uvm.base as base
from cocotb_uvm import BaseTransaction, always_sample_next


def test_public_api_exports_match_base_module() -> None:
    assert sorted(cocotb_uvm.__all__) == sorted(base.__all__)


def test_public_api_exports_are_importable() -> None:
    for name in cocotb_uvm.__all__:
        assert hasattr(cocotb_uvm, name)


def test_base_transaction_uses_id_field() -> None:
    @dataclass
    class DummyTransaction(BaseTransaction):
        payload: int

    transaction = DummyTransaction(payload=3)
    explicit_transaction = DummyTransaction(payload=5, id=7)

    assert transaction.id is None
    assert explicit_transaction.id == 7


def test_always_sample_next_requires_bound_instance() -> None:
    @always_sample_next()
    async def sample() -> None:
        return None

    try:
        asyncio.run(sample())
    except ValueError as exc:
        assert "bound to an instance" in str(exc)
    else:
        raise AssertionError("always_sample_next should reject unbound coroutines")
