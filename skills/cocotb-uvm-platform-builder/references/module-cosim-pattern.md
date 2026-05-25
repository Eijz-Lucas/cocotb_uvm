# Module CoSim Pattern

## Purpose

Describe how to build a module-level environment on top of `CoSimBase`.

## Required Ingredients

For one DUT block, implement these layers:

1. Input transaction type
2. Output transaction type
3. Reference model
4. Driver
5. Input monitor
6. Output monitor
7. Scoreboard
8. Module environment subclass of `CoSimBase`

Keep these layers explicit even when the DUT is simple. The library is designed around that separation.

## Constructor Pattern

Write the module environment constructor as a thin wiring layer:

```python
class my_block_cosim(CoSimBase):
    def __init__(self, dut, name="my_block_cosim", mode="hw", level="ut"):
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
```

Do not manually recreate queues or background tasks in the subclass unless the module truly needs extra side channels.

## Transaction Design

Define transactions around logical operations, not around single cycles.

Use the example pattern:

- input transaction:
  - capture the command fields that start the operation
  - capture any sampled input payload consumed while the DUT is busy
- output transaction:
  - capture the observable outputs associated with one completed operation

When transactions contain numpy arrays:

- implement custom `__eq__()` with `np.array_equal()`
- implement `copy()` to detach monitor-owned mutable state
- implement `clear()` and `empty()` when the monitor accumulates a transaction over time

## Reference Model Pattern

Use `BaseModel.compute()` for a pure functional transform from input transaction to expected output transaction.

Good model behavior:

- deterministic
- side-effect free unless the DUT contract requires stateful modeling
- aligned with the transaction boundary chosen by the monitors

In `sw` mode, the module environment may call `reference_model.compute()` directly instead of waiting for the background queue-based path.

In the current library, `sw` does not remove the need for `dut`. `CoSimBase` still constructs driver and monitor objects during initialization, so the environment still needs an RTL instance or at least an empty placeholder RTL instance.

## Driver Pattern

Drivers usually consume a top-level instruction dictionary and translate it into DUT signal activity.

Recommended shape:

```python
async def run(self, inst, level="ut", en_sig=None, len_sig=None, addr_sig=None):
    if level == "ut":
        en = self.dut.en
        len_sig_local = self.dut.len
    else:
        en = en_sig
        len_sig_local = len_sig
```

Guidelines:

- In UT, drive the child DUT directly.
- In ST, accept top-level signal handles from the wrapper and drive those instead.
- Reset control signals after the command pulse completes.
- Keep protocol timing in the driver, not in the wrapper.

## Monitor Pattern

Monitors are the most protocol-specific part of the environment. The key design task is deciding when a transaction starts and when it is complete.

Typical pattern from the example:

- cache a mutable transaction object on `self`
- append sampled fields while the DUT is active
- when an end condition is observed, copy the transaction, clear the cached state, and return the copy
- return `None` on intermediate cycles

This pattern is visible in both example modules:

- `add_one_input_monitor` accumulates `ram_rdata` while `busy == 1`
- `add_one_output_monitor` accumulates `ram_addr` and `fifo_write_data`
- `sub_one_input_monitor` accumulates `fifo_read_data`
- `sub_one_output_monitor` accumulates `fifo_write_data`

If the DUT exposes one-cycle-late or same-edge visibility issues, use `always_sample_next()` or adjust monitor sampling carefully.

## Scoreboard Pattern

Start with `BaseScoreboard` unless the module needs more than simple equality comparison.

Use a custom scoreboard when you need:

- custom mismatch logging
- event signaling
- recovery or backdoor repair hooks
- non-trivial comparison semantics

Example:

- `add_one_scoreboard` overrides `run()`
- it logs detailed mismatches
- it raises an event and enqueues expected transactions for wrapper-level backdoor handling

If a normal equality compare is sufficient, subclassing `BaseScoreboard` without overrides is acceptable, as shown by `sub_one_scoreboard`.

## `execute_unit_test()` Pattern

Implement UT behavior around `mode`.

### `ut + hw`

- optionally wait until the DUT is idle
- call the driver with local child-module signals
- let monitors, model, and scoreboard complete the rest

### `ut + sw`

- build an input transaction from software-side resources such as RAM or FIFO models
- call `reference_model.compute()`
- update the software-side resource with the modeled output
- rely on `CoSimBase.execute()` to increment `scoreboard.match_count`
- do not rely on driver activity or monitor output for the main scoring path

Even in this mode:

- instantiate the environment with `dut`
- expect driver and monitor objects to exist
- treat them as inactive for the main software execution path rather than absent

This means `sw` mode is not a different class hierarchy. It is a different execution path inside the same module environment.

## `execute_system_test()` Pattern

Implement ST behavior as a thin adapter that accepts top-level signal handles and forwards them into the driver.

Typical flow:

1. wait for the module to become idle if overlap is illegal
2. call `driver.run(..., level="st", en_sig=..., len_sig=..., ...)`

Do not create Python-side transport models between modules in ST. The RTL interconnect is the transport.

## Helper Methods

Module subclasses may add helper methods for protocol-specific control:

- `wait_idle()`
- `get_in_trans()`
- software-side read or write helpers

These helpers should keep `execute_unit_test()` and `execute_system_test()` short and readable.

## Completion Semantics

Remember how module completion works:

- `execute()` increments `executed_count`
- scoreboards increment `match_count` or `mismatch_count`
- `wait_for_completion()` returns only when `match_count + mismatch_count == executed_count`

Therefore, every executed operation must eventually produce exactly one scoreboard decision. If a monitor never emits the closing transaction, the environment will stall.

## Generation Checklist

Before finishing a new module environment, check:

- one input transaction corresponds to one expected output transaction
- the input monitor feeds the reference model queue
- the output monitor feeds the actual queue
- the scoreboard eventually produces one result per `execute()`
- UT and ST driver wiring are both explicit
- `st + sw` is not allowed
- `sw` mode does not rely on RTL observation
- `sw` mode still has a valid `dut` and base-constructed driver/monitor objects
- helper methods hide protocol details instead of bloating `execute_*()`

## Packaging Note

This reference is intended to be self-contained inside the installed skill. Treat the examples described above as bundled patterns, not as pointers to external repository files.
