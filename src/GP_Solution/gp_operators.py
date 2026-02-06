import random
from typing import Literal, Optional
from .gp_structure import NodeGP
from .initalizer import PopulationInitializer
from .gp_structure import NodeGP, Individual, InternalNode, TerminalNode

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
        
        # new_node = NodeGP(op=root.op, terminal=root.terminal, which=root.which)
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
    def apply_mutation(
            indi: Individual, 
            max_depth: int = 6
        ) -> Individual:
        """Đột biến subtree có kiểm soát độ sâu"""
        
        new_indi = indi.copy()
        
        if random.random() < 0.5:
            target_tree = new_indi.r_tree
            which = 'R'
        else:
            target_tree = new_indi.s_tree
            which = 'S'
        
        size = GeneticOperator._count_nodes(target_tree)
        
        for _ in range(10):
            idx = random.randint(0, size-1)
            
            # Tạo cây con với độ sâu nhỏ
            mutation_subtree = PopulationInitializer.make_random_tree(max_depth=random.randint(1, 3), grow=True, which=which)
            new_tree, _ = GeneticOperator._replace_node_at_index(target_tree, idx, mutation_subtree)
            
            if new_tree.depth() <= max_depth:
                if which == 'R':
                    new_indi.r_tree = new_tree
                else:
                    new_indi.s_tree = new_tree
                
                break
        
        return new_indi