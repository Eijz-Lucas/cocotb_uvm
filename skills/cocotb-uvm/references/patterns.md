# cocotb_uvm Component Patterns

Complete, annotated code patterns using **PascalCase** class naming.
Extracted from the working example at `examples/cosim_test/tb/`.

---

## 1. Transaction Definitions

Every verification module needs input and output transactions.
Both are `@dataclass` subclasses of `BaseTransaction` with PascalCase names.

### Pattern

```python
from dataclasses import dataclass
import numpy as np
from cocotb_uvm import BaseTransaction

@dataclass
class {Name}InputTransaction(BaseTransaction):
    """Captures the input side of a DUT operation."""
    # Fields from control inputs and consumed data.
    field1: int
    field2: int
    data_field: np.ndarray

    def clear(self):
        """Reset all fields to default/empty values."""
        self.field1 = 0
        self.field2 = 0
        self.data_field = np.array([])

    @classmethod
    def empty(cls):
        """Construct an empty (zeroed) instance."""
        return cls(field1=0, field2=0, data_field=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, {Name}InputTransaction):
            return False
        if self.field1 != other.field1 or self.field2 != other.field2:
            return False
        return np.array_equal(self.data_field, other.data_field)

    def copy(self):
        """Deep copy (monitors reuse internal state)."""
        return {Name}InputTransaction(
            field1=self.field1,
            field2=self.field2,
            data_field=np.copy(self.data_field),
        )


@dataclass
class {Name}OutputTransaction(BaseTransaction):
    """Captures the output side of a DUT operation."""
    result_field1: list
    result_data: np.ndarray

    def clear(self):
        self.result_field1 = []
        self.result_data = np.array([])

    @classmethod
    def empty(cls):
        return cls(result_field1=[], result_data=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, {Name}OutputTransaction):
            return False
        if self.result_field1 != other.result_field1:
            return False
        return np.array_equal(self.result_data, other.result_data)

    def copy(self):
        return {Name}OutputTransaction(
            result_field1=self.result_field1.copy(),
            result_data=np.copy(self.result_data),
        )
```

**Key points:**
- `id` is inherited from `BaseTransaction` — don't add it to your fields.
- Every transaction needs `clear()`, `empty()`, `__eq__()`, and `copy()`.
- Use `np.array_equal()` for numpy fields in `__eq__()`.

---

## 2. Reference Model

Pure software — no DUT handles, no `await`, no cocotb triggers.

### Pattern

```python
from cocotb_uvm import BaseModel

class {Name}Model(BaseModel):
    def __init__(self, in_queue, exp_queue, name="{Name}Model"):
        super().__init__(in_queue, exp_queue, name)

    def compute(self, input_trans: {Name}InputTransaction) -> {Name}OutputTransaction:
        """Implement the DUT's computation logic synchronously."""
        result_data = input_trans.data_field + 1
        return {Name}OutputTransaction(
            result_field1=[...],
            result_data=result_data,
        )
```

**Key points:**
- `compute()` is called automatically by `BaseModel.run()`.
- The `id` field is propagated automatically.

---

## 3. Driver

Drives DUT signals for one operation. Supports both `ut` and `st` levels.

### Pattern

```python
from cocotb_uvm import BaseDriver
from cocotb.triggers import RisingEdge

class {Name}Driver(BaseDriver):
    def __init__(self, dut, name="{Name}Driver"):
        super().__init__(dut, name)

    async def run(self, item, level="ut", **signals):
        """Execute one command.

        item: dict, dataclass, or any type the sequence produces.
              Use item["field"] for dicts, item.field for dataclasses.
        level: "ut" drives self.dut directly; "st" drives signal handles
               received via **signals.
        """
        if level == "ut":
            en    = self.dut.en
            len_  = self.dut.len
            addr  = self.dut.addr
        elif level == "st":
            en    = signals["en_sig"]
            len_  = signals["len_sig"]
            addr  = signals["addr_sig"]

        # Use item["key"] for dict, or item.key for dataclass
        en.value = 1
        len_.value = item["len"]
        addr.value = item["addr"]
        await RisingEdge(self.dut.clk)
        en.value = 0
        len_.value = 0
        addr.value = 0
```

**Key points:**
- In ST mode, the driver receives top-level signal handles via `**signals`.
  These come from the wrapper → cosim `execute_system_test` → driver `run()`.
  This is required because the cosim's `self.dut` is the sub-module handle,
  which cannot strongly drive top-level signals in most simulators.
- Deassert control signals after each operation — don't hold them high.
- `item` can be dict (`item["len"]`) or dataclass (`item.len`). Be flexible.

