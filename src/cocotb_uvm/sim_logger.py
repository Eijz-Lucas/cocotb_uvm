"""Logging helpers for cocotb_uvm simulations."""

from __future__ import annotations

import logging
from typing import Any

from cocotb.logging import SimLogFormatter, SimTimeContextFilter


class SimLogger:
    """Singleton-style helper for configuring simulation logging."""

    _instance: "SimLogger | None" = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "SimLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        root_level: int = logging.DEBUG,
        cocotb_level: int = logging.DEBUG,
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(root_level)
        self.cocotb_logger = logging.getLogger("cocotb")
        self.cocotb_logger.setLevel(cocotb_level)
        self._initialized = True

    def configure_stream_handlers(self, *configs: Any) -> None:
        """Apply logging configuration objects to non-file stream handlers.

        Supported configuration objects are:
        - ``int`` for the handler level
        - ``logging.Filter`` instances
        - ``logging.Formatter`` instances
        """

        for handler in self.root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler,
                logging.FileHandler,
            ):
                for config in configs:
                    if isinstance(config, int):
                        handler.setLevel(config)
                    elif isinstance(config, logging.Filter):
                        handler.addFilter(config)
                    elif isinstance(config, logging.Formatter):
                        handler.setFormatter(config)

    @staticmethod
    def add_file_handler(
        name: str,
        level: int = logging.DEBUG,
        mode: str = "w",
        formatter: logging.Formatter | None = None,
        filters: list[logging.Filter] | None = None,
    ) -> None:
        """Create and attach a file handler to the root logger."""

        handler = SimLogger.create_file_handler(
            name=name,
            level=level,
            mode=mode,
            formatter=formatter,
            filters=filters,
        )
        logging.getLogger().addHandler(handler)

    @staticmethod
    def create_file_handler(
        name: str,
        level: int = logging.DEBUG,
        mode: str = "w",
        formatter: logging.Formatter | None = None,
        filters: list[logging.Filter] | None = None,
    ) -> logging.FileHandler:
        """Create a configured file handler with simulation-time context."""

        handler = logging.FileHandler(name, mode=mode)
        handler.setLevel(level)
        handler.setFormatter(formatter or SimLogFormatter())
        for filter_ in filters or []:
            handler.addFilter(filter_)
        handler.addFilter(SimTimeContextFilter())
        return handler

    @staticmethod
    def create_filter(reverse: bool = False, *configs: dict[str, Any]) -> logging.Filter:
        """Create a log filter from one or more matching rules.

        When ``reverse`` is ``False``, matching records are filtered out.
        When ``reverse`` is ``True``, only matching records are kept.
        """

        class CustomFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                for config in configs:
                    if "level" in config and record.levelno < config["level"]:
                        continue
                    if "name" in config and config["name"] not in record.name:
                        continue
                    if "message" in config and config["message"] not in record.getMessage():
                        continue
                    return reverse
                return not reverse

        return CustomFilter()
