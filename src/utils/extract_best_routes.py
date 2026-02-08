import os
import json
import sys
import math

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

from GP_Solution.problem_structures import Problem
from GP_Solution.gp_structure import Individual
from GP_Solution.initializer import PopulationInitializer
from GP_Solution.simulator import Simulator


RESULT_FOLDERS = ['results20', 'results21', 'results22', 'result23', 'result24', 'results25']

BASE_DIR = os.path.dirname(src_dir) 
DATA_DIR = os.path.join(BASE_DIR, "data", "WithTimeWindows")
OUTPUT_BASE_DIR = os.path.join(BASE_DIR, "output")


def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_pareto_front_from_results(simulated_results):
    """
    Lọc Pareto Front từ danh sách kết quả ĐÃ CHẠY SIMULATION.
    simulated_results: list of dict {'served':..., 'makespan':..., 'vehicles':...}
    """
    if not simulated_results:
        return []
        
    # 1. Sắp xếp giảm dần theo served, tăng dần theo makespan để dễ xử lý
    # (Optional, nhưng giúp thuật toán ổn định hơn)
    simulated_results.sort(key=lambda x: (-x['served'], x['makespan']))

    pareto_front = []
    
    for i, res_a in enumerate(simulated_results):
        is_dominated = False
        for j, res_b in enumerate(simulated_results):
            if i == j: continue
            
            # B dominates A nếu:
            # B served >= A served  VÀ  B makespan <= A makespan
            # VÀ (B served > A served HOẶC B makespan < A makespan)
            
            b_better_served = res_b['served'] >= res_a['served']
            b_better_time = res_b['makespan'] <= res_a['makespan']
            
            # Strict inequality check
            b_strictly_better = (res_b['served'] > res_a['served']) or (res_b['makespan'] < res_a['makespan'])
            
            if b_better_served and b_better_time and b_strictly_better:
                is_dominated = True
                break
        
        if not is_dominated:
            pareto_front.append(res_a)
            
    # Sắp xếp lại lần cuối để in ra đẹp: Served giảm dần, Makespan tăng dần
    pareto_front.sort(key=lambda x: (-x['served'], x['makespan']))
    return pareto_front

def format_trip_list(trip_routes):
    path = [0] 
    for step in trip_routes:
        if step['action'] == 'pickup':
            path.append(step['req_id'])
    path.append(0)
    return str(path)