---

## 4. Monitors

Two monitors per module. Each maintains internal transaction state and
returns a completed transaction when ready.

### Input Monitor Pattern

```python
from cocotb_uvm import BaseMonitor

class {Name}InputMonitor(BaseMonitor):
    def __init__(self, dut, in_queue, name="{Name}InputMonitor", *args, **kwargs):
        super().__init__(dut, in_queue, name, *args, **kwargs)
        self.input_trans = {Name}InputTransaction.empty()

    async def sample(self, *args, **kwargs):
        if self.dut.en.value == 1:
            self.input_trans.field1 = int(self.dut.addr.value)
            self.input_trans.field2 = int(self.dut.len.value)
        if self.dut.busy.value == 1:
            self.input_trans.data_field = np.append(
                self.input_trans.data_field, int(self.dut.data_in.value))
        elif len(self.input_trans.data_field) > 0:
            self.input_trans.data_field = np.delete(self.input_trans.data_field, -1)
            copy = self.input_trans.copy()
            self.input_trans.clear()
            return copy
        return None
```

### Output Monitor Pattern (with shared resource for UT mode)

```python
class {Name}OutputMonitor(BaseMonitor):
    def __init__(self, dut, act_queue, name="{Name}OutputMonitor", *args, **kwargs):
        # *args/**kwargs forwarded to run() — use for shared resources like FIFO
        super().__init__(dut, act_queue, name, *args, **kwargs)
        self.output_trans = {Name}OutputTransaction.empty()

    async def sample(self, *args, **kwargs):
        if self.dut.busy.value == 1:
            self.output_trans.result_field1.append(int(self.dut.addr_out.value))
        if self.dut.out_valid.value == 1:
            data = self.dut.out_data.value.to_signed()
            self.output_trans.result_data = np.append(
                self.output_trans.result_data, data)
        elif len(self.output_trans.result_data) > 0:
            self.output_trans.result_field1.pop()
            copy = self.output_trans.copy()
            self.output_trans.clear()
            return copy
        return None

    async def run(self, fifo=None, *args, **kwargs):
        """Override run() to push sampled outputs into a shared FIFO model.

        When fifo is provided (UT mode with inter-module FIFO), each completed
        output transaction's data is pushed into the FIFO automatically after
        sampling. This keeps all DUT signal sampling inside the monitor — the
        wrapper does NOT need to do backdoor signal reads.
        """
        while True:
            await Timer(self.sample_delay, unit=self.sample_delay_unit)
            transaction = await self.sample(*args, **kwargs)
            if transaction is not None:
                transaction.id = self._next_id
                self._next_id += 1
                self.output_queue.put_nowait(transaction)
                self.log.debug("[%s Sample] %s", self.name, transaction)
                # Push sampled data into shared resource for downstream module
                if fifo is not None:
                    fifo.push(transaction.result_data.reshape(-1, 1))
            await RisingEdge(self.dut.clk)
```

**Key points:**
- Monitors use an internal state machine: accumulate while busy/valid, return
  a completed copy when the transaction ends, then clear for next one.
- Always `copy()` before returning, `clear()` immediately after.
- **For multi-module UT mode**: Pass shared resources (FIFO, RAM model) via
  `*args/**kwargs` to `__init__`, which are forwarded to `run()` by the base
  class. The monitor handles all DUT signal sampling — the wrapper should NOT
  do backdoor signal reads. This encapsulation keeps the data flow clean.
- `sample()` is called in a loop by the base class with `Timer(sample_delay)`
  between calls, then `RisingEdge(clk)`. You don't manage the timing.

---

## 5. Scoreboard

Usually the default implementation is sufficient.

### Pattern (default)

```python
from cocotb_uvm import BaseScoreboard

class {Name}Scoreboard(BaseScoreboard):
    def __init__(self, act_queue, exp_queue, name="{Name}Scoreboard"):
        super().__init__(act_queue, exp_queue, name)
```

### Pattern (custom comparison with backdoor)

