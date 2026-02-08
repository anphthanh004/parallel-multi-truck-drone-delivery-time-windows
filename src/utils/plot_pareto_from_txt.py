# # import os
# # import re
# # import matplotlib.pyplot as plt
# # import sys
# # from matplotlib.ticker import MultipleLocator


# # def get_project_root():
# #     """
# #     Lấy thư mục gốc của dự án bằng cách đi ngược từ file hiện tại.
# #     """
# #     current_script_path = os.path.abspath(__file__)
# #     utils_dir = os.path.dirname(current_script_path) 
# #     src_dir = os.path.dirname(utils_dir)             
# #     root_dir = os.path.dirname(src_dir)              
# #     return root_dir

# # PROJECT_ROOT = get_project_root()

# # INPUT_DIR = os.path.join(PROJECT_ROOT, "output_P.T.An_20224911")      
# # OUTPUT_IMG_DIR = os.path.join(PROJECT_ROOT, "pareto") 


# # def ensure_dir(directory):
# #     if not os.path.exists(directory):
# #         os.makedirs(directory)

# # def read_pareto_data_from_txt(file_path):
# #     """
# #     Đọc file *_output.txt và trích xuất dữ liệu.
# #     Return: list of tuples (Makespan, Served)
# #     """
# #     solutions = []
# #     if not os.path.exists(file_path):
# #         print(f"[WARN] File not found: {file_path}")
# #         return []

# #     try:
# #         with open(file_path, 'r', encoding='utf-8') as f:
# #             content = f.read()
            
# #         # Regex: Tìm dòng "Served: <số>" và "Makespan: <số>"
# #         pattern = re.compile(r"Served:\s*([\d\.]+)\s+Makespan:\s*([\d\.]+)")
# #         matches = pattern.findall(content)
        
# #         for served_str, makespan_str in matches:
# #             # [FIX] Dùng int(float(...)) để an toàn nếu file ghi "40.0"
# #             served = int(served_str)     
# #             makespan = float(makespan_str) 
# #             solutions.append((makespan, served))
            
# #     except Exception as e:
# #         print(f"[ERR] Lỗi đọc file {file_path}: {e}")
        
# #     return solutions

# # def plot_pareto_front_min_max(instance_name, solutions):
# #     """
# #     Vẽ biểu đồ Pareto: Maximize Served (Y) vs Minimize Makespan (X).
# #     Phong cách: Chuyên nghiệp, Green Theme.
# #     """
# #     if not solutions:
# #         print(f"[SKIP] {instance_name}: Không có dữ liệu để vẽ.")
# #         return

# #     # Sắp xếp theo Makespan tăng dần (trục X - Minimize)
# #     solutions.sort(key=lambda x: x[0])
    
# #     makespans = [s[0] for s in solutions]
# #     serveds = [s[1] for s in solutions]

# #     # --- CẤU HÌNH PLOT ---
# #     plt.figure(figsize=(10, 7))
# #     ax = plt.gca() # Lấy đối tượng trục hiện tại (Axis)

# #     # 1. Vẽ đường nối (Pareto Frontier Line)
# #     plt.plot(makespans, serveds, linestyle='--', color='gray', alpha=0.6, label='Pareto Frontier Line')

# #     # 2. Vẽ các điểm (Solutions)
# #     plt.scatter(makespans, serveds, c='blue', marker='x', s=100, label='Solution', zorder=5)
    
# #     # 3. Trang trí trục
# #     plt.xlabel('Makespan (Minimize)', fontsize=12, fontweight='bold')
# #     plt.ylabel('Served Requests (Maximize)', fontsize=12, fontweight='bold')
    
# #     ax.yaxis.set_major_locator(MultipleLocator(1))


# #     plt.grid(True, which='both', linestyle=':', linewidth=0.5, alpha=0.7)
# #     plt.legend(loc='lower right', framealpha=0.9, shadow=True)
    
