# Generation Strategy

## Purpose

Define how Codex should decide what to generate first and how much to generate from a user request.

## Core Rule

Choose the first generation layer from the user's real request, not from a fixed template.

However, if the request is broad or underspecified, fall back to this dependency order:

1. transaction boundary
2. module-level `CoSimBase`
3. wrapper-level `CoSimWrapperBase`
4. sequence and test entrypoint

In this framework, wrapper code depends on module environments, and most module environments depend on stable transaction definitions. Start from the lowest missing layer that determines the interfaces of the higher layers.

## Prompt Classification

Classify the user request into one of these buckets before generating code.

### Bucket A: New Module-Level CoSim

Typical prompts:

- "为某个 rtl 模块搭一个 cocotb_uvm 验证环境"
- "给这个模块写 cosim"
- "实现 driver/monitor/scoreboard 来验证单个模块"

Start from:

1. transaction classes
2. model
3. driver and monitors
4. scoreboard
5. module `CoSimBase`

Use this bucket even if the user asks only for "a cosim", unless they explicitly describe multi-module composition.

### Bucket B: New Top-Level Wrapper

Typical prompts:

- "把这几个模块拼成一个验证平台"
- "写一个 cosim_wrapper"
- "做 system-level 验证"

Start from:

1. confirm the child module environments already exist
2. if they do not exist, generate those first
3. define top-level instruction schema and routing
4. implement the wrapper
5. add shared UT resources or ST top-level signal routing
6. add sequence and test entrypoint changes if needed

Never start from the wrapper if the child module interfaces are still undefined.

### Bucket C: Fill One Existing Layer

Typical prompts:

- "补一个 scoreboard"
- "monitor 采样有问题"
- "把这个 driver 改成 st 模式"
- "补 transaction"
- "`wait_for_completion()` 卡住了"
- "scoreboard 一直不结束"

Start from the requested layer, but only if lower-level interfaces are already stable.

If they are not stable:

- repair the lower layer first
- then update the requested layer

Example:

- if the user asks for a scoreboard but the monitor boundary is still wrong, fix the monitor boundary first
- if `wait_for_completion()` does not return, inspect transaction flush conditions, monitor completion boundaries, and scoreboard count progression before changing scoreboard comparison logic

### Bucket D: Full Platform From A Broad Requirement

Typical prompts:

- "根据这个模块/接口搭一套验证平台"
- "做完整 cocotb_uvm 环境"
- "先做 ut，后面再支持 st"

Start from:

1. top-level instruction or transaction concept
2. child module transaction definitions
3. child module environments
4. wrapper
5. sequence and test entrypoint

For broad requests, generate in dependency order, not in file order.

## Start Layer Decision Table

Use this table when the user prompt is short or ambiguous.

- If the prompt names one RTL block and asks to "验证" or "搭 cosim": start from module transactions.
- If the prompt names several RTL blocks and asks to "搭平台" or "写 wrapper": start from wrapper only after confirming child modules exist.
- If the prompt mentions `ut`: prefer module-level generation first, then Python-side composition if multiple modules are involved.
- If the prompt mentions `st`: prefer wrapper routing and top-level signal-handle flow, but still ensure child module `execute_system_test()` exists.
- If the prompt mentions `sw`: start from module transactions and model path, because software execution depends on a clean model and software-side resource interface.
- If the prompt mentions `driver`, `monitor`, or `scoreboard` explicitly: start there only when transaction boundaries are already clear.

## Generation Order By Scenario

### Scenario 1: The User Provides Only A DUT Interface

Generate in this order:

1. infer the logical operation boundary from the interface
2. define input and output transactions
3. write a reference model skeleton if behavior is described
4. write monitors around that transaction boundary
5. write the driver
6. write the scoreboard
7. wrap everything in `CoSimBase`

Reason:

- without transaction boundaries, every higher layer is unstable

### Scenario 2: The User Provides Behavior But Not Full Signals

Generate:

1. transaction definitions
2. model
3. partial environment skeleton with TODO-style assumptions encoded as placeholders in code only when necessary

Do not invent arbitrary signal names if the repository already implies a naming scheme. Prefer reading local RTL or existing code first.

### Scenario 3: The Repository Already Has Partial Module Environments

Generate:

1. read existing transaction classes and `execute_*()` signatures
2. keep those interfaces stable
3. fill the missing pieces only

