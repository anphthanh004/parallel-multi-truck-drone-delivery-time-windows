from __future__ import annotations
import math
from abc import ABC, abstractmethod
from typing import Literal, Optional, Callable, Dict, Tuple, Any
from .problem_structures import Vehicle, Problem, Request

def protected_div(a: float, b: float) -> float:
    return a / b if b != 0 else 1.0

FUNC_SET = ['add', 'sub', 'mul', 'div', 'min', 'max']
OPERATORS: Dict[str, Callable[[float, float], float]] = {
    'add': lambda a, b: a + b,
    'sub': lambda a, b: a - b,
    'mul': lambda a, b: a * b,
    'div': protected_div,
    'min': min,
    'max': max
}


class TerminalRegistry:
    """
    Class quản lý các logic tính toán cho Terminal Nodes (RT và ST).
    Giúp tách biệt logic nghiệp vụ ra khỏi cấu trúc cây.
    """
    @staticmethod
    def rt_logic(opt: int, veh: Vehicle, pro: Problem, req: Request) -> float:
        """Logic cho Routing Terminals (RT)"""
        # RT0 càng nhận ít việc càng nên nhận thêm - w=0.05
        if opt == 0:
            total = len(pro.requests)
            return 0.0 if total == 0 else 1.0 - len(veh.req_queue) / total
        
        # RT1: hàng đợi còn trống lượng demand càng nhiều càng nên nhận thêm (đợi max bằng capacity) - w=0.15
        elif opt == 1:
            sum_demand = pro.sum_of_req_demand()
            return 0.0 if sum_demand == 0.0 else (veh.capacity - veh.sum_of_req_demand()) / sum_demand
        
        # RT2: càng gần trung tâm hàng đợi càng được ưu tiên - w=0.15
        elif opt == 2:
            return 1.0 - veh.moving_time(veh.median_of_req_loc(), req.location) / pro.depot_time_window[1]
        
        # RT3: Thời gian di chuyển ngắn nhất từ vị trí hiện tại - w=0.5
        elif opt == 3:
            return 1.0 - veh.moving_time_to(req.location) / pro.depot_time_window[1]
        
        # RT4: demand của request càng lớn càng được ưu tiên - w=0.05
        elif opt == 4:
            sum_demand = pro.sum_of_req_demand()
            return 0.0 if sum_demand == 0.0 else req.demand / sum_demand
        
        # RT5: ưu tiên DRONE (thường nhân với RT3 đế nhận việc gần) - w=0.1
        elif opt == 5:
            return 1.0 if veh.type == 'DRONE' else 0.0
        
        raise ValueError(f"Unknown Routing Terminal option: {opt}")

    @staticmethod
    def st_logic(opt: int, veh: Vehicle, pro: Problem, req: Request, curr_time: float=0.0) -> float:
        """Logic cho Sequencing Terminals (ST)"""
        
        # ST0: thời gian di chuyển đến càng ngắn thì càng được ưu tiên - w=0.4
        if opt == 0:
            return veh.moving_time_to(req.location) / pro.depot_time_window[1]
        
        # ST1: càng xuất hiện sớm (so với hiện tại) thì càng ưu tiên - w=0.05
        elif opt == 1:
        # return -(curr_time - req.release_time) / pro.depot_time_window[1]
        # current time luôn lớn hơn release time vì đơn hàng phải xuất hiện trước khi được thêm vào hàng đọi của xe 
        # do đó thời điểm hiện tại đã muộn hơn thời điểm đơn hàng được đưa vào hàng đợi
            return 1.0 - (curr_time - req.release_time) / pro.depot_time_window[1]
        
        # ST2: càng gấp càng ưu tiên - w=0.4
        elif opt == 2:
            time_until_close = req.time_window[1] - veh.busy_until
            moving_time = veh.moving_time_to(req.location)
            if moving_time > time_until_close or time_until_close <= 1e-3:
                return 1e9
            # return moving_time / time_until_close
            return max(0.0, (time_until_close - moving_time) / time_until_close)
        
        # ST3: kích thước request (demand) càng lớn càng được ưu tiên - w=0.05
        elif opt == 3:
            sum_demand = pro.sum_of_req_demand()
            return 0.0 if sum_demand == 0.0 else 1.0 - req.demand / sum_demand
        
        # ST4: càng chờ lâu được ưu tiên - w=0.05
        elif opt == 4:
            return 1.0 - (curr_time - req.time_window[0]) / pro.depot_time_window[1]
        
        # ST5: ưu tiên thời gian xuất hiện sớm - w=0.05
        elif opt == 5:
            return req.release_time / pro.depot_time_window[1]
            
        raise ValueError(f"Unknown Sequencing Terminal option: {opt}")


