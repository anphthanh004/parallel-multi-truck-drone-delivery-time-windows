import matplotlib.pyplot as plt
import json
import os
import argparse

def load_json(filename):
    """Hàm đọc file JSON an toàn"""
    if not os.path.exists(filename):
        print(f"Lỗi: Không tìm thấy file tại đường dẫn: {filename}")
        return None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi khi đọc file {filename}: {e}")
        return None

def plot():
    parser = argparse.ArgumentParser(description="GPHH Runner Visualization")
    parser.add_argument('instance_name', type=str, help='Tên instance cần vẽ (VD: 6.5.1)')
    args = parser.parse_args()
    instance_name = args.instance_name
    
    current_script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))
    
    input_file = os.path.join(project_root, 'data', 'WithTimeWindows', f'{instance_name}.json')
    solution_dir = os.path.join(project_root, 'results', f'{instance_name}')
    solution_file = os.path.join(solution_dir, 'best_indi.json')

    print(f"Đang đọc dữ liệu từ:\n - Input: {input_file}\n - Solution: {solution_file}")
    
    input_data = load_json(input_file)
    best_indi = load_json(solution_file)

    if input_data and best_indi:
        print("Dữ liệu đã tải thành công. Đang xử lý biểu đồ...")
        
        # Cấu hình Z-ORDER (Thứ tự lớp vẽ: Càng cao càng nằm trên)
        Z_BG = 0
        Z_UNSERVED = 2       # Thấp nhất, nằm dưới đường đi
        Z_ROUTE = 5          # Đường đi nằm đè lên unserved
        Z_SERVED = 10        # Điểm được phục vụ nằm đè lên đường đi
        Z_TEXT = 15          # Chữ phải rõ nhất
        Z_DEPOT = 20         # Depot quan trọng nhất

        plt.figure(figsize=(14, 12))
        ax = plt.gca()

        # --- 2. XỬ LÝ REQUESTS ---
        req_coords = {}
        req_info = {}
        for idx, req in enumerate(input_data['requests']):
            req_id = idx + 1
            req_coords[req_id] = (req[0], req[1])
            req_info[req_id] = {'ready_time': req[4]}

        # --- 3. VẼ ROUTES ---
        served_reqs = set()
        vehicle_colors = {'TRUCK': 'blue', 'DRONE': 'red'}
        vehicle_styles = {'TRUCK': '-', 'DRONE': '--'}

        if 'vehicles' in best_indi:
            for vehicle in best_indi['vehicles']:
                v_id = vehicle.get('id', '?')
                v_type = vehicle.get('type', 'TRUCK')
                
                base_color = vehicle_colors.get(v_type, 'green')
                style = vehicle_styles.get(v_type, '-')
                
                # Duyệt qua từng tuyến (Route) của xe
                for r_idx, route in enumerate(vehicle.get('routes', [])):
                    path_x = [0.0] # Depot X
                    path_y = [0.0] # Depot Y
                    
                    first_node_loc = None # Để gắn nhãn tên xe

                    for step in route:
                        loc = step['location']
                        path_x.append(loc[0])
                        path_y.append(loc[1])
                        
                        # Lưu vị trí điểm đầu tiên khách hàng để gắn nhãn Route
                        if first_node_loc is None and (loc[0] != 0 or loc[1] != 0):
                            first_node_loc = loc

                        if step.get('req_id') is not None:
                            served_reqs.add(step['req_id'])
                            # Hiển thị thời gian đến
                            if step.get('arrival_time') is not None:
                                plt.text(loc[0], loc[1] - 350, f"Arr: {step['arrival_time']:.1f}", 
                                         fontsize=7, color=base_color, ha='center', zorder=Z_TEXT)

                    # Tạo nhãn cho Legend (VD: Veh 1 - R1 (TRUCK))
                    route_label = f"Veh {v_id} - R{r_idx+1} ({v_type})"
                    
                    # Vẽ đường đi
                    plt.plot(path_x, path_y, color=base_color, linestyle=style, 
                             linewidth=2, alpha=0.8, label=route_label, zorder=Z_ROUTE)

                    # Gắn nhãn text trực tiếp lên bản đồ tại điểm khách hàng đầu tiên của tuyến
                    if first_node_loc:
                        plt.text(first_node_loc[0], first_node_loc[1] + 400, 
                                 f"V{v_id}-R{r_idx+1}", 
                                 fontsize=9, fontweight='bold', color=base_color, 
                                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1),
                                 zorder=Z_TEXT)

        # --- 4. VẼ ĐIỂM KHÁCH HÀNG (NODES) ---
        for r_id, coords in req_coords.items():
            ready_time = req_info[r_id]['ready_time']
            
            if r_id in served_reqs:
                # ĐÃ PHỤC VỤ: Màu sáng, viền rõ, lớp cao
                plt.scatter(*coords, c='lightgreen', marker='o', s=120, 
                            edgecolors='green', zorder=Z_SERVED)
                plt.text(coords[0], coords[1] + 200, f"R{r_id}\n(t={ready_time:.0f})", 
                         fontsize=8, ha='center', fontweight='bold', zorder=Z_TEXT)
            else:
                # CHƯA PHỤC VỤ (UNSERVED): Màu xám, mờ, lớp thấp (dưới route)
                plt.scatter(*coords, c='lightgray', marker='X', s=100, 
                            edgecolors='gray', alpha=0.4, zorder=Z_UNSERVED, label='Unserved')
                plt.text(coords[0], coords[1] + 200, f"R{r_id}", 
                         fontsize=8, ha='center', color='gray', alpha=0.6, zorder=Z_UNSERVED)

        # --- 5. VẼ DEPOT ---
        plt.scatter(0, 0, c='black', marker='s', s=150, label='Depot', zorder=Z_DEPOT)

        # --- 6. CẤU HÌNH & LƯU FILE ---
        plt.title(f'Visualizing Instance: {instance_name}\n(Unserved requests are faded)', fontsize=14)
        plt.xlabel('X Coordinate')
        plt.ylabel('Y Coordinate')
        
        # Xử lý Legend: Loại bỏ trùng lặp (ví dụ nhiều điểm Unserved)
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize='small')
        
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.axis('equal')
        plt.tight_layout()

        # Lưu file ảnh vào cùng thư mục với best_indi.json
        output_image_path = os.path.join(solution_dir, 'visualization.png')
        plt.savefig(output_image_path, dpi=300)
        print(f"OK. Đã lưu ảnh biểu đồ tại: {output_image_path}")
        
        plt.show()

    else:
        print("!!! Không thể vẽ biểu đồ do thiếu dữ liệu.")

if __name__ == "__main__":
    plot()