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
                # Thêm vào hàng đợi và dispatch nếu vehicle rảnh
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

    f1 = served_count / total if total > 0 else 0.0  # tối đa số khách được phục vụ
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
        "f2": f2
    }


def _dispatch_vehicle(veh: Vehicle, ind: Individual, pro: Problem, start_time: float, event_queue):
    """
    Dispatch (Điều phối) là một hành động cho veh vào thời gian start_time:
        - chọn req khả thi tốt nhất từ veh.req_queue sử dụng quy tắc sắp xếp S
        - hoặc, nếu không khả thi, veh phải trở về depot

    Quy ước l_w: thời gian cho phép từ khi đơn được pickup (req.pickup_time) tới thời điểm vehicle về depot.
    Nếu delivered_time - req.pickup_time > req.l_w => đơn bị trả lại (không served).

    Cập nhật chính:
      - Trước khi quyết định pickup một req, ước lượng "earliest possible delivered time" nếu:
          vehicle đến pickup lúc service_start rồi quay trực tiếp về depot (không lấy thêm đơn).
        earliest_delivered_time = service_start + distance(next_req.location, depot) / veh.velocity
      - Nếu với delivered time này có bất kỳ đơn nào trong (veh.picked_up_orders + next_req)
        mà elapsed = earliest_delivered_time - req.pickup_time > req.l_w  => thì chắc chắn việc pickup
        này sẽ khiến đơn đó bị trả lại (vì đây là kịch bản tốt nhất: return ngay sau pickup). Khi đó
        ta tránh pickup req đó (bỏ khỏi hàng đợi) và thử candidate khác.
      - Nếu tất cả candidate đều bị loại thì vehicle sẽ quay về depot ngay (như trước).
    """

    ready_time_for_move = max(start_time, veh.busy_until)

    # Build candidate list (score, req, travel_time) from current veh.req_queue
    candidates = []
    for req in list(veh.req_queue):
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
        if arrival > req.time_window[1] + 1e-6:
            continue

        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time))

    if candidates:
        # sort candidates by score (descending preference of larger score? existing code used min on candidates because ST smaller => priority;
        # to keep consistent with original behaviour, use same compare: earlier code appended (score, req) then best = min(candidates,key=lambda x:x[0])
        # Here we will sort ascending so min is first.
        candidates.sort(key=lambda x: x[0])

        # Try candidates in order (best first). If candidate fails l_w-estimate check, skip it and try next.
        for score, next_req, travel_time in candidates:
            arrival = ready_time_for_move + travel_time
            service_start = max(arrival, next_req.time_window[0])

            # Estimate earliest delivered time if vehicle returns immediately after this pickup
            dist_to_depot = math.sqrt(next_req.location[0]**2 + next_req.location[1]**2)
            earliest_delivered_time = service_start + dist_to_depot / veh.velocity

            # Check l_w constraint for all already picked orders and the candidate itself
            violates = False
            # include existing picked up orders
            for picked in veh.picked_up_orders:
                if picked.pickup_time is None:
                    # if somehow none, be conservative: treat as violating only if earliest_delivered_time - 0 > l_w
                    if earliest_delivered_time > getattr(picked, "l_w", 0) + 1e-6:
                        violates = True
                        break
                    else:
                        continue
                elapsed = earliest_delivered_time - picked.pickup_time
                if elapsed > getattr(picked, "l_w", 0) + 1e-6:
                    violates = True
                    break

            # check candidate itself (it would be picked at service_start)
            if not violates:
                elapsed_candidate = earliest_delivered_time - service_start
                if elapsed_candidate > getattr(next_req, "l_w", 0) + 1e-6:
                    violates = True

            if violates:
                # skip this candidate: remove from queue (so it won't be reconsidered immediately)
                veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
                # try next candidate
                continue

            # If not violates -> commit pickup (same as previous logic)
            veh.remaining_capacity -= next_req.demand
            next_req.is_picked_up = True
            next_req.pickup_time = service_start  # pickup_time là thời điểm lấy lên phương tiện
            veh.picked_up_orders.append(next_req)

            if veh.type == "DRONE":
                travel_distance = veh.distance_to(next_req.location)
                veh.remaining_range -= travel_distance / veh.velocity

            # tạo trip mới nếu rời khỏi depot
            if veh.current_location == (0, 0):
                veh.routes.append([])
                veh.routes[-1].append(next_req.id)

            veh.current_location = next_req.location
            # sau khi cập nhật, busy_until được đặt thành thời điểm bắt đầu phục vụ (pickup)
            veh.busy_until = service_start
            # loại khỏi hàng đợi ngay lập tức
            veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]

            heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
            return  # đã dispatch một pickup, thoát

        # Nếu tới đây nghĩa là không có candidate nào thỏa (tất cả bị loại) -> quay về depot
    # else: no candidates

    # Không có candidate khả thi -> quay về depot (nếu đang ở depot thì không làm gì)
    if veh.current_location == (0, 0):
        return

    back_time = veh.moving_time_to((0, 0))
    veh.busy_until = ready_time_for_move + back_time
    veh.current_location = (0, 0)

    # --- TRƯỚC KHI RESET CAPACITY / RANGE: xử lý các đơn đã được lấy ---
    # Khi phương tiện về depot thì tất cả các đơn hàng đã được nó lấy sẽ được kiểm tra:
    # delivered_time - req.pickup_time <= req.l_w  => đơn được phục vụ thành công
    # ngược lại => trả lại cho khách (is_picked_up=False, pickup_time=None)
    delivered_time = veh.busy_until
    for req in list(veh.picked_up_orders):
        if req.pickup_time is None:
            # nếu không có pickup_time thì coi như chưa pickup => không serve
            req.is_picked_up = False
            req.pickup_time = None
            continue

        elapsed = delivered_time - req.pickup_time
        if elapsed <= getattr(req, "l_w", 0) + 1e-6:
            # đơn được phục vụ thành công
            req.is_served = True
            # giữ pickup_time nếu cần
        else:
            # trả lại đơn cho khách: bỏ trạng thái lấy lên
            req.is_picked_up = False
            req.pickup_time = None
            # req.is_served vẫn False

    # Clear picked_up_orders sau khi xử lý
    veh.picked_up_orders = []

    # reset remaining_capacity/ remaining_range
    veh.remaining_capacity = veh.capacity
    if veh.type == "DRONE":
        veh.remaining_range = veh.max_range

    # Đặt sự kiện VEH_FREE để tiếp tục dispatch sau khi về depot
    heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
    
    
