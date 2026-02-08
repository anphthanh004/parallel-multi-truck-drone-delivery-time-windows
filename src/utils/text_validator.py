import sys
import os
import re
import math
import json
from argparse import ArgumentParser


current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

from GP_Solution.problem_structures import Problem


def calculate_distance(loc1, loc2):
    return math.sqrt((loc1[0] - loc2[0])**2 + (loc1[1] - loc2[1])**2)

class TextSolutionParser:
    """Đọc file text output và chuyển thành cấu trúc dữ liệu Python"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.solutions = []

    def parse(self):
        if not os.path.exists(self.filepath):
            print(f"Error: File not found {self.filepath}")
            return []

        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        current_sol = None
        current_veh_type = None
        current_veh_id = None # ID trong file text (1, 2, 3...)

        for line in lines:
            line = line.strip()
            if not line: continue
            
            # 1. Phát hiện Solution
            if line.startswith("Solution"):
                if current_sol:
                    self.solutions.append(current_sol)
                # Tạo solution mới
                current_sol = {'name': line.replace(":", ""), 'routes': {}}
                continue

            # 2. Phát hiện Vehicle (Truck/Drone)
            # Regex bắt: "Truck 1:" hoặc "Drone 2:"
            veh_match = re.match(r'(Truck|Drone)\s+(\d+):', line, re.IGNORECASE)
            if veh_match:
                current_veh_type = veh_match.group(1).upper() # TRUCK/DRONE
                current_veh_id = int(veh_match.group(2))
                continue

            # 3. Phát hiện Route [0, 1, 2, 0]
            if line.startswith("[") and line.endswith("]"):
                if current_sol is None or current_veh_type is None:
                    continue
                
                content = line[1:-1].strip()
                if not content: continue
                
                try:
                    route_ids = [int(x.strip()) for x in content.split(',') if x.strip()]
                except ValueError:
                    print(f"Warning: Cannot parse route line: {line}")
                    continue
                
                # Lưu vào dict: keys là tuple (Loại xe, ID_trong_text)
                key = (current_veh_type, current_veh_id)
                if key not in current_sol['routes']:
                    current_sol['routes'][key] = []
                current_sol['routes'][key].append(route_ids)

        if current_sol:
            self.solutions.append(current_sol)
        
        return self.solutions

def validate_text_solution(instance_name, output_file):
    # --- 1. LOAD DATA ---
    # Cấu trúc thư mục: src/utils/text_validator.py -> data/WithTimeWindows/
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "WithTimeWindows", f"{instance_name}.json")
    
    if not os.path.exists(data_path):
        # Thử fallback path khác nếu cần
        print(f"ERROR: Data file not found at {data_path}")
        return

    print(f"--- Loading Instance: {instance_name} ---")
    try:
        pro = Problem.load_from_file(data_path)
    except Exception as e:
        print(f"ERROR: Failed to load problem file. {e}")
        return

    # Tách danh sách xe thực tế trong Problem để mapping
    real_trucks = [v for v in pro.vehicles if v.type == 'TRUCK']
    real_drones = [v for v in pro.vehicles if v.type == 'DRONE']
    
    req_map = {r.id: r for r in pro.requests}

    # --- 2. PARSE OUTPUT ---
    parser = TextSolutionParser(output_file)
    solutions = parser.parse()
    
    if not solutions:
        print("No solutions found in text file or parse error.")
        return

    # --- 3. VALIDATE LOOP ---
    for sol in solutions:
        print(f"\n{'='*20} Checking {sol['name']} {'='*20}")
        
        errors = []
        
        # Tracking: Request nào đã được phục vụ? (Để check duplicate hoặc missed nếu cần)
        served_requests = set()

        # Duyệt từng xe trong Solution
        for (v_type_txt, v_id_txt), routes in sol['routes'].items():
            
            # --- MAPPING: Text ID -> Real Object ---
            vehicle = None
            if v_type_txt == 'TRUCK':
                if 1 <= v_id_txt <= len(real_trucks):
                    vehicle = real_trucks[v_id_txt - 1] # Index 0-based
            elif v_type_txt == 'DRONE':
                if 1 <= v_id_txt <= len(real_drones):
                    vehicle = real_drones[v_id_txt - 1]

            if not vehicle:
                errors.append(f"❌ CONFIG ERROR: {v_type_txt} {v_id_txt} not found in config (Have {len(real_trucks)} Trucks, {len(real_drones)} Drones)")
                continue

            # --- SIMULATION STATE ---
            sim_time = 0.0          # Thời gian hiện tại của xe
            
            # Duyệt qua các chuyến (routes) của xe này
            for r_idx, route in enumerate(routes):
                if not route: continue
                
                # Check cấu trúc route
                if route[0] != 0 or route[-1] != 0:
                    errors.append(f"❌ STRUCT ERROR: {v_type_txt} {v_id_txt} Route {r_idx+1} must start/end with 0. Got {route}")
                    continue

                current_capacity_usage = 0.0
                current_energy_usage = 0.0 # Reset pin mỗi khi rời depot
                prev_loc = (0.0, 0.0) 

                # Duyệt các điểm trong route (bỏ điểm 0 đầu)
                for i, node_id in enumerate(route[1:]):
                    # Xác định Target
                    if node_id == 0:
                        target_loc = (0.0, 0.0)
                        req = None
                        node_name = "Depot"
                    else:
                        if node_id not in req_map:
                            errors.append(f"❌ DATA ERROR: Req ID {node_id} not exist")
                            continue
                        req = req_map[node_id]
                        target_loc = req.location
                        node_name = f"Req {node_id}"
                        served_requests.add(node_id)

                    # 1. TRAVEL
                    dist = calculate_distance(prev_loc, target_loc)
                    travel_time = dist / vehicle.velocity
                    arrival_time = sim_time + travel_time
                    
                    # 2. DRONE ENERGY CHECK (Check tiêu hao cho đoạn đường vừa đi)
                    if vehicle.type == 'DRONE':
                        current_energy_usage += travel_time
                        if current_energy_usage > vehicle.max_range + 0.001:
                            errors.append(f"❌ ENERGY: {v_type_txt} {v_id_txt} died going to {node_name}. Used {current_energy_usage:.2f} > Max {vehicle.max_range}")

                    # 3. CONSTRAINTS AT NODE
                    if node_id != 0: # Tại khách hàng
                        # a. Drone Capability
                        if vehicle.type == 'DRONE' and req.able_drone == 0:
                             errors.append(f"❌ TYPE ERROR: Drone {v_id_txt} cannot serve {node_name} (heavy item)")

                        # b. Capacity
                        current_capacity_usage += req.demand
                        if current_capacity_usage > vehicle.capacity + 0.001:
                             errors.append(f"❌ CAPACITY: {v_type_txt} {v_id_txt} overloaded at {node_name}. Load {current_capacity_usage:.2f} > Cap {vehicle.capacity}")

                        # c. Time Window
                        # Xe phải đợi nếu đến sớm
                        start_service = max(arrival_time, req.e_i)
                        
                        if start_service > req.l_i + 0.001:
                             errors.append(f"❌ TIME WINDOW: {v_type_txt} {v_id_txt} late at {node_name}. Arrive/Start {start_service:.2f} > Close {req.l_i}")

                        # Update Sim Time = thời điểm phục vụ xong (hoặc bắt đầu rời đi)
                        sim_time = start_service
                    
                    else: # Tại Depot (Kết thúc trip)
                        sim_time = arrival_time
                        # Kiểm tra về depot có kịp giờ đóng cửa không
                        depot_close_time = pro.depot_time_window[1]
                        if sim_time > depot_close_time + 0.001:
                            errors.append(f"❌ DEPOT CLOSE: {v_type_txt} {v_id_txt} returned late. Time {sim_time:.2f} > Close {depot_close_time}")

                    prev_loc = target_loc

        # --- FINAL REPORT FOR SOLUTION ---
        if not errors:
            print(f"✅ VALID SOLUTION")
            print(f"   Served Requests: {len(served_requests)}")
        else:
            print(f"❌ INVALID SOLUTION. Found {len(errors)} errors:")
            for e in errors:
                print(f"   {e}")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('instance_name', help="Tên instance (ví dụ: 6.5.1)")
    parser.add_argument('output_file', help="Đường dẫn đến file output txt")
    args = parser.parse_args()
    
    validate_text_solution(args.instance_name, args.output_file)
    
    
#  python .\text_validator.py 100.40.4 ../../output/100.40.4_output.txt