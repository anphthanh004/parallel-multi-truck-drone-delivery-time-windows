import random
from typing import Literal, Optional
from .gp_structure import NodeGP
from .initializer import PopulationInitializer
from .gp_structure import NodeGP, Individual, InternalNode, TerminalNode, OPERATORS, FUNC_SET


def from_string_to_func(op_name):
    return OPERATORS.get(op_name)

# ----------------------------------
# Helper functions cho thao tác cây
# ----------------------------------

class GeneticOperator:
    @staticmethod
    def _count_nodes(node: NodeGP) -> int:
        if node is None: return 0
        return 1 + GeneticOperator._count_nodes(node.left) + GeneticOperator._count_nodes(node.right)

    @staticmethod
    def _get_node_at_index(
            node: NodeGP, 
            target_idx: int, 
            current_idx: int = 0
        ) -> tuple[NodeGP, int]:
        """Trả về node tại chỉ số target index (duyệt theo pre-order) và index tiếp theo"""
        
        if current_idx == target_idx:
            return node, current_idx + 1
        
        current_idx += 1
        if node.left:
            found, new_idx = GeneticOperator._get_node_at_index(node.left, target_idx, current_idx)
            if found: return found, new_idx
            current_idx = new_idx 
        
        if node.right:
            found, new_idx = GeneticOperator._get_node_at_index(node.right, target_idx, current_idx)
            if found: return found, new_idx
            current_idx = new_idx
        
        return None, current_idx

    @staticmethod
    def _replace_node_at_index(
            root: NodeGP, 
            target_idx: int, 
            new_subtree: NodeGP, 
            current_idx: int = 0
        ) -> tuple[NodeGP, int]:
        """Tạo một bản sao của cây với node tại target_idx được thay thế"""
        
        if current_idx == target_idx:
            return new_subtree.copy(), current_idx + 1
        
        if isinstance(root, InternalNode):
            new_node = InternalNode(op_name=root.op, left=None, right=None, which=root.which)
        elif isinstance(root, TerminalNode):
            new_node = TerminalNode(type_str=root.type_str, index=root.index, which=root.which)
        else:
            raise TypeError("Unknown node type")
        
        current_idx += 1
        
        if root.left:
            if current_idx <= target_idx:
                size_left = GeneticOperator._count_nodes(root.left)
                if target_idx < current_idx + size_left:
                    new_left, new_idx = GeneticOperator._replace_node_at_index(root.left, target_idx, new_subtree, current_idx)
                    new_node.left = new_left
                    new_node.right = root.right.copy() if root.right else None
                    return new_node, new_idx

                else:
                    new_node.left = root.left.copy()
                    current_idx += size_left
                
        if root.right:
            new_right, new_idx = GeneticOperator._replace_node_at_index(root.right, target_idx, new_subtree, current_idx)
            new_node.right = new_right
            return new_node, new_idx
        
        return new_node, current_idx 


    # -----------------------
    # Genetic Operators
    # -----------------------
    @staticmethod
    def perform_crossover(
            parent1: Individual, 
            parent2: Individual, 
            max_depth: int = 6
        ) -> tuple[Individual, Individual]:
        """Lai ghép giữa hai cá thể"""
        
        child1 = parent1.copy()
        child2 = parent2.copy()
        
        # Chọn lai cây R hay lai cây S
        if random.random() < 0.5:
            tree1 = child1.r_tree
            tree2 = child2.r_tree
            which = 'R'
        else:
            tree1 = child1.s_tree
            tree2 = child2.s_tree
            which = 'S'
            
        # Đếm số node
        size1 = GeneticOperator._count_nodes(tree1)
        size2 = GeneticOperator._count_nodes(tree2)
        
        for _ in range(10):
            idx1 = random.randint(0, size1-1)
            idx2 = random.randint(0, size2-1)
            
            # Lấy subtree tại điểm cắt
            subtree1,_ = GeneticOperator._get_node_at_index(tree1, idx1)
            subtree2,_ = GeneticOperator._get_node_at_index(tree2, idx2)
            
            # Kiểm tra deep limit
            if (tree1.depth() - subtree1.depth() + subtree2.depth() <= max_depth) and \
                (tree2.depth() - subtree2.depth() + subtree1.depth() <= max_depth):
                
                # Thực hiện hoán đổi bằng cách xây dựng lại hai cây
                if which == 'R':
                    child1.r_tree, _ = GeneticOperator._replace_node_at_index(child1.r_tree, idx1, subtree2)
                    child2.r_tree, _ = GeneticOperator._replace_node_at_index(child2.r_tree, idx2, subtree1)
                else:
                    child1.s_tree, _ = GeneticOperator._replace_node_at_index(child1.s_tree, idx1, subtree2)
                    child2.s_tree, _ = GeneticOperator._replace_node_at_index(child2.s_tree, idx2, subtree1)
                
                break
        return child1, child2

    @staticmethod
    def _mutation_subtree(target_tree: NodeGP, max_depth: int, which: str) -> Optional[NodeGP]:
        """Đột biến thay thế cả cây con bằng cây ngẫu nhiên mới (Standard)"""
        size = GeneticOperator._count_nodes(target_tree)
        idx = random.randint(0, size - 1)
        
        # Tạo cây con mới nhỏ (depth 1-3) để ghép vào
        mutation_subtree = PopulationInitializer.make_random_tree(max_depth=random.randint(1, 3), grow=True, which=which)
        new_tree, _ = GeneticOperator._replace_node_at_index(target_tree, idx, mutation_subtree)
        
        if new_tree.depth() <= max_depth:
            return new_tree
        return None

    @staticmethod
    def _mutation_point(target_tree: NodeGP, which: str) -> Optional[NodeGP]:
        """Đột biến điểm: Thay đổi toán tử hoặc giá trị terminal giữ nguyên cấu trúc"""
        new_tree = target_tree.copy()
        size = GeneticOperator._count_nodes(new_tree)
        idx = random.randint(0, size - 1)
        
        node_to_mod, _ = GeneticOperator._get_node_at_index(new_tree, idx)
        
        if isinstance(node_to_mod, InternalNode):
            # Thay đổi toán tử (ví dụ: add -> sub)
            current_op = node_to_mod.op
            candidates = [op for op in FUNC_SET if op != current_op]
            if candidates:
                node_to_mod._op_name = random.choice(candidates)
                node_to_mod._func = from_string_to_func(node_to_mod._op_name)
                
                new_internal = InternalNode(random.choice(candidates), node_to_mod.left, node_to_mod.right, which=which)
                final_tree, _ = GeneticOperator._replace_node_at_index(new_tree, idx, new_internal)
                return final_tree
                
        elif isinstance(node_to_mod, TerminalNode):
            # Thay đổi index của terminal (ví dụ: RT1 -> RT3)
            current_idx = node_to_mod.index
            new_val = random.choice([i for i in range(6) if i != current_idx])
            
            new_term = TerminalNode(node_to_mod.type_str, new_val, which=which)
            final_tree, _ = GeneticOperator._replace_node_at_index(new_tree, idx, new_term)
            return final_tree
            
        return new_tree

    @staticmethod
    def _mutation_hoist(target_tree: NodeGP) -> Optional[NodeGP]:
        """Đột biến nâng: Chọn 1 cây con và biến nó thành cây gốc mới (giảm size)"""
        size = GeneticOperator._count_nodes(target_tree)
        if size < 2: return None # Không thể hoist nếu chỉ có 1 node
        
        # Chọn node bất kỳ
        idx = random.randint(0, size - 1)
        subtree, _ = GeneticOperator._get_node_at_index(target_tree, idx)
        
        # Trả về bản copy của subtree đó làm cây mới
        return subtree.copy()

    @staticmethod
    def _mutation_permutation(target_tree: NodeGP) -> Optional[NodeGP]:
        """Đột biến hoán vị: Đổi chỗ con trái/phải của 1 node toán tử"""
        new_tree = target_tree.copy()
        size = GeneticOperator._count_nodes(new_tree)
        
        # Thử tìm internal node 5 lần, nếu toàn vớ phải lá thì thôi
        for _ in range(5):
            idx = random.randint(0, size - 1)
            node, _ = GeneticOperator._get_node_at_index(new_tree, idx)
            if isinstance(node, InternalNode):
                # Swap left and right
                node.left, node.right = node.right, node.left
                return new_tree
                
        return None # Không tìm thấy node nội bộ phù hợp để swap
    
    @staticmethod
    def apply_mutation(
            indi: Individual, 
            max_depth: int = 6
        ) -> Individual:
        """
        Áp dụng đa dạng các loại đột biến:
        - Subtree Mutation (60%): Thay thế nhánh.
        - Point Mutation (20%): Tinh chỉnh tham số/toán tử.
        - Hoist Mutation (10%): Cắt tỉa, giảm độ sâu.
        - Permutation Mutation (10%): Hoán đổi vị trí con.
        """
        new_indi = indi.copy()
        
        # Chọn R hoặc S để đột biến
        if random.random() < 0.5:
            target_tree = new_indi.r_tree
            which = 'R'
        else:
            target_tree = new_indi.s_tree
            which = 'S'
        
        r = random.random()
        mutated_tree = None

        # Logic chọn loại đột biến
        if r < 0.6:
            # 60% Subtree Mutation
            mutated_tree = GeneticOperator._mutation_subtree(target_tree, max_depth, which)
        elif r < 0.8:
            # 20% Point Mutation (Tinh chỉnh nhỏ)
            mutated_tree = GeneticOperator._mutation_point(target_tree, which)
        elif r < 0.9:
             # 10% Hoist Mutation (Chống bloat, giảm depth)
             mutated_tree = GeneticOperator._mutation_hoist(target_tree)
        else:
             # 10% Permutation (Đổi vai trò tham số)
             mutated_tree = GeneticOperator._mutation_permutation(target_tree)
        
        # Nếu đột biến thành công và thỏa mãn depth, cập nhật
        if mutated_tree is not None and mutated_tree.depth() <= max_depth:
            if which == 'R':
                new_indi.r_tree = mutated_tree
            else:
                new_indi.s_tree = mutated_tree
                
        return new_indi