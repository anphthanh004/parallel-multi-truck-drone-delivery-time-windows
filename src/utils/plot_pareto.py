import json
import os
import argparse
import matplotlib.pyplot as plt

def plot_instance_pareto(instance_name):
    # 1. Xác định đường dẫn file dựa trên cấu trúc thư mục của bạn
    current_script_path = os.path.abspath(__file__)
    # project_root/src/utils/plot_pareto.py -> lùi 3 cấp để về root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))
    
    folder_path = os.path.join(project_root, "results20", instance_name)
    file_path = os.path.join(folder_path, "population.json")
    
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file dữ liệu tại {folder_path}")
        return

    # 2. Đọc dữ liệu
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    individuals = data.get("individuals", [])

    # 3. Lọc Rank 0 và Unique (theo r_tree, s_tree, routes)
    unique_pareto_points = {}
    for ind in individuals:
        if ind.get("rank") == 0:
            # Khóa định danh duy nhất cho một giải pháp (cấu trúc + đường đi)
            # key = (ind.get("r_tree"), ind.get("s_tree"), str(ind.get("routes", "")))
            key = (ind.get("served_ratio"), ind.get("makespan_score"), (str(ind.get("routes", ""))))
            # key = str(ind.get("routes", "")) 
            if key not in unique_pareto_points:
                unique_pareto_points[key] = ind

    unique_list = list(unique_pareto_points.values())

    if not unique_list:
        print("Không có dữ liệu Rank 0 để vẽ.")
        return

    # 4. QUAN TRỌNG: Sắp xếp các điểm theo trục X (makespan_score)
    # Việc sắp xếp giúp đường nét đứt chạy mượt mà từ trái sang phải, không bị tạo vòng lặp
    unique_list.sort(key=lambda x: (x['makespan_score'], x['served_ratio']))

    # 5. Thống kê
    print(f"--- Thống kê Pareto cho Instance {instance_name} ---")
    print(f"Tổng số cá thể trong file: {len(individuals)}")
    print(f"Số lượng điểm Pareto (Rank 0) duy nhất: {len(unique_list)}")

    # 6. Vẽ biểu đồ
    x_values = [ind['makespan_score'] for ind in unique_list]
    y_values = [ind['served_ratio'] for ind in unique_list]

    plt.figure(figsize=(10, 6))
    
    # Vẽ đường nét đứt đi qua các điểm đã sắp xếp
    plt.plot(x_values, y_values, linestyle='--', c='blue', alpha=0.5, label='Pareto Frontier Line')
    
    # Vẽ các điểm thực tế
    plt.scatter(x_values, y_values, c='blue', marker='x', s=100, label='Pareto Points (Rank 0)', zorder=5)
    
    plt.title(f'Pareto Front - Instance {instance_name}')
    # Lưu ý: Makespan thường là mục tiêu Cần Giảm (Min)
    plt.xlabel('Makespan Score (Max)') 
    plt.ylabel('Served Ratio (Max)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)

    # 7. Lưu file vào cùng thư mục kết quả
    output_filename = f"pareto_plot_{instance_name}.png"
    output_path = os.path.join(folder_path, output_filename)
    plt.savefig(output_path)
    
    print(f"Đã lưu biểu đồ biên Pareto tại: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vẽ biên Pareto cho kết quả GA.")
    parser.add_argument("instance", type=str, help="Tên instance cần vẽ (ví dụ: 6.5.1)")
    
    args = parser.parse_args()
    plot_instance_pareto(args.instance)