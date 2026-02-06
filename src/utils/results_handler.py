import json
import os
import yaml
from typing import Optional, Literal
from ..GP_Solution.gp_structure import Individual
from ..GP_Solution.problem_structures import Problem, Vehicle

def save_results(
    results_number: Optional[int],
    folder_name: str,
    # solution_type: Literal['with_time_slot', 'without_time_slot'],
    final_results: dict,  # Kết quả từ simulate_policy(best_ind, problem)
    pareto_count: Optional[int] = None,
    final_pop: Optional[list[Individual]] = None,
    execution_time: float = 0.0
    # pop_history: list[list[Individual]],  # Lịch sử pop mỗi gen
    # stats_history: list[dict],  # Stats best mỗi gen
    # config: dict
) -> None:

    # base_dir = f"results/{solution_type}/{folder_name}/"
    if results_number is not None:
        base_dir = f"results{results_number}/{folder_name}/"
    else: 
        base_dir = f"results/{folder_name}/"
    os.makedirs(base_dir, exist_ok=True)

    # # 1. Lưu last_config.yaml
    # config_path = os.path.join(base_dir, "last_config.yaml")
    # with open(config_path, 'w') as f:
    #     # default_flow_style=False giúp file yaml dễ đọc hơn (dạng block thay vì inline)
    #     yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    # 2. Lưu best_indi.json
    sim_pro: Problem = final_results['simulated_problem']
    last_ind_data = {
        "execution_time": execution_time,
        "served": final_results['served'],
        "dropped": final_results['unserved'],
        "makespan": final_results['makespan'],
        "routing_tree": final_results['r_tree'],
        "sequencing_tree": final_results['s_tree'],
        "vehicles": [
            {
                "id": veh.id,
                "type": veh.type,
                "routes": veh.routes, 
                "makespan": veh.busy_until
            }
            for veh in sim_pro.vehicles
        ]
    }
    with open(os.path.join(base_dir, "best_indi.json"), 'w') as f:
        json.dump(last_ind_data, f, indent=4)
        
    # 3. Lưu population.json
    sorted_pop = sorted(final_pop, key=lambda x: x.rank)

    population_data = {
        "pareto_count": pareto_count,
        "individuals": []
    }

    for ind in sorted_pop:
        r_str = ind.r_tree.to_string() if hasattr(ind.r_tree, 'to_string') else str(ind.r_tree)
        s_str = ind.s_tree.to_string() if hasattr(ind.s_tree, 'to_string') else str(ind.s_tree)

        ind_data = {
            "r_tree": r_str,
            "s_tree": s_str,
            "served_ratio": ind.f1,         
            "makespan_score": ind.f2,        
            "rank": ind.rank                
        }
        population_data["individuals"].append(ind_data)

    with open(os.path.join(base_dir, "population.json"), 'w') as f:
        json.dump(population_data, f, indent=4)
    
    print(f"Đã lưu population.json với {len(sorted_pop)} cá thể.")

    # # 3. lưu vào generations.json
    # population_data = {"generations": []}
    # for gen_idx, pop_gen in enumerate(pop_history):
    #     gen_data = {
    #         "gen": stats_history[gen_idx]["gen"],
    #         "best_served_ratio": stats_history[gen_idx]["best_served_ratio"],
    #         "best_makespan_score": stats_history[gen_idx]["best_makespan_score"],
    #         "individuals": [
    #             {
    #                 "r_tree": ind.r_tree.to_string(),
    #                 "s_tree": ind.s_tree.to_string(),
    #                 "served_ratio": ind.f1,
    #                 "makespan_score": ind.f2
    #             }
    #             for ind in pop_gen
    #         ]
    #     }
    #     population_data["generations"].append(gen_data)

    log_events = final_results.get('log_events')
    with open(os.path.join(base_dir, "log_events.txt"), 'w') as f:  # 'w' để overwrite, hoặc 'a' để append nếu multi-run
        f.write("\n".join(log_events) + "\n")  # Mỗi log 1 dòng
    
    print(f"Kết quả đã lưu vào: {base_dir}")
    