import json
import os
import yaml
from typing import Optional, Literal
from ..GP_Solution.gp_structure import Individual
from ..GP_Solution.problem_structures import Problem, Vehicle

def save_results(
    folder_name: str,
    solution_type: Literal['with_time_slot', 'without_time_slot'],
    final_results: dict,  # Kết quả từ simulate_policy(best_ind, problem)
    pop_history: list[list[Individual]],  # Lịch sử pop mỗi gen
    stats_history: list[dict],  # Stats best mỗi gen
    config: dict
) -> None:

    base_dir = f"results2/{solution_type}/{folder_name}/"
    os.makedirs(base_dir, exist_ok=True)

    # 1. Lưu last_config.yaml
    config_path = os.path.join(base_dir, "last_config.yaml")
    with open(config_path, 'w') as f:
        # default_flow_style=False giúp file yaml dễ đọc hơn (dạng block thay vì inline)
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    # 2. Lưu best_indi.json
    sim_pro: Problem = final_results['simulated_problem']
    last_ind_data = {
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

    # 3. lưu vào generations.json
    population_data = {"generations": []}
    for gen_idx, pop_gen in enumerate(pop_history):
        gen_data = {
            "gen": stats_history[gen_idx]["gen"],
            "best_served_ratio": stats_history[gen_idx]["best_served_ratio"],
            "best_makespan_score": stats_history[gen_idx]["best_makespan_score"],
            "individuals": [
                {
                    "r_tree": ind.r_tree.to_string(),
                    "s_tree": ind.s_tree.to_string(),
                    "served_ratio": ind.f1,
                    "makespan_score": ind.f2
                }
                for ind in pop_gen
            ]
        }
        population_data["generations"].append(gen_data)

    with open(os.path.join(base_dir, "generations.json"), 'w') as f:
        json.dump(population_data, f, indent=4)

    print(f"Kết quả đã lưu vào: {base_dir}")