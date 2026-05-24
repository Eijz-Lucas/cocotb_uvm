import cocotb
import numpy as np
from dataclasses import dataclass
from cocotb.triggers import RisingEdge, ValueChange, Event, ReadOnly, Timer
from cocotb.clock import Clock
from cocotb.utils import get_sim_time
from cocotb.handle import Immediate
from cocotb_uvm import BaseDriver, BaseModel, BaseMonitor, BaseScoreboard, BaseTransaction, CoSimBase


@dataclass
class sub_one_input_trans(BaseTransaction):
    len: int
    fifo_read_data: np.array

    def clear(self):
        self.len = 0
        self.fifo_read_data = np.array([])

    @classmethod
    def empty(cls):
        return cls(len=0, fifo_read_data=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, sub_one_input_trans):
            return False
        if self.len != other.len:
            return False
        return np.array_equal(self.fifo_read_data, other.fifo_read_data)

    def copy(self):
        return sub_one_input_trans(len=self.len, fifo_read_data=np.copy(self.fifo_read_data))


@dataclass
class sub_one_output_trans(BaseTransaction):
    fifo_write_data: np.array

    def clear(self):
        self.fifo_write_data = np.array([])

    @classmethod
    def empty(cls):
        return cls(fifo_write_data=np.array([]))

    def __eq__(self, other):
        if not isinstance(other, sub_one_output_trans):
            return False
        return np.array_equal(self.fifo_write_data, other.fifo_write_data)

    def copy(self):
        return sub_one_output_trans(fifo_write_data=np.copy(self.fifo_write_data))


class sub_one_model(BaseModel):
    def __init__(self, in_queue, exp_queue, name="sub_one_sw_model"):
        super().__init__(in_queue, exp_queue, name)

    def compute(self, input_trans: sub_one_input_trans) -> sub_one_output_trans:
        exp_fifo_write_data = input_trans.fifo_read_data-1
        exp_trans = sub_one_output_trans(fifo_write_data=exp_fifo_write_data)
        return exp_trans


class sub_one_driver(BaseDriver):
    def __init__(self, dut, name="sub_one_driver"):
        super().__init__(dut, name)

    async def run(self, inst, level="ut", en_sig=None, len_sig=None):
        self.log.debug(f"[Driver] inst={inst}")
        if level == "ut":
            en = self.dut.en
            len = self.dut.len
        elif level == "st":
            en = en_sig
            len = len_sig
        if inst["op"] == "sub_one":
            await RisingEdge(self.dut.clk)
            en.value = 1
            len.value = inst["len"]
            await RisingEdge(self.dut.clk)
            en.value = 0
            len.value = 0


class sub_one_output_monitor(BaseMonitor):
    def __init__(self, dut, act_queue, name="sub_one_output_monitor"):
        super().__init__(dut, act_queue, name)
        self.output_trans = sub_one_output_trans.empty()

    async def sample(self, *args, **kwargs):
        if self.dut.fifo_write_en.value == 1:
            data = self.dut.fifo_write_data.value.to_signed()
            self.output_trans.fifo_write_data = np.append(
                self.output_trans.fifo_write_data, data)
        else:
            if len(self.output_trans.fifo_write_data) > 0:
                copy = self.output_trans.copy()
                self.log.debug(
                    f"[Output Monitor PUT] fifo_write_data={self.output_trans.fifo_write_data}")
                self.output_trans.clear()
                return copy


class sub_one_input_monitor(BaseMonitor):
    def __init__(self, dut, in_queue, name="sub_one_input_monitor"):
        super().__init__(dut, in_queue, name)
        self.input_trans = sub_one_input_trans.empty()

    async def sample(self, *args, **kwargs):
        if self.dut.en.value == 1:
            self.input_trans.len = int(self.dut.len.value)
        if self.dut.fifo_read_en.value == 1:
            self.input_trans.fifo_read_data = np.append(
                self.input_trans.fifo_read_data, int(self.dut.fifo_read_data.value))
        else:
            if len(self.input_trans.fifo_read_data) > 0:
                copy = self.input_trans.copy()
                self.log.debug(
                    f"[Input Monitor PUT] len={self.input_trans.len}, ram_rdata={self.input_trans.fifo_read_data}")
                self.input_trans.clear()
                return copy


class sub_one_scoreboard(BaseScoreboard):
    def __init__(self, act_queue, exp_queue, name="sub_one_scoreboard"):
        super().__init__(act_queue, exp_queue, name)


class sub_one_cosim(CoSimBase):
    def __init__(self, dut, name="sub_one_cosim", mode="hw", level="ut"):
        super().__init__(dut, sub_one_model, sub_one_driver, sub_one_input_monitor,
                         sub_one_output_monitor, sub_one_scoreboard, mode, level, name)

    async def execute_unit_test(self, inst, fifo):
        if self.mode == "hw":
            await self.wait_idle()
            await self.driver.run(inst, level="ut")
        elif self.mode == "sw":
            in_trans = self.get_in_trans(inst, fifo)
            out_trans = self.reference_model.compute(in_trans)
            fifo.push(out_trans.fifo_write_data)
            self.log.debug(
                f"[SW Execute] Pushed out_trans.fifo_write_data={out_trans.fifo_write_data} to fifo")

    async def execute_system_test(self, inst, en_sig, len_sig):
        await self.driver.run(inst, level="st", en_sig=en_sig, len_sig=len_sig)

    def get_in_trans(self, inst, fifo):
        length = inst["len"]
        fifo_read_data = fifo.pop(length)
        input_trans = sub_one_input_trans(len=length, fifo_read_data=fifo_read_data)
        return input_trans

    async def wait_idle(self):
        while True:
            await RisingEdge(self.dut.clk)
            if (self.dut.busy.value == 0):
                break
