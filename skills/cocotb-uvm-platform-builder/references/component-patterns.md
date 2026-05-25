# Component Patterns

## Purpose

Capture reusable implementation guidance for transactions, models, drivers, monitors, and scoreboards.

## Transaction Boundary Selection

Choose transaction boundaries from the logical operation the DUT performs, not from the clocking details.

A good transaction boundary usually answers:

- what input condition starts one operation
- what sampled state belongs to that operation
- what output observations mean the operation is complete
- what should count as one scoreboard comparison

For this library, prefer one executed instruction mapping to one input transaction and one output transaction. That keeps `executed_count` aligned with scoreboard accounting.

## Transaction Implementation Pattern

Use dataclasses derived from `BaseTransaction`.

Typical transaction fields:

- command fields such as address, length, opcode, mode
- sampled payload arrays
- lists of addresses or indices touched by the operation
- optional metadata needed for checking

Useful helper methods:

- `empty()`
  - create a fresh neutral transaction for monitor accumulation
- `clear()`
  - reset the cached monitor-owned transaction in place
- `copy()`
  - detach the emitted transaction from future monitor mutation
- custom `__eq__()`
  - compare numpy arrays with `np.array_equal()`
  - compare list fields explicitly

Do not rely on default dataclass equality when payloads include numpy arrays.

## Model Pattern

The model should convert one complete input transaction into one complete expected output transaction.

Good practice:

- treat `compute()` as pure functional logic when possible
- encode the expected behavior at the same abstraction level as the transactions
- avoid embedding driver timing or monitor sampling assumptions into the model

For example:

- `add_one_model` turns `addr`, `len`, and `ram_rdata` into expected `ram_addr` and incremented `fifo_write_data`
- `sub_one_model` turns `len` and `fifo_read_data` into decremented `fifo_write_data`

If software execution needs stateful side effects, keep the side effect in the module environment and keep `compute()` focused on expected-value generation.

## Driver Pattern

Treat the driver as the only layer that should know exact control pulse timing.

Good driver behavior:

- accept one logical instruction
- select the correct signal handles for UT or ST
- drive enable, address, length, or similar controls
- wait the required clock edges
- restore controls to inactive values

Keep the wrapper free of signal timing details. The wrapper should route operations, not bit-bang protocols.

## Monitor Pattern

Monitors should aggregate cycle-level observations into complete logical transactions.

Recommended monitor state machine:

1. keep a mutable cached transaction on `self`
2. detect the start of an operation and record setup fields
3. append sampled values while the operation is active
4. detect the end of the operation
5. copy the cached transaction, clear the cache, and return the copy

This is why helper methods on transaction classes are useful: monitors often need mutable accumulation followed by immutable emission.

Typical end-of-transaction patterns from the example:

- the DUT deasserts a write-enable after one or more data beats
- the DUT deasserts `busy` after consuming input payload
- a previously non-empty sampled array stops growing

If the last sampled cycle contains a stale or extra value, remove or adjust it before emitting the transaction. The `add_one` example does this with `pop()` and `np.delete()` during flush.

## Scoreboard Pattern

Use the default `BaseScoreboard` behavior when:

- one actual transaction should equal one expected transaction
- normal `==` or custom transaction `__eq__()` is enough
- simple match and mismatch counts are sufficient

Use a custom scoreboard when:

- mismatch logs need more detail
- the wrapper must react to a mismatch
- recovery requires sending extra data to another coroutine
- comparison requires domain-specific logic beyond transaction equality

The `add_one` example shows a useful escalation pattern:

- compare actual and expected
- log field-level differences
- raise an event on failure
- publish expected data through a side queue for wrapper-level repair

## Common Failure Modes

### Off-By-One Sampling

Symptoms:

- monitors capture one extra beat
- the first or last item in an array is wrong
- expected and actual lengths differ by one

Responses:

- change monitor flush condition
- adjust when sampling occurs relative to `busy` or valid signals
- use `always_sample_next()` if simulator visibility is shifted by a cycle

### Incomplete Flush

Symptoms:

- `wait_for_completion()` never returns
- scoreboard counts never catch up to `executed_count`

Cause:

- a monitor cached data but never returned a completed transaction

Response:

- define an explicit end condition for each monitor-owned transaction

### Queue Mismatch

Symptoms:

- scoreboard compares unrelated operations
- transactions match structurally but belong to different commands

Cause:

- the input monitor and output monitor chose incompatible transaction boundaries

Response:

- ensure one input transaction and one output transaction represent the same logical operation

### Shared Mutable State Leakage

Symptoms:

- previously emitted transactions change later
- scoreboard sees unexpected final values

Cause:

- monitor returned the live cached object instead of a detached copy

Response:

- always return a copied transaction when the monitor cache will be reused

## Generation Heuristics

When asked to create only part of a platform:

- start with transactions if no stable data boundary exists yet
- start with monitors if the user already knows the signal protocol but not the transaction shape
- start with the model if the algorithm is known and the checking contract is clear
- start with the scoreboard only when comparison needs are more complex than default equality

If uncertain, derive transactions first. In this framework, almost every other layer depends on them.

## Packaging Note

This reference is intended to be self-contained inside the installed skill. Treat the examples described above as bundled patterns, not as pointers to external repository files.
