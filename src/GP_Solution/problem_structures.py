import os
import math
import json
from typing import Any, Literal, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

@dataclass
class Request:
    id: int
    location: tuple[float, float]
    demand: float
    able_drone: Literal[0, 1]
    release_time: float
    e_i: float
    l_i: float
    time_window: tuple[float, float] = field(init=False)
    l_w: float = 3600.0
    is_picked_up: bool = False
    is_served: bool = False
    pickup_time: float | None = None
    
    def __post_init__(self):
        self.time_window = (self.e_i, self.l_i)
    
class Vehicle(ABC):
    def __init__(
        self, 
        id: int, 
        capacity: float, 
        velocity: float, 
        start_location: tuple[float, float] = (0.0, 0.0)
    ) -> None:
        self.id: int = id
        self.capacity: float = capacity
        self.remaining_capacity: float = capacity
        self.velocity: float = velocity
        self.current_location: tuple[float, float] = start_location
        self.req_queue: list[Request] = []
        self.picked_up_orders: list[Request] = []
        self.busy_until: float = 0.0
        # self.routes: list[list[int | str]] = []
        self.routes: list[list[dict]] = []
        # self.current_trip = None
    
    def moving_time_to(self, location: tuple[float, float]) -> float:
        dis = self.distance_to(location)
        return dis / self.velocity
    
    def moving_time(self, loc_a: tuple[float, float], loc_b: tuple[float, float]) -> float:
        dis = math.sqrt((loc_a[0]-loc_b[0])**2+(loc_a[1]-loc_b[1])**2)
        return dis / self.velocity
    
    def sum_of_req_demand(self) -> float:
        if not self.req_queue:
            return 0.0
        return sum([req.demand for req in self.req_queue])
    
    def distance_to(self, location: tuple[float, float]):
        return math.sqrt((self.current_location[0]-location[0])**2+(self.current_location[1]-location[1])**2)
    
    def median_of_req_loc(self) -> float:
        if not self.req_queue:
            return self.current_location
        avg_x = sum([req.location[0] for req in self.req_queue]) / len(self.req_queue)
        avg_y = sum([req.location[1] for req in self.req_queue]) / len(self.req_queue)
        return (avg_x, avg_y)
    
    @abstractmethod
    def can_handle_request(self, req: Request) -> bool:
        pass

    def recharge(self) -> None:
        pass  # Chỉ override ở Drone
    
    
class Truck(Vehicle):
    def __init__(self, id: int, capacity: float, velocity: float) -> None:
        super().__init__(id, capacity, velocity)
        self.type: str = 'TRUCK'

    def can_handle_request(self, req: Request) -> bool:
        return self.remaining_capacity >= req.demand  
    
class Drone(Vehicle):
    def __init__(self, id: int, capacity: float, velocity: float, max_range: float):
        super().__init__(id, capacity, velocity)
        self.max_range: float = max_range
        self.remaining_range: float = max_range
        self.type: str = 'DRONE'
    
    def check_can_fly(self, location: float) -> bool:
        travel_time = self.moving_time_to(location)
        return_time = self.moving_time(location, (0.0, 0.0))
        return self.remaining_range >= travel_time + return_time
    
    def can_handle_request(self, req: Request) -> bool:
        if not req.able_drone:
            return False
        travel_time = self.moving_time_to(req.location)
        return_time = self.moving_time(req.location, (0.0, 0.0))
        return (self.remaining_capacity >= req.demand) and (self.remaining_range >= travel_time + return_time)
    
    def recharge(self) -> None:
        self.remaining_range = self.max_range
        
class Problem:
    def __init__(self, depot_time_window_end: float) -> None:
        self.requests: list[Request] = []
        self.vehicles: list[Vehicle] = []
        self.depot_time_window: tuple[float, float] = (0.0, depot_time_window_end)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'Problem':
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No such file at {file_path}")

        with open(file_path, 'r') as f:
            data = json.load(f)

        pro = cls(data['close'])

        for idx, r in enumerate(data['requests']):
            pro.requests.append(
                Request(
                    idx + 1, # id
                    (r[0], r[1]), # location
                    r[2], # demand
                    r[3], # able_drone
                    r[4], # release time
                    r[5], # e - ealiest time - open time
                    r[6], # l - latest time - close time
                )
            )
        t_vel = data['truck_vel']
        d_vel = data['drone_vel']
        t_cap = data['truck_cap']
        d_cap = data['drone_cap']
        t_num = data['truck_num']
        d_num = data['drone_num']
        d_lim = data['drone_lim']

        v_id = 1

        for _ in range(t_num):
            pro.vehicles.append(Truck(v_id, t_cap, t_vel))
            v_id += 1

        for _ in range(d_num):
            pro.vehicles.append(Drone(v_id, d_cap, d_vel, d_lim))
            v_id += 1

        return pro
    
    def sum_of_req_demand(self) -> float:
        if not self.requests:
            return 0.0
        return sum([req.demand for req in self.requests])

        