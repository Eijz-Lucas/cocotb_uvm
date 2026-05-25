# cocotb_uvm API Reference

## BaseTransaction (`transaction.py`)
Base dataclass for verification transactions.

```python
from dataclasses import dataclass, field
from cocotb_uvm import BaseTransaction

@dataclass
class MyTransaction(BaseTransaction):
    # User-defined payload fields go here
    id: int | None = field(default=None, kw_only=True)  # auto-assigned by monitor
```

## BaseModel (`components.py`)
Software reference model consuming input transactions, producing expected results.

```python
class BaseModel(ABC):
    def __init__(self, input_queue: Queue, expected_queue: Queue, name: str = "ReferenceModel",
                 *args, **kwargs):
        # name: logger name prefix
        # input_queue: receives transactions from input monitor
        # expected_queue: delivers computed expected transactions to scoreboard
        # *args, **kwargs: forwarded to self.run()
        # self._task is auto-started via cocotb.start_soon(self.run(...))

    @abstractmethod
    def compute(self, input_transaction: BaseTransaction, *args, **kwargs) -> BaseTransaction:
        # Override this. Convert one input transaction to one expected output.
        # Do NOT use await — this is synchronous computation.

    async def run(self, *args, **kwargs):
        # Already implemented: loops on input_queue, calls compute(), pushes to expected_queue.
        # Do NOT override unless you need custom queue handling.
```

## BaseDriver (`components.py`)
Drives DUT signals based on commands or transactions.

```python
class BaseDriver(ABC):
    def __init__(self, dut: HierarchyObject, name: str = "Driver", *args, **kwargs):
        # dut: cocotb handle to the DUT
        # name: logger name prefix
        # self.dut, self.log available

    @abstractmethod
    async def run(self, *args, **kwargs):
        # Override this. Execute one command/transaction by driving DUT signals.
        # Use await RisingEdge(self.dut.clk) for cycle-by-cycle control.
```

## BaseMonitor (`components.py`)
Samples DUT state, converts observations into transactions, publishes to a queue.

```python
class BaseMonitor(ABC):
    def __init__(self, dut: HierarchyObject, output_queue: Queue, name: str = "Monitor",
                 sample_delay: int = 10, sample_delay_unit: str = "ns", *args, **kwargs):
        # dut: cocotb handle to the DUT
        # output_queue: where completed transactions are put
        # sample_delay / sample_delay_unit: wait before each sample attempt
        # *args, **kwargs: forwarded to self.run()
        # self._next_id auto-increments for each transaction
        # self._task is auto-started via cocotb.start_soon(self.run(...))

    @abstractmethod
    async def sample(self, *args, **kwargs) -> Optional[BaseTransaction]:
        # Override this. Check DUT signals, return a transaction when one is
        # complete, or None if nothing is ready.

    async def run(self, *args, **kwargs):
        # Already implemented: loops with Timer(sample_delay) → sample() →
        # assign id → put to queue → RisingEdge(clk).
        # Do NOT override unless you need custom sampling timing.
```

## BaseScoreboard (`components.py`)
Compares actual vs expected transactions, tracks match/mismatch counts.

```python
class BaseScoreboard(ABC):
    def __init__(self, actual_queue: Queue, expected_queue: Queue, name: str = "Scoreboard",
                 *args, **kwargs):
        # actual_queue: receives transactions from output monitor
        # expected_queue: receives transactions from reference model
        # self.match_count, self.mismatch_count tracked
        # self._task is auto-started via cocotb.start_soon(self.run(...))

    def compare(self, actual: BaseTransaction, expected: BaseTransaction, *args, **kwargs) -> bool:
        # Default: actual_transaction == expected_transaction.
        # Override for custom comparison (float tolerance, field subsets, etc.)
        # Returns True on match, False on mismatch.
        # Increments self.match_count or self.mismatch_count.

    async def run(self, *args, **kwargs):
        # Already implemented: loops, gets from both queues, calls compare().
        # Do NOT override unless you need custom comparison flow.
```

## BaseSequence (`sequencing.py`)
Iterable stimulus source.

```python
class BaseSequence(ABC):
    def __init__(self, name: str = "Sequence", *args, **kwargs):
        self.name = name

    @abstractmethod
    def __next__(self) -> Any:
        # Return the next command/transaction.
        # Raise StopIteration when exhausted.
```

## BaseSequencer (`sequencing.py`)
Feeds items from sequences to an executor via an internal queue.

