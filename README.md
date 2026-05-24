# cocotb_uvm

`cocotb_uvm` is a cocotb-based co-simulation verification framework with a
UVM-style layered architecture. It is designed for building reusable Python
verification environments that can scale from module-level unit testing to
system-level co-simulation.

The package focuses on a small set of abstract base classes:

- transaction definition
- reference model
- driver
- monitor
- scoreboard
- sequence / sequencer
- module-level CoSim environment
- wrapper-level system environment

The repository also contains a runnable example project under
`examples/cosim_test/`.

## Features

- UVM-style separation between stimulus, observation, checking, and environment composition
- Unified `execute()` entry point on `CoSimBase` and `CoSimWrapperBase`
- Support for unit test (`ut`) and system test (`st`) flows
- Support for hardware mode (`hw`) and software mode (`sw`) on module environments
- Reusable utility helpers such as `always_sample_next()` and `connect_check()`
- Lightweight logging configuration via `SimLogger`

## Installation

### Install the library

With `uv`:

```bash
uv sync
```

With `pip`:

```bash
pip install .
```

### Install example dependencies

The example project depends on `numpy` and `einops`, which are intentionally
kept out of the core runtime dependency set.

With `uv`:

```bash
uv sync --extra examples
```

With `pip`:

```bash
pip install ".[examples]"
```

### Install development dependencies

```bash
uv sync --extra examples --group dev
```

## Quick Start

Import the public API from the package root:

```python
from cocotb_uvm import (
    BaseDriver,
    BaseModel,
    BaseMonitor,
    BaseScoreboard,
    BaseSequence,
    BaseSequencer,
    BaseTransaction,
    CoSimBase,
    CoSimWrapperBase,
    SimLogger,
    always_sample_next,
    connect_check,
)
```

The package is organized internally into focused modules:

- `transaction.py`
- `components.py`
- `sequencing.py`
- `cosim.py`
- `sim_logger.py`
- `utils.py`

`base.py` is kept as a convenience re-export layer.

## Repository Layout

```text
src/cocotb_uvm/          Python package
examples/cosim_test/     Runnable cocotb example project
tests/                   Minimal package regression tests
utils/                   Repository helper scripts
makefile                 Repository-level demo entry
```

Only `src/cocotb_uvm/` is packaged into the wheel. The example RTL, testbench,
and helper scripts remain repository assets and are not part of the runtime
package.

## Core Abstractions

| Class | Responsibility |
| --- | --- |
| `BaseTransaction` | Base dataclass for transactions passed between components. |
| `BaseModel` | Software reference model that consumes input transactions and produces expected transactions. |
| `BaseDriver` | Hardware driver that converts commands or transactions into DUT signal activity through `run()`. |
| `BaseMonitor` | Monitor that samples DUT state and publishes observed transactions. |
| `BaseScoreboard` | Checker that compares actual and expected transactions and tracks match / mismatch counts. |
| `BaseSequence` | Iterable stimulus source. |
| `BaseSequencer` | Sequencer that feeds items from one or more sequences into an executor with `execute()`. |
| `CoSimBase` | Module-level environment that owns a model, driver, monitors, and scoreboard. |
| `CoSimWrapperBase` | Wrapper environment that composes multiple module or wrapper environments. |
| `SimLogger` | Logging helper for stream handlers, filters, and file handlers. |

## Example Project

The repository ships with a runnable example at `examples/cosim_test/`.

### Example DUT

The example verifies a small dataflow composed of:

- `add_one`
  Reads data from RAM, increments each element by one, and writes to FIFO.
- `sub_one`
  Reads data from FIFO, decrements each element by one, and writes to output.
- `memory.py`
  Provides Python-side RAM and FIFO models for unit-test mode.

