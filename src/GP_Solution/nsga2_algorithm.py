from collections import defaultdict
import random
import math

from typing import Any, Literal
from .problem_structures import Vehicle, Problem, Request
from .gp_structure import NodeGP, Individual

# from .initalization_old import create_greedy_pop
from .initalization import create_greedy_pop
from .simulation import simulate_policy
from .gp_operators import apply_mutation, perform_crossover

def dominate(ind1: Individual, ind2: Individual) -> bool:
    f1_a, f2_a = ind1.fitness
    f1_b, f2_b = ind2.fitness
    
    # Dominate nếu tốt hơn hoặc bằng ở mọi mục tiêu và tốt hơn ít nhất 1 mục tiêu
    if (f1_a >= f1_b and f2_a >= f2_b) and (f1_a > f1_b or f2_a > f2_b):
        return True
    return False

def apply_fast_non_dominated_sorting(pop: list[Individual]) -> list[list[Individual]]:
    fronts = [[]]
    domination_count = defaultdict(int) # chỉ lưu số lượng các indi trội hơn nó
    dominated_solutions = defaultdict(list) # lưu list các indi bị trội bởi nó
    
    for p in pop:
        for q in pop:
            if p == q: continue
            if dominate(p, q):
                dominated_solutions[p].append(q)
            elif dominate(q, p):
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
        
    return fronts

def assign_crowding_distance(front: list[Individual]) -> None:
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
            
def nsga2_tourn_selection(pop: list[Individual], tour_size: int) -> Individual:
    """
    Chọn cha mẹ: So sánh 2 cá thể ngẫu nhiên.
    1. Rank nhỏ hơn (tốt hơn) được chọn
    2. Nếu rank bằng nhau, crowing distance lớn hơn (tức đa dạng hơn) được chọn
    """
    tourn = random.sample(pop, tour_size)
    while len(tourn) > 1:
        i1, i2 = random.sample(tourn, 2)
        if i1.rank < i2.rank:
            tourn.remove(i2)
        elif i2.rank < i1.rank:
            tourn.remove(i1)
        else:
            if i1.distance > i2.distance:
                tourn.remove(i2)
            else:
                tourn.remove(i1)
    return tourn[0]

def nsga2_sv_selection(combined_pop: list[Individual], pop_size: int) -> list[Individual]:
    """Chọn lọc sinh tồn đủ số cá thể cho quần thể từ quần thể kết hợp"""
    fronts = apply_fast_non_dominated_sorting(combined_pop)
    new_pop = []
    
    for front in fronts:
        assign_crowding_distance(front)
        front.sort(key=lambda x: x.distance, reverse=True)
        
        if len(new_pop) + len(front) <= pop_size:
            new_pop.extend(front)
        else:
            needs = pop_size - len(new_pop)
            new_pop.extend(front[:needs])
            break
    
    return new_pop