# #     # Title
# #     plt.title(f'Pareto Front - Instance: {instance_name}', fontsize=14, fontweight='bold', pad=15)

# #     # Lưu file
# #     output_filename = f"{instance_name}_pareto.png"
# #     output_path = os.path.join(OUTPUT_IMG_DIR, output_filename)
    
# #     plt.tight_layout()
# #     plt.savefig(output_path, dpi=300) # Xuất ảnh độ phân giải cao
# #     plt.close()
    
# #     print(f"[OK] Saved plot: {output_path}")


# # def process_all_pareto_plots():
# #     print(f"--- START PLOTTING (MAX SERVED / MIN MAKESPAN) ---")
# #     print(f"Root Dir:   {PROJECT_ROOT}")
# #     print(f"Input Dir:  {INPUT_DIR}")
# #     print(f"Output Dir: {OUTPUT_IMG_DIR}")
    
# #     ensure_dir(OUTPUT_IMG_DIR)

# #     if not os.path.exists(INPUT_DIR):
# #         print(f"[ERR] Thư mục output không tồn tại: {INPUT_DIR}")
# #         return

# #     # Quét file *_output.txt
# #     files = [f for f in os.listdir(INPUT_DIR) if f.endswith("_output.txt")]
    
# #     if not files:
# #         print("[WARN] Không tìm thấy file *_output.txt nào để vẽ.")
# #         return

# #     count = 0
# #     for file_name in files:
# #         # Tách tên instance
# #         instance_name = file_name.replace("_output.txt", "")
# #         file_path = os.path.join(INPUT_DIR, file_name)
        
# #         # 1. Đọc dữ liệu
# #         data = read_pareto_data_from_txt(file_path)
        
# #         # 2. Vẽ biểu đồ
# #         if data:
# #             plot_pareto_front_min_max(instance_name, data)
# #             count += 1
            
# #     print(f"--- COMPLETED: Processed {count} instances ---")

# # if __name__ == "__main__":
# #     process_all_pareto_plots()
# import os
# import re
# import sys
# import matplotlib.pyplot as plt
# from matplotlib.ticker import MultipleLocator

# # ---------------- CONFIGURATION ----------------
# def get_project_root():
#     current_script_path = os.path.abspath(__file__)
#     utils_dir = os.path.dirname(current_script_path)
#     src_dir = os.path.dirname(utils_dir)
#     root_dir = os.path.dirname(src_dir)
#     return root_dir

# PROJECT_ROOT = get_project_root()

# # Thư mục output cho chế độ đơn lẻ
# DEFAULT_INPUT_DIR = os.path.join(PROJECT_ROOT, "output_P.T.An_20224911")
# DEFAULT_OUTPUT_IMG_DIR = os.path.join(PROJECT_ROOT, "pareto")

# # Thư mục output cho chế độ so sánh
# COMPARE_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "pareto_comparison")

# # Định nghĩa các nguồn dữ liệu cần so sánh
# # Key: Tên hiển thị trên biểu đồ (Label)
# # Value: Tên thư mục chứa file output
# COMPARE_SOURCES = {
#     "P.T.An": "output_P.T.An_20224911",
#     "H.H.Hoang": "output_H.H.Hoang_20224988",
#     "L.S.Linh": "output_L.S.Linh_20225029"
# }

# # Màu sắc và kiểu đường cho từng người (để dễ phân biệt)
# STYLES = {
#     "P.T.An":    {"color": "blue",  "marker": "o", "linestyle": "-"},
#     "H.H.Hoang": {"color": "red",   "marker": "s", "linestyle": "--"},
#     "L.S.Linh":  {"color": "green", "marker": "^", "linestyle": "-."}
# }

# # ---------------- UTILS ----------------

# def ensure_dir(directory):
#     if not os.path.exists(directory):
#         os.makedirs(directory)

