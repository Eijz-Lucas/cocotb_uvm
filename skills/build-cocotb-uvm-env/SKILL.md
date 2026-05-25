---
name: build-cocotb-uvm-env
description: Build or extend cocotb verification environments with the local cocotb_uvm Python library. Use when Codex needs to create individual verification components such as transactions, drivers, monitors, scoreboards, sequences, or cocotb tests, or larger module-level CoSimBase environments and wrapper-level CoSimWrapperBase environments that follow this repository's UVM-style architecture, including UT/ST and HW/SW flow selection.
---

# Build cocotb_uvm Environments

Build around the framework's actual layering instead of writing ad hoc cocotb benches. Treat the local `cocotb_uvm` sources as authoritative if the workspace differs from this skill's bundled reference.

## Start Here

1. Inspect the local public API and the nearest example before editing.
2. Match the output scope to the user's request:
   - If the user asks for one component such as a driver, monitor, scoreboard, sequence, or test, generate only that component and any tiny supporting code it strictly depends on.
   - If the user asks for a `CoSimBase` subclass, generate the `CoSim` class plus only the missing support classes the user explicitly requested or that the class cannot exist without.
   - If the user asks for a `CoSimWrapperBase` subclass, focus on wrapper routing, shared software models, and `module_specs`; do not expand every child module unless requested.
   - If the user asks for a full platform, generate the whole stack.
3. Decide whether the task is module-level or wrapper-level.
4. Decide the execution flow:
   - `level="ut"` for transaction-oriented unit testing.
   - `level="st"` for system testing through connected RTL blocks.
   - `mode="hw"` to drive the DUT.
   - `mode="sw"` only for `ut`; `st` plus `sw` is invalid.
5. Build the environment in the framework's canonical order when the requested scope is broad enough:
   - transaction
   - reference model
   - driver
   - input monitor
   - output monitor
   - scoreboard
   - `CoSimBase` or `CoSimWrapperBase`
   - sequence / sequencer
   - cocotb test

## Scope Control

Honor the user's requested granularity.

- Do not force a full environment when the user asked for one component.
- Do not invent wrapper-level plumbing when the user asked for a single module `CoSim`.
- If a requested component depends on undeclared transaction types or helper methods, add the smallest necessary stubs and state those assumptions in code comments or the response.
- Reuse existing local transactions, models, or monitors when they already exist instead of regenerating parallel versions.

Prefer these default outputs:

- user asks for `driver`: generate one `BaseDriver` subclass and keep stimulus assumptions explicit
- user asks for `monitor`: generate one `BaseMonitor` subclass, define sample boundaries, and clarify whether it is input-side or output-side
- user asks for `scoreboard`: generate one `BaseScoreboard` subclass only when default equality is insufficient
- user asks for `CoSim`: generate constructor wiring and `execute_*()` methods first, then only the dependencies needed around it
- user asks for `CoSimWrapper`: generate `module_specs`, routing, shared models, completion policy, and teardown/report usage

## Module Environment Pattern

For one DUT block, create a `CoSimBase` subclass and wire these responsibilities:

- Define protocol-specific transactions as `dataclass` subclasses of `BaseTransaction`.
- Implement `BaseModel.compute()` to turn one input transaction into one expected output transaction.
- Implement `BaseDriver.run()` to drive one command or transaction onto DUT signals.
- Implement `BaseMonitor.sample()` for input and output observation.
- Use `BaseScoreboard` directly when equality is enough; subclass it when arrays, diagnostics, or recovery behavior need custom comparison.
- Implement `execute_unit_test()` and `execute_system_test()` in the `CoSimBase` subclass.

Preserve the queue pipeline:

- input monitor -> `input_queue`
- reference model -> `expected_queue`
- output monitor -> `actual_queue`
- scoreboard consumes `actual_queue` and `expected_queue`

Do not assign transaction IDs manually in normal monitor flow. `BaseMonitor` assigns incrementing `id` values when a completed transaction is emitted, and `BaseModel.run()` propagates that `id` onto the expected transaction.

## Wrapper Environment Pattern

Use `CoSimWrapperBase` when one top-level flow coordinates multiple module environments.

- Pass `module_specs` as `(module_name, module_cls, module_config)` tuples.
- Route top-level instructions in `execute_unit_test()` / `execute_system_test()`.
- Keep shared Python-side models such as RAM or FIFO inside the wrapper when running UT mode.
- Start those software-side helper coroutines only in UT mode unless the design explicitly needs them in ST mode.
- Gate dependent operations with `await self.wait_for_completion()` when later commands depend on prior scoreboard completion or shared transport state.

## Batch Generation for Complex Requests

If the requested `CoSimBase` or `CoSimWrapperBase` is more than a small single-module pattern, split the work into batches instead of generating everything monolithically.

Use batching when you see one or more of these conditions:

- multiple child modules or nested wrappers
- shared RAM/FIFO/backdoor models
- distinct UT and ST routing paths
- multiple transaction types or instruction formats
- nontrivial scoreboard recovery or debug hooks

Use this default batch order:

1. define transactions, command shape, and execution assumptions
2. generate leaf components: model, driver, monitors, scoreboard
3. generate `CoSimBase` or `CoSimWrapperBase` wiring and routing
4. generate sequences and top-level cocotb tests

When batching, tell the user what batch you are implementing now and what remains. If the user asks directly for a complex `CoSim` or wrapper, start with the first batch that unblocks the requested class rather than refusing or dumping an oversized one-shot file.

## Sequencing Pattern

Use `BaseSequence` for iterable stimulus sources and `BaseSequencer.run()` to feed items into any executor that exposes `name` and `execute(item)`.

- Keep the sequence payload aligned with the environment entry point.
- For wrapper environments, prefer top-level command dictionaries or lightweight dataclasses.
- Put randomization or file-backed instruction replay inside the sequence, not the driver.

## Monitor and Scoreboard Rules

- Return `None` from `sample()` while a transaction is incomplete.
- Emit a transaction only once the full observation window is finished.
- If the simulator exposes updated values one cycle later than expected, prefer `always_sample_next()` instead of scattering extra delays manually.
- Use `connect_check()` only for persistent signal-equivalence assertions between connected signals.
- In `mode="sw"` unit-test paths, `CoSimBase.execute()` auto-increments `scoreboard.match_count` after `execute_unit_test()`. Do not write code that expects scoreboard queue traffic in that path unless you intentionally add it.

## Cocotb Test Pattern

A typical top-level test should do this:

1. Start clocks and apply reset.
2. Instantiate module specs and the wrapper or module environment.
3. Instantiate a sequencer and one or more sequences.
4. Run `await sequencer.run(executor, sequence, ...)`.
5. Wait for scoreboard completion with `wait_for_completion()`.
6. Call `report()`.
7. Assert `success`.
8. Call `teardown()` to cancel background tasks.

## Implementation Heuristics

- Mirror the naming split already used in the repository: `*_model`, `*_driver`, `*_input_monitor`, `*_output_monitor`, `*_scoreboard`, `*_cosim`.
- Keep transactions comparable. If payloads use `numpy.ndarray`, implement `__eq__()` explicitly.
- Put DUT-specific idling or ready checks in a small helper such as `wait_idle()`.
- Keep driver APIs thin. Accept one top-level instruction object plus only the extra signals or software models needed for the selected flow.
- Prefer wrapper-level orchestration over cross-coupling modules directly.
- If the task is "build a new verification platform", copy the structure of `examples/cosim_test/tb/` rather than inventing a new architecture.

## Reference Files

- Read `references/api-and-patterns.md` for the current API map, UT/ST and HW/SW rules, and the repository example mapping.
