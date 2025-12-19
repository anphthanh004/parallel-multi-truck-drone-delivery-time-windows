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
            # if not req or req.is_picked_up or req.is_served or cur_time > req.time_window[1] + 1e-6:
            if not req or req.is_served or cur_time > req.time_window[1] + 1e-6:
                continue
            
            candidates = []
            for veh in local_pro.vehicles:
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
            
            candidates.sort(key=lambda x: x[0], reverse = True)
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
            if veh and veh.req_queue:
                _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)
            
        # Sau khi xử lý sự kiện, cũng kiểm tra bất kỳ vehicle nào có busy_until == curret_time để đảm bảo an toàn
        for veh in local_pro.vehicles:
            if abs(veh.busy_until - cur_time) < 1e-6 and veh.req_queue:
                _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)
    
    
    # Tính toán kết quả
    served_count = sum(1 for r in local_pro.requests if r.is_served)
    total = len(local_pro.requests)
    makespan = max((v.busy_until for v in local_pro.vehicles), default=0.0)
    
    f1 = served_count / total if total > 0 else 0.0 # tối đa số khách được phục vụ
    f2 = max(0.0, 1.0 - makespan / close_time) 
    
    indi.f1 = f1
    indi.f2 = f2
    indi.fitness = (f1, f2)
    
    return {
        "total": total,
        "served": served_count,
        "unserved": total-served_count,
        "makespan": makespan,
        "ratio": f1,
        "f1": f1,
        "f2": f2
    }


def _dispatch_vehicle(veh: Vehicle, ind: Individual, pro: Problem, start_time: float, event_queue):
    """
    Dispatch (Điều phối) là một hành động cho veh vào thời gian start_time:
        - chọn req khả thi tốt nhất từ veh.req_queue sử dụng quy tắc sắp xếp S
        - hoặc, nếu không khả thi, veh phải trở về depot
    Sau khi lên lịch hành động, đặt veh.busy_until và đẩy (veh.busy_until, "VEH_FREE", veh.id) vào event_queue.
    """
    ready_time_for_move = max(start_time, veh.busy_until)
    
    candidates = []
    for req in veh.req_queue:
        if req.is_served:
            veh.req_queue.remove(req)
            continue
        
        if veh.type == "DRONE":
            d_moving = veh.distance_to(req.location)
            d_returning = math.sqrt(req.location[0]**2 + req.location[1]**2)
            total_time = d_moving / veh.velocity + d_returning / veh.velocity
            if veh.remaining_range < total_time - 1e-6:
                continue
        
        travel_time = veh.moving_time_to(req.location)
        arrival = ready_time_for_move + travel_time
        
        # Constraint 1: Time Window check
        if arrival > req.time_window[1] + 1e-6:
            continue
        
        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time))
        
    if candidates:
        best = min(candidates, key=lambda x: x[0])
        _, next_req, travel_time = best
        
        arrival = ready_time_for_move + travel_time
        service_start = max(arrival, next_req.time_window[0])
        
        # cập nhật trạng thái vehicle
        veh.remaining_capacity -= next_req.demand
        next_req.is_picked_up = True
        next_req.pickup_time = service_start
        veh.picked_up_orders.append(next_req)
        
        if veh.type == "DRONE":
            veh.remaining_range -= travel_time
        
        # tạo trip mới nếu rời khỏi depot
        if veh.current_location == (0, 0):
            veh.routes.append([])
            veh.routes[-1].append(next_req.id)
        
        veh.current_location = next_req.location
        veh.busy_until = service_start
        # next_req.is_served = True
        next_req.is_picked_up = True
        # next_req.is_served = True
        veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
        
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        
    else:
        if veh.current_location == (0, 0):
            return

        back_time = veh.moving_time_to((0, 0))
        veh.busy_until = ready_time_for_move + back_time
        veh.current_location = (0, 0)
        
        # reset remaining_capacity/ remaining_range
        veh.remaining_capacity = veh.capacity
        if veh.type == "DRONE":
            veh.remaining_range = veh.max_range
            
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        

