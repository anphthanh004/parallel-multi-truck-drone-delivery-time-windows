import math
from typing import Any, Literal, Optional
from dataclasses import dataclass, field

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
    
class Vehicle:
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
    
class Truck(Vehicle):
    def __init__(self, id: int, capacity: float, velocity: float) -> None:
        super().__init__(id, capacity, velocity)
        self.type: str = 'TRUCK'

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
    
    def recharge(self) -> None:
        self.remaining_range = self.max_range
        
class Problem:
    def __init__(self, depot_time_window_end: float) -> None:
        self.requests: list[Request] = []
        self.vehicles: list[Vehicle] = []
        self.depot_time_window: tuple[float, float] = (0.0, depot_time_window_end)
    
    def sum_of_req_demand(self) -> float:
        if not self.requests:
            return 0.0
        return sum([req.demand for req in self.requests])

        