# gemini
def _dispatch_vehicle(veh: Vehicle, ind: Individual, pro: Problem, start_time: float, event_queue):
    ready_time_for_move = max(start_time, veh.busy_until)
    
    # 1. Kiểm tra các đơn hàng đang có trên xe xem có đơn nào sắp bị quá hạn l_w không
    # Nếu có đơn vi phạm, xe ƯU TIÊN đi trả hàng ngay lập tức
    urgent_return = None
    for picked_req in veh.picked_up_orders:
        # Giả định: nếu đi từ vị trí hiện tại về thẳng nhà khách đó mà vượt quá l_w
        # hoặc nếu đi thêm bất cứ đâu nữa sẽ quá l_w, ta nên đi trả hàng.
        time_to_customer = veh.moving_time_to(picked_req.location)
        if (ready_time_for_move + time_to_customer) - picked_req.pickup_time > picked_req.l_w:
            urgent_return = picked_req
            break

    if urgent_return:
        # Logic trả hàng: Xe đến vị trí khách, giải phóng hàng, nhưng không tính là is_served
        travel_time = veh.moving_time_to(urgent_return.location)
        arrival = ready_time_for_move + travel_time
        
        veh.current_location = urgent_return.location
        veh.busy_until = arrival
        
        # Trả hàng: xóa khỏi danh sách trên xe, quay lại hàng đợi chung của Problem để xe khác lấy
        urgent_return.is_picked_up = False
        urgent_return.pickup_time = None
        veh.remaining_capacity += urgent_return.demand
        veh.picked_up_orders.remove(urgent_return)
        
        # Log lộ trình trả hàng (nếu cần)
        if veh.current_location != (0,0):
             veh.routes[-1].append(f"RETURN_{urgent_return.id}")

        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        return

    # 2. Nếu không có đơn nào quá hạn, tiếp tục tìm ứng viên mới
    candidates = []
    for req in veh.req_queue:
        if req.is_served or req.is_picked_up:
            continue
        
        # Drone range check
        if veh.type == "DRONE":
            d_moving = veh.distance_to(req.location)
            d_returning = math.sqrt(req.location[0]**2 + req.location[1]**2)
            total_time = (d_moving + d_returning) / veh.velocity
            if veh.remaining_range < total_time - 1e-6:
                continue
        
        travel_time = veh.moving_time_to(req.location)
        arrival = ready_time_for_move + travel_time
        
        # Kiểm tra Time Window và l_w cho các đơn đang có trên xe
        if arrival > req.time_window[1] + 1e-6:
            continue
            
        can_pick = True
        for p in veh.picked_up_orders:
            # Nếu ghé thăm khách mới này làm các khách cũ trên xe chờ quá l_w
            if (arrival - p.pickup_time) > p.l_w:
                can_pick = False
                break
        if not can_pick: continue
        
        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time))
        
    if candidates:
        best = min(candidates, key=lambda x: x[0])
        _, next_req, travel_time = best
        
        arrival = ready_time_for_move + travel_time
        service_start = max(arrival, next_req.time_window[0])
        
        veh.remaining_capacity -= next_req.demand
        next_req.is_picked_up = True
        next_req.pickup_time = service_start 
        veh.picked_up_orders.append(next_req)
        
        if veh.type == "DRONE":
            veh.remaining_range -= travel_time
        
        if veh.current_location == (0, 0):
            veh.routes.append([])
        veh.routes[-1].append(next_req.id)
        
        veh.current_location = next_req.location
        veh.busy_until = service_start
        veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
        
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        
    else:
        # XE QUAY VỀ DEPOT
        if veh.current_location == (0, 0):
            return

        back_time = veh.moving_time_to((0, 0))
        arrival_at_depot = ready_time_for_move + back_time
        
        # Khi về đến kho, tất cả đơn hàng trên xe được coi là phục vụ xong (is_served)
        # Vì ta đã kiểm tra l_w ở bước trên nên chắc chắn các đơn này đều hợp lệ
        for r in veh.picked_up_orders:
            r.is_served = True

        veh.busy_until = arrival_at_depot
        veh.current_location = (0, 0)
        veh.remaining_capacity = veh.capacity
        veh.picked_up_orders = []
        
        if veh.type == "DRONE":
            veh.remaining_range = veh.max_range
            
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        
        
        
# gemini T-end
def _dispatch_vehicle(veh: Vehicle, ind: Individual, pro: Problem, start_time: float, event_queue):
    ready_time_for_move = max(start_time, veh.busy_until)
    depot_close_time = pro.depot_time_window[1]
    
    # ---------------------------------------------------------
    # 1. KIỂM TRA ƯU TIÊN: TRẢ HÀNG NẾU SẮP VI PHẠM l_w HOẶC T_end
    # ---------------------------------------------------------
    urgent_return = None
    for picked_req in veh.picked_up_orders:
        time_to_customer = veh.moving_time_to(picked_req.location)
        arrival_at_customer = ready_time_for_move + time_to_customer
        
        # Vi phạm l_w hoặc vượt quá giờ đóng cửa depot khi đang đi trả hàng
        if (arrival_at_customer - picked_req.pickup_time > picked_req.l_w) or \
           (arrival_at_customer > depot_close_time):
            urgent_return = picked_req
            break

    if urgent_return:
        travel_time = veh.moving_time_to(urgent_return.location)
        arrival = ready_time_for_move + travel_time
        
        # Xe đến vị trí khách để trả lại đơn hàng (thất bại)
        veh.current_location = urgent_return.location
        veh.busy_until = arrival
        urgent_return.is_picked_up = False
        urgent_return.pickup_time = None
        veh.remaining_capacity += urgent_return.demand
        veh.picked_up_orders.remove(urgent_return)
        
        if veh.current_location != (0,0):
             veh.routes[-1].append(f"FAILED_RETURN_{urgent_return.id}")

        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        return

    # ---------------------------------------------------------
    # 2. TÌM ỨNG VIÊN MỚI (PHẢI ĐẢM BẢO VỀ KHO KỊP T_end)
    # ---------------------------------------------------------
    candidates = []
    for req in veh.req_queue:
        if req.is_served or req.is_picked_up:
            continue
        
        travel_time = veh.moving_time_to(req.location)
        arrival_at_req = ready_time_for_move + travel_time
        # Thời gian từ vị trí khách mới về thẳng Depot
        time_to_depot = veh.moving_time(req.location, (0, 0))
        arrival_at_depot_after_req = max(arrival_at_req, req.time_window[0]) + time_to_depot

        # Ràng buộc A: Phải về Depot trước khi đóng cửa
        if arrival_at_depot_after_req > depot_close_time:
            continue

        # Ràng buộc B: Time Window của chính khách đó
        if arrival_at_req > req.time_window[1] + 1e-6:
            continue
            
        # Ràng buộc C: Kiểm tra l_w của các đơn hàng cũ trên xe nếu đi thêm khách này
        can_pick = True
        for p in veh.picked_up_orders:
            if (arrival_at_depot_after_req - p.pickup_time) > p.l_w:
                can_pick = False
                break
        if not can_pick: continue

        # Kiểm tra năng lượng cho Drone (nếu có)
        if veh.type == "DRONE":
            total_trip_time = (veh.distance_to(req.location) + math.sqrt(req.location[0]**2 + req.location[1]**2)) / veh.velocity
            if veh.remaining_range < total_trip_time - 1e-6:
                continue
        
        score = ind.s_tree.evaluate(veh, pro, req, start_time)
        candidates.append((score, req, travel_time))
        
    if candidates:
        best = min(candidates, key=lambda x: x[0])
        _, next_req, travel_time = best
        
        arrival = ready_time_for_move + travel_time
        service_start = max(arrival, next_req.time_window[0])
        
        veh.remaining_capacity -= next_req.demand
        next_req.is_picked_up = True
        next_req.pickup_time = service_start 
        veh.picked_up_orders.append(next_req)
        
        if veh.type == "DRONE":
            veh.remaining_range -= travel_time
        
        if veh.current_location == (0, 0):
            veh.routes.append([])
        veh.routes[-1].append(next_req.id)
        
        veh.current_location = next_req.location
        veh.busy_until = service_start
        veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
        
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))
        
    else:
        # ---------------------------------------------------------
        # 3. TRƯỜNG HỢP KHÔNG CÒN VIỆC: QUAY VỀ KHO
        # ---------------------------------------------------------
        if veh.current_location == (0, 0):
            return

        back_time = veh.moving_time_to((0, 0))
        arrival_at_depot = ready_time_for_move + back_time
        
        # Khi về đến kho, các đơn hàng còn lại được hoàn tất
        for r in veh.picked_up_orders:
            # Kiểm tra chốt chặn cuối cùng về l_w và T_end
            if (arrival_at_depot - r.pickup_time <= r.l_w) and (arrival_at_depot <= depot_close_time):
                r.is_served = True
            else:
                r.is_served = False
                r.is_picked_up = False

        veh.busy_until = arrival_at_depot
        veh.current_location = (0, 0)
        veh.remaining_capacity = veh.capacity
        veh.picked_up_orders = []
        
        if veh.type == "DRONE":
            veh.remaining_range = veh.max_range
            
        heapq.heappush(event_queue, (veh.busy_until, "VEH_FREE", veh.id))