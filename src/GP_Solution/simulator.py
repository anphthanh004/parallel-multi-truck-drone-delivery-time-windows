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

        # Reset hàng đợi của các xe trong bản copy
        for veh in self.problem.vehicles:
            veh.req_queue = []

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

            elif ev_type == "TRY_PENDING":
                self._handle_try_pending_event()

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
            heapq.heappush(self.event_queue, (self.cur_time + 1.0, "TRY_PENDING", None))

    def _handle_veh_free_event(self, vid: int):
        if self.enable_logging:
            self.log_events.append(f"{self.cur_time:.4f}: VEH_FREE veh {vid}")

        if self.pending_requests:
            # Lọc lại các request đã quá hạn trong pending
            self.pending_requests = [r for r in self.pending_requests if self.cur_time <= r.time_window[1] + 1e-6]
            self.pending_requests.sort(key=lambda r: (r.time_window[1], -r.demand))
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
            
    def _handle_try_pending_event(self):
        """
        Thử gán lại tất cả pending_requests tại thời điểm hiện tại.
        Ghi log cho từng lần success/fail. Nếu vẫn còn pending sau attempts, schedule
        một TRY_PENDING nhỏ thời gian sau (self.cur_time + epsilon) để thử tiếp.
        """
        next_try = self.cur_time + 5.0
        if not self.pending_requests:
            heapq.heappush(self.event_queue, (next_try, "TRY_PENDING", None))
            return

        if self.enable_logging:
            self.log_events.append(f"{self.cur_time:.4f}: TRY_PENDING start, pending_count={len(self.pending_requests)}")

        # Loại ngay các pending đã hết hạn và log chúng
        expired = [r for r in self.pending_requests if self.cur_time > r.time_window[1] + 1e-6]
        if expired and self.enable_logging:
            expired_ids = [r.id for r in expired]
            self.log_events.append(f"{self.cur_time:.4f}: PENDING_EXPIRED removed {expired_ids}")

        self.pending_requests = [r for r in self.pending_requests if self.cur_time <= r.time_window[1] + 1e-6]
        self.pending_requests.sort(key=lambda r: (r.time_window[1], -r.demand))

        still_pending = []
        for p_req in self.pending_requests:
            success = self._try_assign_request(p_req, self.problem.vehicles)
            if not success:
                still_pending.append(p_req)
                if self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: RETRY_ASSIGN FAILED for pending req {p_req.id}")
            else:
                if self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: RETRY_ASSIGN SUCCESS for pending req {p_req.id}")

        self.pending_requests = still_pending

        if self.pending_requests:
            next_try = self.cur_time + 1.0
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: Scheduled TRY_PENDING at {next_try:.4f} for {len(self.pending_requests)} pending")
        

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

            # Ràng buộc hàng đợi phục vụ tối đa (kiểm tra sơ bộ - không xét top-rank logic ở đây)
            if veh.sum_of_req_demand() + req.demand > veh.capacity + 1e-6:
                # keep it out as candidate
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
        Thử gán req vào veh:
        - Tính các request hiện có trên veh mà veh là rank-0 cho chúng (top_requests_on_veh).
        - Nếu chỗ (tổng demand top + req.demand <= cap) -> append và return True, [].
        - Ngược lại thử replacement: loại những top request có combined score thấp hơn req (worst-first) cho tới khi vừa chỗ.
        - Trả về (True, removed_requests) nếu thành công (có thể remove >0), else (False, []).
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

        # If there is room when counting only top-ranked requests -> assign directly
        if sum_top_demand + req.demand <= capacity + 1e-6:
            veh.req_queue.append(req)
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: ASSIGN_DIRECT req {req.id} -> veh {veh.id}")
            if veh.busy_until <= self.cur_time + 1e-6:
                self._dispatch_vehicle(veh)
            return True, []

        # Otherwise attempt replacement: build removable list from top_requests_on_veh
        removable: List[Tuple[Request, float]] = []
        for q in top_requests_on_veh:
            q_cand_list = self._compute_candidate_list(q, self.problem.vehicles)
            # find combined score for this veh
            q_score_on_veh = None
            for sc, qc in q_cand_list:
                if qc["veh"].id == veh.id:
                    q_score_on_veh = sc
                    break
            if q_score_on_veh is None:
                # if not found, skip
                continue
            removable.append((q, q_score_on_veh))

        # Sort removable by q_score_on_veh ascending (worst first, since higher combined better)
        removable.sort(key=lambda x: x[1])

        freed = 0.0
        removed_reqs: List[Request] = []
        for q, q_score in removable:
            # only remove if the new request is strictly better than this queued request on this vehicle
            if combined_score_on_veh <= q_score + 1e-9:
                # new request not better -> skip removing this one
                continue
            removed_reqs.append(q)
            freed += q.demand
            if sum_top_demand - freed + req.demand <= capacity + 1e-6:
                break

        # If after removing selected ones we can fit new req => perform replacement
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
        Cố gắng gán request cho vehicles theo thứ tự candidate:
        - Tính danh sách candidate của req, duyệt từ best->worst.
        - Tại mỗi vehicle: cố gán bằng _attempt_assign_to_vehicle (có thể tạo removed list).
        - Khi có removed requests, thực hiện reassign cho từng removed theo thứ tự next-ranks:
          tìm candidate list của removed_req, bắt đầu từ vị trí ngay sau vehicle đã loại nó.
        - Nếu removed không thể gán cho bất kỳ candidate nào -> push vào pending.
        """
        exclude_vehicle_ids = exclude_vehicle_ids or set()
        cand_list = self._compute_candidate_list(req, self.problem.vehicles, exclude_vehicle_ids)
        if not cand_list:
            if self.enable_logging:
                self.log_events.append(f"{self.cur_time:.4f}: NO_CANDIDATES for req {req.id}: constraints violate")
            return False

        assigned_any = False
        to_reassign_queue: List[Tuple[Request, Optional[int]]] = []  # tuples (removed_request, removed_from_vehicle_id)

        for combined_score, cand in cand_list:
            veh = cand["veh"]
            # skip excluded vehicles
            if veh.id in exclude_vehicle_ids:
                continue

            # arrival_time feasibility
            arrival_time = cand["arrival_time"]
            if arrival_time > req.time_window[1] + 1e-6:
                continue

            # Try to assign to this vehicle
            ok, removed = self._attempt_assign_to_vehicle(req, veh, combined_score)
            if ok:
                assigned_any = True
                # enqueue removed requests for reassign (they will be tried at their next ranks)
                for rr in removed:
                    to_reassign_queue.append((rr, veh.id))
                break  # assigned req (respect assignment_n typically 1). If assignment_n>1, loop could continue.

        # Process reassign queue: each removed request should try next-best vehicle (rank+1, rank+2, ...)
        while to_reassign_queue:
            removed_req, removed_from_vid = to_reassign_queue.pop(0)
            # Compute candidate list for removed_req
            removed_cands = self._compute_candidate_list(removed_req, self.problem.vehicles)
            # Find index of removed_from_vid
            start_idx = 0
            for idx, (_sc, cd) in enumerate(removed_cands):
                if cd["veh"].id == removed_from_vid:
                    start_idx = idx + 1  # start from next rank
                    break
            reassigned = False
            # Try each next candidate in order
            for idx in range(start_idx, len(removed_cands)):
                sc, cd = removed_cands[idx]
                target_veh = cd["veh"]
                # Try to assign to target_veh (this may produce further removed requests)
                ok, further_removed = self._attempt_assign_to_vehicle(removed_req, target_veh, sc)
                if ok:
                    reassigned = True
                    # any further_removed need to be re-assigned too (they were removed from target_veh)
                    for fr in further_removed:
                        to_reassign_queue.append((fr, target_veh.id))
                    break
            if not reassigned:
                # Could not reassign to any candidate -> push to pending
                if self.enable_logging:
                    self.log_events.append(f"{self.cur_time:.4f}: PUSH_TO_PENDING removed req {removed_req.id} after replacement attempts")
                self.pending_requests.append(removed_req)

        return assigned_any

    # -------------------------
    # Dispatch & execution (unchanged except minor cleanups)
    # -------------------------
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
            # Sort theo score (min=best). Tie-break theo travel_time nhỏ hơn
            candidates.sort(key=lambda x: (x[0], x[2]))
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