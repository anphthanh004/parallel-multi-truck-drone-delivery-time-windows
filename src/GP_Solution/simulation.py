import copy
import heapq
import math

from typing import Any, Literal, Optional
from .problem_structures import Vehicle, Problem, Request
from .gp_structure import NodeGP, Individual

# -------------------------
# Giả lập phân bổ sự kiện
# -------------------------

def simulate_policy(indi: Individual, pro: Problem, **kwargs) -> dict:
    local_pro = copy.deepcopy(pro)
    close_time = local_pro.depot_time_window[1]
    assignment_n = kwargs.get("assignment_n", 1)
    time_slot = kwargs.get("time_slot", 0)
    
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
            if not req or req.is_picked_up or req.is_served or cur_time > req.time_window[1] + 1e-6:
                continue

            candidates = []
            for veh in local_pro.vehicles:
                veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]

                # Ràng buộc cho phép DRONE lấy hàng
                if veh.type == "DRONE" and req.able_drone == 0:
                    continue
                
                # Ràng buộc hàng đợi phục vụ tối đa
                if veh.sum_of_req_demand() + req.demand > veh.capacity + 1e-6:
                    continue
                
                # Ràng buộc về phạm vi bay của DRONE
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
            
            assigned_count = 0
            for score, veh in candidates:
                start_service_time = max(cur_time, veh.busy_until)
                travel_time = veh.moving_time_to(req.location)
                arrival_time = start_service_time + travel_time
                if arrival_time > req.time_window[1] + 1e-6:
                    continue
                veh.req_queue.append(req)
                # Nếu hiện tại xe đang rảnh thì điều phối cho xe này luôn
                if veh.busy_until <= cur_time + 1e-6:
                    _dispatch_vehicle(veh, indi, local_pro, cur_time, event_queue)
                
                assigned_count += 1
                # Nếu đã gán đủ số lượng xe quy định thì dừng
                if assigned_count >= assignment_n:
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
        "total": total, # tổng số request
        "served": served_count, # tổng số request được phục vụ
        "unserved": total - served_count, # tổng số request không được phục vụ
        "makespan": makespan, # thời gian hoàn thành muộn nhất
        "ratio": f1, # tỉ lệ được phục vụ = f1
        "f1": f1, # f1 của indi
        "f2": f2,  # f2 của indi
        "r_tree": indi.r_tree.to_string(),
        "s_tree": indi.s_tree.to_string(),
        "simulated_problem": local_pro # pro sau khi điều phối: các request và vehicle đã thay đổi trạng thái
    }

def _dispatch_vehicle(
        veh: Vehicle, 
        ind: Individual, 
        pro: Problem, 
        start_time: float, 
        event_queue: list[tuple[float, str, Optional[int]]]
    ) -> None:
    veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
    ready_time = max(start_time, veh.busy_until)
    depot_close = pro.depot_time_window[1]
    
    # 1. Kiểm tra có đơn nào sắp vi phạm l_w không (đơn hàng được phục vụ sớm nhất là lúc hàng về kho)
    if veh.picked_up_orders:
        time_to_depot = veh.moving_time(veh.current_location, (0, 0))
        arrival_at_depot = ready_time + time_to_depot
        
        for picked in veh.picked_up_orders:
            if (arrival_at_depot - picked.pickup_time > picked.l_w + 1e-6) or \
               (arrival_at_depot > depot_close + 1e-6):
                # _execute_failed_return_sequence(veh, picked, ready_time, depot_close, event_queue)
                _execute_failed_return_sequence(veh, picked, ready_time, event_queue)
                return

    # 2. Chọn khách hàng tiếp theo để đến lấy hàng
    candidates = []
    for req in veh.req_queue:
        if req.is_served or req.is_picked_up: continue
        
        # ready_time: thời điểm sẵn sàng đi (lấy muộn nhất của thời điểm bắt đầu và thời điểm xe hết bận rộn)
        travel_time = veh.moving_time_to(req.location) # khoảng thời gian di chuyển đến địa điểm mới
        arrival_req = ready_time + travel_time         # thời điểm tới địa điểm mới
        service_start = max(arrival_req, req.time_window[0])  # nếu đến sớm thì phải chờ 
        
        # Kiểm tra ràng buộc thời gian khách hàng
        if arrival_req > req.time_window[1] + 1e-6: continue
        
        # Nếu lấy đơn của khách này thì phải đảm bảo về đuọc kho, do đó tốt nhất là kiểm tra phải về được luôn từ điểm đón
        # Kiểm tra khả năng về depot sau khi lấy khách này
        arrival_depot_after = service_start + veh.moving_time(req.location, (0, 0))
        if arrival_depot_after > depot_close + 1e-6: continue
        
        # Nếu lấy đơn này mà trả được ngay thì phải kiểm tra trong trường hợp tốt nhất đó, các đơn còn lại còn được đáp ứng l_w không
        # Kiểm tra l_w của toàn bộ hàng trên xe (bao gồm cả req mới) 
        if any((arrival_depot_after - p.pickup_time > p.l_w + 1e-6) for p in veh.picked_up_orders):
            continue
        if (arrival_depot_after - service_start > req.l_w + 1e-6):
            continue

        # Kiểm tra tầm bay DRONE
        if veh.type == "DRONE":
            total_dist_time = (veh.distance_to(req.location) + \
                              math.sqrt(req.location[0]**2 + req.location[1]**2)) / veh.velocity
            if veh.remaining_range < total_dist_time - 1e-6: continue

        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time, service_start))

    if candidates:
        # _execute_pickup(veh, candidates, ready_time, event_queue)
        _execute_pickup(veh, candidates, event_queue)
        return

    # 3. quay về depot nếu không còn khách hàng nào có thể phục vụ 
    # (lúc này mọi đơn trên xe đều đã được kiểm tra l_w)
    if veh.current_location != (0, 0):
        # veh: xe,  ready_time: thời điểm bắt đầu đi, depot_close: thời điểm đóng cửa của bài toán, event_queue: hàng đợi sự kiện
        # _process_final_return(veh, ready_time, depot_close, event_queue)
        _process_final_return(veh, ready_time, event_queue)

