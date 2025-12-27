from .gp_structure import Individual
from .problem_structures import Problem, Vehicle, Drone, Truck
import copy
import heapq
import math

# -------------------------
# Giả lập phân bổ sự kiện
# -------------------------

def simulate_policy(indi: Individual, pro: Problem):
    local_pro = copy.deepcopy(pro)
    close_time = local_pro.depot_time_window[1]

    event_queue = []
    for req in local_pro.requests:
        heapq.heappush(event_queue, (req.release_time, "ARRIVE", req.id))
    heapq.heappush(event_queue, (close_time + 1e-9, "END", None))

    cur_time = 0.0

    while event_queue:
        time, ev_type, payload = heapq.heappop(event_queue)
        cur_time = time
        if ev_type == "END":
            break
        if ev_type == "ARRIVE":
            req = next((r for r in local_pro.requests if r.id == payload), None)
            if not req or req.is_served or cur_time > req.time_window[1] + 1e-6:
                continue

            candidates = []
            for veh in local_pro.vehicles:
                veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]

                if veh.type == "DRONE" and req.able_drone == 0:
                    continue
                if veh.sum_of_req_demand() + req.demand > veh.capacity + 1e-6:
                    continue

                if veh.type == "DRONE":
                    d_moving = math.sqrt((veh.current_location[0] - req.location[0])**2 +
                                         (veh.current_location[1] - req.location[1])**2)
                    d_returning = math.sqrt(req.location[0]**2 + req.location[1]**2)

                    total_time = (d_moving + d_returning) / veh.velocity

                    if veh.remaining_range < total_time - 1e-6:
                        continue

                score = indi.r_tree.evaluate(veh, local_pro, req, cur_time)
                candidates.append((score, veh))

            if not candidates:
                continue

            candidates.sort(key=lambda x: x[0], reverse=True)
            for score, veh in candidates:
                start_service_time = max(cur_time, veh.busy_until)
                travel_time = veh.moving_time_to(req.location)
                arrival_time = start_service_time + travel_time
                if arrival_time > req.time_window[1] + 1e-6:
                    continue
                veh.req_queue.append(req)
                if veh.busy_until <= cur_time + 1e-6:
                    _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)
                break

        elif ev_type == "VEH_FREE":
            vid = payload
            veh = next((v for v in local_pro.vehicles if v.id == vid), None)
            if veh:
                veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
                _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)

        for veh in local_pro.vehicles:
            veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
            if abs(veh.busy_until - cur_time) < 1e-6:
                _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)


    served_count = sum(1 for r in local_pro.requests if r.is_served)
    total = len(local_pro.requests)
    makespan = max((v.busy_until for v in local_pro.vehicles), default=0.0)

    f1 = served_count / total if total > 0 else 0.0
    f2 = max(0.0, 1.0 - makespan / close_time)

    indi.f1 = f1
    indi.f2 = f2
    indi.fitness = (f1, f2)

    return {
        "total": total,
        "served": served_count,
        "unserved": total - served_count,
        "makespan": makespan,
        "ratio": f1,
        "f1": f1,
        "f2": f2,
        "simulated_problem": local_pro
    }