# def read_pareto_data_from_txt(file_path):
#     """
#     Đọc file *_output.txt và trích xuất dữ liệu.
#     Return: list of tuples (Makespan, Served)
#     """
#     solutions = []
#     if not os.path.exists(file_path):
#         return []

#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
            
#         # Regex tìm dòng "Served: <số> ... Makespan: <số>"
#         pattern = re.compile(r"Served:\s*([\d\.]+)\s+Makespan:\s*([\d\.]+)")
#         matches = pattern.findall(content)
        
#         for served_str, makespan_str in matches:
#             served = float(served_str)
#             makespan = float(makespan_str)
#             solutions.append((makespan, served))
            
#     except Exception as e:
#         print(f"[ERR] Lỗi đọc file {file_path}: {e}")
        
#     return solutions

# # ---------------- PLOTTING LOGIC ----------------

# def plot_single_pareto(instance_name, solutions, output_dir):
#     """Vẽ biểu đồ đơn (Code cũ)"""
#     if not solutions: return

#     solutions.sort(key=lambda x: x[0])
#     makespans = [s[0] for s in solutions]
#     serveds = [s[1] for s in solutions]

#     plt.figure(figsize=(10, 7))
#     ax = plt.gca()
    
#     plt.plot(makespans, serveds, linestyle='--', color='gray', alpha=0.6)
#     plt.scatter(makespans, serveds, c='blue', marker='x', s=100, label='Solution', zorder=5)
    
#     plt.xlabel('Makespan (Minimize)', fontsize=12, fontweight='bold')
#     plt.ylabel('Served Requests (Maximize)', fontsize=12, fontweight='bold')
#     ax.yaxis.set_major_locator(MultipleLocator(1))
#     plt.grid(True, linestyle=':', alpha=0.7)
#     plt.title(f'Pareto Front - {instance_name}', fontsize=14, fontweight='bold')
    
#     ensure_dir(output_dir)
#     output_path = os.path.join(output_dir, f"{instance_name}_pareto.png")
#     plt.tight_layout()
#     plt.savefig(output_path, dpi=300)
#     plt.close()
#     print(f"[OK] Saved: {output_path}")

# def plot_comparison_pareto(instance_name, all_data_dict):
#     """
#     Vẽ biểu đồ so sánh nhiều nguồn dữ liệu.
#     all_data_dict: { "P.T.An": [(makespan, served), ...], "H.H.Hoang": ... }
#     """
#     if not all_data_dict:
#         return

#     plt.figure(figsize=(12, 8))
#     ax = plt.gca()

#     # Vẽ từng đường dữ liệu
#     for label, solutions in all_data_dict.items():
#         if not solutions:
#             continue
            
#         # Sắp xếp theo Makespan (trục X) để vẽ đường nối liền mạch
#         solutions.sort(key=lambda x: x[0])
        
#         makespans = [s[0] for s in solutions]
#         serveds = [s[1] for s in solutions]
        
#         style = STYLES.get(label, {"color": "black", "marker": "o", "linestyle": "-"})
        
#         # Vẽ đường nối
#         plt.plot(makespans, serveds, 
#                  color=style["color"], 
#                  linestyle=style["linestyle"], 
#                  alpha=0.7, 
#                  label=f"{label} (Line)")
        
#         # Vẽ điểm
#         plt.scatter(makespans, serveds, 
#                     color=style["color"], 
#                     marker=style["marker"], 
#                     s=80, 
#                     label=f"{label} (Points)")

#     # Trang trí
#     plt.xlabel('Makespan (Minimize)', fontsize=12, fontweight='bold')
#     plt.ylabel('Served Requests (Maximize)', fontsize=12, fontweight='bold')
#     ax.yaxis.set_major_locator(MultipleLocator(1))
#     plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
    
#     plt.legend(loc='best', shadow=True, title="Solutions")
#     plt.title(f'Pareto Comparison - Instance: {instance_name}', fontsize=14, fontweight='bold', pad=15)