# ---------------------------------------
# Genetic Programming Hyper Heuristic
# ---------------------------------------
def run_gphh_evolution(
        problem: Problem, 
        **kwargs: Any
    ) -> tuple[list[Individual], list[Individual], list[dict]]:
    
    seed = kwargs.get('seed', None)
    if seed is not None:
        random.seed(seed)
    pop_size = kwargs.get('pop_size', 50)
    c_rate = kwargs.get('c_rate', 0.8)
    m_rate = kwargs.get('m_rate', 0.2)
    max_depth = kwargs.get('max_depth', 6) # full depth for mutation, crossover
    tourn_s_size = kwargs.get('tourn_s_size', 4)
    max_gen = kwargs.get('max_generations', 20)
    assignment_n = kwargs.get('assignment_n', 1)
    time_slot = kwargs.get('assignment_n', 0)
    
    current_pop = create_greedy_pop(pop_size, max_depth=max_depth-1)
    
    for ind in current_pop:
        simulate_policy(ind, problem, assignment_n=assignment_n, time_slot=time_slot)
    
    # sắp xếp nhanh không trội để đạt được các pareto front và tính khoảng cách mật độ cho từng cá thể trong front
    initial_pareto_fronts = apply_fast_non_dominated_sorting(current_pop)
    for front in initial_pareto_fronts:
        assign_crowding_distance(front)
    
    stats_history = []
    initial_best_f1 = max(current_pop, key=lambda x: x.f1)
    initial_best_f2 = max(current_pop, key=lambda x: x.f2)
    
    stats = {
        "gen": 0,
        "best_served_ratio": initial_best_f1.f1,
        "best_makespan_score": initial_best_f2.f2
    }
    stats_history.append(stats)
    
    for gen in range(1, max_gen + 1):
        offspring = []
        
        while len(offspring) < pop_size:
            p1 = nsga2_tourn_selection(current_pop, tour_size=tourn_s_size)
            p2 = nsga2_tourn_selection(current_pop, tour_size=tourn_s_size)
            
            if random.random() < c_rate:
                c1, c2 = perform_crossover(p1, p2, max_depth)
            else:
                c1 = p1
                c2 = p2
            if random.random() < m_rate: c1 = apply_mutation(c1, max_depth)
            if random.random() < m_rate: c2 = apply_mutation(c2, max_depth)
                
            offspring.extend([c1, c2])
        
        offspring = offspring[:pop_size]
        
        # Đánh giá offspring
        for ind in offspring:
            simulate_policy(ind, problem)
        
        combined_pop = current_pop + offspring
        
        current_pop = nsga2_sv_selection(combined_pop, pop_size)
        
        current_pareto_fronts = apply_fast_non_dominated_sorting(current_pop)
        for front in current_pareto_fronts:
            assign_crowding_distance(front)
            
        # Thống kê
        current_best_f1 = max(current_pop, key=lambda x: x.f1)
        current_best_f2 = max(current_pop, key=lambda x: x.f2)
        
        stats = {
            "gen": gen,
            "best_served_ratio": current_best_f1.f1,
            "best_makespan_score": current_best_f2.f2
        }
        stats_history.append(stats)
        
        print(f"Gen {gen:3d} | Best Served Ratio: {current_best_f1.f1:.3f} | Best Makespan Score: {current_best_f2.f2:.3f}")
        
    # Trả về quần thể cuối cùng và Pareto Front
    fronts = apply_fast_non_dominated_sorting(current_pop)
    first_front = fronts[0]
    
    # best_f1 = min(first_front, key=lambda x: x.f1).f1
    # best_f2 = min(first_front, key=lambda x: x.f2).f2
    best_f1 = max(first_front, key=lambda x: x.f1).f1
    best_f2 = max(first_front, key=lambda x: x.f2).f2
    
    # return current_pop, first_front, stats_history
    
    # --- LOGIC TÌM CÁ THỂ TỐT NHẤT VÀ IN ROUTE ---
    best_ind = None
    min_dist = float('inf')

    for ind in first_front:
        dist = math.sqrt(((best_f1- ind.f1)/best_f1)**2 + ((best_f2 - ind.f2)/best_f2)**2)
        if dist < min_dist:
            min_dist = dist
            best_ind = ind

    if best_ind:
        # Chạy lại mô phỏng một lần cuối cho cá thể tốt nhất để lấy dữ liệu route
        final_results = simulate_policy(best_ind, problem)
        sim_pro = final_results['simulated_problem']

        print("\n" + "="*50)
        print("LOG LỘ TRÌNH CÁ THỂ TỐT NHẤT (BEST DISTANCE TO IDEAL)")
        print(f"Khoảng cách tới điểm lý tưởng: {min_dist:.4f}")
        print(f"Served Ratio (f1): {best_ind.f1:.2%}")
        print(f"Makespan Score (f2): {best_ind.f2:.4f}")
        print("-" * 50)

        for v in sim_pro.vehicles:
            print(f"Vehicle {v.id} [{v.type}]:")
            if not v.routes or (len(v.routes) == 1 and not v.routes[0]):
                print("  - Không thực hiện nhiệm vụ nào.")
            else:
                for i, trip in enumerate(v.routes):
                    route_str = " -> ".join(map(str, trip))
                    print(f"  Chuyến {i+1}: Depot -> {route_str} -> Depot")
            print(f"  Thời gian hoàn thành: {v.busy_until:.2f}")
            print("-" * 30)
        print("="*50 + "\n")

    return current_pop, first_front, stats_history
        
                
    
    