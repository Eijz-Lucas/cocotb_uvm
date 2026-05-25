---
name: cocotb-uvm-platform-builder
description: Build or modify layered verification environments with the cocotb_uvm library. Use when Codex needs to create a new module-level CoSim environment, add or refactor transactions/models/drivers/monitors/scoreboards, compose a top-level CoSimWrapper environment from existing modules, or extend an existing cocotb_uvm-based testbench from user requirements, DUT interfaces, or example code.
---

# Cocotb Uvm Platform Builder

## Overview

Use this skill to map a user request onto the cocotb_uvm architecture and generate code in layers. Prefer open-ended adaptation to the DUT and repository layout, but keep the framework structure explicit so generated environments remain consistent with the library.

Generate only testbench-side code. Do not generate or modify RTL unless the user explicitly asks for RTL outside the scope of this skill.

## Workflow Decision

Start by classifying the request:

- Build a new module environment: read `references/module-cosim-pattern.md`
- Build or extend a top-level wrapper: read `references/wrapper-pattern.md`
- Modify or fill in specific layers: read `references/component-patterns.md`
- Align with the current repository example: read `references/example-cosim-test.md`
- Check base-class responsibilities before coding: read `references/api-map.md`

If the user asks for a full platform, implement in this order unless the repository already provides some layers:

1. Define transactions and data flow boundaries.
2. Implement module-level CoSim environments.
3. Implement or adapt sequences and test entrypoints.
4. Compose the top-level CoSimWrapper.
5. Add completion waits, reporting, and teardown.

## Operating Rules

- Preserve the cocotb_uvm layering. Do not collapse model, driver, monitor, scoreboard, and environment logic into one file unless the repository already does so.
- Treat `level` and `mode` as construction-time environment properties. Set them when instantiating `CoSimBase` or `CoSimWrapperBase`, then implement behavior around those fixed values.
- Interpret `ut` as unit-test composition. A module-level `CoSimBase` instance represents one unit under test. A `CoSimWrapperBase` may compose multiple unit-level environments, with data movement between them implemented in cocotb or Python rather than by RTL interconnect.
- Interpret `st` as system-test composition. Use it when multiple RTL submodules are connected through RTL. In this mode, route stimulus through the wrapper and pass top-level RTL signal handles down into child module `execute_system_test()` calls instead of trying to force child-instance inputs directly.
- Interpret `hw` as hardware execution. In this mode, drive the RTL module through the driver and use the standard monitor and scoreboard flow.
- Interpret `sw` as software execution. In this mode, `CoSimBase` still requires a `dut`, and still instantiates driver and monitor objects because of the base-class construction flow, but the `sw` execution path may bypass driver activity and hardware observation by computing results from software-side models or data structures. Only use `sw` when `level == "ut"`.
- Let the user prompt decide whether to build a module-level `CoSimBase` or a wrapper-level `CoSimWrapperBase`, but assume wrapper construction usually depends on one or more module environments.
- Generate complete code for the requested layer, but do not invent unnecessary infrastructure that the current DUT does not need.
- Keep generation scope on testbench code: transactions, models, drivers, monitors, scoreboards, cosim classes, wrappers, sequences, tests, logging, and software-side helper models. Do not generate RTL modules, RTL interconnect, or synthesizable logic in this skill.
- Follow the repository's local naming and layout when extending an existing project. When starting from scratch, keep names readable and close to the DUT function.
- Use `execute_unit_test()` and `execute_system_test()` to separate UT and ST behavior instead of mixing both in one branch-heavy function.
- In UT flows, a wrapper `execute_unit_test()` may call child module `execute()` methods and supply Python-side shared resources such as RAM or FIFO models.
- In ST flows, a wrapper `execute_system_test()` should accept or derive top-level signal handles and pass them into child module `execute_system_test()` calls.
- Keep `hw` and `sw` mode behavior explicit. Only use `sw` mode for module environments in UT flows.
- Make transaction boundaries concrete. A monitor should emit complete logical transactions, not raw per-cycle fragments, unless the protocol genuinely requires stream fragments.

## Output Strategy

Generate code in layers. When the request is broad, present or implement the layers in this order:

1. Transaction classes and their equality or copy semantics.
2. Reference model behavior.
3. Driver behavior.
4. Input and output monitors.
5. Scoreboard behavior.
6. Module-level `CoSimBase`.
7. Wrapper-level `CoSimWrapperBase`.
8. Sequence, sequencer, and cocotb test entrypoint.

When some layers are already present, fill only the missing or broken layers and keep interfaces compatible.

## Checks Before Finishing

- Confirm each queue connection is consistent with the intended data flow.
- Confirm `wait_for_completion()` can terminate because scoreboard `match_count + mismatch_count` will eventually catch up to `executed_count`.
- Confirm wrapper routing matches the operation fields carried by the top-level instruction or transaction.
- Confirm UT/ST and HW/SW combinations are valid for the generated environment.
- Confirm teardown cancels background tasks created by the environment.

## References

- `references/api-map.md`
- `references/component-patterns.md`
- `references/module-cosim-pattern.md`
- `references/wrapper-pattern.md`
- `references/example-cosim-test.md`
- `references/generation-strategy.md`
