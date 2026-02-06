import copy
import heapq
import math
from typing import Any, Literal, Optional
from .problem_structures import Vehicle, Problem, Request
from .gp_structure import Individual

class Simulator:
    def __init__(self, problem: Problem, individual: Individual, assignment_n: int = 1, enable_logging: bool = False):
        """
        Khởi tạo Simulator với Problem và Individual cụ thể.
        """
        # Lưu reference gốc để lấy dữ liệu requests ban đầu
        self.original_requests = problem.requests
        
        # Deepcopy problem để chạy local simulation không ảnh hưởng dữ liệu gốc
        self.problem = copy.deepcopy(problem)
        self.problem.requests = []  # Bắt đầu với list rỗng, sẽ thêm vào khi có sự kiện ARRIVE
        
        # Reset hàng đợi của các xe trong bản copy
        for veh in self.problem.vehicles:
            veh.req_queue = []
            
        self.individual = individual
        self.assignment_n = assignment_n
        self.enable_logging = enable_logging
        
        # State
        self.cur_time = 0.0
        self.event_queue = []
        self.pending_requests = []
        self.log_events = []
        
        # Map để tra cứu request gốc
        self.source_requests_map = {r.id: r for r in self.original_requests}

        # Khởi tạo các sự kiện ban đầu
        self._initialize_events()

    def _initialize_events(self):
        """Thêm các sự kiện ARRIVE ban đầu và sự kiện END vào hàng đợi."""
        for req in self.original_requests:
            heapq.heappush(self.event_queue, (req.release_time, "ARRIVE", req.id))
        
        close_time = self.problem.depot_time_window[1]
        heapq.heappush(self.event_queue, (close_time + 1e-9, "END", None))

    def run(self) -> dict:
        """
        Chạy vòng lặp sự kiện chính.
        """
        while self.event_queue:
            time, ev_type, payload = heapq.heappop(self.event_queue)
            self.cur_time = time
            
            if ev_type == "END":
                break
            
            if ev_type == "ARRIVE":
                self._handle_arrive_event(payload)

            elif ev_type == "VEH_FREE":
                self._handle_veh_free_event(payload)
                
            # Trigger kiểm tra định kỳ cho các xe rảnh (đề phòng trôi sự kiện)
            for veh in self.problem.vehicles:
                veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
                if abs(veh.busy_until - self.cur_time) < 1e-6:
                    self._dispatch_vehicle(veh)

        return self._finalize_results()

    def _handle_arrive_event(self, req_id: int):
        source_req = self.source_requests_map.get(req_id)
        if not source_req:
            return
        
        req = copy.deepcopy(source_req)
        self.problem.requests.append(req)
        
        if self.enable_logging:
            self.log_events.append(f"{self.cur_time:.4f}: ARRIVE req {req.id} at location {req.location}, time_window {req.time_window}")
        
        # Logic kiểm tra cơ bản (nếu dữ liệu lỗi time window từ đầu)
        if req.time_window[1] < self.cur_time:
            return
        
        # Làm sạch queue xe
        for veh in self.problem.vehicles:
            veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
        
        success = self._try_assign_request(req, self.problem.vehicles)
        
        if not success:
            self.pending_requests.append(req)

    def _handle_veh_free_event(self, vid: int):
        if self.enable_logging: 
            self.log_events.append(f"{self.cur_time:.4f}: VEH_FREE veh {vid}")
            
        if self.pending_requests:
            # Lọc lại các request đã quá hạn trong pending
            self.pending_requests = [r for r in self.pending_requests if self.cur_time <= r.time_window[1] + 1e-6]
            
            still_pending = []
            for p_req in self.pending_requests:
                # Thử gán lại đơn hàng chờ cho bất kỳ xe nào (bao gồm xe vừa rảnh)
                success = self._try_assign_request(p_req, self.problem.vehicles)
                if not success:
                    still_pending.append(p_req)
                elif self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: RETRY_ASSIGN success for pending req {p_req.id}")
            
            self.pending_requests = still_pending
            
        veh = next((v for v in self.problem.vehicles if v.id == vid), None)
        if veh:
            veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
            self._dispatch_vehicle(veh)

    def _finalize_results(self) -> dict:
        served_count = sum(1 for r in self.problem.requests if r.is_served)
        total = len(self.problem.requests)
        close_time = self.problem.depot_time_window[1]
        makespan = max((v.busy_until for v in self.problem.vehicles), default=0.0)

        f1 = served_count / total if total > 0 else 0.0
        f2 = max(0.0, 1.0 - makespan / close_time)

        self.individual.f1 = f1
        self.individual.f2 = f2
        self.individual.fitness = (f1, f2)
        
        if self.enable_logging:
            unserved_ids = [r.id for r in self.problem.requests if not r.is_served]
            self.log_events.append(f"END: Served {served_count}/{total}, Unserved: {unserved_ids}, Makespan: {makespan:.2f}")

        return {
            "total": total,
            "served": served_count,
            "unserved": total - served_count,
            "makespan": makespan,
            "ratio": f1,
            "f1": f1,
            "f2": f2,
            "r_tree": self.individual.r_tree.to_string(),
            "s_tree": self.individual.s_tree.to_string(),
            "simulated_problem": self.problem,
            "log_events": self.log_events if self.enable_logging else None
        }

    def _try_assign_request(self, req: Request, vehicles: list[Vehicle]) -> bool:
        """Cố gắng gán request cho xe sử dụng R-tree của cá thể."""
        candidates = []
        for veh in vehicles:
            # Ràng buộc cho phép DRONE lấy hàng
            if veh.type == "DRONE" and req.able_drone == 0:
                continue
            
            # Ràng buộc hàng đợi phục vụ tối đa
            if veh.sum_of_req_demand() + req.demand > veh.capacity + 1e-6:
                continue
            
            # Ràng buộc về phạm vi bay của DRONE
            # if veh.type == "DRONE":
            #     d_moving = math.sqrt((veh.current_location[0] - req.location[0])**2 +
            #                          (veh.current_location[1] - req.location[1])**2)
            #     d_returning = math.sqrt(req.location[0]**2 + req.location[1]**2)

            #     total_time = (d_moving + d_returning) / veh.velocity

            #     if veh.remaining_range < total_time - 1e-6:
            #         continue
            if veh.type =="DRONE" and not veh.check_can_fly(req.location):
                continue

            score = self.individual.r_tree.evaluate(veh, self.problem, req, self.cur_time)
            candidates.append((score, veh))

        if not candidates:
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: NO_CANDIDATES for req {req.id}: constraints violate")
            return False

        candidates.sort(key=lambda x: x[0], reverse=True)
        
        assigned_count = 0
        assigned_any = False
        
        for score, veh in candidates:
            if req.is_picked_up or req.is_served:
                break
            
            start_service_time = max(self.cur_time, veh.busy_until)
            travel_time = veh.moving_time_to(req.location)
            arrival_time = start_service_time + travel_time
            
            if arrival_time > req.time_window[1] + 1e-6:
                continue
            
            veh.req_queue.append(req)
            assigned_any = True
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: ASSIGN req {req.id} to veh {veh.id} (score {score:.2f})")
            
            # Nếu hiện tại xe đang rảnh thì điều phối cho xe này luôn
            if veh.busy_until <= self.cur_time + 1e-6:
                self._dispatch_vehicle(veh)
            
            assigned_count += 1
            if assigned_count >= self.assignment_n:
                break
        
        return assigned_any

    def _dispatch_vehicle(self, veh: Vehicle) -> None:
        """Điều phối xe: chọn request tiếp theo từ hàng đợi hoặc về depot."""
        veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]
        
        # ready_time: thời điểm bắt đầu đi (lấy muộn nhất của thời điểm hiện tại và thời điểm xe hết bận)
        ready_time = max(self.cur_time, veh.busy_until)
        depot_close = self.problem.depot_time_window[1]
        
        # 1. Kiểm tra có đơn nào trên xe sắp vi phạm l_w không
        if veh.picked_up_orders:
            time_to_depot = veh.moving_time(veh.current_location, (0, 0))
            arrival_at_depot = ready_time + time_to_depot
            
            for picked in veh.picked_up_orders:
                if (arrival_at_depot - picked.pickup_time > picked.l_w + 1e-6):
                    self._execute_failed_return_sequence(veh, picked, ready_time, note="Violate l_w")
                    return
                if (arrival_at_depot > depot_close + 1e-6):
                    self._execute_failed_return_sequence(veh, picked, ready_time, note="Violate depot time window")
                    return

        # 2. Chọn khách hàng tiếp theo để đến lấy hàng sử dụng S-tree
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

            # Kiểm tra tầm bay DRONE
            if veh.type == "DRONE":
                total_dist_time = (veh.distance_to(req.location) + \
                                  math.sqrt(req.location[0]**2 + req.location[1]**2)) / veh.velocity
                if veh.remaining_range < total_dist_time - 1e-6: continue

            score = self.individual.s_tree.evaluate(veh, self.problem, req, self.cur_time)
            candidates.append((score, req, travel_time, service_start))

        if candidates:
            # Sort theo score (min=best)
            candidates.sort(key=lambda x: x[0])
            for can in candidates:
                req = can[1]
                travel_time = can[2]
                service_start = can[3]
                
                if veh.remaining_capacity < req.demand - 1e-6:
                    continue
                
                if self.enable_logging:
                    self.log_events.append(f"{ready_time:.4f}: DISPATCH veh {veh.id} from {veh.current_location} (busy_until {veh.busy_until:.4f})")
                
                self._execute_pickup(veh, req, ready_time, travel_time, service_start)
                return

        if not candidates and veh.current_location == (0, 0):
            if self.enable_logging:
                self.log_events.append(f"{ready_time:.4f}: NO_SEQ_CANDIDATES for veh {veh.id}: no feasible req in queue")
        
        # 3. Quay về depot nếu không còn khách hàng nào có thể phục vụ
        if veh.current_location != (0, 0):
            self._process_final_return(veh, ready_time)

    def _execute_pickup(self, veh: Vehicle, next_req: Request, ready_time: float, travel_time: float, service_start: float) -> None:
        """Thực hiện hành động lấy hàng và cập nhật trạng thái."""
        arrival_time = ready_time + travel_time
        
        if self.enable_logging:
            self.log_events.append(f"{service_start:.4f}: PICKUP req {next_req.id} by veh {veh.id} at {next_req.location}, arrival {arrival_time:.4f}")    
        
        if veh.current_location == (0.0, 0.0): 
            veh.routes.append([])
            
        if veh.type == "DRONE":
            veh.remaining_range -= veh.moving_time_to(next_req.location)
            
        entry = {
            'action': 'pickup',
            'req_id': next_req.id,
            'ready_time': ready_time,
            'travel_time': travel_time,
            'arrival_time': arrival_time,
            'service_start': service_start,
            'location': next_req.location,
            'prev_location': veh.current_location,
            'vehicle_state': {
                'busy_until': service_start,
                'remaining_capacity': veh.remaining_capacity - next_req.demand,
                'remaining_range': veh.remaining_range if veh.type == 'DRONE' else None
            },
            'note': None
        }
        veh.routes[-1].append(entry)
        
        # Cập nhật trạng thái
        next_req.is_picked_up = True
        next_req.pickup_time = service_start
        
        veh.remaining_capacity -= next_req.demand
        veh.picked_up_orders.append(next_req)
        veh.current_location = next_req.location
        veh.busy_until = service_start
        veh.req_queue = [r for r in veh.req_queue if r.id != next_req.id]
        
        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", veh.id))

    def _process_final_return(self, veh: Vehicle, ready_time: float) -> None:
        """Quay về depot và hoàn tất các đơn hàng."""
        travel_time = veh.moving_time_to((0.0, 0.0))
        arrival_at_depot = ready_time + travel_time
        
        if self.enable_logging:
            self.log_events.append(f"{arrival_at_depot:.4f}: RETURN_DEPOT veh {veh.id}, serve {len(veh.picked_up_orders)} orders")
        
        if veh.type == "DRONE": 
            veh.recharge()
        
        entry = {
            'action': 'return_depot',
            'req_id': None,
            'ready_time': ready_time,
            'travel_time': travel_time,
            'arrival_time': arrival_at_depot,
            'service_start': None,
            'location': (0.0, 0.0),
            'prev_location': veh.current_location,
            'vehicle_state': {
                'remaining_capacity': veh.capacity,
                'busy_until': arrival_at_depot,
                'remaining_range': veh.max_range if veh.type == 'DRONE' else None
            },
            'note': None
        }
        veh.routes[-1].append(entry)

        for r in veh.picked_up_orders:
            r.is_served = True
                
        veh.picked_up_orders = []
        veh.busy_until = arrival_at_depot
        veh.current_location = (0.0, 0.0)
        veh.remaining_capacity = veh.capacity
        
        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", veh.id))

    def _execute_failed_return_sequence(self, veh: Vehicle, urgent_req: Request, ready_time: float, note: str) -> None:
        """Xử lý trường hợp bắt buộc phải trả hàng do vi phạm ràng buộc thời gian (failed return)."""
        travel_to_cust = veh.moving_time_to(urgent_req.location)
        arrival_at_cust = ready_time + travel_to_cust
        
        if self.enable_logging:
            self.log_events.append(f"{arrival_at_cust:.4f}: FAILED_RETURN req {urgent_req.id} by veh {veh.id}, note: {note}")
        
        if not veh.routes: 
            veh.routes.append([])
        
        if veh.type == "DRONE":
            veh.remaining_range -= veh.moving_time_to(urgent_req.location)
            
        entry = {
            'action': 'failed_return',
            'req_id': urgent_req.id,
            'ready_time': ready_time,
            'travel_time': travel_to_cust,
            'arrival_time': arrival_at_cust,
            'service_start': None,
            'location': urgent_req.location,
            'prev_location': veh.current_location,
            'vehicle_state': {
                'remaining_capacity': veh.remaining_capacity + urgent_req.demand,
                'busy_until': arrival_at_cust,
                'remaining_range': veh.remaining_range if veh.type == 'DRONE' else None
            },
            'note': note
        }
        veh.routes[-1].append(entry)
        
        # Reset trạng thái request
        urgent_req.is_picked_up = False
        urgent_req.pickup_time = None
        
        # Nếu vẫn còn trong time window thì ném lại vào pending để xử lý sau
        if arrival_at_cust <= urgent_req.time_window[1] + 1e-6:
            self.pending_requests.append(urgent_req)
            
        veh.current_location = urgent_req.location
        veh.busy_until = arrival_at_cust
        veh.remaining_capacity += urgent_req.demand
        veh.picked_up_orders = [p for p in veh.picked_up_orders if p.id != urgent_req.id]
        
        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", veh.id))