```python
class BaseSequencer(ABC):
    def __init__(self, name: str = "Sequencer", max_queue_size: int = 10, *args, **kwargs):
        self.name = name
        self.transaction_queue: Queue = Queue(max_queue_size)

    async def run(self, executor: SupportsExecute, *sequences: BaseSequence):
        # Main entry point. Consumes all sequences, dispatches each item to
        # executor.execute(item). The executor must have name and execute().

    async def _run_executor(self, executor: SupportsExecute): ...
    async def _enqueue_sequences(self, *sequences: BaseSequence): ...
    async def _enqueue_sequence_items(self, sequence: BaseSequence): ...
```

## CoSimBase (`cosim.py`)
Module-level environment owning one set of verification components.

```python
class CoSimBase(ABC):
    def __init__(self, dut: HierarchyObject,
                 reference_model_cls: type[BaseModel],
                 driver_cls: type[BaseDriver],
                 input_monitor_cls: type[BaseMonitor],
                 output_monitor_cls: type[BaseMonitor],
                 scoreboard_cls: type[BaseScoreboard],
                 mode: str = "hw", level: str = "ut", name: str = "CoSimBase",
                 *args, **kwargs):
        # Valid mode: "hw" or "sw"
        # Valid level: "ut" or "st"
        # Cannot combine level="st" with mode="sw" (raises RuntimeError)
        # Creates: self.input_queue, self.actual_queue, self.expected_queue
        # Instantiates: reference_model, driver, input_monitor, output_monitor, scoreboard
        # self.executed_count tracks number of execute() calls

    @abstractmethod
    async def execute_unit_test(self, *args, **kwargs): ...
    @abstractmethod
    async def execute_system_test(self, *args, **kwargs): ...

    async def execute(self, *args, **kwargs):
        # Dispatches to execute_unit_test or execute_system_test based on self.level.
        # In sw mode, auto-increments scoreboard.match_count.

    async def wait_for_completion(self):
        # Blocks until all executed ops are compared.

    def report(self): ...
    def teardown(self): ...  # cancels all component tasks
    @property
    def success(self) -> bool: ...
```

## CoSimWrapperBase (`cosim.py`)
Wrapper environment managing multiple CoSimBase or CoSimWrapperBase instances.

```python
class CoSimWrapperBase(ABC):
    def __init__(self, dut: HierarchyObject, module_specs: list[ModuleSpec],
                 level: str = "ut", name: str = "CoSimWrapperBase", *args, **kwargs):
        # module_specs: list of (name, class, config_dict) tuples
        #   e.g. [("add_one_cosim", add_one_cosim, {"dut": dut.u_add_one, "mode": "hw"})]
        # self.modules: dict[str, Any] — access by name
        # Validates: no sw-mode modules in st level

    @abstractmethod
    async def execute_unit_test(self, *args, **kwargs): ...
    @abstractmethod
    async def execute_system_test(self, *args, **kwargs): ...

    async def execute(self, *args, **kwargs): ...  # dispatches by level
    async def wait_for_completion(self): ...  # waits for all modules
    def report(self): ...  # reports for all modules
    def teardown(self): ...  # teardown all modules
    @property
    def success(self) -> bool: ...  # True if all modules passed
```

## SimLogger (`sim_logger.py`)
Singleton logging configuration helper.

```python
class SimLogger:
    def __init__(self, root_level: int = logging.DEBUG, cocotb_level: int = logging.DEBUG):
        # Singleton — repeated calls return the same instance.

    def configure_stream_handlers(self, *configs):
        # Apply int (level), Filter, or Formatter to non-file stream handlers.

    @staticmethod
    def add_file_handler(name: str, level: int = logging.DEBUG, mode: str = "w",
                         formatter=None, filters=None): ...
    @staticmethod
    def create_file_handler(name, level=logging.DEBUG, mode="w",
                            formatter=None, filters=None) -> logging.FileHandler: ...

    @staticmethod
    def create_filter(reverse: bool = False, *configs: dict) -> logging.Filter:
        # reverse=False: matching records are filtered OUT.
        # reverse=True: only matching records are kept.
        # Each config dict may have: "level", "name" (substring match), "message" (substring match).
```

## Utilities (`utils.py`)

```python
def always_sample_next(time: int = 10, unit: str = "ns") -> Callable:
    # Decorator for monitor coroutines. Waits Timer → samples → RisingEdge.
    # Returns a decorator that wraps the sampling function.

async def connect_check(signal_0, signal_1) -> None:
    # Continuously watches two signals. Asserts they remain equal.
    # Use: cocotb.start_soon(connect_check(dut.sig_a, dut.sig_b))
    # Cancel the returned task to stop checking.
```

## Public API (`__init__.py`)

```python
from cocotb_uvm import (
    BaseDriver, BaseModel, BaseMonitor, BaseScoreboard,
    BaseSequence, BaseSequencer, BaseTransaction,
    CoSimBase, CoSimWrapperBase, SimLogger,
    always_sample_next, connect_check,
)
```
