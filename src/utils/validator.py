import json
import math
from problem_structures import Problem, Vehicle, Request  # Import từ GP_Solution

def validate_solution(json_path: str, original_data_path: str) -> dict:
    # Load original problem
    with open(original_data_path, 'r') as f:
        data = json.load(f)
    pro = Problem(data['close'])  # Tái tạo problem từ data (tương tự load_data.py)
    # ... (thêm code để populate pro.requests và pro.vehicles từ data)

    # Load simulated results
    with open(json_path, 'r') as f:
        results = json.load(f)
    vehicles_routes = results['vehicles_routes']  # Dict {veh_id: list[dict]}

    errors = []  # List lỗi

    # Tái tạo trạng thái từ routes
    simulated_vehicles = {v.id: copy.deepcopy(v) for v in pro.vehicles}  # Copy vehicles gốc
    served_reqs = set()

    for veh_id, routes in vehicles_routes.items():
        veh = simulated_vehicles[veh_id]
        current_time = 0.0
        current_loc = (0.0, 0.0)
        picked_up = []

        for entry in routes:
            # Kiểm tra di chuyển
            expected_travel = veh.moving_time(current_loc, entry['location'])
            if abs(expected_travel - entry['travel_time']) > 1e-6:
                errors.append(f"Vehicle {veh_id}: Invalid travel_time for {entry['action']} at req {entry['req_id']}")

            # Cập nhật thời gian
            current_time = max(current_time, entry['start_time']) + entry['travel_time']
            if entry['arrival_time'] != current_time:
                errors.append(f"Vehicle {veh_id}: Mismatch arrival_time")

            # Kiểm tra action cụ thể
            if entry['action'] == 'pickup':
                req = next(r for r in pro.requests if r.id == entry['req_id'])
                # Check time window
                if not (req.time_window[0] <= entry['service_start'] <= req.time_window[1]):
                    errors.append(f"Vehicle {veh_id}: Time window violation for req {req.id}")
                # Check capacity
                if veh.remaining_capacity < req.demand:
                    errors.append(f"Vehicle {veh_id}: Capacity violation for req {req.id}")
                # Check drone able
                if veh.type == 'DRONE' and req.able_drone == 0:
                    errors.append(f"Drone {veh_id}: Cannot serve req {req.id}")
                # Update
                picked_up.append(req)
                veh.remaining_capacity -= req.demand
                if veh.type == 'DRONE':
                    veh.remaining_range -= expected_travel

            elif entry['action'] == 'return_depot':
                # Check l_w for all picked_up
                for r in picked_up:
                    if entry['arrival_time'] - r.pickup_time > r.l_w:
                        errors.append(f"Vehicle {veh_id}: l_w violation for req {r.id}")
                    served_reqs.add(r.id)
                picked_up = []
                veh.remaining_capacity = veh.capacity
                if veh.type == 'DRONE':
                    veh.remaining_range = veh.max_range

            elif entry['action'] == 'failed_return':
                # Check note and reset
                req = next(r for r in pro.requests if r.id == entry['req_id'])
                picked_up = [p for p in picked_up if p.id != req.id]
                veh.remaining_capacity += req.demand

            # Check vehicle_state match
            for key, val in entry['vehicle_state'].items():
                if val is not None and abs(getattr(veh, key) - val) > 1e-6:
                    errors.append(f"Vehicle {veh_id}: State mismatch for {key}")

            # Update loc and time
            current_loc = entry['location']
            veh.busy_until = entry['vehicle_state']['busy_until']

        # Check makespan
        if veh.busy_until > pro.depot_time_window[1]:
            errors.append(f"Vehicle {veh_id}: Makespan exceeds close_time")

    # Check overall
    served_count = len(served_reqs)
    if served_count != results['served']:
        errors.append("Mismatch served count")
    # ... (thêm check f1, f2, unserved, etc.)

    return {'valid': len(errors) == 0, 'errors': errors}

# Usage: python validator.py results/best_indi.json data/WithTimeWindows3/6.5.1.json
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: validator.py <results_json> <original_data_json>")
        sys.exit(1)
    report = validate_solution(sys.argv[1], sys.argv[2])
    print("Valid:", report['valid'])
    for err in report['errors']:
        print(err)