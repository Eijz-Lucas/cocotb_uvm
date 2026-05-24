"""Transaction primitives used by the verification framework."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field


@dataclass
class BaseTransaction(ABC):
    """Base class for transactions exchanged between verification components.

    Subclasses typically add protocol-specific payload fields. The optional
    ``id`` field is assigned by monitors and propagated through the
    reference-model and scoreboard pipeline.
    """

    id: int | None = field(default=None, kw_only=True)
