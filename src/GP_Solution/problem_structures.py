import math

class Request:
    def __init__(self, id, location, d_i, able_drone, r_i, e_i, l_i):
        self.id = id
        self.location = location # (x,y)
        self.demand = d_i
        self.able_drone = able_drone
        self.release_time = r_i
        self.time_window = (e_i, l_i)
        self.is_picked_up = False
        self.pickup_time = None
        self.is_served = False
        self.l_w = 3600.0

class Vehicle:
    def __init__(self, id, capacity, velocity, start_location=(0,0)):
        self.id = id
        self.capacity = capacity
        self.remaining_capacity = capacity
        self.velocity = velocity
        self.current_location = start_location
        self.req_queue = []
        self.picked_up_orders = []
        self.busy_until = 0
        self.routes = []
        self.current_trip = None
    
    def moving_time_to(self, location):
        dis = self.distance_to(location)
        return dis / self.velocity
    def moving_time(self, loc_a, loc_b):
        dis = math.sqrt((loc_a[0]-loc_b[0])**2+(loc_a[1]-loc_b[1])**2)
        return dis / self.velocity
    def sum_of_req_demand(self):
        if not self.req_queue:
            return 0.0
        return sum([req.demand for req in self.req_queue])
    def distance_to(self, location):
        return math.sqrt((self.current_location[0]-location[0])**2+(self.current_location[1]-location[1])**2)
    def median_of_req_loc(self):
        if not self.req_queue:
            return self.current_location
        avg_x = sum([req.location[0] for req in self.req_queue]) / len(self.req_queue)
        avg_y = sum([req.location[1] for req in self.req_queue]) / len(self.req_queue)
        
        return (avg_x, avg_y)
    
class Truck(Vehicle):
    def __init__(self, id, capacity, velocity):
        super().__init__(id, capacity, velocity)
        self.type = 'TRUCK'

class Drone(Vehicle):
    def __init__(self, id, capacity, velocity, max_range):
        super().__init__(id, capacity, velocity)
        self.max_range = max_range
        self.remaining_range = max_range
        self.type = 'DRONE'
    
    def check_can_fly(self, location):
        travel_time = self.moving_time_to(location)
        return_time = self.moving_time(location, (0,0))
        return self.remaining_range >= travel_time + return_time
    
    def recharge(self):
        self.remaining_range = self.max_range
        
class Problem:
    def __init__(self, depot_time_window_end):
        self.requests = []
        self.vehicles = []
        self.depot_time_window = (0, depot_time_window_end)
    
    def sum_of_req_demand(self):
        if not self.requests:
            return 0.0
        return sum([req.demand for req in self.requests])

        