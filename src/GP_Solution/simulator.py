# simulator.py
import copy
import heapq
import math
from typing import Any, Literal, Optional, Iterable, Set, List, Tuple, Dict
from .problem_structures import Vehicle, Problem, Request
from .gp_structure import Individual

class Simulator:
    def __init__(self, problem: Problem, individual: Individual, assignment_n: int = 1, enable_logging: bool = False,
                 r_alpha: float = 0.7, arrival_beta: float = 0.3):
        """
        Khởi tạo Simulator với Problem và Individual cụ thể.
        r_alpha, arrival_beta: trọng số để kết hợp R-tree score và projected arrival time
        """
        # Lưu reference gốc để lấy dữ liệu requests ban đầu
        self.original_requests = problem.requests

        # Deepcopy problem để chạy local simulation không ảnh hưởng dữ liệu gốc
        self.problem = copy.deepcopy(problem)
        self.problem.requests = []  # Bắt đầu với list rỗng, sẽ thêm vào khi có sự kiện ARRIVE

        # Reset hàng đợi của các xe trong bản copy và đảm bảo thuộc tính wake-related tồn tại
        for veh in self.problem.vehicles:
            veh.req_queue = []
            # add wake-related attributes dynamically if they don't exist
            if not hasattr(veh, 'scheduled_wake_time'):
                veh.scheduled_wake_time: Optional[float] = None
                setattr(veh, 'scheduled_wake_time', None)
            if not hasattr(veh, 'waiting_for_req_id'):
                setattr(veh, 'waiting_for_req_id', None)
            if not hasattr(veh, 'waiting_for_s_score'):
                setattr(veh, 'waiting_for_s_score', None)

        self.individual = individual
        self.assignment_n = assignment_n
        self.enable_logging = enable_logging

        # Heuristic weights
        self.r_alpha = r_alpha
        self.arrival_beta = arrival_beta

        # State
        self.cur_time = 0.0
        self.event_queue = []
        self.pending_requests: List[Request] = []
        self.log_events: List[str] = []

        # Map để tra cứu request gốc
        self.source_requests_map = {r.id: r for r in self.original_requests}

        # Khởi tạo các sự kiện ban đầu
        self._initialize_events()

    def _initialize_events(self):
        """Thêm các sự kiện ARRIVE ban đầu và sự kiện END vào hàng đợi."""
        for req in self.original_requests:
            priority = (req.time_window[1], -req.demand)
            heapq.heappush(self.event_queue, (req.release_time, "ARRIVE", (priority, req.id)))
        
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
                req_id = payload[1]
                self._handle_arrive_event(req_id)

            elif ev_type == "VEH_FREE":
                self._handle_veh_free_event(payload)

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
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: ADD_TO_PENDING req {req.id} (deadline {req.time_window[1]:.4f})")
            self.pending_requests.append(req)

            # Nếu có xe đang ngủ chờ tại depot, kiểm tra xem request mới có ưu tiên hơn request mà xe đang chờ hay không.
            # Nếu có -> đánh thức xe ngay (push VEH_FREE tại thời điểm hiện tại).
            for veh in self.problem.vehicles:
                # chỉ quan tâm xe ở depot có scheduled_wake_time được set
                if getattr(veh, 'scheduled_wake_time', None) is None:
                    continue
                # xe phải đang ở depot (chỉ ngủ ở depot)
                if veh.current_location != (0.0, 0.0):
                    continue
                # scheduled_wake_time ở tương lai (còn đang ngủ)
                if veh.scheduled_wake_time is None or veh.scheduled_wake_time <= self.cur_time + 1e-9:
                    continue

                # Tính score của request mới theo S-tree trên xe này (lower = better trong dispatch sort)
                try:
                    new_s_score = self.individual.s_tree.evaluate(veh, self.problem, req, self.cur_time)
                except Exception:
                    new_s_score = None

                waiting_s = getattr(veh, 'waiting_for_s_score', None)
                # Nếu xe đang chờ 1 request cụ thể (có điểm s) và request mới tốt hơn thì wake
                if new_s_score is not None and waiting_s is not None:
                    if new_s_score < waiting_s - 1e-9:
                        if self.enable_logging:
                            self.log_events.append(
                                f"{self.cur_time:.4f}: WAKE_UP_TRIGGER by ARRIVE req {req.id} for veh {veh.id} "
                                f"(new_s={new_s_score:.4f} < waiting_s={waiting_s:.4f})"
                            )
                        # Push immediate VEH_FREE event to wake vehicle now. Payload as tuple (id, action, detail)
                        heapq.heappush(self.event_queue, (self.cur_time, "VEH_FREE", (veh.id, "WAKE_UP", req.id)))
                        # Clear scheduled wake metadata to avoid duplicate wake later
                        veh.scheduled_wake_time = None
                        veh.waiting_for_req_id = None
                        veh.waiting_for_s_score = None

    def _handle_veh_free_event(self, payload: Any):
        # Normalize payload parsing. Accept:
        # - simple int (vehicle id)
        # - tuple (veh_id, action, detail) or (veh_id, action)
        if isinstance(payload, tuple):
            if len(payload) == 3:
                vid, action, detail = payload
            elif len(payload) == 2:
                vid, action = payload
                detail = None
            else:
                vid = payload[0]
                action = "WAKE_UP"
                detail = None
        else:
            vid = payload
            action = "WAKE_UP"
            detail = None

        # Logging
        if self.enable_logging:
            if action == "PICKUP":
                self.log_events.append(f"{self.cur_time:.4f}: [EVENT] FINISHED PICKUP req {detail} by veh {vid}")
            elif action == "RETURN":
                self.log_events.append(f"{self.cur_time:.4f}: [EVENT] RETURNED DEPOT veh {vid}, served {detail} orders")
            elif action == "WAKE_UP":
                self.log_events.append(f"{self.cur_time:.4f}: [EVENT] WAKE UP veh {vid} at Depot (trigger detail={detail})")
            else:
                self.log_events.append(f"{self.cur_time:.4f}: [EVENT] VEH_FREE veh {vid} action={action} detail={detail}")

        # Trước khi wake/dispatch, xử lý pending requests chung (nếu có).
        # Điều này cho phép xe vừa RETURN kiểm tra pending và nhận việc ngay nếu phù hợp.
        if self.pending_requests:
            # Loại expired
            self.pending_requests = [r for r in self.pending_requests if self.cur_time <= r.time_window[1] + 1e-6]
            self.pending_requests.sort(key=lambda r: (r.time_window[1], -r.demand))
            still_pending = []
            for p_req in self.pending_requests:
                success = self._try_assign_request(p_req, self.problem.vehicles)
                if not success:
                    still_pending.append(p_req)
                elif self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: RETRY_ASSIGN success for pending req {p_req.id}")
            self.pending_requests = still_pending

        # Find vehicle object
        veh = next((v for v in self.problem.vehicles if v.id == vid), None)
        if not veh:
            return

        # If action is RETURN or PICKUP, clear any scheduled wake metadata (vehicle state changed)
        if action in ("RETURN", "PICKUP"):
            veh.scheduled_wake_time = None
            veh.waiting_for_req_id = None
            veh.waiting_for_s_score = None

        # Clean queue and dispatch
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

    # -------------------------
    # Helpers for candidate & ranks
    # -------------------------
    def _compute_raw_candidates_for_request(self, req: Request, vehicles: Iterable[Vehicle], exclude_vehicle_ids: Optional[Set[int]] = None):
        """
        Trả về raw_candidates list tương tự format trước đó:
        mỗi phần tử là dict với keys: veh, r_score, start_service_time, travel_time, arrival_time
        exclude_vehicle_ids: set các id xe cần loại
        """
        raw_candidates = []
        exclude_vehicle_ids = exclude_vehicle_ids or set()
        for veh in vehicles:
            if veh.id in exclude_vehicle_ids:
                continue

            # Ràng buộc cho phép DRONE lấy hàng
            if veh.type == "DRONE" and req.able_drone == 0:
                continue

            if req.demand > veh.capacity + 1e-6:
                continue

            if veh.type == "DRONE" and not veh.check_can_fly(req.location):
                continue

            # compute raw r_score
            r_score = self.individual.r_tree.evaluate(veh, self.problem, req, self.cur_time)

            start_service_time = max(self.cur_time, veh.busy_until)
            travel_time = veh.moving_time_to(req.location)
            arrival_time = start_service_time + travel_time

            raw_candidates.append({
                "veh": veh,
                "r_score": r_score,
                "start_service_time": start_service_time,
                "travel_time": travel_time,
                "arrival_time": arrival_time
            })
        return raw_candidates

    def _compute_combined_candidates(self, raw_candidates: List[Dict]):
        """
        Từ raw_candidates tính normalized combined score và trả về list (combined, candidate_dict) sorted desc.
        """
        if not raw_candidates:
            return []

        r_scores = [c["r_score"] for c in raw_candidates]
        arr_times = [c["arrival_time"] for c in raw_candidates]

        r_min, r_max = min(r_scores), max(r_scores)
        arr_min, arr_max = min(arr_times), max(arr_times)

        r_span = r_max - r_min if abs(r_max - r_min) > 1e-9 else 1.0
        arr_span = arr_max - arr_min if abs(arr_max - arr_min) > 1e-9 else 1.0

        combined_candidates = []
        for c in raw_candidates:
            r_norm = (c["r_score"] - r_min) / r_span
            arr_norm = 1.0 - ((c["arrival_time"] - arr_min) / arr_span)
            combined = self.r_alpha * r_norm + self.arrival_beta * arr_norm
            combined_candidates.append((combined, c))

        combined_candidates.sort(key=lambda x: x[0], reverse=True)
        return combined_candidates

    def _compute_candidate_list(self, req: Request, vehicles: Iterable[Vehicle], exclude_vehicle_ids: Optional[Set[int]] = None):
        """Trả về danh sách candidates được sắp xếp (combined_score, candidate_dict)"""
        raw = self._compute_raw_candidates_for_request(req, vehicles, exclude_vehicle_ids)
        return self._compute_combined_candidates(raw)

    def _get_rank_of_vehicle_for_request(self, req: Request, veh_id: int, candidate_list: List[Tuple[float, Dict]]) -> Optional[int]:
        """Trả về rank (index) của veh_id trong candidate_list, None nếu không nằm trong danh sách"""
        for idx, (_score, cand) in enumerate(candidate_list):
            if cand["veh"].id == veh_id:
                return idx
        return None

    # -------------------------
    # Try assigning to a single vehicle (with possible replacement of top-ranked requests)
    # -------------------------
    def _attempt_assign_to_vehicle(self, req: Request, veh: Vehicle, combined_score_on_veh: float) -> Tuple[bool, List[Request]]:
        """
        Thử gán req vào veh...
        (giữ nguyên logic cũ)
        """
        # Tìm các request hiện có mà veh là top candidate (rank 0)
        top_requests_on_veh: List[Request] = []
        for q in list(veh.req_queue):
            if q.is_picked_up or q.is_served:
                continue
            cand_list = self._compute_candidate_list(q, self.problem.vehicles)
            rank = self._get_rank_of_vehicle_for_request(q, veh.id, cand_list)
            if rank == 0:
                top_requests_on_veh.append(q)

        sum_top_demand = sum([rq.demand for rq in top_requests_on_veh])
        capacity = veh.capacity

        if sum_top_demand + req.demand <= capacity + 1e-6:
            veh.req_queue.append(req)
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: ASSIGN_DIRECT req {req.id} -> veh {veh.id}")
            if veh.busy_until <= self.cur_time + 1e-6:
                self._dispatch_vehicle(veh)
            return True, []

        removable: List[Tuple[Request, float]] = []
        for q in top_requests_on_veh:
            q_cand_list = self._compute_candidate_list(q, self.problem.vehicles)
            q_score_on_veh = None
            for sc, qc in q_cand_list:
                if qc["veh"].id == veh.id:
                    q_score_on_veh = sc
                    break
            if q_score_on_veh is None:
                continue
            removable.append((q, q_score_on_veh))

        removable.sort(key=lambda x: x[1])

        freed = 0.0
        removed_reqs: List[Request] = []
        for q, q_score in removable:
            if combined_score_on_veh <= q_score + 1e-9:
                continue
            removed_reqs.append(q)
            freed += q.demand
            if sum_top_demand - freed + req.demand <= capacity + 1e-6:
                break

        if removed_reqs and (sum_top_demand - freed + req.demand <= capacity + 1e-6):
            for q in removed_reqs:
                try:
                    veh.req_queue.remove(q)
                except ValueError:
                    pass
                q.is_picked_up = False
                q.pickup_time = None
            veh.req_queue.append(req)
            if self.enable_logging:
                removed_ids = [r.id for r in removed_reqs]
                self.log_events.append(f"{self.cur_time:.4f}: REPLACE on veh {veh.id}: removed {removed_ids} -> added req {req.id}")
            if veh.busy_until <= self.cur_time + 1e-6:
                self._dispatch_vehicle(veh)
            return True, removed_reqs

        return False, []

    # -------------------------
    # Main assignment with rank tiers + reassign-as-next-rank
    # -------------------------
    def _try_assign_request(self, req: Request, vehicles: Iterable[Vehicle], exclude_vehicle_ids: Optional[Set[int]] = None) -> bool:
        """
        Cố gắng gán request cho vehicles...
        """
        exclude_vehicle_ids = exclude_vehicle_ids or set()
        if hasattr(req, 'cached_candidates') and req.cached_candidates is not None:
             cand_list = req.cached_candidates
        else:
             cand_list = self._compute_candidate_list(req, self.problem.vehicles, exclude_vehicle_ids)
             req.cached_candidates = cand_list

        if not cand_list:
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: NO_CANDIDATES for req {req.id}: constraints violate")
            return False

        assigned_any = False
        to_reassign_queue: List[Tuple[Request, Optional[int]]] = []

        for combined_score, cand in cand_list:
            veh = cand["veh"]
            if veh.id in exclude_vehicle_ids:
                continue

            arrival_time = cand["arrival_time"]
            if arrival_time > req.time_window[1] + 1e-6:
                continue

            ok, removed = self._attempt_assign_to_vehicle(req, veh, combined_score)
            if ok:
                assigned_any = True
                for rr in removed:
                    to_reassign_queue.append((rr, veh.id))
                break

        while to_reassign_queue:
            removed_req, removed_from_vid = to_reassign_queue.pop(0)
            if hasattr(removed_req, 'cached_candidates'):
                removed_cands = removed_req.cached_candidates
            else:
                removed_cands = self._compute_candidate_list(removed_req, self.problem.vehicles)
            start_idx = 0
            for idx, (_sc, cd) in enumerate(removed_cands):
                if cd["veh"].id == removed_from_vid:
                    start_idx = idx + 1
                    break
            reassigned = False
            for idx in range(start_idx, len(removed_cands)):
                sc, cd = removed_cands[idx]
                target_veh = cd["veh"]
                ok, further_removed = self._attempt_assign_to_vehicle(removed_req, target_veh, sc)
                if ok:
                    reassigned = True
                    for fr in further_removed:
                        to_reassign_queue.append((fr, target_veh.id))
                    break
            if not reassigned:
                if self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: PUSH_TO_PENDING removed req {removed_req.id} after replacement attempts")
                self.pending_requests.append(removed_req)

        return assigned_any

    # -------------------------
    # Dispatch & execution
    # -------------------------
    def _dispatch_vehicle(self, veh: Vehicle) -> None:
        """
        Điều phối xe với chiến thuật Just-in-Time:
        Nếu xe ở Depot và đơn hàng tốt nhất chưa đến giờ phục vụ, 
        xe sẽ ngủ tại Depot thay vì đi đến khách hàng rồi đứng chờ.
        """
        # Làm sạch hàng đợi (loại bỏ đơn đã xử lý)
        veh.req_queue = [rq for rq in veh.req_queue if (not rq.is_picked_up) and (not rq.is_served)]

        # Thời điểm xe sẵn sàng
        ready_time = max(self.cur_time, veh.busy_until)
        depot_close = self.problem.depot_time_window[1]

        # 1. Kiểm tra l_w (Max Wait Time) của các đơn đã nhặt trên xe (nếu có)
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

        # 2. Duyệt qua hàng đợi để tìm ứng viên tốt nhất
        candidates = []
        
        for req in veh.req_queue:
            if req.is_served or req.is_picked_up: continue

            travel_time = veh.moving_time_to(req.location)
            jit_departure_time = req.time_window[0] - travel_time
            arrival_if_go_now = ready_time + travel_time
            service_start = max(arrival_if_go_now, req.time_window[0])

            # KIỂM TRA RÀNG BUỘC
            if arrival_if_go_now > req.time_window[1] + 1e-6: continue
            arrival_depot_after = service_start + veh.moving_time(req.location, (0, 0))
            if arrival_depot_after > depot_close + 1e-6: continue
            if any((arrival_depot_after - p.pickup_time > p.l_w + 1e-6) for p in veh.picked_up_orders):
                continue
            if (arrival_depot_after - service_start > req.l_w + 1e-6):
                continue
            if veh.type == "DRONE":
                total_dist_time = (veh.distance_to(req.location) + \
                                  math.sqrt(req.location[0]**2 + req.location[1]**2)) / veh.velocity
                if veh.remaining_range < total_dist_time - 1e-6: continue
            if veh.remaining_capacity < req.demand - 1e-6:
                continue

            # TÍNH ĐIỂM S-TREE
            score = self.individual.s_tree.evaluate(veh, self.problem, req, self.cur_time)
            
            candidates.append({
                'score': score,
                'req': req,
                'travel_time': travel_time,
                'service_start': service_start,
                'jit_departure_time': jit_departure_time
            })

        # 3. Ra quyết định
        if candidates:
            candidates.sort(key=lambda x: (x['score'], x['travel_time']))
            best = candidates[0]
            req_to_serve = best['req']
            
            # --- LOGIC CHỜ (JUST-IN-TIME) ---
            if veh.current_location == (0.0, 0.0):
                if ready_time < best['jit_departure_time'] - 1e-6:
                    wake_up_time = best['jit_departure_time']
                    
                    if self.enable_logging:
                        self.log_events.append(
                            f"{self.cur_time:.4f}: [DECISION] Veh {veh.id} WAITS at Depot. "
                            f"Best Req {best['req'].id} starts at {best['req'].time_window[0]:.2f}. "
                            f"Travel: {best['travel_time']:.2f}. "
                            f"Wake up at: {wake_up_time:.2f}"
                        )
                    
                    # Schedule VEH_FREE with detailed payload and record waiting meta
                    veh.scheduled_wake_time = wake_up_time
                    veh.waiting_for_req_id = best['req'].id
                    veh.waiting_for_s_score = best['score']
                    heapq.heappush(self.event_queue, (wake_up_time, "VEH_FREE", (veh.id, "WAKE_UP", best['req'].id)))
                    return
            
            # Nếu không chờ nữa -> dispatch ngay
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: [DECISION] DISPATCH veh {veh.id} from {veh.current_location} to req {best['req'].id}. Travel: {best['travel_time']:.2f}")

            # Clear scheduled wake metadata
            veh.scheduled_wake_time = None
            veh.waiting_for_req_id = None
            veh.waiting_for_s_score = None

            self._execute_pickup(veh, req_to_serve, ready_time, best['travel_time'], best['service_start'])
            return

        # 4. Nếu không có đơn nào -> return hoặc log
        if not candidates and veh.current_location != (0, 0):
            self._process_final_return(veh, ready_time)
        
        elif not candidates and veh.current_location == (0, 0):
            if self.enable_logging:
                self.log_events.append(f"{ready_time:.4f}: NO_CANDIDATES veh {veh.id} at depot")

    def _execute_pickup(self, veh: Vehicle, next_req: Request, ready_time: float, travel_time: float, service_start: float) -> None:
        """Thực hiện hành động lấy hàng và cập nhật trạng thái."""
        arrival_time = ready_time + travel_time

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

        # Clear any scheduled wake (we are now busy)
        veh.scheduled_wake_time = None
        veh.waiting_for_req_id = None
        veh.waiting_for_s_score = None

        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", (veh.id, "PICKUP", next_req.id)))

    def _process_final_return(self, veh: Vehicle, ready_time: float) -> None:
        """Quay về depot và hoàn tất các đơn hàng."""
        travel_time = veh.moving_time_to((0.0, 0.0))
        arrival_at_depot = ready_time + travel_time

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
        served = len(veh.picked_up_orders)
        veh.picked_up_orders = []
        veh.busy_until = arrival_at_depot
        veh.current_location = (0.0, 0.0)
        veh.remaining_capacity = veh.capacity

        # Clear any scheduled wake (we're back at depot after a return)
        veh.scheduled_wake_time = None
        veh.waiting_for_req_id = None
        veh.waiting_for_s_score = None

        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", (veh.id, "RETURN", served)))

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

        # Clear any scheduled wake (we are busy)
        veh.scheduled_wake_time = None
        veh.waiting_for_req_id = None
        veh.waiting_for_s_score = None

        heapq.heappush(self.event_queue, (veh.busy_until, "VEH_FREE", (veh.id, "RETURN", urgent_req.id)))