```text
         +-----------------------------------------------------------------------+
         |                             RTL TOP (DUT)                             |
         |                                                                       |
[Clocks] |                                                                       |
 clk   >-|-------------------------------------------------------+               |
 rst_n >-|-------------------------------------------------------+               |
         |                                                       |               |
[Ctrl 1] |                        +-----------+                  v               |
 en_add  >----------------------->|           |       +----------------------+   |
 addr_add>----------------------->|  add_one  |======>| RAM                  |   |
 len_add >----------------------->|           |<======| (ram_addr, ram_rdata)|   |
         |                        +-----------+       +----------------------+   |
         |                              ||                                       |
         |                              || fifo_write_0                          |
         |                              || (write_en, write_data)                |
         |                              \/                                       |
         |                        +-----------+                                  |
         |                        |           |                                  |
         |                        |   FIFO    |                                  |
         |                        |           |                                  |
         |                        +-----------+                                  |
         |                          ||     /\                                    |
         |        fifo_read         ||     || fifo_write_1                       |
         |   (read_en, read_data)   ||     || (write_en, write_data)             |
         |                          \/     ||                                    |
[Ctrl 2] |                        +-----------+                                  |
 en_sub  >----------------------->|           |                                  |
 len_sub >----------------------->|  sub_one  |                                  |
         |                        +-----------+                                  |
         |                                                                       |
         +-----------------------------------------------------------------------+
```

### Firmware-Style Stimulus

The example uses firmware-like dictionaries as top-level commands:

```python
firmware = [
    {"op": "add_one", "addr": 0, "len": 5},
    {"op": "sub_one", "len": 3},
    {"op": "sub_one", "len": 2},
]
```

It also provides a sequence-based generator in
`examples/cosim_test/tb/test_cosim_test.py`.

### Run the Example

From the repository root:

```bash
make ctb-cosim_test
```

Run system-test mode:

```bash
make ctb-cosim_test ST=1
```

The root `makefile` dispatches into `examples/cosim_test/tb/ctb.mk`.

## Verification Model

### UT vs ST

- `ut`
  Transaction-oriented module testing. Software-side RAM/FIFO models can be
  used between components.
- `st`
  System-level testing of hardware-connected modules. Inter-module transport is
  performed by RTL rather than software models.

### HW vs SW

- `hw`
  The DUT is driven through the real hardware driver and checked with monitors
  and scoreboards.
- `sw`
  The reference model is used as the functional implementation. This is useful
  in unit-test mode for early software-side bring-up.

`CoSimBase` supports both `hw` and `sw` in unit-test mode. In system-test mode,
module environments are expected to run in `hw`.

### Environment Composition

`CoSimBase` represents one module environment. `CoSimWrapperBase` represents a
larger environment that can own multiple module environments and nested wrapper
environments.

Each environment exposes:

- `execute(...)`
- `wait_for_completion()`
- `report()`
- `teardown()`
- `success`

The wrapper example in `examples/cosim_test/tb/cosim_test_wrapper.py` shows how
to coordinate multiple module environments and shared software-side resources.

## Utilities

### `always_sample_next()`

`always_sample_next()` is intended for simulators where cocotb observes updated
register values at the same edge that triggered the coroutine. It lets a monitor
sample “the next cycle view” in a reusable way.

### `connect_check()`

`connect_check()` continuously watches two signals and asserts that they remain
equal throughout simulation.

```python
await cocotb.start_soon(connect_check(dut.sig_a, dut.sig_b))
```

### `SimLogger`

`SimLogger` provides:

- `configure_stream_handlers(...)`
- `create_filter(...)`
- `add_file_handler(...)`
- `create_file_handler(...)`

The example testbench demonstrates one way to configure filtered console and
file logging.

## Development

Run the minimal regression suite:

```bash
PYTHONPATH=src python -m pytest tests
```

Build lockfile and distribution artifacts:

```bash
uv lock
uv build
```

Artifacts are generated under `dist/`.

## Packaging Notes

- The wheel contains only the `cocotb_uvm` Python package.
- The example project under `examples/` is repository-only content.
- The package is typed via `py.typed`.
- The project license is MIT.

## Status

The project is currently marked as `0.1.0` and classified as alpha.
