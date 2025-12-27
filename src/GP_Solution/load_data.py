import os
import json
# from problem_structures import Problem, Request, Drone, Truck
from .problem_structures import Problem, Request, Drone, Truck
# problem_structures.py
def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file at {file_path}")
    with open(file_path, 'r') as file:
        data = json.load(file)
    requests = data['requests']
    depot_time_window_end = data['close']
    pro = Problem(depot_time_window_end)
    for idx, r in enumerate(requests):
        rq = Request(
                idx+1,   # id
                (r[0], r[1]), # location
                r[2], # demand
                r[3], # able_drone
                r[4], # release time
                r[5], # e - ealiest time - open time
                r[6], # l - latest time - close time
            )
        pro.requests.append(rq)
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
    
        
        