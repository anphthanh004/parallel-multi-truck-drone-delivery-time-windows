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

def get_file_key(filename):
    """
    Hàm hỗ trợ sort: Chuyển tên file '6.10.1.json' thành tuple (6, 10, 1)
    để so sánh chính xác thứ tự numeric.
    """
    stem = filename.replace('.json', '')
    try:
        # Tách các phần tử bởi dấu chấm và chuyển sang int
        return [int(p) for p in stem.split('.') if p.isdigit()]
    except ValueError:
        # Fallback nếu tên file có chứa ký tự lạ không phải số
        return [0]


# def main():
#     parser = argparse.ArgumentParser(description="GPHH Runner")
#     parser.add_argument('file_name', type=str, help='Tên file yaml hoặc "all" để chạy hết')
#     parser.add_argument('--start', type=str, help='Tên file bắt đầu (VD: 6.5.1)')
#     parser.add_argument('--end', type=str, help='Tên file kết thúc (VD: 10.5.1)')
#     parser.add_argument('-rsn', '--results_number', type=int, help='Lần chạy kết quả')
#     parser.add_argument('--pop_size', type=int)
#     parser.add_argument('--max_gen', type=int)
#     parser.add_argument('--max_depth', type=int)
#     parser.add_argument('--c_rate', type=float)
#     parser.add_argument('--m_rate', type=float)
#     parser.add_argument('--tourn_size', type=int)
#     parser.add_argument('-asn','--assignment_n', type=int)
#     parser.add_argument('--seed', type=int)

#     args = parser.parse_args()

#     # Cấu hình mặc định
#     base_config = {
#         'pop_size': 50,
#         'max_gen': 80,
#         'max_depth': 5,
#         'c_rate': 0.8,
#         'm_rate': 0.2,
#         'tourn_size': 4,
#         'seed': 42,
#         'assignment_n': 1,
#     }

#     print("\n" + "="*50)
#     print(f"BẮT ĐẦU CHẠY GPHH - Mode: {args.file_name.upper()}")
#     print("="*50)

#     # --- LOGIC XỬ LÝ MODE ---
    
#     # Mode chạy 1 file cụ thể (không phải 'all' và không phải 'range')
#     if args.file_name.lower() not in ['all', 'range']:
#         file_stem = args.file_name.replace('.json', '')
#         run_single_case(file_stem, args, base_config)
#         return

#     # Mode chạy danh sách ('all' hoặc 'range')
#     data_dir = 'data/WithTimeWindows'
#     if not os.path.exists(data_dir):
#         print(f"Error: Directory {data_dir} not found.")
#         sys.exit(1)
        
#     # 1. Lấy và Sort file chuẩn xác (Numeric Sort)
#     files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
#     files.sort(key=get_file_key) # Sử dụng hàm sort mới
    
#     # 2. Xử lý lọc danh sách file cần chạy
#     files_to_run = []
    
#     if args.file_name.lower() == 'all':
#         files_to_run = files
        
#     elif args.file_name.lower() == 'range':
#         if not args.start:
#             print("Lỗi: Mode 'range' yêu cầu tham số --start")
#             sys.exit(1)
            
#         start_file = args.start if args.start.endswith('.json') else f"{args.start}.json"
#         end_file = (args.end if args.end.endswith('.json') else f"{args.end}.json") if args.end else None
        
#         # Kiểm tra file start có tồn tại không
#         if start_file not in files:
#             print(f"Lỗi: Không tìm thấy file bắt đầu '{start_file}' trong data.")
#             # Gợi ý file gần đúng nếu cần, hoặc in list file đầu
#             print(f"File đầu tiên có sẵn: {files[0]}")
#             sys.exit(1)

#         start_idx = files.index(start_file)
#         end_idx = len(files) # Mặc định chạy đến hết

#         if end_file:
#             if end_file not in files:
#                 print(f"Lỗi: Không tìm thấy file kết thúc '{end_file}'")
#                 sys.exit(1)
#             # +1 để bao gồm cả file end
#             end_idx = files.index(end_file) + 1 
            