Examples:

- if driver and monitors exist but scoreboard is missing, add the scoreboard only
- if module cosims exist but wrapper is missing, start from wrapper routing and shared resources

### Scenario 4: The User Wants UT First

Generate:

1. module transactions
2. module UT execution path
3. wrapper UT composition if multiple modules are involved
4. software-side RAM/FIFO or similar shared resources when needed
5. sequence and test

Delay ST-specific top-level signal handle flow until the user asks for it or the repository already mixes both paths.

### Scenario 5: The User Wants ST First

Generate:

1. module transaction and monitor boundaries
2. module `execute_system_test()` and driver ST path
3. wrapper `execute_system_test()` with top-level signal handles
4. connectivity checks and test entrypoint

Do not create Python-side transport models unless the request also requires UT.

### Scenario 6: The User Reports A Completion Hang

Typical symptoms:

- `wait_for_completion()` never returns
- `executed_count` increases but scoreboard totals do not catch up
- the user blames the scoreboard but cannot show a real mismatch yet

Generate or debug in this order:

1. inspect the transaction boundary
2. inspect monitor flush and end-of-operation conditions
3. inspect whether the reference-model queue and actual queue produce one decision per execute
4. inspect scoreboard logging only after the previous three layers are coherent

Do not start by rewriting the scoreboard unless the monitor and transaction boundary are already proven correct.

## How To Infer Missing Layers

Before writing code, inspect the repository for:

- transaction classes already defined
- child `CoSimBase` classes already defined
- existing `module_specs` or wrapper routing
- sequence or test entrypoints already present

Then apply these rules:

- if transactions exist and match the DUT behavior, reuse them
- if module cosims exist, do not redesign their public interface just to simplify the wrapper
- if wrapper routing exists, preserve the top-level instruction schema unless the user asks to change it
- if tests already instantiate environments with specific `mode` and `level`, keep those constructor conventions stable

## Broad Vs Narrow Output

Match the amount of code to the prompt.

### Narrow Prompts

For narrow prompts such as "补 monitor" or "加 st 支持":

- implement only the requested layer and the minimum required supporting edits
- avoid rewriting unrelated layers

### Broad Prompts

For broad prompts such as "搭完整平台":

- generate all dependent layers needed for a runnable path
- prefer a complete thin stack over a deep but incomplete partial implementation

## Open-Ended But Constrained

This skill should stay adaptable to different DUTs, but the following conventions should remain stable:

- preserve cocotb_uvm layering
- keep `ut/st` separated through `execute_unit_test()` and `execute_system_test()`
- keep `hw/sw` explicit
- keep one executed logical operation aligned with one scoreboard decision
- keep wrapper responsibilities above child-module responsibilities
- generate testbench code only, not RTL

Adapt everything else:

- transaction field names
- instruction schema
- helper methods
- software-side resource types
- routing logic

## When Information Is Incomplete

Prefer discovering missing context from the repository before asking the user.

Reasonable assumptions:

- reuse repository naming patterns
- follow existing DUT instance naming
- preserve current instruction dictionary structure if one exists
- in `sw`, assume the environment still needs `dut` and base-constructed driver/monitor objects unless the library code changes

Ask the user only when the missing information changes architecture-level decisions, such as:

- whether the target flow is module-only or multi-module
- whether the target is UT or ST
- whether a `sw` path is required
- what one logical operation should mean for scoring

If architecture is clear but signals are partially missing, implement the stable layers first and leave the signal-level layer for after repository inspection.

## Immediate Implementation Vs Proposal

Implement immediately when:

- the repository already provides enough structure to infer the next layer
- the user asked for code, not brainstorming
- the missing details do not affect the architecture

Propose or clarify first when:

- the user request would change the transaction boundary in multiple possible ways
- the user has not indicated whether the work is UT or ST and both would lead to different wrappers or execution paths
- the repository does not reveal enough about the DUT interface to generate valid driver or monitor code

## Final Sanity Check

Before finalizing a generated solution, verify that the chosen starting layer was correct:

- if the wrapper required child API changes, the start layer was too high
- if the scoreboard required monitor redesign, the start layer was too high
- if the driver required redefining transactions, the start layer was too high

When that happens, step back to the lower layer and regenerate upward.

## Inputs To Consider

- User prompt
- Existing repository layout
- DUT signal structure
- Existing examples and partial environments
