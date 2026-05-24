import cocotb
import numpy as np
from cocotb.triggers import RisingEdge, ValueChange
from cocotb_uvm import CoSimWrapperBase

from .add_one_cosim import add_one_cosim
from .memory import FIFO, RAM
from .sub_one_cosim import sub_one_cosim


class ram_model(RAM):
    def __init__(self, size, depth, block_num, addr_sig, rdata_sig):
        super().__init__(size, depth, block_num)
        self.addr_sig = addr_sig
        self.rdata_sig = rdata_sig

    async def run(self):
        if 'X' in str(self.addr_sig.value):
            self.rdata_sig.value = 0
        while True:
            await ValueChange(self.addr_sig)
            self.rdata_sig.value = int(self.read(0, int(self.addr_sig.value), 1)[0][0])


class fifo_model(FIFO):
    def __init__(self, size, depth, clk_sig, fifo_read_en_sig, fifo_read_data_sig, fifo_write_en_sig_0, fifo_write_data_sig_0,
                 fifo_write_en_sig_1, fifo_write_data_sig_1):
        super().__init__(size, depth)
        self.fifo_read_en_sig = fifo_read_en_sig
        self.fifo_read_data_sig = fifo_read_data_sig
        self.fifo_write_en_sig_0 = fifo_write_en_sig_0
        self.fifo_write_data_sig_0 = fifo_write_data_sig_0
        self.fifo_write_en_sig_1 = fifo_write_en_sig_1
        self.fifo_write_data_sig_1 = fifo_write_data_sig_1
        self.clk_sig = clk_sig

    async def run(self):
        async def read_coroutine():
            while True:
                await ValueChange(self.fifo_read_en_sig)
                if 'X' in str(self.fifo_read_en_sig.value):
                    self.fifo_read_data_sig.value = 0
                if self.fifo_read_en_sig.value == 1:
                    self.fifo_read_data_sig.value = int(self.pop(1)[0][0])

        async def write_coroutine():
            while True:
                await RisingEdge(self.clk_sig)
                if self.fifo_write_en_sig_0.value == 1:
                    self.push(np.array([[int(self.fifo_write_data_sig_0.value)]]))
                if self.fifo_write_en_sig_1.value == 1:
                    self.push(np.array([[int(self.fifo_write_data_sig_1.value)]]))
        cocotb.start_soon(read_coroutine())
        cocotb.start_soon(write_coroutine())


class cosim_test_wrapper(CoSimWrapperBase):
    def __init__(self, dut, modules, level="ut", name="cosim_test_wrapper"):
        super().__init__(dut, modules, level=level, name=name)
        self.ram = ram_model(1, 16, 1, dut.u_add_one.ram_addr, dut.u_add_one.ram_rdata)
        self.fifo = fifo_model(1, 64, dut.clk, dut.u_sub_one.fifo_read_en, dut.u_sub_one.fifo_read_data, dut.u_add_one.fifo_write_en,
                               dut.u_add_one.fifo_write_data, dut.u_sub_one.fifo_write_en, dut.u_sub_one.fifo_write_data)
        if self.level == "ut":
            cocotb.start_soon(self.ram.run())
            cocotb.start_soon(self.fifo.run())
        cocotb.start_soon(self.backdoor_handler())

    async def execute_system_test(self, inst, top: bool = True, en_sig=None, len_sig=None):
        await self.wait_for_completion()
        if top is True:
            if inst["op"] == "add_one":
                await self.modules["add_one_cosim"].execute(inst=inst, en_sig=self.dut.en_add, len_sig=self.dut.len_add, addr_sig=self.dut.addr_add)
            elif inst["op"] == "sub_one":
                await self.modules["sub_one_cosim"].execute(inst=inst, en_sig=self.dut.en_sub, len_sig=self.dut.len_sub)
        else:
            if inst["op"] == "sub_one":
                await self.modules["sub_one_cosim"].execute(inst=inst, en_sig=en_sig, len_sig=len_sig)

    async def execute_unit_test(self, inst):
        await self.wait_for_completion()
        if inst["op"] == "add_one":
            await self.modules["add_one_cosim"].execute(inst=inst, ram=self.ram, fifo=self.fifo)
        elif inst["op"] == "sub_one":
            await self.modules["sub_one_cosim"].execute(inst=inst, fifo=self.fifo)

    async def backdoor_handler(self):
        while True:
            await self.modules["add_one_cosim"].scoreboard.error.wait()
            excepted_trans = await self.modules["add_one_cosim"].scoreboard.backdoor_queue.get()
            self.modules["add_one_cosim"].scoreboard.error.clear()
            self.fifo.write(0, excepted_trans.fifo_write_data.reshape(-1, 1))
            self.log.info(
                f"[Backdoor Handler] Wrote expected fifo_write_data={excepted_trans.fifo_write_data} to fifo")
