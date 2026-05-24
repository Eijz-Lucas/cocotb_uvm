import numpy as np
# from ml_dtypes import bfloat16, float8_e4m3fn
from typing import List, Any, Optional
from collections import deque

class FIFO:
    """
    FIFO used to store numpy array
    """
    def __init__(self, size:int, depth:int) -> None:
        self._size = size
        self._depth = depth
        self._q = deque()
    
    def pop(self, num) -> np.ndarray:
        """
        num:number of rows popped up
        return:data read out, shape:(num, size)
        """
        if num > len(self._q):
            raise RuntimeError(f"not enough rows in FIFO:{len(self._q)}")
        else:
            rows = [self._q.popleft() for _ in range(num)]
            return np.stack(rows, axis=0)
        
    def push(self, data:np.ndarray) -> None:
        """
        data:data to be pushed into FIFO
        """
        if data.shape[1] != self._size:
            raise RuntimeError(f"number of lines must be {self._size}")
        elif len(self._q) + data.shape[0] > self._depth:
            raise RuntimeError(f"FIFO has insufficient remaining space")
        else:
            self._q.extend(data)

    def write(self, start: int, data: np.ndarray) -> None:
        """
        从指定位置批量写入，替换对应位置的数据
        start: 起始索引
        data: shape必须为 (n, size)
        """
        if data.ndim != 2 or data.shape[1] != self._size:
            raise RuntimeError(f"data shape must be (n, {self._size}), got {data.shape}")
        if start < 0 or start + data.shape[0] > len(self._q):
            raise IndexError(f"range [{start}, {start+data.shape[0]}) out of range for FIFO of length {len(self._q)}")
        for i, row in enumerate(data):
            self._q[start + i] = row
    
    def read(self, start: int, num: int) -> np.ndarray:
        """
        从指定位置批量读取，不改变队列状态
        start: 起始索引
        num: 读取行数
        return: shape: (num, size)
        """
        if start < 0 or start + num > len(self._q):
            raise IndexError(f"range [{start}, {start+num}) out of range for FIFO of length {len(self._q)}")
        rows = [self._q[i] for i in range(start, start + num)]
        return np.stack(rows, axis=0)

    def is_empty(self) -> bool:
        return len(self._q) == 0
    
    def is_full(self) -> bool:
        return len(self._q) == self._depth
    
    def clear(self) -> None:
        self._q.clear()
    
    def __len__(self) -> int:
        return len(self._q)
            
class AccuMem:
    def __init__(self, size, depth, block_num) -> None:
        self._size = size
        self._depth = depth
        self._block_num = block_num
        # self._dtype = np.float32
        self._mem = [FIFO(size=self._size, depth=self._depth) for _ in range(self._block_num)]
        self._occupied_by: List[Optional[Any]] = [None] * self._block_num 
        
    @property
    def block_num(self) -> int:
        """get AccuMem.block_num"""
        return self._block_num
    
    def check_ready(self, block_num: int) -> bool:
        """check data"""
        if block_num >= self._block_num:
            return False
        return len(self._mem[block_num]) > 0
    
    def pop(self, block_num:int, device_id:Any, depth:int = 128) -> np.ndarray:
        """
        read AccuMem[block_num]
        return: shape (size, size)
        """
        if self._occupied_by[block_num] is None:
            self._occupied_by[block_num] = device_id
        elif self._occupied_by[block_num] != device_id:
            raise RuntimeError(f"AccuMem[{block_num}] is occupied by {self._occupied_by[block_num]}")
        return self._mem[block_num].pop(depth)
        
    def push(self, block_num:int, data:np.ndarray, device_id:Any) -> None:
        """
        write AccuMem[block_num]
        data: shape (size, size)
        """
        if self._occupied_by[block_num] is None:
            self._occupied_by[block_num] = device_id
        elif self._occupied_by[block_num] != device_id:
            raise RuntimeError(f"AccuMem[{block_num}] is occupied by {self._occupied_by[block_num]}")
        self._mem[block_num].push(data)
    
    def occupy(self, block_num:int, device_id:Any) -> None:
        """
        occupy AccuMem[block_num] by device
        """
        if self._occupied_by[block_num] is not None:
            raise RuntimeError(f"AccuMem[{block_num}] is occupied by {self._occupied_by[block_num]}")
        else: 
            self._occupied_by[block_num] = device_id
            
    def release(self, block_num:int, device_id:Any) -> None:
        """
        release AccuMem[block_num]
        """
        if self._occupied_by[block_num] != device_id:
            raise RuntimeError(f"AccuMem[{block_num}] is occupied by {self._occupied_by[block_num]}")
        else:
            self._occupied_by[block_num] = None
    
    def clear(self) -> None:
        for fifo in self._mem:
            fifo.clear()

class RAM:
    def __init__(self, size:int, depth:int, block_num:int) -> None:
        self._size = size
        self._block_num = block_num
        self._depth = depth
        self._mem = np.zeros((self._block_num, self._depth, self._size), dtype=np.float32)
        
    @property
    def block_num(self) -> int:
        return self._block_num
    
    def write(self, block_num:int, data:np.ndarray, bias:int = 0, depth:int=128) -> None:
        if data.shape[1] != self._size:
            raise RuntimeError(f"data.shape[1] must be {self._size}")
        if bias < 0 or bias + depth > self._depth:
            raise RuntimeError(f"Write address out of range: bias={bias}, depth={depth}, valid range=[0, {self._depth-1}]")

        self._mem[block_num, bias:bias+depth, :] = data

    def read(self, block_num:int, bias:int = 0, depth:int = 128) -> np.ndarray:
        if bias < 0 or bias + depth > self._depth:
            raise RuntimeError(f"Read address out of range: bias={bias}, depth={depth}, valid range=[0, {self._depth-1}]")

        return self._mem[block_num, bias:bias+depth, :].copy()
    
class WeightMem(RAM):
    """
    在GEMM模式下装载B，在FA模式下装载Q
    """
    def __init__(self, size=128, depth=128, block_num=1):
        super().__init__(size, depth, block_num)


class SharedMem(RAM):
    """
    SharedMem: SA之间共享，12个block
    在GEMM模式下装载A，在FA模式下装载K、V
    """
    def __init__(self, size=128, depth=128, block_num=12):
        super().__init__(size, depth, block_num)
