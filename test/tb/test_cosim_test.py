import cocotb
import logging
import json
import os
import random

from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_uvm import BaseSequence, BaseSequencer, SimLogger, connect_check

from .add_one_cosim import add_one_cosim
from .cosim_test_wrapper import cosim_test_wrapper
from .sub_one_cosim import sub_one_cosim
from .sys_ctrl import sys_ctrl

if "ST" in os.environ:
    level = "st" if os.environ["ST"] == "1" else "ut"
else:
    level = "ut"

log = logging.getLogger("cocotb")

if level == "st":
    log.info("Running in ST mode")
else:
    log.info("Running in UT mode")

firmware = [
    {"op": "add_one", "addr": 0, "len": 5},
    {"op": "sub_one", "len": 3},
    {"op": "sub_one", "len": 2},
    {"op": "add_one", "addr": 0, "len": 5},
    {"op": "sub_one", "len": 3},
    {"op": "sub_one", "len": 2}
]

simlogger = SimLogger()
stream_filter = SimLogger.create_filter(True,
                                        {'level': logging.INFO, 'message': 'REPORT'},
                                        {'name': 'regression'},
                                        {'level': logging.WARNING})
simlogger.configure_stream_handlers(stream_filter)
sequence_filter = SimLogger.create_filter(False, {'name': 'Sequencer'})
SimLogger.add_file_handler("sim.log", filters=[sequence_filter])


class cosim_test_sequence(BaseSequence):
    def __init__(self, name="cosim_test_sequence", max_count=16, write_file=True, read_file=False, file_name='test_data.jsonl'):
        super().__init__(name)
        self.fifo_depth = 8
        self.fifo_items_num = 0
        self.max_count = max_count
        self.count = 0
        self.write_file: bool = write_file
        self.read_file: bool = read_file
        self.file_name = file_name

        if self.read_file:
            if not os.path.exists(self.file_name):
                raise FileNotFoundError(f"can't find file {self.file_name}")
            self.instruction_stream = self._stream_reader()
            cocotb.log.info(f"[{name}] read file {self.file_name}")

    def _stream_reader(self):
        with open(self.file_name, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def __next__(self):
        if self.read_file:
            try:
                inst = next(self.instruction_stream)
                self.count += 1
                return inst
            except StopIteration:
                raise StopIteration
        else:
            if self.count >= self.max_count:
                raise StopIteration
            self.count += 1
            if self.fifo_items_num == 0:
                op = "add_one"
            elif self.fifo_items_num == self.fifo_depth:
                op = "sub_one"
            else:
                op = random.choice(["add_one", "sub_one"])
            if op == "add_one":
                addr = random.randint(0, 7)
                max_len = min(8-addr, self.fifo_depth-self.fifo_items_num-1)
                max_len = 1 if max_len <= 1 else max_len
                length = random.randint(1, max_len)
                self.fifo_items_num += length
                inst = {'op': op, 'addr': addr, 'len': length}
            elif op == "sub_one":
                max_len = self.fifo_items_num
                length = random.randint(1, max_len)
                self.fifo_items_num -= length
                inst = {'op': op, 'len': length}
            if self.write_file:
                with open(self.file_name, 'a', encoding='utf-8') as file:
                    file.write(json.dumps(inst, ensure_ascii=False) + '\n')
            return inst


class cosim_test_sequencer(BaseSequencer):
    def __init__(self, max_size=10, *args, **kwargs):
        super().__init__(max_queue_size=max_size, *args, **kwargs)


@cocotb.test()
async def test(dut):
    # random seed
    random.seed(0xdeadbeef)

    # signal init
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 1
    await Timer(20, unit="ns")
    await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    if level == "st":
        # backdoor write success
        dut.u_single_port_ram.mem[0].value = 10
        dut.u_single_port_ram.mem[1].value = 20
        dut.u_single_port_ram.mem[2].value = 30
        dut.u_single_port_ram.mem[3].value = 40
        dut.u_single_port_ram.mem[4].value = 50
        cocotb.log.info(f"Initial RAM[0]: {dut.u_single_port_ram.mem[0].value}")
        await RisingEdge(dut.clk)
        cocotb.log.info(f"After one cycle RAM[0]: {dut.u_single_port_ram.mem[0].value}")

    # class init
    if level == "ut":
        cosim_test_wrapper_modules = [
            ("add_one_cosim", add_one_cosim, {
             "dut": dut.u_add_one, "mode": "hw", "level": "ut"}),
            ("sub_one_cosim", sub_one_cosim,  {
             "dut": dut.u_sub_one, "mode": "hw", "level": "ut"})
        ]
    else:
        cosim_test_wrapper_modules = [
            ("add_one_cosim", add_one_cosim, {
             "dut": dut.u_add_one, "mode": "hw", "level": "st"}),
            ("sub_one_cosim", sub_one_cosim, {
             "dut": dut.u_sub_one, "mode": "hw", "level": "st"})
        ]
    cosim_test_wrapper_instance = cosim_test_wrapper(
        dut, cosim_test_wrapper_modules, level=level)
    # firmware_iterator = iter(firmware)
    cosim_test_sequencer_instance = cosim_test_sequencer()

    # connect check
    # if level == "st":
    #     connect_check_task = cocotb.start_soon(connect_check(dut.fifo_write_data_add,
    #                                                          dut.u_sy_fifo.fifo_write_data))
    if level == "st":
        connect_check_task = cocotb.start_soon(connect_check(
            dut.fifo_read_data_sub, dut.u_sy_fifo.fifo_read_data))

    # sim
    await cosim_test_sequencer_instance.run(cosim_test_wrapper_instance, cosim_test_sequence(write_file=False, read_file=False))
    await cosim_test_wrapper_instance.wait_for_completion()

    # report
    cosim_test_wrapper_instance.report()
    assert cosim_test_wrapper_instance.success

    # teardown
    cosim_test_wrapper_instance.teardown()
    if level == "st":
        connect_check_task.cancel()
