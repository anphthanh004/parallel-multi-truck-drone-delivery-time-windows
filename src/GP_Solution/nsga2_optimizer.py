import random
import math
import json
import numpy as np
from collections import defaultdict
from typing import Any, List, Tuple, Dict, Optional

from .problem_structures import Problem
from .gp_structure import NodeGP, Individual
from .initializer import PopulationInitializer
from .simulator import Simulator
from .gp_operators import GeneticOperator

class NSGA2Optimizer:
    def __init__(
        self, 
        pop_size: int = 50, 
        max_gen: int = 20, 
        c_rate: float = 0.8, 
        m_rate: float = 0.3,    
        elite_ratio: float = 0.1, 
        tourn_size: int = 4, 
        max_depth: int = 6,
        seed: Optional[int] = None
    ):
        self.pop_size = pop_size
        self.max_gen = max_gen
        self.c_rate = c_rate
        self.m_rate = m_rate
        self.elite_size = int(pop_size * elite_ratio) 
        self.tourn_size = tourn_size
        self.max_depth = max_depth
        
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def evolve(
        self, 
        problem: Problem, 
        assignment_n: int = 1,
    ) -> Dict[str, Any]:
        """
        Thực thi quá trình tiến hóa GPHH sử dụng thuật toán NSGA-II 
        với cơ chế Elitism (Ưu tú hóa).
        """
        # 1. Khởi tạo quần thể ban đầu
        current_pop = PopulationInitializer.create_greedy_pop(self.pop_size, max_depth=self.max_depth - 1)
        self._evaluate_population(current_pop, problem, assignment_n)
        
        # Lưu lịch sử
        pop_history = []
        pop_history.append([ind.copy() for ind in current_pop])
        
        # Sắp xếp ban đầu
        fronts = self._fast_non_dominated_sort(current_pop)
        for front in fronts:
            self._assign_crowding_distance(front)
            
        stats_history = []
        self._record_stats(0, current_pop, stats_history)
        
        # 2. Vòng lặp tiến hóa
        for gen in range(1, self.max_gen + 1):
            
            offspring = []
            
            # --- ELITISM---
            sorted_pop = sorted(current_pop, key=lambda x: (x.rank, -x.distance))
            for i in range(min(self.elite_size, len(sorted_pop))):
                elite_ind = sorted_pop[i].copy()
                offspring.append(elite_ind)
            
            # ------Tạo thế hệ con--------
            while len(offspring) < self.pop_size:
                p1 = self._tournament_selection(current_pop)
                p2 = self._tournament_selection(current_pop)
                
                if random.random() < self.c_rate:
                    c1, c2 = GeneticOperator.perform_crossover(p1, p2, self.max_depth)
                else:
                    c1, c2 = p1.copy(), p2.copy()
                
                if random.random() < self.m_rate: 
                    c1 = GeneticOperator.apply_mutation(c1, self.max_depth)
                if random.random() < self.m_rate: 
                    c2 = GeneticOperator.apply_mutation(c2, self.max_depth)
                    
                offspring.extend([c1, c2])
            
            offspring = offspring[:self.pop_size]
            
            # Đánh giá thế hệ con
            self._evaluate_population(offspring, problem, assignment_n)
            
            # Kết hợp Parent + Offspring để chọn lọc sinh tồn
            combined_pop = current_pop + offspring
            current_pop = self._survival_selection(combined_pop)
            
            # Sắp xếp lại để chuẩn bị cho thế hệ sau
            fronts = self._fast_non_dominated_sort(current_pop)
            for front in fronts:
                self._assign_crowding_distance(front)
            
            pop_history.append([ind.copy() for ind in current_pop])
            self._record_stats(gen, current_pop, stats_history)
            
        # 3. Kết thúc và tìm cá thể tốt nhất
        first_front = self._fast_non_dominated_sort(current_pop)[0]
        best_ind, best_results = self._select_best_individual(first_front, problem, assignment_n)
        
        return {
            "final_pop": current_pop,
            "pareto_front": first_front,
            "pareto_count": len(first_front),
            "stats_history": stats_history,
            "pop_history": pop_history,
            "best_individual": best_ind,
            "best_results": best_results
        }

    def _evaluate_population(self, pop: List[Individual], problem: Problem, assignment_n: int):
        """Đánh giá fitness cho toàn bộ quần thể sử dụng Simulator."""
        for ind in pop:
            sim = Simulator(problem, ind, assignment_n=assignment_n)
            sim.run()

    def _record_stats(self, gen: int, pop: List[Individual], history: List[dict]):
        if not pop: return
        best_f1 = max(pop, key=lambda x: x.f1).f1
        best_f2 = max(pop, key=lambda x: x.f2).f2
        
        stats = {
            "gen": gen,
            "best_served_ratio": best_f1,
            "best_makespan_score": best_f2
        }
        history.append(stats)
        print(f"Gen {gen:3d} | Served Ratio: {best_f1:.3f} | Makespan Score: {best_f2:.3f}")

    def _select_best_individual(self, front: List[Individual], problem: Problem, assignment_n: int):
        """Chọn cá thể có f1 lớn nhất, nếu trùng thì chọn f2 lớn nhất."""
        if not front:
            return None, None

        # Chọn cá thể có (f1, f2) lớn nhất
        best_ind = max(front, key=lambda x: (x.f1, x.f2))

        final_results = None
        if best_ind:
            sim = Simulator(problem, best_ind, assignment_n=assignment_n, enable_logging=True)
            final_results = sim.run()

        return best_ind, final_results


    def _dominate(self, ind1: Individual, ind2: Individual) -> bool:
        f1_a, f2_a = ind1.fitness
        f1_b, f2_b = ind2.fitness
        # Dominate nếu tốt hơn hoặc bằng ở mọi mục tiêu và tốt hơn ít nhất 1 mục tiêu
        if (f1_a >= f1_b and f2_a >= f2_b) and (f1_a > f1_b or f2_a > f2_b):
            return True
        return False

    def _fast_non_dominated_sort(self, pop: List[Individual]) -> List[List[Individual]]:
        fronts = [[]]
        domination_count = defaultdict(int) 
        dominated_solutions = defaultdict(list) 
        
        for p in pop:
            domination_count[p] = 0 # Reset count
            for q in pop:
                if p == q: continue
                if self._dominate(p, q):
                    dominated_solutions[p].append(q)
                elif self._dominate(q, p):
                    domination_count[p] += 1
            
            if domination_count[p] == 0:
                p.rank = 0
                fronts[0].append(p)
        
        i = 0
        while fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in dominated_solutions[p]:
                    domination_count[q] -= 1
                    if domination_count[q] == 0:
                        q.rank = i + 1
                        next_front.append(q)
            i += 1
            if next_front:
                fronts.append(next_front)
            else:
                break
        
        if not fronts[-1]:
            fronts.pop()
            
        return fronts

    def _assign_crowding_distance(self, front: List[Individual]) -> None:
        l = len(front)
        if l == 0: return
        
        for indi in front:
            indi.distance = 0
            
        # Tính cho từng mục tiêu (2 mục tiêu)
        for m in range(2):
            front.sort(key=lambda x: x.fitness[m])
            
            front[0].distance = float('inf')
            front[-1].distance = float('inf')
            
            f_min = front[0].fitness[m]
            f_max = front[-1].fitness[m]
            
            if f_min == f_max: continue
            
            norm = f_max - f_min
            
            for i in range(1, l-1):
                front[i].distance += (front[i+1].fitness[m] - front[i-1].fitness[m]) / norm

    def _tournament_selection(self, pop: List[Individual]) -> Individual:
        """Binary Tournament Selection dựa trên Rank và Crowding Distance."""
        tourn = random.sample(pop, self.tourn_size)
        
        best = tourn[0]
        for candidate in tourn[1:]:
            if candidate.rank < best.rank:
                best = candidate
            elif candidate.rank == best.rank:
                if candidate.distance > best.distance:
                    best = candidate
        return best

    def _survival_selection(self, combined_pop: List[Individual]) -> List[Individual]:
        """Chọn lọc sinh tồn để giữ kích thước quần thể ổn định."""
        fronts = self._fast_non_dominated_sort(combined_pop)
        new_pop = []
        
        for front in fronts:
            self._assign_crowding_distance(front)
            # Sort theo distance giảm dần (càng xa càng tốt)
            front.sort(key=lambda x: x.distance, reverse=True)
            
            if len(new_pop) + len(front) <= self.pop_size:
                new_pop.extend(front)
            else:
                needs = self.pop_size - len(new_pop)
                new_pop.extend(front[:needs])
                break
        
        return new_pop