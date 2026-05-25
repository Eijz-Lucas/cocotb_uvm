# API Map

## Purpose

Summarize the cocotb_uvm public API and the role each class plays when building a verification environment.

## Public Exports

Import from the package root when building new code:

- `BaseTransaction`
- `BaseModel`
- `BaseDriver`
- `BaseMonitor`
- `BaseScoreboard`
- `BaseSequence`
- `BaseSequencer`
- `CoSimBase`
- `CoSimWrapperBase`
- `SimLogger`
- `always_sample_next`
- `connect_check`

## Core Data Types

### `BaseTransaction`

Use `BaseTransaction` as the root dataclass for any logical unit exchanged between model, monitors, scoreboard, or software-side resources.

- The base class only contributes `id`.
- `id` is assigned by monitors and propagated by `BaseModel.run()`.
- Add protocol-specific fields in subclasses.
- Add custom `__eq__()` when payloads contain numpy arrays or other data structures that do not compare correctly with default dataclass equality.
- Add helper methods such as `empty()`, `clear()`, and `copy()` when monitors need to accumulate data over multiple cycles before emitting a completed transaction.

## Component Base Classes

### `BaseModel`

Use `BaseModel` for the software reference path.

- Constructor inputs: `input_queue`, `expected_queue`, optional `name`
- Background behavior: starts `run()` automatically with `cocotb.start_soon()`
- Default `run()` behavior:
  - wait for one input transaction from `input_queue`
  - call `compute()`
  - copy the input `id` onto the expected transaction
  - push the result into `expected_queue`
- Override `compute()` for the actual functional transform.

Use `compute()` directly in `sw` mode when the module environment bypasses the normal hardware-driven execution path.

### `BaseDriver`

Use `BaseDriver` to convert a high-level instruction or transaction into DUT signal activity.

- Constructor input: `dut`
- Implement `run()`
- Keep UT and ST signal sourcing explicit inside `run()` or in the caller.
- In this library, drivers usually consume instruction dictionaries such as `{"op": "add_one", ...}` rather than typed transaction objects.

### `BaseMonitor`

Use `BaseMonitor` to reconstruct logical transactions from sampled DUT behavior.

- Constructor inputs: `dut`, `output_queue`, optional `sample_delay`
- Background behavior: starts `run()` automatically
- Default `run()` behavior:
  - wait `sample_delay`
  - call `sample()`
  - if a transaction is returned, assign a new incrementing `id`
  - push to `output_queue`
  - wait for the next rising clock edge

`sample()` should usually accumulate data internally and return `None` until a full transaction boundary is reached.

### `BaseScoreboard`

Use `BaseScoreboard` to compare actual and expected transactions.

- Constructor inputs: `actual_queue`, `expected_queue`
- Background behavior: starts `run()` automatically
- Default `run()` behavior:
  - read one actual transaction
  - read one expected transaction
  - call `compare()`
- Default `compare()` uses `==` and updates `match_count` or `mismatch_count`

Override `run()` or `compare()` only when extra behavior is required, such as richer logging, recovery hooks, or side-channel events.

## Stimulus Classes

### `BaseSequence`

Use `BaseSequence` for iterable stimulus generation.

- Implement `__next__()`
- Raise `StopIteration` when exhausted
- Return whatever the target executor expects, typically an instruction dictionary

### `BaseSequencer`

Use `BaseSequencer` to feed one or more sequences into an executor that exposes `execute()`.

- Internal queue: `transaction_queue`
- `run(executor, *sequences)` starts both the producer and executor coroutine
- A private stop token terminates the executor loop after all sequences are exhausted

The executor may be a `CoSimBase` instance, a `CoSimWrapperBase` instance, or any other object with `name` and `execute()`.

## Environment Classes

### `CoSimBase`

Use `CoSimBase` for one module-level environment.

- Owns:
  - `input_queue`
  - `actual_queue`
  - `expected_queue`
  - `reference_model`
  - `driver`
  - `input_monitor`
  - `output_monitor`
  - `scoreboard`
  - `executed_count`
- `mode` is validated against `{"hw", "sw"}`
- `level` is validated against `{"ut", "st"}`
- `st + sw` is illegal

Execution semantics:

- `execute()` dispatches to `execute_unit_test()` or `execute_system_test()` based on `level`
- `executed_count` increments after every successful dispatch
- In `ut + sw`, `execute()` also increments `scoreboard.match_count` directly because the software path may bypass normal hardware observation for scoring
- `wait_for_completion()` waits until `scoreboard.match_count + scoreboard.mismatch_count == executed_count`
- `success` means `match_count == executed_count` and `mismatch_count == 0`
- `teardown()` cancels the background tasks created by model, monitors, and scoreboard

Construction note:

- Even in `sw`, `CoSimBase` still constructs the driver, monitors, and scoreboard, and still requires `dut`
- In practice this means the current library expects an RTL instance or at least an empty placeholder RTL instance so base construction can succeed
- `sw` changes the execution path, not the base object graph

### `CoSimWrapperBase`

Use `CoSimWrapperBase` to compose multiple module environments or nested wrappers.

- Constructor input: `module_specs`, where each item is `(module_name, module_cls, module_config)`
- Instantiates all child modules into `self.modules`
- Validates that no child `CoSimBase` runs in `sw` mode when the wrapper `level` is `st`
- `execute()` dispatches to `execute_unit_test()` or `execute_system_test()` based on wrapper `level`
- `wait_for_completion()`, `report()`, and `teardown()` forward to all child modules
- `success` is `all(module.success for module in self.modules.values())`

The wrapper does not create a shared scoreboard. Each child `CoSimBase` remains responsible for its own completion and pass/fail state.

## Utilities

### `always_sample_next()`

Use this decorator when a monitor must sample the next-cycle visible state rather than the same-edge view. It wraps a bound coroutine and performs:

1. `Timer(time, unit)`
2. wrapped sampling coroutine
3. `RisingEdge(instance.dut.clk)`

Only apply it to instance methods that have `self.dut.clk`.

### `connect_check()`

Use `connect_check(signal_0, signal_1)` as a long-running assertion that two signals remain equal throughout simulation. It waits on either signal changing and asserts equality immediately afterward.

## Mode And Level Rules

- `level` and `mode` are fixed at environment construction time.
- `ut` means software-orchestrated unit composition. Child modules in a wrapper may exchange data through Python-side resources such as RAM or FIFO models.
- `st` means RTL-connected system composition. Wrapper code routes top-level control into child module `execute_system_test()` calls and passes top-level signal handles when needed.
- `hw` means normal RTL-driven execution through the driver, monitors, and scoreboard.
- `sw` means software execution that may bypass normal RTL driving and observation during `execute_unit_test()`, but the environment still requires `dut` and instantiated driver and monitor objects because of `CoSimBase` construction. Limit it to module-level environments in `ut`.

## Scope Boundary

This skill is for testbench generation only.

Generate:

- transactions
- reference models
- drivers
- monitors
- scoreboards
- module-level cosim classes
- wrapper classes
- sequences
- cocotb tests
- Python-side helper resources such as RAM or FIFO models

Do not generate:

- RTL modules
- RTL top wiring
- synthesizable logic
- protocol implementation RTL

## Packaging Note

This reference is intended to be self-contained inside the installed skill. Do not depend on external repository file paths when using it.
