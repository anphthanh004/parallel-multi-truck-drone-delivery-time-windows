import os
import re
import sys
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

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