#     ensure_dir(COMPARE_OUTPUT_DIR)
#     output_path = os.path.join(COMPARE_OUTPUT_DIR, f"{instance_name}_compare.png")
    
#     plt.tight_layout()
#     plt.savefig(output_path, dpi=300)
#     plt.close()
#     print(f"[COMPARE] Saved: {output_path}")

# # ---------------- MAIN PROCESSORS ----------------

# def process_single_mode():
#     print(f"--- MODE: SINGLE PLOT ({DEFAULT_INPUT_DIR}) ---")
#     if not os.path.exists(DEFAULT_INPUT_DIR):
#         print(f"[ERR] Input dir not found: {DEFAULT_INPUT_DIR}")
#         return

#     files = [f for f in os.listdir(DEFAULT_INPUT_DIR) if f.endswith("_output.txt")]
#     for file_name in files:
#         instance_name = file_name.replace("_output.txt", "")
#         file_path = os.path.join(DEFAULT_INPUT_DIR, file_name)
#         data = read_pareto_data_from_txt(file_path)
#         if data:
#             plot_single_pareto(instance_name, data, DEFAULT_OUTPUT_IMG_DIR)

# def process_compare_mode():
#     print(f"--- MODE: COMPARISON PLOT (OPTIMIZED) ---")
#     print(f"Sources: {list(COMPARE_SOURCES.keys())}")
#     print(f"Output: {COMPARE_OUTPUT_DIR}")
    
#     # 1. TẠO TẬP HỢP CÁC FILE DUY NHẤT (Set Union)
#     # Thay vì duyệt theo người "nhiều file nhất", ta quét tất cả và gộp lại.
#     unique_instances = set()
    
#     print(">>> Scanning directories...")
#     for label, folder_name in COMPARE_SOURCES.items():
#         folder_path = os.path.join(PROJECT_ROOT, folder_name)
        
#         if os.path.exists(folder_path):
#             # Lấy tất cả file trong thư mục này
#             files = os.listdir(folder_path)
#             # Chỉ lấy file đúng định dạng _output.txt
#             valid_files = {f.replace("_output.txt", "") for f in files if f.endswith("_output.txt")}
#             # Gộp vào tập hợp chung (Set tự động loại bỏ trùng lặp)
#             unique_instances.update(valid_files)
#         else:
#             print(f"[WARN] Folder not found: {folder_path}")

#     if not unique_instances:
#         print("[WARN] No output files found in any source folder.")
#         return

#     print(f">>> Found {len(unique_instances)} unique instances. Processing...")

#     # 2. DUYỆT QUA DANH SÁCH DUY NHẤT
#     count_plotted = 0
    
#     # Sắp xếp tên instance để log chạy cho đẹp
#     for instance_name in sorted(list(unique_instances)):
        
#         # Dictionary chứa dữ liệu của các bên
#         instance_data = {} 
        
#         # 3. Thu thập dữ liệu (Chỉ đọc file nếu tồn tại)
#         for label, folder_name in COMPARE_SOURCES.items():
#             file_name = f"{instance_name}_output.txt"
#             file_path = os.path.join(PROJECT_ROOT, folder_name, file_name)
            
#             # Hàm đọc này đã có check os.path.exists bên trong nên rất an toàn
#             data = read_pareto_data_from_txt(file_path)
            
#             if data:
#                 instance_data[label] = data
        
#         # 4. LOGIC VẼ: 
#         # Chỉ vẽ nếu có dữ liệu. 
#         # TỐI ƯU: Nếu bạn chỉ muốn so sánh khi có ÍT NHẤT 2 người có kết quả -> đổi > 0 thành > 1
#         if len(instance_data) > 0: 
#             plot_comparison_pareto(instance_name, instance_data)
#             count_plotted += 1
            
#             # Optional: In tiến độ để đỡ sốt ruột
#             if count_plotted % 10 == 0:
#                 print(f"   Processed {count_plotted} charts...")
                
#     print(f"--- COMPLETED: Generated {count_plotted} comparison charts ---")