def process_instances():
    print(f"Working Directory: {BASE_DIR}")
    ensure_dir(OUTPUT_BASE_DIR)
    
    instances = set()
    for res_folder in RESULT_FOLDERS:
        path = os.path.join(BASE_DIR, res_folder)
        if os.path.exists(path):
            subs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
            instances.update(subs)

    sorted_instances = sorted(list(instances))
    print(f"Found {len(sorted_instances)} instances.")

    if not sorted_instances:
        return

    for instance_name in sorted_instances:
        print(f"\n>>> Processing {instance_name}...")
        
        # 1. GOM DỮ LIỆU THÔ (Chưa lọc Pareto vội, chỉ lọc trùng Tree để đỡ tốn công chạy Sim)
        unique_trees_data = {} # Key: (r_tree_str, s_tree_str) -> Value: ind_data
        
        for res_folder in RESULT_FOLDERS:
            folder_path = os.path.join(BASE_DIR, res_folder, instance_name)
            fname = "population.json"
            fpath = os.path.join(folder_path, fname)
            if os.path.exists(fpath):
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                extracted = []
                extracted = data["individuals"]
                # Lưu vào dict để khử trùng lặp cây ngay từ đầu
                for ind in extracted:
                    key = (ind['r_tree'], ind['s_tree'])
                    if key not in unique_trees_data:
                        unique_trees_data[key] = ind
                        
        if not unique_trees_data:
            print(f"    [FAIL] No valid data found.")
            continue
            
        # Load Problem
        problem_file = os.path.join(DATA_DIR, f"{instance_name}.json")
        if not os.path.exists(problem_file):
            print(f"    [FAIL] Missing Data: {problem_file}")
            continue
        
        try:
            problem = Problem.load_from_file(problem_file)
        except Exception as e:
            print(f"    [FAIL] Load Problem Error: {e}")
            continue

        # 2. CHẠY SIMULATION CHO TẤT CẢ CÁC CÂY KHÁC NHAU
        # Mục đích: Lấy số liệu Served/Makespan mới (thuật toán mô phỏng là ánh xạ Ncây<->1route nên không có sai số hay random)
        simulated_candidates = []
        seen_phenotypes = set() # Lọc trùng kết quả lộ trình
        
        
        for (r_str, s_str), ind_data in unique_trees_data.items():
            try:
                r_tree = PopulationInitializer.build_tree_from_string(r_str, 'R')
                s_tree = PopulationInitializer.build_tree_from_string(s_str, 'S')
                individual = Individual(r_tree, s_tree)
                
                sim = Simulator(problem, individual, assignment_n=1, enable_logging=False)
                result = sim.run()
                
                simulated_problem = result['simulated_problem']
                sorted_vehicles = sorted(simulated_problem.vehicles, key=lambda v: v.id)
                
                vehicles_output_data = []
                signature_parts = []
                
                truck_idx = 1
                drone_idx = 1
                
                for veh in sorted_vehicles:
                    has_trip = any(trip for trip in veh.routes)
                    if has_trip:
                        if veh.type == 'TRUCK':
                            v_name = f"Truck {truck_idx}"
                            truck_idx += 1
                        else:
                            v_name = f"Drone {drone_idx}"
                            drone_idx += 1
                        
                        trips_str_list = []
                        for trip in veh.routes:
                            if trip:
                                route_str = format_trip_list(trip)
                                trips_str_list.append(route_str)
                        
                        # Dữ liệu để in
                        vehicles_output_data.append((v_name, trips_str_list))
                        # Dữ liệu để lọc trùng (Signature)
                        signature_parts.append(f"{v_name}:" + ";".join(trips_str_list))
                
                current_signature = "|".join(signature_parts)
                
                # Lọc trùng Phenotype (Lộ trình y hệt nhau)
                if current_signature in seen_phenotypes:
                    continue
                seen_phenotypes.add(current_signature)
                
                # Lưu kết quả "tươi" vào danh sách ứng viên
                simulated_candidates.append({
                    'served': result['served'],
                    'makespan': result['makespan'],
                    'vehicles': vehicles_output_data
                })
                
            except Exception as e:
                pass

        # 3. LỌC PARETO TRÊN KẾT QUẢ THỰC TẾ
        final_pareto_solutions = get_pareto_front_from_results(simulated_candidates)

        # 4. GHI FILE
        output_file_path =  os.path.join(OUTPUT_BASE_DIR, f"{instance_name}_output.txt")
        try:
            if final_pareto_solutions:
                with open(output_file_path, "w", encoding="utf-8") as f_out:
                    f_out.write(f"Pareto Count: {len(final_pareto_solutions)}\n")
                    
                    for idx, sol in enumerate(final_pareto_solutions):
                        f_out.write(f"Solution {idx + 1}:\n")
                        f_out.write(f"    Served: {sol['served']}\n")
                        f_out.write(f"    Makespan: {sol['makespan']}\n")
                        
                        for v_name, trips in sol['vehicles']:
                            f_out.write(f"    {v_name}: \n")
                            for t_str in trips:
                                f_out.write(f"        {t_str}\n")
                
                print(f"    -> [OK] Saved {len(final_pareto_solutions)} TRUE PARETO solutions to {output_file_path}")
            else:
                print(f"    -> [FAIL] No solutions found after simulation.")
                
        except Exception as e:
             print(f"    [FAIL] Write File Error: {e}")

if __name__ == "__main__":
    process_instances()