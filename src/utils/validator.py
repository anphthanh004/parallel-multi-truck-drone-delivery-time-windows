import json
import math
import copy
import os
import sys
from argparse import ArgumentParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GP_Solution.problem_structures import Problem, Vehicle, Request
# from draft.load_data import load_data 

def validate_solution(instance: str) -> dict:
    """
    Xác thực kết quả best_indi.json theo bộ dữ liệu gốc của nó.
    :return: Dict gồm 'valid' (bool), 'errors' (list các str), 'log' (list các str).
    """
 
    original_data_path = f"../../data/WithTimeWindows/{instance}.json"
    results_json_path = f"../../results20/{instance}/best_indi.json"
    pro = Problem.load_from_file(original_data_path)

    # Lấy kết quả log 
    with open(results_json_path, 'r') as f:
        results = json.load(f)

    # Lấy item vehicles từ results 
    logged_vehicles = results.get('vehicles')
    if not logged_vehicles:
        return {'valid': False, 'errors': ['Missing "vehicles" in results JSON'], 'log': ['Missing "vehicles" in results JSON']}

    errors = []  # Danh sách lỗi (chỉ thêm những dòng có ❌)
    all_log = []  # Full log (thêm tất cả dòng ✅ và ❌)

    # Tạo lại xe từ bài toán 
    simulated_vehicles = {v.id: copy.deepcopy(v) for v in pro.vehicles}

    served_reqs = set() # tập hợp các request được phục vụ 
    unserved_reqs = set(r.id for r in pro.requests) # tập hợp các request chưa được phục vụ 

    for logged_veh in logged_vehicles:
        logged_veh_id = logged_veh.get('id')
        all_log.append("=" * 20 + f" VEHICLE {logged_veh_id} " + "=" * 20)

        veh = simulated_vehicles.get(logged_veh_id)
        if not veh:
            msg = f"❌ Invalid vehicle ID: {logged_veh_id}"
            all_log.append(msg)
            errors.append(msg[2:])
            continue

        all_log.append(f"✅ Valid vehicle ID: {logged_veh_id}")

        current_time = 0.0
        picked_up = [] 

        logged_veh_type = logged_veh.get('type')
        logged_routes_list = logged_veh.get('routes', [])
        # Check routes 
        all_log.append("*"*10+f" VEHICLE: {logged_veh_id} - NUM_ROUTES: {len(logged_routes_list)} "+"*"*10)
        for idx, route in enumerate(logged_routes_list):
            # if len(logged_routes_list) >= 2:
            all_log.append("-"*10+f" VEHICLE: {logged_veh_id} - TYPE: {logged_veh_type} - ROUTE: {idx+1} "+"-"*10)

            # Check các trường thông tin trong mỗi route
            for entry in route:
                # Kiểm tra các trường cơ bản trong mọi tình huống: 'action', 'location', 'prev_location', 'ready_time', 'travel_time', 'arrival_time'
                logged_action = entry.get('action')
                logged_loc = entry.get('location')
                logged_prev_loc = entry.get('prev_location')
                logged_ready = entry.get('ready_time')
                logged_travel = entry.get('travel_time')
                logged_arrival = entry.get('arrival_time')
                logged_service_start = entry.get('service_start')
                logged_req_id = entry.get('req_id')
                logged_vehicle_state = entry.get('vehicle_state')
                logged_busy_until = logged_vehicle_state.get('busy_until')
                logged_remaining_capacity = logged_vehicle_state.get('remaining_capacity')
                logged_remaining_range = logged_vehicle_state.get('remaining_range')
                req = next((r for r in pro.requests if r.id == logged_req_id), None)
                
                if logged_action is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing action"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                if logged_loc is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing location"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                if logged_prev_loc is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing previous location"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue                
                if logged_ready is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing ready_time"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                if logged_travel is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing travel_time"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                if logged_arrival is None:
                    msg = f"❌ Vehicle {logged_veh_id}: Missing arrival_time"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                # Kiểm tra logged_action (log về hành động action)
                if logged_action not in ['pickup', 'return_depot', 'failed_return']:
                    msg = f"❌ Invalid action in entry for vehicle {logged_veh_id}"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                all_log.append(f"✅ Valid action in entry for vehicle {logged_veh_id}: {logged_action}")

                # Kiểm tra logged_loc (log về điểm location)
                if not isinstance(logged_loc, (list, tuple)) or len(logged_loc) != 2:
                    msg = f"❌ Invalid location in entry for vehicle {logged_veh_id}"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                all_log.append(f"✅ Valid location in entry for vehicle {logged_veh_id}")
                
                # Kiểm tra logged_prev_loc (log về điểm previous location)
                if not isinstance(logged_prev_loc, (list, tuple)) or len(logged_prev_loc) != 2:
                    msg = f"❌ Invalid previous location in entry for vehicle {logged_veh_id}"
                    all_log.append(msg)
                    errors.append(msg[2:])
                    continue
                all_log.append(f"✅ Valid previous location in entry for vehicle {logged_veh_id}")
                
                # Kiểm tra logged_ready (ready_time phải sau busy_until)
                expected_ready = max(current_time, veh.busy_until, req.release_time if req else 0)

                if abs(expected_ready - logged_ready) > 1e-6:
                    msg = f"❌ Vehicle {logged_veh_id}: Invalid ready_time for {logged_action} at req {logged_req_id} (expected {expected_ready:.4f}, got {logged_ready:.4f})"
                    all_log.append(msg)
                    errors.append(msg[2:])
                else:
                    all_log.append(f"✅ Vehicle {logged_veh_id}: Valid ready_time for {logged_action} at req {logged_req_id} (expected {expected_ready:.4f}, got {logged_ready:.4f})")

                # Kiểm tra logged_travel (log về khoảng thời gian di chuyển travel_time)
                expected_travel = veh.moving_time_to(logged_loc)
                if abs(expected_travel - logged_travel) > 1e-6:
                    msg = f"❌ Vehicle {logged_veh_id}: Invalid travel_time for {logged_action} at req {entry.get('req_id')} (expected {expected_travel:.4f}, got {logged_travel:.4f})"
                    all_log.append(msg)
                    errors.append(msg[2:])
                else:
                    all_log.append(f"✅ Vehicle {logged_veh_id}: Valid travel_time for {logged_action} at req {entry.get('req_id')} (expected {expected_travel:.4f}, got {logged_travel:.4f})")
                  
                # Kiểm tra arrival_time (có phải là tổng của ready_time và travel_time không)
                expected_arrival = expected_ready + expected_travel
                if abs(expected_arrival - logged_arrival) > 1e-6:
                    msg = f"❌ Vehicle {logged_veh_id}: Mismatch arrival_time for {logged_action} (expected {expected_arrival:.4f}, got {logged_arrival:.4f})"
                    all_log.append(msg)
                    errors.append(msg[2:])
                else:
                    all_log.append(f"✅ Vehicle {logged_veh_id}: Match arrival_time for {logged_action} (expected {expected_arrival:.4f}, got {logged_arrival:.4f})")

                current_time = expected_arrival

                # Kiểm tra cho từng hành động cụ thể
                
                # Action #1. Lấy hàng (Pickup)
                if logged_action == 'pickup':
                    if not req:
                        msg = f"❌ Vehicle {logged_veh_id}: Invalid req_id {logged_req_id}"
                        all_log.append(msg)
                        errors.append(msg[2:])
                        continue
                    all_log.append(f"✅ Vehicle {logged_veh_id}: Valid req_id {logged_req_id}")

                    current_time = max(current_time, req.time_window[0])
                    
                    if (abs(logged_service_start - current_time) > 1e-6):
                        msg = f"❌ Vehicle {logged_veh_id}: Invalid service_start for pickup req {logged_req_id}"
                        all_log.append(msg)
                        errors.append(msg[2:])
                        continue
                    if not (req.time_window[0] <= logged_service_start <= req.time_window[1] + 1e-6):
                        msg = f"❌ Vehicle {logged_veh_id}: Time window violation for req {logged_req_id} (service_start {logged_service_start:.4f}, window {req.time_window})"
                        all_log.append(msg)
                        errors.append(msg[2:])
                    else:
                        all_log.append(f"✅ Vehicle {logged_veh_id}: No time window violation for req {logged_req_id} (service_start {logged_service_start:.4f}, window {req.time_window})")
                    
                    
                    if veh.remaining_capacity < req.demand - 1e-6:
                        msg = f"❌ Vehicle {logged_veh_id}: Capacity violation for req {logged_req_id} (remaining {veh.remaining_capacity:.4f}, demand {req.demand:.4f})"
                        all_log.append(msg)
                        errors.append(msg[2:])
                    else:
                        all_log.append(f"✅ Vehicle {logged_veh_id}: No capacity violation for req {logged_req_id} (remaining {veh.remaining_capacity:.4f}, demand {req.demand:.4f})")

                    if veh.type == 'DRONE' and req.able_drone == 0:
                        msg = f"❌ Drone {logged_veh_id}: Cannot serve req {logged_req_id} (not drone-able)"
                        all_log.append(msg)
                        errors.append(msg[2:])
                    else:
                        all_log.append(f"✅ Vehicle {logged_veh_id}: Can serve req {logged_req_id}")

                    # Cập nhật trạng thái
                    picked_up.append(req)
                    veh.remaining_capacity -= req.demand
                    if veh.type == 'DRONE':
                        veh.remaining_range -= expected_travel
                    unserved_reqs.discard(logged_req_id)
                    req.pickup_time = current_time 
                    veh.busy_until = current_time

                # Action #2. Về kho (Return Depot) 
                elif logged_action == 'return_depot':
                    for r in picked_up:
                        if r.pickup_time is None:
                            msg = f"❌ Vehicle {logged_veh_id}: Missing pickup_time for req {r.id}"
                            all_log.append(msg)
                            errors.append(msg[2:])
                        elif logged_arrival - r.pickup_time > r.l_w + 1e-6:
                            msg = f"❌ Vehicle {logged_veh_id}: l_w violation for req {r.id} (time {logged_arrival - r.pickup_time:.4f}, l_w {r.l_w:.4f})"
                            all_log.append(msg)
                            errors.append(msg[2:])
                        else:
                            all_log.append(f"✅ Vehicle {logged_veh_id}: No l_w violation for req {r.id} (time {logged_arrival - r.pickup_time:.4f}, l_w {r.l_w:.4f})")
                        served_reqs.add(r.id)
                    picked_up = []
                    veh.remaining_capacity = veh.capacity
                    if veh.type == 'DRONE':
                        veh.remaining_range = veh.max_range
                    veh.busy_until = current_time
               
               
                # Action #3. Trả hàng (Failed Return)
                elif logged_action == 'failed_return':
                    if not req:
                        msg = f"❌ Vehicle {logged_veh_id}: Invalid req_id {logged_req_id} for failed_return"
                        all_log.append(msg)
                        errors.append(msg[2:])
                        continue
                    all_log.append(f"✅ Vehicle {logged_veh_id}: Valid req_id {logged_req_id} for failed_return")

                    picked_up = [p for p in picked_up if p.id != logged_req_id]
                    veh.busy_until = current_time
                    veh.remaining_capacity += req.demand
                    if veh.type == 'DRONE':
                        veh.remaining_range -= expected_travel
                    unserved_reqs.add(logged_req_id)

                # Kiểm tra vehicle_state có khớp với veh được giả lập lại
                for key, val in logged_vehicle_state.items():
                    if val is not None:
                        attr_val = getattr(veh, key, None)
                        if attr_val is None:
                            msg = f"❌ Vehicle {logged_veh_id}: Missing attribute {key}"
                            all_log.append(msg)
                            errors.append(msg[2:])
                        elif isinstance(attr_val, float) and abs(attr_val - val) > 1e-6:
                            msg = f"❌ Vehicle {logged_veh_id}: State mismatch for {key} (expected {attr_val:.4f}, got {val:.4f})"
                            all_log.append(msg)
                            errors.append(msg[2:])
                        elif attr_val != val:
                            msg = f"❌ Vehicle {logged_veh_id}: State mismatch for {key} (expected {attr_val}, got {val})"
                            all_log.append(msg)
                            errors.append(msg[2:])
                        else:
                            all_log.append(f"✅ Vehicle {logged_veh_id}: State match for {key}")

                # Cập nhật trạng thái
                veh.current_location = logged_loc
                veh.remaining_capacity = logged_remaining_capacity
                if veh.type == 'DRONE':
                    veh.remaining_range = logged_remaining_range

        # Sau khi đã duyệt qua hết các route (routes) của vehicle này
        # Kiểm tra makespan cho vehicle này
        if veh.busy_until > pro.depot_time_window[1] + 1e-6:
            msg = f"❌ Vehicle {logged_veh_id}: Makespan exceeds depot close time ({veh.busy_until:.4f} > {pro.depot_time_window[1]:.4f})"
            all_log.append(msg)
            errors.append(msg[2:])
        else:
            all_log.append(f"✅ Vehicle {logged_veh_id}: Makespan does not exceed depot close time")

    # Overall checks
    all_log.append("=" * 20 + " Overall Checks " + "=" * 20)

    served_count = len(served_reqs)
    reported_served = results.get('served')
    if served_count != reported_served:
        msg = f"❌ Mismatch served count (validated {served_count}, reported {reported_served})"
        all_log.append(msg)
        errors.append(msg[2:])
    else:
        all_log.append(f"✅ Match served count (validated {served_count}, reported {reported_served})")

    unserved_count = len(unserved_reqs)
    reported_unserved = results.get('dropped')
    if unserved_count != reported_unserved:
        msg = f"❌ Mismatch unserved count (validated {unserved_count}, reported {reported_unserved})"
        all_log.append(msg)
        errors.append(msg[2:])
    else:
        all_log.append(f"✅ Match unserved count (validated {unserved_count}, reported {reported_unserved})")

    makespan = max(v.busy_until for v in simulated_vehicles.values())
    reported_makespan = results.get('makespan')
    if abs(makespan - reported_makespan) > 1e-6:
        msg = f"❌ Mismatch makespan (validated {makespan:.4f}, reported {reported_makespan:.4f})"
        all_log.append(msg)
        errors.append(msg[2:])
    else:
        all_log.append(f"✅ Match makespan (validated {makespan:.4f}, reported {reported_makespan:.4f})")

    valid = len(errors) == 0

    return {'valid': valid, 'errors': errors, 'log': all_log}


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('instance_name', help="Instance name")
    args = parser.parse_args()
    report = validate_solution(args.instance_name)
    print("Valid:", report['valid'])
    print("\nDetailed Log:")
    for line in report['log']:
        print(line)
    if report['errors']:
        print("\nErrors:")
        for err in report['errors']:
            print(f"- {err}")