#             if end_idx <= start_idx:
#                 print("Lỗi: File kết thúc phải nằm sau file bắt đầu.")
#                 sys.exit(1)

#         files_to_run = files[start_idx:end_idx]

#     print(f"Đã tìm thấy {len(files_to_run)} file phù hợp để chạy.")
    
#     # 3. Vòng lặp chạy thực nghiệm
#     for idx, f in enumerate(files_to_run):
#         file_stem = f.replace('.json', '')
#         print(f"\n[{idx+1}/{len(files_to_run)}] Running {file_stem}...")
#         run_single_case(file_stem, args, base_config)

# if __name__ == "__main__":
#     main()

def main():
    parser = argparse.ArgumentParser(description="GPHH Runner")
    # nargs='+' để nhận 1 hoặc nhiều tên file
    parser.add_argument('file_names', nargs='+', help='Danh sách tên file, hoặc "all", hoặc "range"')
    
    parser.add_argument('--start', type=str, help='Tên file bắt đầu (VD: 6.5.1)')
    parser.add_argument('--end', type=str, help='Tên file kết thúc (VD: 10.5.1)')
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
    
    # Lấy mode từ phần tử đầu tiên của list inputs
    # Ví dụ: python main.py all -> mode = 'all'
    # Ví dụ: python main.py 6.10.1 6.10.2 -> mode = '6.10.1'
    first_arg = args.file_names[0].lower()

    print("\n" + "="*50)
    print(f"BẮT ĐẦU CHẠY GPHH - Input: {args.file_names}")
    print("="*50)

    data_dir = 'data/WithTimeWindows'
    files_to_run = []
    
    # --- LOGIC XỬ LÝ MODE ---

    # MODE 1: ALL hoặc RANGE
    if first_arg in ['all', 'range']:
        if not os.path.exists(data_dir):
            print(f"Error: Directory {data_dir} not found.")
            sys.exit(1)
            
        all_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        all_files.sort(key=get_file_key) 

        if first_arg == 'all':
            files_to_run = all_files
            
        elif first_arg == 'range':
            if not args.start:
                print("Lỗi: Mode 'range' yêu cầu tham số --start")
                sys.exit(1)
                
            start_file = args.start if args.start.endswith('.json') else f"{args.start}.json"
            end_file = (args.end if args.end.endswith('.json') else f"{args.end}.json") if args.end else None
            
            if start_file not in all_files:
                print(f"Lỗi: Không tìm thấy file bắt đầu '{start_file}'")
                sys.exit(1)

            start_idx = all_files.index(start_file)
            end_idx = len(all_files) 

            if end_file:
                if end_file not in all_files:
                    print(f"Lỗi: Không tìm thấy file kết thúc '{end_file}'")
                    sys.exit(1)
                end_idx = all_files.index(end_file) + 1 
                
                if end_idx <= start_idx:
                    print("Lỗi: File kết thúc phải nằm sau file bắt đầu.")
                    sys.exit(1)

            files_to_run = all_files[start_idx:end_idx]

    # MODE 2: CUSTOM LIST (Nhập trực tiếp danh sách file)
    else:
        files_to_run = args.file_names

    print(f"Đã tìm thấy {len(files_to_run)} file phù hợp để chạy.")
    
    for idx, f in enumerate(files_to_run):
        file_stem = f.replace('.json', '')
        
        full_path = os.path.join(data_dir, f"{file_stem}.json")
        if not os.path.exists(full_path):
             print(f"\n[WARNING] Không tìm thấy file: {full_path}. Bỏ qua.")
             continue

        print(f"\n[{idx+1}/{len(files_to_run)}] Running {file_stem}...")
        
        run_single_case(file_stem, args, base_config)

if __name__ == "__main__":
    main()


# chạy 1 file: python main.py 6.10.1 -rsn 1
# chạy toàn bộ file: python main.py all -rsn 1
# chạy toàn bộ nhưng override tham số: python main.py all -rsn 2 --gen 200
# python main.py range --start 6.5.1 --end 6.10.4 -rsn 1
# python main.py range --start 12.10.1 -rsn 1