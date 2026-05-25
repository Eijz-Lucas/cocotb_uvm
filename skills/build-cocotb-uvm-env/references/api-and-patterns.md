# cocotb_uvm API and Patterns

Use this file when you need concrete class responsibilities or want to map a new DUT onto the repository's existing example.

## Public API Map

The package root exports these symbols:

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

Source layout in this repository:

- `src/cocotb_uvm/transaction.py`
- `src/cocotb_uvm/components.py`
- `src/cocotb_uvm/sequencing.py`
- `src/cocotb_uvm/cosim.py`
- `src/cocotb_uvm/sim_logger.py`
- `src/cocotb_uvm/utils.py`

## Core Responsibilities

### `BaseTransaction`

- Abstract dataclass base for protocol transactions.
- Provides optional keyword-only `id`.
- Add payload fields in subclasses.
- If payload contains arrays or mutable containers, implement `__eq__()` and any copy helpers you need.

### `BaseModel`

- Constructor takes `input_queue` and `expected_queue`.
- Spawns `run()` automatically.
- Default `run()` waits for one input transaction, calls `compute()`, copies the transaction `id`, and enqueues the expected transaction.
- Usually only `compute()` needs overriding.

### `BaseDriver`

- Owns `dut` and logging.
- `run()` is abstract and should drive one operation.
- Keep it focused on signal activity, not scoreboarding or routing.

### `BaseMonitor`

- Constructor takes `dut` and `output_queue`.
- Spawns `run()` automatically.
- Default `run()` does:
  - wait `sample_delay`
  - call `sample()`
  - if a transaction is returned, assign `id` and enqueue it
  - wait one rising edge on `dut.clk`
- `sample()` should return `None` until the observation is complete.

### `BaseScoreboard`

- Constructor takes `actual_queue` and `expected_queue`.
- Spawns `run()` automatically.
- Default `compare()` increments `match_count` when transactions are equal, else `mismatch_count`.
- Override when you need richer mismatch logging or recovery behavior.

### `BaseSequence`

- Iterable stimulus source.
- Implement `__next__()` and raise `StopIteration` when exhausted.

### `BaseSequencer`

- Owns an internal queue.
- `run(executor, *sequences)` starts a producer and consumer.
- The executor only needs `name` and `execute(item)`.

### `CoSimBase`

- Constructs and owns the reference model, driver, monitors, and scoreboard.
- Creates `input_queue`, `actual_queue`, and `expected_queue`.
- Validates `mode in {"hw", "sw"}` and `level in {"ut", "st"}`.
- Rejects `mode="sw"` with `level="st"`.
- `execute()` dispatches to `execute_unit_test()` or `execute_system_test()`.
- In UT+SW mode, `execute()` increments `scoreboard.match_count` after `execute_unit_test()`.
- `wait_for_completion()` blocks until `match_count + mismatch_count == executed_count`.
- `teardown()` cancels background tasks created by the model, monitors, and scoreboard.

### `CoSimWrapperBase`

- Builds multiple module or wrapper environments from `module_specs`.
- Routes `execute()` into UT or ST handlers.
- `wait_for_completion()`, `report()`, and `teardown()` delegate to children.
- In ST mode, rejects child `CoSimBase` instances that use `mode="sw"`.

### `SimLogger`

- Configures root and `cocotb` loggers.
- Can adjust stream handlers, add file handlers, and build custom filters.

### Utilities

- `always_sample_next(time=10, unit="ns")`: wrap a bound monitor coroutine when you need sample-then-next-edge timing.
- `connect_check(signal_0, signal_1)`: continuously assert that two connected signals stay equal.

## UT/ST and HW/SW Rules

Use this decision table:

| Goal | `level` | `mode` | Typical use |
| --- | --- | --- | --- |
| Exercise one module with software-side transport models | `ut` | `hw` | Driver talks to DUT, wrapper owns Python RAM/FIFO |
| Bring up module behavior without driving real DUT datapath | `ut` | `sw` | Compute with reference model and mutate software-side transport directly |
| Verify connected RTL modules as a system | `st` | `hw` | Top-level wrapper routes commands into real DUT signals |

Do not use `st` with `sw`.

## Repository Example Mapping

The example under `examples/cosim_test/tb/` maps the framework like this:

- `add_one_input_trans` / `add_one_output_trans`: transaction definitions
- `add_one_model`: reference model
- `add_one_driver`: DUT driver
- `add_one_input_monitor` / `add_one_output_monitor`: transaction capture
- `add_one_scoreboard`: custom compare and backdoor recovery
- `add_one_cosim`: module environment built on `CoSimBase`

