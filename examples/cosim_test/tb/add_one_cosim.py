from dataclasses import dataclass

import numpy as np
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge, Event
from cocotb_uvm import BaseDriver, BaseModel, BaseMonitor, BaseScoreboard, BaseTransaction, CoSimBase
from einops import rearrange


@dataclass
class add_one_input_trans(BaseTransaction):
    addr: int
    len: int
    ram_rdata: np.ndarray

    def clear(self):
        self.addr = 0
        self.len = 0
        self.ram_rdata = np.array([])

    @classmethod
    def empty(cls):
        return cls(addr=0, len=0, ram_rdata=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, add_one_input_trans):
            return False
        if self.addr != other.addr or self.len != other.len:
            return False
        return np.array_equal(self.ram_rdata, other.ram_rdata)

    def copy(self):
        return add_one_input_trans(addr=self.addr, len=self.len, ram_rdata=np.copy(self.ram_rdata))


@dataclass
class add_one_output_trans(BaseTransaction):
    ram_addr: list
    fifo_write_data: np.ndarray

    def clear(self):
        self.ram_addr = []
        self.fifo_write_data = np.array([])

    @classmethod
    def empty(cls):
        return cls(ram_addr=[], fifo_write_data=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, add_one_output_trans):
            return False
        if self.ram_addr != other.ram_addr:
            return False
        return np.array_equal(self.fifo_write_data, other.fifo_write_data)

    def copy(self):
        return add_one_output_trans(ram_addr=self.ram_addr.copy(), fifo_write_data=np.copy(self.fifo_write_data))


class add_one_model(BaseModel):
    def __init__(self, in_queue, exp_queue, name="add_one_sw_model"):
        super().__init__(in_queue, exp_queue, name)

    def compute(self, input_trans: add_one_input_trans) -> add_one_output_trans:
        exp_ram_addr = []
        for i in range(input_trans.len):
            exp_ram_addr.append(input_trans.addr + i)
        exp_fifo_write_data = input_trans.ram_rdata + 1
        exp_trans = add_one_output_trans(
            ram_addr=exp_ram_addr, fifo_write_data=exp_fifo_write_data)
        return exp_trans


class add_one_driver(BaseDriver):
    def __init__(self, dut, name="add_one_driver"):
        super().__init__(dut, name)

    async def run(self, inst, level="ut", en_sig=None, len_sig=None, addr_sig=None):
        self.log.debug(f"[Driver] inst={inst}")
        if level == "ut":
            en = self.dut.en
            len = self.dut.len
            addr = self.dut.addr
        elif level == "st":
            en = en_sig
            len = len_sig
            addr = addr_sig
        if inst["op"] == "add_one":
            en.value = 1
            len.value = inst["len"]
            addr.value = inst["addr"]
            await RisingEdge(self.dut.clk)
            en.value = 0
            len.value = 0
            addr.value = 0


class add_one_output_monitor(BaseMonitor):
    def __init__(self, dut, act_queue, name="add_one_output_monitor"):
        super().__init__(dut, act_queue, name)
        self.output_trans = add_one_output_trans.empty()

    async def sample(self):
        if self.dut.busy.value == 1:
            self.output_trans.ram_addr.append(int(self.dut.ram_addr.value))
        if self.dut.fifo_write_en.value == 1:
            data = self.dut.fifo_write_data.value.to_signed()
            self.output_trans.fifo_write_data = np.append(
                self.output_trans.fifo_write_data, data)
        elif len(self.output_trans.fifo_write_data) > 0:
            self.output_trans.ram_addr.pop()
            copy = self.output_trans.copy()
            self.output_trans.clear()
            return copy
        else:
            return None


class add_one_input_monitor(BaseMonitor):
    def __init__(self, dut, in_queue, name="add_one_input_monitor"):
        super().__init__(dut, in_queue, name)
        self.input_trans = add_one_input_trans.empty()

    async def sample(self):
        if self.dut.en.value == 1:
            self.input_trans.addr = int(self.dut.addr.value)
            self.input_trans.len = int(self.dut.len.value)
        if self.dut.busy.value == 1:
            self.input_trans.ram_rdata = np.append(
                self.input_trans.ram_rdata, int(self.dut.ram_rdata.value))
        elif len(self.input_trans.ram_rdata) > 0:
            self.input_trans.ram_rdata = np.delete(self.input_trans.ram_rdata, -1)
            copy = self.input_trans.copy()
            self.input_trans.clear()
            return copy
        else:
            return None


class add_one_scoreboard(BaseScoreboard):
    def __init__(self, act_queue, exp_queue, name="add_one_scoreboard"):
        super().__init__(act_queue, exp_queue, name)
        self.error = Event()
        self.backdoor_queue = Queue()

    async def run(self):
        while True:
            actual_trans = await self.actual_queue.get()
            expected_trans = await self.expected_queue.get()

            self.log.debug(
                f"[Compare] Actual ram_addr: {actual_trans.ram_addr}, len={len(actual_trans.ram_addr)}")
            self.log.debug(
                f"[Compare] Expected ram_addr: {expected_trans.ram_addr}, len={len(expected_trans.ram_addr)}")
            self.log.debug(f"[Compare] Actual fifo_data: {actual_trans.fifo_write_data}")
            self.log.debug(f"[Compare] Expected fifo_data: {expected_trans.fifo_write_data}")

            if actual_trans == expected_trans:
                self.match_count += 1
                self.log.debug(f"[Result] MATCH! match_count={self.match_count}")
            else:
                self.mismatch_count += 1
                self.error.set()
                self.backdoor_queue.put_nowait(expected_trans)
                self.log.error(f"[Result] MISMATCH! mismatch_count={self.mismatch_count}")
                if actual_trans.ram_addr != expected_trans.ram_addr:
                    self.log.error(
                        f"  -> ram_addr mismatch: actual={actual_trans.ram_addr}, expected={expected_trans.ram_addr}")
                if not np.array_equal(actual_trans.fifo_write_data, expected_trans.fifo_write_data):
                    self.log.error(f"  -> fifo_data mismatch")


class add_one_cosim(CoSimBase):
    def __init__(self, dut, name="add_one_cosim", mode="hw", level="ut"):
        super().__init__(dut, add_one_model, add_one_driver, add_one_input_monitor,
                         add_one_output_monitor, add_one_scoreboard, mode, level, name)

    async def execute_system_test(self, inst, en_sig, len_sig, addr_sig):
        await self.wait_idle()
        await self.driver.run(inst, level="st", en_sig=en_sig, len_sig=len_sig, addr_sig=addr_sig)

    async def execute_unit_test(self, inst, ram, fifo):
        if self.mode == "hw":
            await self.wait_idle()
            await self.driver.run(inst, level="ut")
        elif self.mode == "sw":
            in_trans = self.get_in_trans(inst, ram)
            out_trans = self.reference_model.compute(in_trans)
            fifo.push(rearrange(out_trans.fifo_write_data, "x -> x 1"))
            self.log.debug(
                f"[SW Execute] Pushed out_trans.fifo_write_data={out_trans.fifo_write_data} to fifo")

    def get_in_trans(self, inst, ram):
        if inst["op"] == "add_one":
            addr = inst["addr"]
            length = inst["len"]
            ram_rdata = ram.read(0, addr, length).flatten()
            input_trans = add_one_input_trans(addr=addr, len=length, ram_rdata=ram_rdata)
            return input_trans

    async def wait_idle(self):
        while True:
            await RisingEdge(self.dut.clk)
            if (self.dut.busy.value == 0):
                break
