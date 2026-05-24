from __future__ import annotations

import logging
from pathlib import Path

from cocotb_uvm import SimLogger


def reset_sim_logger_singleton() -> None:
    SimLogger._instance = None


def test_sim_logger_is_singleton() -> None:
    reset_sim_logger_singleton()

    first = SimLogger(root_level=logging.INFO)
    second = SimLogger(root_level=logging.DEBUG)

    assert first is second


def test_configure_stream_handlers_updates_stream_handler_only() -> None:
    reset_sim_logger_singleton()
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)

    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(Path("/tmp/cocotb_uvm_test.log"))
    root_logger.handlers = [stream_handler, file_handler]

    try:
        logger = SimLogger()
        logger.configure_stream_handlers(logging.WARNING)

        assert stream_handler.level == logging.WARNING
        assert file_handler.level != logging.WARNING
    finally:
        file_handler.close()
        root_logger.handlers = original_handlers


def test_create_filter_excludes_matching_records_by_default() -> None:
    record = logging.LogRecord(
        name="cocotb.scoreboard",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="mismatch detected",
        args=(),
        exc_info=None,
    )
    filter_ = SimLogger.create_filter(
        False,
        {"level": logging.ERROR, "message": "mismatch"},
    )

    assert filter_.filter(record) is False


def test_create_filter_keeps_only_matching_records_when_reversed() -> None:
    matching_record = logging.LogRecord(
        name="cocotb.scoreboard",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="report line",
        args=(),
        exc_info=None,
    )
    non_matching_record = logging.LogRecord(
        name="cocotb.driver",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="driver line",
        args=(),
        exc_info=None,
    )
    filter_ = SimLogger.create_filter(
        True,
        {"name": "scoreboard", "message": "report"},
    )

    assert filter_.filter(matching_record) is True
    assert filter_.filter(non_matching_record) is False