The same split exists for `sub_one_*`.

Wrapper pattern:

- `cosim_test_wrapper`: `CoSimWrapperBase` subclass
- owns `ram_model` and `fifo_model`
- routes top-level instruction dictionaries by `inst["op"]`
- only starts software RAM/FIFO models in UT mode

Top-level test pattern:

- `test_cosim_test.py` starts clock and reset
- builds module specs
- instantiates the wrapper
- instantiates a `BaseSequencer` subclass and a `BaseSequence` subclass
- runs `sequencer.run(wrapper, sequence)`
- waits for completion
- reports, asserts success, tears down

## Skeletons

### Module environment skeleton

```python
from dataclasses import dataclass

from cocotb.triggers import RisingEdge
from cocotb_uvm import (
    BaseDriver,
    BaseModel,
    BaseMonitor,
    BaseScoreboard,
    BaseTransaction,
    CoSimBase,
)


@dataclass
class my_input_trans(BaseTransaction):
    addr: int
    data: int


@dataclass
class my_output_trans(BaseTransaction):
    data: int


class my_model(BaseModel):
    def compute(self, input_trans: my_input_trans) -> my_output_trans:
        return my_output_trans(data=input_trans.data + 1)


class my_driver(BaseDriver):
    async def run(self, inst):
        self.dut.valid.value = 1
        self.dut.addr.value = inst["addr"]
        self.dut.data.value = inst["data"]
        await RisingEdge(self.dut.clk)
        self.dut.valid.value = 0


class my_input_monitor(BaseMonitor):
    async def sample(self):
        if self.dut.valid.value == 1:
            return my_input_trans(
                addr=int(self.dut.addr.value),
                data=int(self.dut.data.value),
            )
        return None


class my_output_monitor(BaseMonitor):
    async def sample(self):
        if self.dut.out_valid.value == 1:
            return my_output_trans(data=int(self.dut.out_data.value))
        return None


class my_scoreboard(BaseScoreboard):
    pass


class my_cosim(CoSimBase):
    def __init__(self, dut, mode="hw", level="ut", name="my_cosim"):
        super().__init__(
            dut,
            my_model,
            my_driver,
            my_input_monitor,
            my_output_monitor,
            my_scoreboard,
            mode,
            level,
            name,
        )

    async def execute_unit_test(self, inst):
        await self.driver.run(inst)

    async def execute_system_test(self, inst):
        await self.driver.run(inst)
```

### Wrapper skeleton

```python
from cocotb_uvm import CoSimWrapperBase


class my_wrapper(CoSimWrapperBase):
    async def execute_unit_test(self, inst):
        if inst["op"] == "mod0":
            await self.modules["mod0"].execute(inst)
        elif inst["op"] == "mod1":
            await self.modules["mod1"].execute(inst)

    async def execute_system_test(self, inst):
        await self.execute_unit_test(inst)
```

## Practical Constraints

- Keep `execute_*()` signatures aligned with the data the sequencer feeds.
- If one DUT operation spans multiple cycles, accumulate partial data inside the monitor and emit a completed transaction at the boundary.
- If the wrapper has software RAM/FIFO helpers, keep those helpers deterministic and local to the wrapper instead of letting child modules mutate global state directly.
- If the user asks for a new platform, prefer following `examples/cosim_test/tb/` file structure: one file per module environment plus one wrapper plus one test entry.

## Partial Generation Rules

Generate only the layer the user asked for unless a hard dependency makes that impossible.

- For a `driver` request, assume transactions or instruction dictionaries already exist unless the user asks for them too.
- For a `monitor` request, decide whether it is input-side or output-side and document the transaction completion rule.
- For a `CoSimBase` request, wire the class around existing local components when possible instead of regenerating all of them.
- For a `CoSimWrapperBase` request, focus on child-module orchestration, shared helper models, and instruction routing.

If a missing dependency blocks code generation, add only a minimal placeholder and keep it obvious that the placeholder is meant to be replaced by protocol-specific logic.

## Batch Planning Heuristics

Split work into batches when the requested class is not a small self-contained module environment.

Recommended batch cuts:

1. protocol definition
   - transactions
   - command dictionaries or dataclasses
   - mode and level assumptions
2. leaf verification components
   - model
   - driver
   - monitors
   - scoreboard
3. environment assembly
   - `CoSimBase` constructor wiring
   - `execute_unit_test()` and `execute_system_test()`
   - wrapper `module_specs` and routing
4. runnable harness
   - sequence
   - sequencer
   - cocotb test

For complex wrappers, prefer finishing one working vertical slice first instead of scaffolding every module at once.
