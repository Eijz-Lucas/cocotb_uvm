# Wrapper Pattern

## Purpose

Describe how to compose multiple module environments into a top-level `CoSimWrapperBase`.

## When To Use A Wrapper

Build a `CoSimWrapperBase` subclass when either condition is true:

- the platform contains multiple module-level `CoSimBase` environments
- top-level stimulus must be routed across several blocks or shared software-side resources

Do not use a wrapper for a single isolated block unless the repository already expects one.

## `module_specs` Pattern

Construct `module_specs` as a list of tuples:

```python
[
    ("add_one_cosim", add_one_cosim, {"dut": dut.u_add_one, "mode": "hw", "level": "ut"}),
    ("sub_one_cosim", sub_one_cosim, {"dut": dut.u_sub_one, "mode": "hw", "level": "ut"}),
]
```

Each entry is:

1. the key stored in `self.modules`
2. the module environment class
3. the keyword arguments used to instantiate that child

Use stable names that match the child environment role. Wrapper logic often routes by these keys.

## Wrapper Responsibilities

The wrapper should own:

- child environment instantiation through `module_specs`
- top-level routing decisions
- shared software-side models needed only in UT
- top-level sequencing rules between child operations
- optional cross-module recovery or coordination logic

The wrapper should not duplicate:

- child transaction definitions
- child driver timing
- child monitor internals
- child scoreboard comparison logic

## UT Wrapper Pattern

In `ut`, child RTL blocks are not connected through RTL transport. The wrapper is responsible for orchestrating that composition in Python.

Typical responsibilities:

- create shared software-side RAM or FIFO models
- start their background coroutines when needed
- route each top-level instruction to the correct child module
- pass the shared resource handles into child `execute()` calls

Example pattern:

```python
async def execute_unit_test(self, inst):
    await self.wait_for_completion()
    if inst["op"] == "add_one":
        await self.modules["add_one_cosim"].execute(inst=inst, ram=self.ram, fifo=self.fifo)
    elif inst["op"] == "sub_one":
        await self.modules["sub_one_cosim"].execute(inst=inst, fifo=self.fifo)
```

Notes:

- Waiting for completion before dispatching the next command serializes operation-level checking.
- Shared resources may be simple Python data structures or cocotb-aware models that drive child DUT ports.

## ST Wrapper Pattern

In `st`, child blocks are connected through RTL and the wrapper mainly routes top-level control.

Typical responsibilities:

- accept top-level instructions
- map them to the correct child module
- pass top-level signal handles into child `execute_system_test()` calls
- avoid software-side transport models that duplicate existing RTL connectivity

Example pattern:

```python
async def execute_system_test(self, inst):
    await self.wait_for_completion()
    if inst["op"] == "add_one":
        await self.modules["add_one_cosim"].execute(
            inst=inst,
            en_sig=self.dut.en_add,
            len_sig=self.dut.len_add,
            addr_sig=self.dut.addr_add,
        )
```

This matches the library's intended ST usage: drive top-level handles because child-instance ports may already be driven by RTL top wiring.

## Shared Software-Side Resources

Only create software-side transport resources in UT.

Common resource roles:

- emulate RAM for a child module
- emulate FIFO between child modules
- provide backdoor read/write access for bring-up or mismatch recovery

Keep resource ownership in the wrapper when multiple child environments share the resource. Pass resource handles into child `execute()` calls rather than storing wrapper state inside the child classes.

## Cross-Module Coordination

Wrappers may add extra coordination coroutines when module-local scoreboards are not enough.

Example from the repository:

- `backdoor_handler()` waits for an event from `add_one_cosim.scoreboard`
- it pulls an expected transaction from a queue
- it writes repaired data back into the shared FIFO model

Use this style only when the platform truly needs cross-module repair or synchronization. Keep it out of the child module if it depends on system-level knowledge.

## Completion And Reporting

Wrapper completion is delegated:

- `wait_for_completion()` iterates through all child modules and awaits each child completion
- `report()` calls each child report
- `teardown()` calls each child teardown
- `success` is the conjunction of all child successes

The wrapper does not track its own `executed_count`. Completion comes from child environments.

## Generation Checklist

Before finishing a wrapper, check:

- every child module is instantiated through `module_specs`
- wrapper `level` matches the intended execution flow
- no child `CoSimBase` uses `sw` mode when the wrapper level is `st`
- top-level instruction routing is explicit and deterministic
- UT wrappers own Python-side transport resources
- ST wrappers pass top-level signal handles into child calls
- cross-module helper coroutines belong to the wrapper, not the child
- child completion is awaited at the correct times for the intended concurrency model

## Packaging Note

This reference is intended to be self-contained inside the installed skill. Treat the examples described above as bundled patterns, not as pointers to external repository files.
