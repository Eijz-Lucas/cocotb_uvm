---
name: cocotb-uvm
description: >
  Build complete cocotb_uvm verification environments from DUT descriptions.
  Use this skill whenever the user describes a DUT they want to verify,
  provides a port list or signal interface, asks to generate transaction/
  model/driver/monitor/scoreboard components, or wants to scaffold a cocotb
  testbench. Trigger even if they don't say "cocotb_uvm" explicitly — any
  mention of verifying hardware with cocotb, writing a UVM-style testbench
  in Python, or needing verification components (drivers, monitors,
  scoreboards, reference models) should activate this skill.
---

# cocotb_uvm Verification Environment Builder

Help experienced verification engineers quickly scaffold complete cocotb_uvm
verification environments. Focus on generating correct, compilable code
following the framework's patterns, not on teaching basics.

## Naming conventions

- **Class names**: PascalCase (e.g. `AddOneInputTransaction`, `AddOneDriver`,
  `AddOneCoSim`, `PopcountModel`, `EncoderDecoderWrapper`)
- **File names**: snake_case (e.g. `add_one_cosim.py`, `popcount_transactions.py`)
- **Method/variable names**: snake_case (e.g. `input_trans`, `fifo_write_data`)

## Interaction mode detection

At the start of each session, detect whether you have an interactive user:

**Interactive mode** (user is present): Follow the 4-phase workflow below,
asking for confirmation at each phase boundary. This is the default.

**Non-interactive mode** (batch/automated, no user available): Skip Phase 1 and
Phase 2 confirmation steps. Extract DUT info from the prompt, make reasonable
defaults (mode="hw", level="ut"), and generate all code in one pass without
stopping. Still follow the correct patterns — just don't wait for confirmations.

## Two input modes

The user can describe their DUT in either (or both) of these ways:

**Natural language** — "I have an add_one module that reads from RAM, adds 1,
and writes to a FIFO."

**Port list** — A structured signal listing:
```
Module: add_one
Input: clk, rst_n, en, [31:0] addr, [31:0] len
Output: busy, [31:0] ram_addr, fifo_write_en, [31:0] fifo_write_data
```

When only natural language is given, ask the user to also provide the port
list — accurate signal names are essential for driver and monitor code.

When only a port list is given, ask the user to describe what the module
*does* — the computation logic is essential for the reference model.

## Full vs. partial generation

Before starting, determine what the user needs:

**Full environment** — "build a verification environment", "verify module X",
"set up cocotb_uvm for...". Follow the complete 4-phase workflow below.

**Individual component** — "generate a driver for...", "write the monitor",
"just the scoreboard". Skip directly to Phase 3 and generate only the
requested component(s). You still need enough context (port list, signal
description, DUT behavior) to write correct code — ask for it if missing,
but don't go through the full Phase 1/2 confirmation cycle.

For individual components, read `references/patterns.md` for the specific
component template, adapt it to the user's DUT, and output only that code.

## Workflow (interactive mode)

### Phase 1 — Gather DUT information

From the user's description, extract and confirm:

1. **Module name** (PascalCase for classes, e.g. `AddOne`, `PacketParser`)
2. **Signal classification**:
   - **Control inputs**: signals the driver toggles (en, start, addr, len, opcode...)
   - **Control outputs**: status signals the monitor watches (busy, done, error...)
   - **Data inputs**: data the DUT consumes (read data buses, input FIFO data...)
   - **Data outputs**: data the DUT produces (write data buses, output valid...)
3. **Transaction fields** — map signals to fields:
   - **Input transaction**: control inputs + data consumed
   - **Output transaction**: data produced
4. **Mode**: `hw` or `sw`. Default to `hw`.
5. **Level**: `ut` or `st`. Default to `ut`.
6. **Wrapper needed?** — Multi-module coordination? → `CoSimWrapperBase`.

### Phase 2 — Framework overview

Show the file plan and component list, then confirm.

### Phase 3 — Generate components

Generate in dependency order. See `references/patterns.md` for complete code
templates — this document describes the design rules; patterns.md has the
copyable code.

**3.1 Transactions** (`BaseTransaction` subclasses)

`@dataclass` with PascalCase names. One input, one output. Each must have:
`clear()`, `empty()` (classmethod), `__eq__()`, `copy()`.

**3.2 Reference Model** (`BaseModel` subclass)

Override `compute(input_trans) -> output_trans`. Pure synchronous software.

**3.3 Driver** (`BaseDriver` subclass)

Override `async def run(self, item, level="ut", **signals)`.

- `item`: the sequence item — can be dict, dataclass, or any type. Use
  `item["field"]` for dicts, `item.field` for dataclasses.
- `level="ut"`: drive `self.dut` signals directly.
- `level="st"`: receive external signal handles via `**signals` (e.g.
  `en_sig`, `addr_sig`) and drive those instead. **The simulator cannot
  strongly drive signals from a sub-module handle — top-level signal
  handles must be passed down from the wrapper through the cosim.**

