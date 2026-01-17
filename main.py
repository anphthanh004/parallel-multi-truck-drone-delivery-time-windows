import argparse
import random
import numpy as np
import os
import sys
import yaml  
from pathlib import Path

from src.GP_Solution.load_data import load_data
from src.GP_Solution.nsga2_algorithm import run_gphh_evolution
from src.GP_Solution.problem_structures import Problem
from src.utils.results_handler import save_results

def set_seed(seed_value):
    random.seed(seed_value)
    np.random.seed(seed_value)

def load_config(config_path):
    """Đọc file YAML và trả về dictionary"""
    if not os.path.exists(config_path):
        print(f"Lỗi: Không tìm thấy file config tại {config_path}")
        sys.exit(1)
    with open(config_path, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(f"Lỗi định dạng YAML: {exc}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="GPHH Runner with Config File")
    
    parser.add_argument('file_name', type=str, help='Tên file yaml')

    # Các tham số khác (Có thể override)
    parser.add_argument('--data', type=str)
    parser.add_argument('--pop_size', type=int)
    parser.add_argument('--gen', type=int)
    parser.add_argument('--max_depth', type=int)
    parser.add_argument('--c_rate', type=float)
    parser.add_argument('--m_rate', type=float)
    parser.add_argument('--tourn_size', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('-asn','--assignment_n', type=int)
    # parser.add_argument('-ts','--time_slot', type=int, default=0)
    # nargs='?': 0 hoặc 1 giá trị
    # const=-1: Giá trị nhận được nếu chỉ gõ --ts (hoặc -ts) mà không nhập số
    parser.add_argument('-ts','--time_slot', type=int, nargs='?', const=-1, default=None)

    args = parser.parse_args()

    # --- LOGIC XỬ LÝ CẤU HÌNH ---
    # 1. Cấu hình mặc định (Fallback)
    config = {
        'data': 'data/WithTimeWindows3/6.5.1.json',
        'pop_size': 50,
        'gen': 50,
        'max_depth': 6,
        'c_rate': 0.8,
        'm_rate': 0.2,
        'tourn_size': 4,
        'seed': 42,
        'assignment_n': 1,
        'time_slot': 0
    }
    
    # 2. Nếu có file config, load và ghi đè mặc định
    file_path = f'config/{args.file_name}.yaml'
    print(f"Đang đọc cấu hình từ: {file_path}")
    yaml_config = load_config(file_path)
    for key, value in yaml_config.items():
        if key in config:
            config[key] = value

    # 3. Nếu có tham số dòng lệnh, ghi đè tiếp (Override cao nhất)
    arg_dict = vars(args)
    for key, value in arg_dict.items():
        # if key != 'config' and value is not None:
        if value is not None and key != 'time_slot':
            config[key] = value
    
    # if not args.time_slot:
    #     config['time_slot'] = 0

    if args.time_slot is None:
        # Trường hợp 1: Không nhập -ts -> Mặc định về 0 
        config['time_slot'] = 0 
    elif args.time_slot == -1:
        # Trường hợp 2: Nhập -ts (nhưng không số) -> Giữ nguyên giá trị đã load từ YAML
        pass 
    else:
        # Trường hợp 3: Nhập -ts 1000 -> Ghi đè bằng giá trị nhập vào
        config['time_slot'] = args.time_slot
    
    # --- BẮT ĐẦU CHẠY ---
    set_seed(config['seed'])
    
    print("\n" + "="*50)
    print(f"BẮT ĐẦU CHẠY GPHH")
    print(f"Data:      {config['data']}")
    print(
            f"Settings: Pop={config['pop_size']}, \
            Gen={config['gen']}, \
            Depth={config['max_depth']}"
        )
    print(
            f"C_RATE={config['c_rate']}, \
            M_RATE={config['m_rate']}, \
            TOURN_SIZE={config['tourn_size']},\
            SEED={config['seed']},\
            ASSIGNMENT_N = {config['assignment_n']},\
            TIME_SLOT = {config['time_slot']}"
        )
    print("="*50 + "\n")

    # Load Data
    if not os.path.exists(config['data']):
        print(f"Lỗi: File dữ liệu không tồn tại: {config['data']}")
        sys.exit(1)
        
    try:
        problem_instance = load_data(config['data'])
    except Exception as e:
        print(f"Lỗi khi load data: {e}")
        sys.exit(1)
    # final_pop, first_front, history, pop_history, best_ind, final_results
    # final_pop, first_front, history 
    final_pop, first_front, history, pop_history, best_ind, final_results= run_gphh_evolution(
        problem_instance,
        pop_size=config['pop_size'],
        max_generations=config['gen'],
        max_depth=config['max_depth'],
        c_rate=config['c_rate'],
        m_rate=config['m_rate'],
        tourn_s_size=config['tourn_size'],
        seed=config['seed'],
        assignment_n=config['assignment_n'],
        time_slot=config['time_slot']
    )

    # Print Results
    print("\n" + "="*50)
    print(f"KẾT QUẢ")
    print("="*50)
    
    first_front.sort(key=lambda x: x.f1, reverse=True)
    close_time = problem_instance.depot_time_window[1]

    for i, ind in enumerate(first_front):
        served_reqs = int(ind.f1 * len(problem_instance.requests))
        raw_makespan = (1.0 - ind.f2) * close_time
        print(f"#{i+1}: Served: {served_reqs} ({ind.f1:.2%}) | Makespan: {raw_makespan:.4f} (Score: {ind.f2:.4f})")
    
    save_results(
        file_name=args.file_name, 
        final_results=final_results, 
        pop_history=pop_history, 
        stats_history=history, 
    )
    
if __name__ == "__main__":
    main()