def _execute_failed_return_sequence(
        veh: Vehicle, 
        urgent_req: Request, # đơn hàng đã được lấy, bây giờ cần phải trả đến nơi cũ của khách
        ready_time: float, 
        # depot_close: float, 
        event_queue: list[tuple[float, str, Optional[int]]]
    ) -> None:
    """Xử lý khi một đơn hàng chắc chắn vi phạm l_w"""
    
    travel_to_cust = veh.moving_time_to(urgent_req.location) # khoảng thời gian đến chỗ customer
    arrival_at_cust = ready_time + travel_to_cust
    
    # Xe đến chỗ khách: tọa độ hiện tại của xe là tọa độ của khách, hết bận là lúc đến chỗ khách (không cần kiểm tra time window của khách) 
    if veh.type == "DRONE":
        veh.remaining_range -= (veh.distance_to(urgent_req.location) / veh.velocity)
    veh.current_location = urgent_req.location
    veh.busy_until = arrival_at_cust
    
    if not veh.routes: veh.routes.append([])
    veh.routes[-1].append(f"FAILED_RETURN_{urgent_req.id}")
    
    # Trả hàng cho khách
    # Cập nhật:
    # + Request: được lấy=False, thời điểm lấy=False (reset cho đơn hàng)
    # + Vehicle: trả lại sức chứa, danh sách lấy hàng bỏ đi đơn đó
    urgent_req.is_picked_up = False
    urgent_req.pickup_time = None
    veh.remaining_capacity += urgent_req.demand
    veh.picked_up_orders = [p for p in veh.picked_up_orders if p.id != urgent_req.id]
    
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))


def _execute_pickup(
        veh: Vehicle, 
        candidates: Vehicle, 
        # ready_time: float, 
        event_queue: list[tuple[float, str, Optional[int]]]
    ) -> None:
    """Thực hiện hành động lấy hàng cho ứng viên tốt nhất."""
    # candidates: là list gồm (score, req, travel_time, service_start)
    # score: điểm cho sequencing rule (min=best), req: Request, travel_time: khoảng thời gian di chuyển, service_start: thời điểm bắt đầu phục vụ 
    _, next_req, _, service_start = min(candidates, key=lambda x: x[0])
    
    # Sau khi lấy hàng này thì những cái sau thay đổi:
    # + sức chứa còn lại của xe (remaining_capacity) 
    # + danh sách các đơn hàng đang giữ trên xe (picked_up_orders)
    # + (nếu là DRONE) bán kính bay bị giảm
    # + lộ trình cuối cùng của xe thêm id của đơn hàng
    # + vị trí (location) của xe
    # + thời điểm hết bận rộn (busy_until) của xe (là sau khi phục vụ=thời điểm bắt đầu phục vụ)
    # + hàng đợi request (request_queue) bỏ đi đơn hàng đó
    
    veh.remaining_capacity -= next_req.demand
    veh.picked_up_orders.append(next_req)
    
    next_req.is_picked_up = True
    next_req.pickup_time = service_start
    
    if veh.type == "DRONE":
        veh.remaining_range -= (veh.distance_to(next_req.location) / veh.velocity)
        
    if veh.current_location == (0, 0): 
        veh.routes.append([])
    veh.routes[-1].append(next_req.id)
    
    veh.current_location = next_req.location
    veh.busy_until = service_start
    
    veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
    
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))


def _process_final_return(
        veh: Vehicle, 
        ready_time: float, 
        event_queue: list[tuple[float, str, Optional[int]]]
    ) -> None:
    """Quay về depot và cập nhật trạng thái phục vụ cuối cùng của các đơn hàng."""
    arrival_at_depot = ready_time + veh.moving_time(veh.current_location, (0, 0))
    
    for r in veh.picked_up_orders:
        r.is_served = True
            
    veh.picked_up_orders = []
    veh.busy_until = arrival_at_depot
    veh.current_location = (0.0, 0.0)
    veh.remaining_capacity = veh.capacity
    if veh.type == "DRONE": veh.recharge()
    
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))