class NodeGP(ABC):
    """ABC cho tất cả các node trong cây GP."""
    
    def __init__(self, which: Literal['S', 'R'] = 'R'):
        self.which = which
        self.left: Optional[NodeGP] = None
        self.right: Optional[NodeGP] = None

    @abstractmethod
    def evaluate(self, veh: Vehicle, pro: Problem, req: Request, curr_time: float = 0.0) -> float:
        pass

    @abstractmethod
    def copy(self) -> NodeGP:
        pass

    @abstractmethod
    def size(self) -> int:
        pass

    @abstractmethod
    def depth(self) -> int:
        pass

    @abstractmethod
    def to_string(self) -> str:
        pass
    
    @property
    @abstractmethod
    def op(self) -> Optional[str]:
        """Trả về tên operator nếu là node trong, None nếu là node lá"""
        pass
    
    @property
    @abstractmethod
    def terminal(self) -> Optional[Tuple[str, int]]:
        """Trả về tuple thông tin terminal nếu là node lá, None nếu là node trong"""
        pass


class InternalNode(NodeGP):
    """Node trong chứa operator"""
    
    def __init__(self, op_name: str, left: NodeGP, right: NodeGP, which: Literal['S', 'R'] = 'R'):
        super().__init__(which)
        if op_name not in OPERATORS:
            raise ValueError(f"Unknown operator: {op_name}")
        self._op_name = op_name
        self._func = OPERATORS[op_name]
        self.left = left
        self.right = right

    def evaluate(self, veh: Vehicle, pro: Problem, req: Request, curr_time: float = 0.0) -> float:
        l_val = self.left.evaluate(veh, pro, req, curr_time)
        r_val = self.right.evaluate(veh, pro, req, curr_time)
        return self._func(l_val, r_val)

    def copy(self) -> InternalNode:
        return InternalNode(self._op_name, self.left.copy(), self.right.copy(), self.which)

    def size(self) -> int:
        return 1 + self.left.size() + self.right.size()

    def depth(self) -> int:
        return 1 + max(self.left.depth(), self.right.depth())

    def to_string(self) -> str:
        return f"({self._op_name} {self.left.to_string()} {self.right.to_string()})"

    @property
    def op(self) -> str:
        return self._op_name

    @property
    def terminal(self) -> None:
        return None


class TerminalNode(NodeGP):
    """Node lá chứa logic terminal"""
    
    def __init__(self, type_str: str, index: int, which: Literal['S', 'R'] = 'R'):
        super().__init__(which)
        self.type_str = type_str  # 'RT' or 'ST'
        self.index = index
        self.left = None
        self.right = None

    def evaluate(self, veh: Vehicle, pro: Problem, req: Request, curr_time: float = 0.0) -> float:
        if self.type_str == 'RT':
            return TerminalRegistry.rt_logic(self.index, veh, pro, req)
        elif self.type_str == 'ST':
            return TerminalRegistry.st_logic(self.index, veh, pro, req, curr_time)
        else:
            return 0.0

    def copy(self) -> TerminalNode:
        return TerminalNode(self.type_str, self.index, self.which)

    def size(self) -> int:
        return 1

    def depth(self) -> int:
        return 1

    def to_string(self) -> str:
        return f"{self.type_str}{self.index}"
    
    @property
    def op(self) -> None:
        return None

    @property
    def terminal(self) -> Tuple[str, int]:
        return (self.type_str, self.index)


class Individual:
    def __init__(self, r_tree: NodeGP, s_tree: NodeGP) -> None:
        self.r_tree = r_tree
        self.s_tree = s_tree
        self.fitness: Optional[Tuple[float, float]] = None
        self.f1: Optional[float] = None
        self.f2: Optional[float] = None
        
    def copy(self) -> Individual:
        new_indi = Individual(self.r_tree.copy(), self.s_tree.copy())
        new_indi.f1 = self.f1
        new_indi.f2 = self.f2
        new_indi.fitness = self.fitness
        return new_indi
    
    def to_string(self) -> None:
        print(f"R: {self.r_tree.to_string()} | S: {self.s_tree.to_string()}")