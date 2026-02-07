import random
from .gp_structure import NodeGP, Individual
from typing import Any, Literal, Optional
from .problem_structures import Vehicle, Problem, Request
from .gp_structure import NodeGP, Individual, InternalNode, TerminalNode, FUNC_SET


type Terminal = tuple[Literal['ST', 'RT'], Literal[0, 1, 2, 3, 4, 5]]

TERMINAL_ROUTING = [('RT', i) for i in range(6)]
TERMINAL_SEQUENCING = [('ST', i) for i in range(6)]
ROUTING_WEIGHTS = [0.05, 0.15, 0.15, 0.50, 0.05, 0.10]
SEQ_WEIGHTS = [0.40, 0.05, 0.40, 0.05, 0.05, 0.05]


class PopulationInitializer:
    """
    Class chịu trách nhiệm khởi tạo cá thể và quần thể.
    """
    @staticmethod
    def build_tree_from_string(s: str, which: Literal['S', 'R'] = 'R') -> NodeGP:
        s = s.strip()
        # Terminal 
        if s.startswith('RT') and which == 'R':
            num = int(''.join(filter(str.isdigit, s)))
            return TerminalNode(type_str='RT', index=num, which='R')
        if s.startswith('ST') and which == 'S':
            num = int(''.join(filter(str.isdigit, s)))
            return TerminalNode(type_str='ST', index=num, which='S')

        # Expression with parentheses
        if s.startswith('(') and s.endswith(')'):
            content = s[1:-1].strip()
            parts = content.split()
            if len(parts) < 1:
                raise ValueError("Invalid expression")
            op = parts[0]
            rest = ' '.join(parts[1:])
            
            depth = 0
            split_pos = None
            for i, char in enumerate(rest):
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                elif char == ' ' and depth == 0 and split_pos is None:
                    split_pos = i
                    break
            left_str = rest[:split_pos].strip()
            right_str = rest[split_pos:].strip()
            
            left = PopulationInitializer.build_tree_from_string(left_str, which)
            right = PopulationInitializer.build_tree_from_string(right_str, which)
            
            return InternalNode(op_name=op, left=left, right=right, which=which)
        raise ValueError(f"Cannot parse: {s}")

    @staticmethod
    def _random_terminal(which: Literal['S', 'R'] = 'R') -> Terminal:
        if which == 'R':
            return ('RT', random.randint(0,5))
        return ('ST', random.randint(0,5))

    @staticmethod
    def make_random_tree(
            max_depth: int = 5, 
            grow: bool = True, 
            which: Literal['S', 'R'] = 'R'
        ) -> NodeGP:
        if max_depth == 1 or (grow and random.random() < 0.4):
            term_type, term_idx = PopulationInitializer._random_terminal(which)
            return TerminalNode(type_str=term_type, index=term_idx, which=which)
        
        op = random.choice(FUNC_SET)
        left = PopulationInitializer.make_random_tree(max_depth-1, grow, which)
        right = PopulationInitializer.make_random_tree(max_depth-1, grow, which)
        # return NodeGP(op=op, left=left, right=right, which=which)
        return InternalNode(op_name=op, left=left, right=right, which=which)

    @staticmethod
    def weighted_terminal(which: Literal['S', 'R'] = 'R') -> Terminal:
        if which=='R':
            opt = random.choices(range(6), weights=ROUTING_WEIGHTS, k=1)[0]
            return ('RT', opt)
        else: 
            opt = random.choices(range(6), weights=SEQ_WEIGHTS, k=1)[0]
            return ('ST', opt)         
   
    @staticmethod
    def _make_weighted_random_tree(
            max_depth: int, 
            grow: bool = True, 
            which: Literal['S', 'R'] = 'R'
        ) -> NodeGP:
        if max_depth == 1 or (grow and random.random() < 0.4):
            term_type, term_idx = PopulationInitializer.weighted_terminal(which)
            return TerminalNode(type_str=term_type, index=term_idx, which=which)
        
        op = random.choice(FUNC_SET)
        left = PopulationInitializer._make_weighted_random_tree(max_depth-1, grow, which)
        right = PopulationInitializer._make_weighted_random_tree(max_depth-1, grow, which)
        
        return InternalNode(op_name=op, left=left, right=right, which=which)

    @staticmethod
    def create_greedy_pop(
            pop_size: int, 
            max_depth: int = 5
        ) -> list[Individual]:
        pop = []
        # 1. hand-crafted strong individuals
        strong_individuals = [
            # 1. RT3 gần nhất trước, RT1 hàng đợi còn còn trống lượng demand nhiều + ST0 gần nhất trước, ST2 ưu tiên gấp
            ("(add RT3 RT1)", "(min ST0 ST2)"),
            # 2. RT3 gần nhất trước + ST0 gần nhất trước, ST2 ưu tiên gấp
            ("RT3", "(min ST0 ST2)"),
            # 3. RT1 hàng đợi còn trống lượng demand nhiều, RT3 gần nhất trước + ST2 ưu tiên gấp
            ("(add RT1 RT3)", "ST2"),
            # 4. RT3 gần nhất trước, RT5 ưu tiên DRONE (nhân với R3 là ưu tiên DRONE gần nhất) + ST0 gần nhất trước
            ("(add RT3 (mul RT3 RT5))", "ST0"),
            # 5. RT0 càng ít việc càng nên nhận thêm, RT3 gần nhất trước + ST0 gần nhất trước, ST2 ưu tiên gấp
            ("(add RT0 RT3)", "(min ST0 ST2)"),
            # 6. RT1 hàng đợi còn trống lượng demand nhiều, RT2 gần trung tâm hàng đợi + ST0 gần nhất trước, ST2 ưu tiên gấp
            ("(add RT1 RT2)", "(min ST0 ST2)"),
            # 7. RT3 gần nhất trước + ST0 gần nhất trước, ST2 ưu tiên gấp
            ("RT3", "(div ST2 ST0)"),
            # 8. đơn giản, lựa chọn các luật mạnh là RT3 gần nhất trước + ST2 ưu tiên gấp
            ("RT3", "ST2")
        ]
        greedy_size = pop_size//3
        for r_str, s_str in strong_individuals[:greedy_size]:
            if len(pop) >= pop_size:
                break
            try:
                r_tree = PopulationInitializer.build_tree_from_string(r_str, which='R')
                s_tree = PopulationInitializer.build_tree_from_string(s_str, which='S')
                pop.append(Individual(r_tree, s_tree))
            except Exception as e:
                print(f"Skipping invalid greedy individual {e}")
        
        while len(pop) < pop_size * 2 //3:
            r_tree = PopulationInitializer._make_weighted_random_tree(max_depth, grow=True, which='R')
            s_tree = PopulationInitializer._make_weighted_random_tree(max_depth, grow=True, which='S')
            pop.append(Individual(r_tree, s_tree))
        
        while len(pop) < pop_size:
            use_grow = random.random() < 0.5
            r_tree = PopulationInitializer.make_random_tree(max_depth, use_grow, which='R')
            s_tree = PopulationInitializer.make_random_tree(max_depth, use_grow, which='S')
            pop.append(Individual(r_tree, s_tree))
        
        return pop[:pop_size]

            