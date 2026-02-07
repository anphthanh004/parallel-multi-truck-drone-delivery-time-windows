import argparse
import random
import numpy as np
import os
import sys
import yaml  
import time

from src.GP_Solution.problem_structures import Problem
from src.GP_Solution.nsga2_optimizer import NSGA2Optimizer
from src.utils.results_handler import save_results

def set_seed(seed_value):
    random.seed(seed_value)
    np.random.seed(seed_value)

def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"Lỗi: Không tìm thấy file config tại {config_path}")
        sys.exit(1)
    with open(config_path, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(f"Lỗi định dạng YAML: {exc}")
            sys.exit(1)

def run_single_case(file_name_stem, args, base_config):
    """
    Hàm chạy optimization cho 1 trường hợp data cụ thể.
    file_name_stem: Tên file không đuôi (vd: '6.10.1')
    """
    # 1. Tạo bản sao config để không bị ghi đè khi chạy loop
    current_config = base_config.copy()
    
    # 2. Xác định Config File riêng cho data này
    folder_path = 'configs'
    config_prefix = file_name_stem.split('.')[0]
    priority_path = os.path.join(folder_path, f'config_{config_prefix}.yaml')
    default_path = os.path.join(folder_path, 'default_config.yaml')
    
    config_path = None
    if os.path.exists(priority_path):
        config_path = priority_path
        print(f"--> [Config] Found specific: {config_path}")
    elif os.path.exists(default_path):
        config_path = default_path
        print(f"--> [Config] Using default: {config_path}")
    
    # Load config từ file YAML nếu có
    if config_path:
        yaml_config = load_config(config_path)
        for key, value in yaml_config.items():
            if key in current_config: 
                current_config[key] = value
                     
    # Override config bằng arguments từ command line
    arg_dict = vars(args)
    for key, value in arg_dict.items():
        if value is not None and key != 'file_name':
            current_config[key] = value

    
    set_seed(current_config['seed'])
    
    print(f"\nProcessing Data: {file_name_stem}.json")
    print(f"Params: Pop={current_config['pop_size']}, Gen={current_config['max_gen']}, Seed={current_config['seed']}")

    # 3. Load Data
    data_path = f'data/WithTimeWindows/{file_name_stem}.json'
    if not os.path.exists(data_path):
        print(f"Skipping: File {data_path} not found.")
        return

    try:
        problem_instance = Problem.load_from_file(data_path)
    except Exception as e:
        print(f"Lỗi khi load data {file_name_stem}: {e}")
        return

    # 4. Khởi tạo Optimizer Object
    optimizer = NSGA2Optimizer(
        pop_size=current_config['pop_size'],
        max_gen=current_config['max_gen'],       
        max_depth=current_config['max_depth'],
        c_rate=current_config['c_rate'],
        m_rate=current_config['m_rate'],
        tourn_size=current_config['tourn_size'],
        seed=current_config['seed']
    )
    
    start_time = time.time()
    
    # 5. Evolve
    results_dict = optimizer.evolve(
        problem=problem_instance,
        assignment_n=current_config['assignment_n']
    )
    
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"--> Thời gian chạy: {execution_time:.4f} giây")
    
    # 6. Kết quả
    final_pop = results_dict["final_pop"]
    first_front = results_dict["pareto_front"]
    pareto_count = results_dict["pareto_count"]
    final_results = results_dict["best_results"]

    first_front.sort(key=lambda x: x.f1, reverse=True)
    close_time = problem_instance.depot_time_window[1]


    # 7. Save results
    save_results(
        results_number=args.results_number,
        folder_name=file_name_stem, 
        final_results=final_results,
        pareto_count=pareto_count,
        final_pop=final_pop,
        execution_time=execution_time
    )
    print("-" * 50)

def main():
    parser = argparse.ArgumentParser(description="GPHH Runner")
    parser.add_argument('file_name', type=str, help='Tên file yaml hoặc "all" để chạy hết')
    parser.add_argument('-rsn', '--results_number', type=int, help='Lần chạy kết quả')
    parser.add_argument('--pop_size', type=int)
    parser.add_argument('--max_gen', type=int)
    parser.add_argument('--max_depth', type=int)
    parser.add_argument('--c_rate', type=float)
    parser.add_argument('--m_rate', type=float)
    parser.add_argument('--tourn_size', type=int)
    parser.add_argument('-asn','--assignment_n', type=int)
    parser.add_argument('--seed', type=int)

    args = parser.parse_args()

    # Cấu hình mặc định
    base_config = {
        'pop_size': 50,
        'max_gen': 80,
        'max_depth': 5,
        'c_rate': 0.8,
        'm_rate': 0.2,
        'tourn_size': 4,
        'seed': 42,
        'assignment_n': 1,
    }

    print("\n" + "="*50)
    print(f"BẮT ĐẦU CHẠY GPHH - Mode: {args.file_name.upper()}")
    print("="*50)

    # --- LOGIC CHỌN MODE ---
    if args.file_name.lower() == 'all':
        data_dir = 'data/WithTimeWindows'
        if not os.path.exists(data_dir):
            print(f"Error: Directory {data_dir} not found.")
            sys.exit(1)
            
        # Lấy tất cả file .json
        files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        files.sort(key=lambda x: int(x.split('.')[0]))
        
        print(f"Tìm thấy {len(files)} file dữ liệu.")
        
        for idx, f in enumerate(files):
            file_stem = f.replace('.json', '')
            print(f"\n[{idx+1}/{len(files)}] Running {file_stem}...")
            run_single_case(file_stem, args, base_config)
            
    else:
        file_stem = args.file_name.replace('.json', '')
        run_single_case(file_stem, args, base_config)

if __name__ == "__main__":
    main()
    
# chạy 1 file: python main.py 6.10.1 -rsn 1
# chạy toàn bộ file: python main.py all -rsn 1
# chạy toàn bộ nhưng override tham số: python main.py all -rsn 2 --gen 200