# if __name__ == "__main__":
#     # Kiểm tra tham số dòng lệnh
#     if len(sys.argv) > 1 and sys.argv[1].lower() == 'compare':
#         process_compare_mode()
#     else:
#         process_single_mode()

import os
import re
import sys
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# ---------------- CONFIGURATION ----------------
def get_project_root():
    current_script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(current_script_path)
    src_dir = os.path.dirname(utils_dir)
    root_dir = os.path.dirname(src_dir)
    return root_dir

PROJECT_ROOT = get_project_root()

# Thư mục output cho chế độ đơn lẻ
DEFAULT_INPUT_DIR = os.path.join(PROJECT_ROOT, "output_P.T.An_20224911")
DEFAULT_OUTPUT_IMG_DIR = os.path.join(PROJECT_ROOT, "pareto")

# Thư mục output cho chế độ so sánh
COMPARE_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "pareto_comparison")

# Định nghĩa các nguồn dữ liệu cần so sánh
COMPARE_SOURCES = {
    "P.T.An": "output_P.T.An_20224911",
    "H.H.Hoang": "output_H.H.Hoang_20224988",
    "L.S.Linh": "output_L.S.Linh_20225029"
}

# Màu sắc và kiểu đường
STYLES = {
    "P.T.An":    {"color": "blue",  "marker": "o", "linestyle": "-"},
    "H.H.Hoang": {"color": "red",   "marker": "s", "linestyle": "--"},
    "L.S.Linh":  {"color": "green", "marker": "^", "linestyle": "-."}
}

# ---------------- UTILS ----------------

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def read_pareto_data_from_txt(file_path):
    solutions = []
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = re.compile(r"Served:\s*([\d\.]+)\s+Makespan:\s*([\d\.]+)")
        matches = pattern.findall(content)
        for served_str, makespan_str in matches:
            solutions.append((float(makespan_str), float(served_str)))
    except Exception as e:
        print(f"[ERR] Lỗi đọc file {file_path}: {e}")
    return solutions

# ---------------- PLOTTING LOGIC ----------------

def plot_single_pareto(instance_name, solutions, output_dir):
    if not solutions: return
    solutions.sort(key=lambda x: x[0])
    makespans = [s[0] for s in solutions]
    serveds = [s[1] for s in solutions]

    plt.figure(figsize=(10, 7))
    ax = plt.gca()
    plt.plot(makespans, serveds, linestyle='--', color='gray', alpha=0.6)
    plt.scatter(makespans, serveds, c='blue', marker='x', s=100, label='Solution', zorder=5)
    plt.xlabel('Makespan (Minimize)', fontsize=12, fontweight='bold')
    plt.ylabel('Served Requests (Maximize)', fontsize=12, fontweight='bold')
    ax.yaxis.set_major_locator(MultipleLocator(1))
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.title(f'Pareto Front - {instance_name}', fontsize=14, fontweight='bold')
    
    ensure_dir(output_dir)
    output_path = os.path.join(output_dir, f"{instance_name}_pareto.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved: {output_path}")

def plot_comparison_pareto(instance_name, all_data_dict):
    if not all_data_dict: return

    plt.figure(figsize=(12, 8))
    ax = plt.gca()

    for label, solutions in all_data_dict.items():
        if not solutions: continue
        solutions.sort(key=lambda x: x[0])
        makespans = [s[0] for s in solutions]
        serveds = [s[1] for s in solutions]
        
        style = STYLES.get(label, {"color": "black", "marker": "o", "linestyle": "-"})
        plt.plot(makespans, serveds, color=style["color"], linestyle=style["linestyle"], alpha=0.7, label=f"{label} (Line)")
        plt.scatter(makespans, serveds, color=style["color"], marker=style["marker"], s=80, label=f"{label} (Points)")

    plt.xlabel('Makespan (Minimize)', fontsize=12, fontweight='bold')
    plt.ylabel('Served Requests (Maximize)', fontsize=12, fontweight='bold')
    ax.yaxis.set_major_locator(MultipleLocator(1))
    plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
    plt.legend(loc='best', shadow=True, title="Solutions")
    plt.title(f'Pareto Comparison - Instance: {instance_name}', fontsize=14, fontweight='bold', pad=15)

    ensure_dir(COMPARE_OUTPUT_DIR)
    output_path = os.path.join(COMPARE_OUTPUT_DIR, f"{instance_name}_compare.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[COMPARE] Saved: {output_path}")