**3.4 Monitors** (`BaseMonitor` subclasses)

Two monitors — input and output. Each maintains an internal transaction
object. The `sample()` method accumulates data while the DUT is active,
returns a completed copy when a transaction ends, or `None` when nothing is
ready.

**For multi-module UT mode**: If the monitor needs to push/pull data from
a shared software resource (FIFO, RAM model), accept the resource via
`*args/**kwargs` to `run()`. The base class forwards `*args/**kwargs` from
`__init__` to `run()`. The wrapper passes the resource when constructing
modules. This way all DUT signal sampling stays inside the monitor — the
wrapper does NOT do backdoor signal reads.

**3.5 Scoreboard** (`BaseScoreboard` subclass)

Default implementation usually suffices. Customize `compare()` when needed.

**3.6 CoSimBase** (wires components together)

```python
class {Name}CoSim(CoSimBase):
    def __init__(self, dut, name="...", mode="hw", level="ut"):
        super().__init__(dut, {Name}Model, {Name}Driver,
                         {Name}InputMonitor, {Name}OutputMonitor,
                         {Name}Scoreboard, mode, level, name)

    async def execute_unit_test(self, item, **resources): ...
    async def execute_system_test(self, item, **signals): ...
```

**ST mode signal chain** — When the wrapper calls
`self.modules["encoder"].execute(inst=inst, en_sig=self.dut.top_en, ...)`,
the cosim's `execute_system_test` receives these kwargs and forwards them
to `self.driver.run(inst, level="st", en_sig=en_sig, ...)`. The driver
uses the received signal handles to drive the DUT. This is essential because
the cosim's `self.dut` is the sub-module, which cannot strongly drive
top-level signals in most simulators.

**3.7 Wrapper** (multi-module systems only)

```python
class {Name}Wrapper(CoSimWrapperBase):
    def __init__(self, dut, modules, level="ut", name="..."):
        super().__init__(dut, modules, level=level, name=name)
        # For UT mode: initialize shared software resources here
        # self.fifo = FifoModel(...)

    async def execute_unit_test(self, item): ...
    async def execute_system_test(self, item, **signals): ...
```

Route items to the appropriate module. The routing pattern depends on the
system architecture:
- **Op-based routing**: `if item["op"] == "encode": await self.modules["encoder"].execute(...)` —
  good when the sequencer emits dict commands with an `op` field
- **Pipeline routing**: always encode→decode in sequence — good for
  fixed dataflow pipelines
- **Type-based routing**: `if isinstance(item, EncoderInput): ...` —
  good when the sequencer emits typed dataclass objects

Choose the pattern that fits the DUT architecture. Do not force
`inst['op']` routing when the dataflow is naturally a fixed pipeline.

**3.8 Test entry point**

```python
@cocotb.test()
async def test(dut):
    # 1. Clock and reset
    # 2. Logging (SimLogger)
    # 3. Environment setup (wrapper or cosim)
    # 4. Sequencer + sequence
    # 5. Wait, report, assert
    # 6. Teardown
```

The sequence's `__next__` can return dicts (`{"op": "...", ...}`),
dataclass instances (`AddOneInput(data=...)`), or any type — as long as
the cosim/wrapper's `execute` method accepts it. Pick the simplest type
that works for the DUT.

### Phase 4 — Integration notes

1. **PYTHONPATH**: Ensure `src/` is on PYTHONPATH.
2. **Makefile**: Set `COCOTB_TEST_MODULES`, `VERILOG_SOURCES`.
3. **SIM**: Default is `verilator`.

## Batch generation for large projects

When the verification environment is large (multi-module systems, complex
protocols), generating everything in one pass may exceed output token limits.
In these cases, use **batch generation** — split the work into multiple
rounds, each producing a subset of files:

**Batch 1 — Data layer:**
- Transaction definitions (all modules)
- Shared software models (FIFO, RAM, etc.)

**Batch 2 — Per-module components (one module at a time if needed):**
- Reference model
- Driver
- Input and output monitors
- Scoreboard
- CoSimBase

**Batch 3 — Integration:**
- CoSimWrapperBase (if multi-module)
- Test entry point

Tell the user: *"This is a large project. I'll generate the code in 2-3
batches to keep each batch focused and correct."* Then proceed batch by
batch, keeping each round's output concise. The user doesn't need to
approve between batches — just generate all batches sequentially.

**When to batch:** The trigger is project complexity, not file count:
- Single module with simple protocol → one pass
- Single module with complex protocol (many signals, multi-cycle state
  machine) → consider 2 batches
- Two modules → 2 batches (data layer + per-module, then integration)
- Three or more modules → definitely batch

## Reference files

- `references/api_reference.md` — Full API signatures for every base class.
- `references/patterns.md` — Complete, copyable code templates for each
  component type, using PascalCase naming.
