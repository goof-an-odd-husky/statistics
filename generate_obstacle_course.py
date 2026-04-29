import math
import random

lat_ref = math.radians(49.82358736969999)
lon_ref = math.radians(24.027099609375)

lat_dir_1 = math.radians(49.81829)
lon_dir_1 = math.radians(24.02359)
lat_dir_2 = math.radians(49.82061)
lon_dir_2 = math.radians(24.02401)

lat_course_start = math.radians(49.81829)
lon_course_start = math.radians(24.02359)

COURSE_LENGTH_METERS = 40.0
OFFSET_X = 3.0
OFFSET_Y = -12.0

a = 6378137.0
b = 6356752.314245
f = (a - b) / a
e_sq = f * (2 - f)


def geodetic_to_enu(lat, lon, lat_ref, lon_ref):
    N_ref = a / math.sqrt(1 - e_sq * math.sin(lat_ref) ** 2)
    M_ref = a * (1 - e_sq) / (1 - e_sq * math.sin(lat_ref) ** 2) ** 1.5
    x = (lon - lon_ref) * N_ref * math.cos(lat_ref)
    y = (lat - lat_ref) * M_ref
    return x, y


x1, y1 = geodetic_to_enu(lat_dir_1, lon_dir_1, lat_ref, lon_ref)
x2, y2 = geodetic_to_enu(lat_dir_2, lon_dir_2, lat_ref, lon_ref)

dx = x2 - x1
dy = y2 - y1
heading_length = math.hypot(dx, dy)

dir_x = dx / heading_length
dir_y = dy / heading_length

start_x, start_y = geodetic_to_enu(lat_course_start, lon_course_start, lat_ref, lon_ref)
start_x += OFFSET_X
start_y += OFFSET_Y

perp_x = -dir_y
perp_y = dir_x
yaw_perp = math.atan2(perp_y, perp_x)

random.seed(42)
actors_xml = ""
dist_along_path = 0.0
actor_id = 1


def get_exact_waypoints():
    """Calculates turnaround waypoints for consistent walking speed."""
    speed = random.uniform(0.1, 0.26)
    walk_dist = random.uniform(6.0, 9.0)
    time_one_way = walk_dist / speed
    total_cycle = time_one_way * 2
    t_offset = random.uniform(0, total_cycle)

    def get_pos_at(t_input):
        t_eff = (t_input + t_offset) % total_cycle
        if t_eff <= time_one_way:
            return (walk_dist / time_one_way) * t_eff
        else:
            return walk_dist - (walk_dist / time_one_way) * (t_eff - time_one_way)

    t_to_turnaround = (time_one_way - t_offset) % total_cycle
    t_to_zero = (total_cycle - t_offset) % total_cycle

    pts = [
        (0.0, get_pos_at(0.0)),
        (t_to_turnaround, walk_dist),
        (t_to_zero, 0.0),
        (total_cycle, get_pos_at(total_cycle)),
    ]
    return sorted(list(set([(round(t, 3), round(x, 3)) for t, x in pts])))


while dist_along_path <= COURSE_LENGTH_METERS:
    curr_x = start_x + dir_x * dist_along_path
    curr_y = start_y + dir_y * dist_along_path

    current_waypoints = get_exact_waypoints()

    actors_xml += f"""
    <actor name="dynamic_pedestrian_{actor_id}">
      <pose>{curr_x:.2f} {curr_y:.2f} 6.92 0 0 {yaw_perp:.3f}</pose> 
      <script>
        <loop>true</loop>
        <auto_start>true</auto_start>
        <trajectory id="0" type="walking">"""

    for t, x in current_waypoints:
        actors_xml += f"""
          <waypoint><time>{t}</time><pose>{x} 0 0 0 0 0</pose></waypoint>"""

    actors_xml += """
        </trajectory>
      </script>
      <link name="link">
        <visual name="visual">
          <pose>0 0 3.0 0 0 0</pose>
          <geometry><cylinder><radius>0.25</radius><length>6.0</length></cylinder></geometry>
          <material><ambient>0.8 0.1 0.1 1.0</ambient></material> 
        </visual>
      </link>
    </actor>"""

    dist_along_path += random.uniform(2.0, 6.0)
    actor_id += 1

full_sdf = f"""<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="default">
    {actors_xml}
  </world>
</sdf>
"""

with open("park_populated.sdf", "w") as f:
    f.write(full_sdf)

print(f"Generated {actor_id - 1} pedestrians over {COURSE_LENGTH_METERS} meters.")