```python
from cocotb.trigger import Event
from cocotb.queue import Queue

class {Name}Scoreboard(BaseScoreboard):
    def __init__(self, act_queue, exp_queue, name="{Name}Scoreboard"):
        super().__init__(act_queue, exp_queue, name)
        self.error = Event()
        self.backdoor_queue = Queue()

    async def run(self):
        while True:
            actual_trans = await self.actual_queue.get()
            expected_trans = await self.expected_queue.get()
            self.log.debug(f"Actual: {actual_trans}")
            self.log.debug(f"Expected: {expected_trans}")
            if actual_trans == expected_trans:
                self.match_count += 1
                self.log.debug(f"MATCH! count={self.match_count}")
            else:
                self.mismatch_count += 1
                self.error.set()
                self.backdoor_queue.put_nowait(expected_trans)
                self.log.error(f"MISMATCH! count={self.mismatch_count}")
                if actual_trans.result_field1 != expected_trans.result_field1:
                    self.log.error(f"  field1 mismatch: actual=..., expected=...")
                if not np.array_equal(actual_trans.result_data, expected_trans.result_data):
                    self.log.error(f"  data mismatch")
```

---

## 6. CoSimBase

Wires all five components together. The `execute_*` methods forward signals
to the driver in ST mode.

### Pattern

```python
from cocotb_uvm import CoSimBase
from cocotb.triggers import RisingEdge

class {Name}CoSim(CoSimBase):
    def __init__(self, dut, name="{Name}CoSim", mode="hw", level="ut",
                 *args, **kwargs):
        super().__init__(
            dut,
            {Name}Model,
            {Name}Driver,
            {Name}InputMonitor,
            {Name}OutputMonitor,
            {Name}Scoreboard,
            mode, level, name,
            *args, **kwargs,
        )

    async def execute_unit_test(self, item, **resources):
        """UT: use software-side models for interconnects."""
        if self.mode == "hw":
            await self._wait_idle()
            await self.driver.run(item, level="ut")
        elif self.mode == "sw":
            in_trans = self._build_input(item, **resources)
            out_trans = self.reference_model.compute(in_trans)
            resources["fifo"].push(out_trans.result_data.reshape(-1, 1))

    async def execute_system_test(self, item, **signals):
        """ST: forward top-level signal handles to the driver.

        The **signals kwargs come from the wrapper, which passes top-level
        DUT signal handles (e.g. en_sig=dut.top_en). These are forwarded
        to the driver so it can drive top-level signals. The driver cannot
        use self.dut.* in ST mode because self.dut is the sub-module handle,
        and most simulators don't support strong driving from sub-modules.
        """
        await self._wait_idle()
        await self.driver.run(item, level="st", **signals)

    async def _wait_idle(self):
        while True:
            await RisingEdge(self.dut.clk)
            if self.dut.busy.value == 0:
                break
```

**Key points:**
- `execute()` (from base) dispatches to `execute_unit_test` or
  `execute_system_test` based on `self.level`.
- **ST mode signal chain**: wrapper → `cosim.execute_system_test(**signals)`
  → `driver.run(level="st", **signals)`. Each layer forwards the top-level
  signal handles. This is essential for simulator compatibility.
- `*args/**kwargs` to `__init__` are forwarded to component constructors
  by `CoSimBase`. Use this to pass shared resources to monitors in UT mode.

---

## 7. CoSimWrapperBase

For multi-module systems. Routes items to the appropriate module.

### Pattern (op-based routing)

```python
from cocotb_uvm import CoSimWrapperBase

class {Name}Wrapper(CoSimWrapperBase):
    def __init__(self, dut, modules, level="ut", name="{Name}Wrapper"):
        super().__init__(dut, modules, level=level, name=name)
        # For UT mode: initialize shared software resources
        if self.level == "ut":
            self.fifo = FifoModel(size=1, depth=64)

    async def execute_unit_test(self, item):
        await self.wait_for_completion()
        # Choose routing based on item type or content
        if item["op"] == "encode":
            await self.modules["encoder"].execute(item=item, fifo=self.fifo)
        elif item["op"] == "decode":
            await self.modules["decoder"].execute(item=item, fifo=self.fifo)

    async def execute_system_test(self, item, **signals):
        await self.wait_for_completion()
        # Pass top-level signal handles down to the module's cosim,
        # which forwards them to the driver.
        if item["op"] == "encode":
            await self.modules["encoder"].execute(
                item=item,
                en_sig=self.dut.top_en,
                len_sig=self.dut.top_len,
                addr_sig=self.dut.top_addr,
            )
        elif item["op"] == "decode":
            await self.modules["decoder"].execute(
                item=item,
                en_sig=self.dut.top_en_dec,
                len_sig=self.dut.top_len_dec,
            )
```

### Pattern (pipeline routing — for fixed dataflows)

When the dataflow is always A→B→A→B... (e.g. encoder→decoder pipeline),
the wrapper can use a state machine or paired operations instead of
per-item op routing. Choose the clearest approach for the architecture.