def _dispatch_vehicle(veh, ind, pro, start_time, event_queue):
    veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
    ready_time = max(start_time, veh.busy_until)
    depot_close = pro.depot_time_window[1]

    # 1. Kiểm tra có đơn nào sắp vi phạm l_w không (đơn hàng được phục vụ sớm nhất là lúc hàng về kho)
    if veh.picked_up_orders:
        time_to_depot = veh.moving_time(veh.current_location, (0, 0))
        arrival_at_depot = ready_time + time_to_depot
        
        for picked in list(veh.picked_up_orders):
            if (arrival_at_depot - picked.pickup_time > picked.l_w + 1e-6) or \
               (arrival_at_depot > depot_close + 1e-6):
                _execute_failed_return_sequence(veh, picked, ready_time, depot_close, event_queue)
                return

    # 2. Chọn khách hàng tiếp theo để đến lấy hàng
    candidates = []
    for req in veh.req_queue:
        if req.is_served or req.is_picked_up: continue
        
        travel_time = veh.moving_time_to(req.location)
        arrival_req = ready_time + travel_time
        service_start = max(arrival_req, req.time_window[0])
        
        # Kiểm tra ràng buộc thời gian khách hàng
        if arrival_req > req.time_window[1] + 1e-6: continue
        
        # Kiểm tra khả năng về depot sau khi lấy khách này
        arrival_depot_after = service_start + veh.moving_time(req.location, (0, 0))
        if arrival_depot_after > depot_close + 1e-6: continue
        
        # Kiểm tra l_w của toàn bộ hàng trên xe (bao gồm cả req mới) 
        if any((arrival_depot_after - p.pickup_time > p.l_w + 1e-6) for p in veh.picked_up_orders):
            continue
        if (arrival_depot_after - service_start > req.l_w + 1e-6):
            continue

        # Kiểm tra tầm bay Drone
        if veh.type == "DRONE":
            total_dist_time = (veh.distance_to(req.location) + \
                              math.sqrt(req.location[0]**2 + req.location[1]**2)) / veh.velocity
            if veh.remaining_range < total_dist_time - 1e-6: continue

        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time, service_start))

    if candidates:
        _execute_pickup(veh, candidates, ready_time, event_queue)
        return

    # 3. quay về depot nếu không còn khách hàng nào có thể phục vụ 
    # (lúc này mọi đơn trên xe đều đã được kiểm tra l_w)
    if veh.current_location != (0, 0):
        _process_final_return(veh, ready_time, depot_close, event_queue)


def _execute_failed_return_sequence(veh, urgent_req, ready_time, depot_close, event_queue):
    """Xử lý khi một đơn hàng chắc chắn vi phạm l_w: đi trả hàng và về kho."""
    travel_to_cust = veh.moving_time_to(urgent_req.location)
    arrival_at_cust = ready_time + travel_to_cust
    
    veh.current_location = urgent_req.location
    veh.busy_until = arrival_at_cust
    if not veh.routes: veh.routes.append([])
    veh.routes[-1].append(f"FAILED_RETURN_{urgent_req.id}")
    
    # Trả hàng cho khách
    urgent_req.is_picked_up = False
    urgent_req.pickup_time = None
    veh.remaining_capacity += urgent_req.demand
    veh.picked_up_orders = [p for p in veh.picked_up_orders if p.id != urgent_req.id]
    
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
    # # Quay về depot ngay sau đó
    # _process_final_return(veh, veh.busy_until, depot_close, event_queue)


def _execute_pickup(veh, candidates, ready_time, event_queue):
    """Thực hiện hành động lấy hàng cho ứng viên tốt nhất."""
    _, next_req, travel_time, service_start = min(candidates, key=lambda x: x[0])
    
    veh.remaining_capacity -= next_req.demand
    next_req.is_picked_up = True
    next_req.pickup_time = service_start
    veh.picked_up_orders.append(next_req)
    
    if veh.type == "DRONE":
        veh.remaining_range -= (veh.distance_to(next_req.location) / veh.velocity)
        
    if veh.current_location == (0, 0): veh.routes.append([])
    veh.routes[-1].append(next_req.id)
    
    veh.current_location = next_req.location
    veh.busy_until = service_start
    veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))


def _process_final_return(veh, ready_time, depot_close, event_queue):
    """Quay về depot và cập nhật trạng thái phục vụ cuối cùng của các đơn hàng."""
    arrival_at_depot = ready_time + veh.moving_time(veh.current_location, (0, 0))
    
    for r in list(veh.picked_up_orders):
        # Kiểm tra l_w và giờ đóng kho tại thời điểm thực tế cập bến 
        if (arrival_at_depot - r.pickup_time <= r.l_w + 1e-6) and \
           (arrival_at_depot <= depot_close + 1e-6):
            r.is_served = True
        else:
            r.is_served = False
            r.is_picked_up = False
            r.pickup_time = None
            
    veh.picked_up_orders = []
    veh.busy_until = arrival_at_depot
    veh.current_location = (0, 0)
    veh.remaining_capacity = veh.capacity
    if veh.type == "DRONE": veh.recharge()
    
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))