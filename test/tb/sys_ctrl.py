class sys_ctrl:
    def __init__(self, cosim_wrapper, firmware: list):
        self.cosim_wrapper = cosim_wrapper
        self.firmware = firmware

    async def execute(self):
        for inst in self.firmware:
            await self.cosim_wrapper.execute(inst)
        await self.cosim_wrapper.wait_for_completion()
