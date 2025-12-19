import random
import copy

# ---------------------
# GP terminal node
# ---------------------
def routing_rule_terminal(opt, **kwargs):
    veh = kwargs['veh']
    pro = kwargs['pro']
    req = kwargs['req']
    
    # RT0 càng nhận ít việc càng nên nhận thêm - w=0.05
    if opt == 0:
        total = len(pro.requests)
        if total == 0:
            return 0.0
        return 1.0 - len(veh.req_queue) / len(pro.requests)
    
    # RT1: hàng đợi còn trống lượng demand càng nhiều càng nên nhận thêm (đợi max bằng capacity) - w=0.15
    elif opt == 1:
        sum_demand = pro.sum_of_req_demand()
        if sum_demand == 0.0:
            return 0.0
        return (veh.capacity - veh.sum_of_req_demand()) / sum_demand
    
    # RT2: càng gần trung tâm hàng đợi càng được ưu tiên - w=0.15
    elif opt == 2:
        return 1.0 - veh.moving_time(veh.median_of_req_loc(), req.location) / pro.depot_time_window[1]   
    
    # RT3: Thời gian di chuyển ngắn nhất từ vị trí hiện tại - w=0.5
    elif opt == 3:
        return 1.0 - veh.moving_time_to(req.location) / pro.depot_time_window[1]
    
    # RT4: demand của request càng lớn càng được ưu tiên - w=0.05
    elif opt == 4:
        sum_demand = pro.sum_of_req_demand()
        if sum_demand == 0.0:
            return 0.0
        return req.demand / sum_demand
    
    # RT5: ưu tiên DRONE (thường nhân với RT3 đế nhận việc gần) - w=0.1
    elif opt == 5:
        return 1 if veh.type == 'DRONE' else 0.0


def sequencing_rule_terminal(opt, **kwargs):
    veh = kwargs['veh']
    pro = kwargs['pro']
    req = kwargs['req']
    
    curr_time = kwargs.get('curr_time', 0.0)
    
    # ST0: thời gian di chuyển càng ngắn thì càng ngắn thì càng được ưu tiên - w=0.4
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
        if moving_time > time_until_close or time_until_close <= 0.001:
            # return float('inf')
            return 1e9
        # if time_until_close <= 0.001:
        #     return 1.0
        return moving_time/time_until_close
    
    # ST3: kích thước request (demand) càng lớn càng được ưu tiên - w=0.05
    elif opt == 3:
        sum_demand = pro.sum_of_req_demand()
        if sum_demand == 0.0:
            return 0.0
        return 1.0 - req.demand / sum_demand
    
    # ST4: càng chờ lâu được ưu tiên - w=0.05
    elif opt == 4:
        return 1.0 - (curr_time - req.time_window[0]) / pro.depot_time_window[1]
    
    # ST5: ưu tiên thời gian xuất hiện sớm - w=0.05
    elif opt == 5:
        return req.release_time / pro.depot_time_window[1]

# -------------------------------
# CONSTRUCT GP TREE
# ------------------------------

def protected_div(a,b):
    return a/b if b!=0 else 1.0


# each gp tree is represented as a node which may have a left node and/or right node
class NodeGP:
    def __init__(self, op=None, left=None, right=None, terminal=None, which='R'):
        self.op = op
        self.left = left
        self.right = right
        self.terminal = terminal
        self.which = which
    
    def copy(self):
        return NodeGP(
            op=self.op,
            left=self.left.copy() if self.left else None,
            right=self.right.copy() if self.right else None,
            terminal=self.terminal,
            which=self.which
        )
    
    def is_terminal(self):
        return (self.terminal is not None)
    
    def size(self):
        if self.is_terminal():
          return 1
        return 1 + (self.left.size() if self.left else 0) + (self.right.size() if self.right else 0)
    
    def depth(self):
        if self.is_terminal():
            return 1
        return 1 + max(self.left.depth() if self.left else 0, self.right.depth() if self.right else 0)
    
    def evaluate(self, veh, pro, req, curr_time=0.0):
        if self.is_terminal():
            typ, opt = self.terminal
            if typ == 'RT':
                return routing_rule_terminal(opt, veh=veh, pro=pro, req=req)
            elif typ == 'ST':
                return sequencing_rule_terminal(opt, veh=veh, pro=pro, req=req, curr_time=curr_time)
        
        left = self.left.evaluate(veh, pro, req, curr_time)
        right = self.right.evaluate(veh, pro, req, curr_time)
        
        if self.op == 'add':
            return left + right
        elif self.op == 'sub':
            return left - right
        elif self.op == 'mul':
            return left * right
        elif self.op == 'div':
            return protected_div(left, right)
        elif self.op == 'min':
            return min(left, right)
        elif self.op == 'max':
            return max(left, right)
        
    def to_string(self):
        if self.is_terminal():
            typ, opt = self.terminal
            return f"{typ}{opt}"
        return f"({self.op} {self.left.to_string()} {self.right.to_string()})"


# 
class Individual:
    def __init__(self, r_tree:NodeGP, s_tree:NodeGP):
        self.r_tree = r_tree
        self.s_tree = s_tree
        self.fitness = None
        self.f1 = None
        self.f2 = None
        
    def copy(self):
        r_tree_dc = self.r_tree.copy()
        s_tree_dc = self.s_tree.copy()
        return Individual(r_tree_dc, s_tree_dc)
    
    def to_string(self):
        print(f"R: {self.r_tree.to_string()} | S: {self.s_tree.to_string()}")
    
    # def evaluate(self, veh, pro, req, curr_time=0.0):
    #     r_value = self.r_tree.evaluate(veh, pro, req, curr_time)
    #     s_value = self.s_tree.evaluate(veh, pro, req, curr_time)
    #     self.fitness = r_value, s_value
    #     return self.fitness
    
    
    