```python
class {Name}Wrapper(CoSimWrapperBase):
    async def execute_unit_test(self, item):
        await self.wait_for_completion()
        # Always: run encoder first, then decoder with the encoded data
        await self.modules["encoder"].execute(item=item, fifo=self.fifo)
        encoded = self.fifo.pop()
        await self.modules["decoder"].execute(
            item={"encoded_len": encoded.len, "encoded_data": encoded.data},
            fifo=self.fifo)
```

**Key points:**
- `self.modules` is a dict keyed by the names from `module_specs`.
- `wait_for_completion()` before each operation ensures the previous one is
  fully processed.
- **UT mode**: pass shared software resources (FIFO, RAM model) to modules.
  Resources are ultimately received by monitors via `*args/**kwargs`.
- **ST mode**: pass top-level signal handles. They flow through: wrapper →
  cosim.execute_system_test(**signals) → driver.run(level="st", **signals).
  Never do backdoor signal reads in the wrapper — let monitors do that.

---

## 8. Test Entry Point

The `@cocotb.test()` coroutine that cocotb invokes.

### Pattern

```python
import cocotb
import logging
import os
import random

from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_uvm import BaseSequence, BaseSequencer, SimLogger, connect_check

from .{module}_cosim import {Name}CoSim
from .{module}_wrapper import {Name}Wrapper

# --- Logging (module-level, configured once) ---
simlogger = SimLogger()
stream_filter = SimLogger.create_filter(True,
    {"level": logging.INFO, "message": "REPORT"},
    {"level": logging.WARNING},
)
simlogger.configure_stream_handlers(stream_filter)
SimLogger.add_file_handler("sim.log")

# --- Level detection ---
level = "st" if os.environ.get("ST") == "1" else "ut"


# --- Sequence ---
class {Name}Sequence(BaseSequence):
    """Iterable stimulus source. __next__ can return dicts, dataclasses,
    or any type the cosim/wrapper's execute method accepts."""

    def __init__(self, name="{Name}Sequence", max_count=16):
        super().__init__(name)
        self.max_count = max_count
        self.count = 0

    def __next__(self):
        if self.count >= self.max_count:
            raise StopIteration
        self.count += 1
        # Return whatever type the execute methods accept:
        return {"op": "encode", "addr": random.randint(0, 7),
                "len": random.randint(1, 4)}
        # Or: return {Name}InputTransaction(data_in=random.randint(0, 0xFFFF))


# --- Sequencer ---
class {Name}Sequencer(BaseSequencer):
    def __init__(self, max_size=10, *args, **kwargs):
        super().__init__(max_queue_size=max_size, *args, **kwargs)


# --- Test ---
@cocotb.test()
async def test(dut):
    random.seed(0xDEADBEEF)

    # 1. Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # 2. Reset (active-low)
    dut.rst_n.value = 1
    await Timer(20, unit="ns")
    await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    # 3. Backdoor init (st mode only)
    if level == "st":
        dut.u_ram.mem[0].value = 10

    # 4. Environment
    if level == "ut":
        modules = [
            ("encoder", EncoderCoSim, {"dut": dut.u_encoder, "mode": "hw", "level": "ut"}),
            ("decoder", DecoderCoSim, {"dut": dut.u_decoder, "mode": "hw", "level": "ut"}),
        ]
    else:
        modules = [
            ("encoder", EncoderCoSim, {"dut": dut.u_encoder, "mode": "hw", "level": "st"}),
            ("decoder", DecoderCoSim, {"dut": dut.u_decoder, "mode": "hw", "level": "st"}),
        ]
    env = {Name}Wrapper(dut, modules, level=level)

    # 5. Connect checks (st mode, optional)
    if level == "st":
        check_task = cocotb.start_soon(
            connect_check(dut.sig_a, dut.u_sub.sig_b))

    # 6. Run
    sequencer = {Name}Sequencer()
    await sequencer.run(env, {Name}Sequence(max_count=100))
    await env.wait_for_completion()

    # 7. Report and assert
    env.report()
    assert env.success, "Verification failed — mismatches detected"

    # 8. Teardown
    env.teardown()
    if level == "st":
        check_task.cancel()
```

**Key points:**
- `__next__` can return dict, dataclass, or any type — as long as the
  cosim/wrapper `execute` methods accept it. Default to dict for simplicity;
  use dataclass when type safety is preferred.
- Seed the RNG for reproducibility.
- Reset: deassert, wait 2 cycles, assert, wait 1 cycle, deassert.
- `SimLogger()` is a singleton — configure once at module level.
- Always `assert env.success` and call `teardown()`.
