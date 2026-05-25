# Example Cosim Test

## Purpose

Extract the reusable patterns from the repository example without copying large source files into the skill body.

## Topology

The example platform verifies a two-stage dataflow:

1. `add_one`
   - reads values from RAM
   - increments each item by one
   - writes the result into a FIFO-like channel
2. `sub_one`
   - reads values from that FIFO-like channel
   - decrements each item by one
   - writes the final result to output

This is a good demonstration of how the library separates:

- module-level checking inside each child `CoSimBase`
- top-level composition inside a `CoSimWrapperBase`
- UT composition through Python-side models
- ST composition through RTL wiring

## Child Module Roles

### `add_one_cosim`

This module environment demonstrates:

- an input transaction containing command fields plus sampled RAM data
- an output transaction containing visited RAM addresses plus emitted FIFO data
- a custom scoreboard with mismatch events and side-channel recovery support
- a `sw` execution path that reads from software RAM and writes to software FIFO

### `sub_one_cosim`

This module environment demonstrates:

- a simpler input transaction with `len` plus sampled FIFO read data
- a simpler output transaction with emitted FIFO write data
- a scoreboard that can stay close to `BaseScoreboard`
- a `sw` execution path that reads and writes software FIFO data

Together, these two modules show that not every block needs the same scoreboard or transaction richness.

## Wrapper-Level UT Composition

The wrapper builds two software-side resources in UT:

- `ram_model`
- `fifo_model`

These resources do two jobs:

1. store shared state in Python
2. drive child DUT-facing ports through cocotb coroutines when UT still uses hardware child modules

This is an important pattern in your framework:

- UT does not mean "no RTL exists"
- UT means module composition happens in Python rather than through RTL top interconnect

The wrapper starts these background coroutines only in `ut`, which keeps ST behavior aligned with real RTL connectivity.

## Wrapper-Level ST Composition

In ST, the wrapper does not emulate transport between modules. Instead it:

- receives a top-level instruction
- selects the target child module
- passes the relevant top-level signal handles down to that child module

This reflects the intended Verilator-compatible usage where top-level signals drive child instances and forcing child ports directly is not the right abstraction.

## Top-Level Stimulus Pattern

The example uses firmware-like dictionaries as the top-level instruction format:

```python
{"op": "add_one", "addr": 0, "len": 5}
{"op": "sub_one", "len": 3}
```

This is a strong pattern for the skill:

- the sequence emits simple instruction dictionaries
- the wrapper routes by `inst["op"]`
- child drivers map the instruction to concrete signal activity

The example sequence also tracks FIFO occupancy so it does not generate obviously illegal operations. That is a useful pattern when random traffic must respect resource limits.

## Sequence And Sequencer Pattern

`cosim_test_sequence` shows two reusable ideas:

- random constrained instruction generation
- optional file-backed instruction replay through JSONL

This means a sequence in this framework can be:

- deterministic and file-driven
- algorithmic and random
- stateful with respect to resource occupancy

`cosim_test_sequencer` only customizes queue depth. That is a reminder that many sequencers can remain thin subclasses of `BaseSequencer`.

## Test Entrypoint Pattern

The bundled example cocotb test follows a useful standard order:

1. seed randomness
2. start the clock
3. apply reset
4. optionally initialize DUT state for ST
5. create child module specs with the chosen `level`
6. instantiate the wrapper
7. instantiate the sequencer
8. optionally start long-running connectivity checks
9. run sequencer against wrapper
10. wait for completion
11. report and assert success
12. teardown and cancel helper tasks

This sequence is a good default template for skill-generated test entrypoints.

## Connectivity And Cross-Checks

The example uses `connect_check()` in ST to verify that selected top-level and internal FIFO signals remain equal.

This shows a good system-level practice:

- keep module-local correctness in scoreboards
- add separate connectivity assertions for wrapper-level wiring assumptions

Use this pattern when the user asks for interconnect validation or wants confidence that top-level wiring matches internal expectations.

## Example-Specific Details

These details belong to the repository example and should not be generalized blindly:

- the `op` values are `"add_one"` and `"sub_one"`
- RAM and FIFO widths, depths, and shapes are example-specific
- the wrapper's `backdoor_handler()` is tailored to this flow and scoreboard
- the sequence's occupancy rules are specific to the example FIFO contract
- ST initialization backdoor writes directly into one example RAM instance

When using this example as a template, preserve the structural pattern and replace these protocol-specific details.

## Generalizable Patterns

These parts are broadly reusable across other cocotb_uvm platforms:

- one child `CoSimBase` per logical DUT block
- one wrapper to compose multiple child environments
- UT composition through Python-side shared resources
- ST composition through top-level RTL signal handles
- top-level instruction routing by operation field
- sequence-driven execution via `BaseSequencer`
- explicit completion wait, reporting, and teardown

## How To Reuse This Example

When the user asks for a new platform similar to the example:

1. identify the logical child blocks
2. define one module environment per block
3. decide whether inter-block transport is Python-side UT or RTL-side ST
4. define a simple top-level instruction schema
5. route by that schema in the wrapper
6. add any shared software-side resources only if UT requires them
7. add connectivity checks only for actual wiring assumptions

This example is best treated as a structural template, not as a literal code template.

## Packaging Note

This reference is intended to be self-contained inside the installed skill. Treat the example described above as bundled guidance, not as a dependency on external repository files.