# ---------------- MAIN PROCESSORS ----------------

def process_single_mode():
    print(f"--- MODE: SINGLE PLOT ({DEFAULT_INPUT_DIR}) ---")
    if not os.path.exists(DEFAULT_INPUT_DIR):
        print(f"[ERR] Input dir not found: {DEFAULT_INPUT_DIR}")
        return
    files = [f for f in os.listdir(DEFAULT_INPUT_DIR) if f.endswith("_output.txt")]
    for file_name in files:
        instance_name = file_name.replace("_output.txt", "")
        file_path = os.path.join(DEFAULT_INPUT_DIR, file_name)
        data = read_pareto_data_from_txt(file_path)
        if data:
            plot_single_pareto(instance_name, data, DEFAULT_OUTPUT_IMG_DIR)

def process_compare_mode():
    print(f"--- MODE: COMPARISON PLOT (INTERSECTION ONLY) ---")
    print(f"Sources: {list(COMPARE_SOURCES.keys())}")
    
    # --- TÌM GIAO CỦA CÁC FILE (INTERSECTION) ---
    common_instances = None
    
    print(">>> Scanning directories for COMMON files...")
    for label, folder_name in COMPARE_SOURCES.items():
        folder_path = os.path.join(PROJECT_ROOT, folder_name)
        
        # Lấy danh sách instance của người hiện tại
        current_source_instances = set()
        if os.path.exists(folder_path):
            files = os.listdir(folder_path)
            current_source_instances = {f.replace("_output.txt", "") for f in files if f.endswith("_output.txt")}
        else:
            print(f"[WARN] Folder not found: {folder_path}. Common set will be empty.")
            # Nếu 1 thư mục không tồn tại -> Giao của 3 cái chắc chắn là Rỗng -> Dừng luôn
            common_instances = set()
            break
            
        # Thuật toán Giao (Intersection)
        if common_instances is None:
            # Người đầu tiên: Khởi tạo tập hợp
            common_instances = current_source_instances
        else:
            # Các người sau: Giữ lại những cái chung
            common_instances = common_instances.intersection(current_source_instances)

    if not common_instances:
        print("[WARN] No common output files found across ALL 3 sources.")
        return

    print(f">>> Found {len(common_instances)} instances present in ALL folders. Processing...")

    # --- DUYỆT QUA DANH SÁCH CHUNG ---
    count_plotted = 0
    for instance_name in sorted(list(common_instances)):
        instance_data = {}
        
        # Đọc dữ liệu (Chắc chắn file tồn tại vì đã check ở trên)
        for label, folder_name in COMPARE_SOURCES.items():
            file_name = f"{instance_name}_output.txt"
            file_path = os.path.join(PROJECT_ROOT, folder_name, file_name)
            
            data = read_pareto_data_from_txt(file_path)
            if data:
                instance_data[label] = data
            
        # Chỉ vẽ nếu đọc được dữ liệu của cả 3 (đề phòng file rỗng/lỗi)
        if len(instance_data) == len(COMPARE_SOURCES):
            plot_comparison_pareto(instance_name, instance_data)
            count_plotted += 1
            if count_plotted % 10 == 0:
                print(f"   Processed {count_plotted} charts...")
                
    print(f"--- COMPLETED: Generated {count_plotted} comparison charts ---")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'compare':
        process_compare_mode()
    else:
        process_single_mode()