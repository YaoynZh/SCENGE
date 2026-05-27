# Description: The ego vehicle drives straight on a two-lane road; a pedestrian is standing obscured by a parked van on the right front and suddenly sprints directly into the ego’s path before stopping abruptly in the middle of the road. 
# AdvType: pedestrian
# AdvPos: right front
# AdvBehavior: Sprints from behind an obstacle into the ego's path and halts mid-road without yielding.

Town = globalParameters.town
EgoSpawnPt = globalParameters.spawnPt
yaw = globalParameters.yaw
egoTrajectory = PolylineRegion(globalParameters.waypoints)
param map = localPath(f'../maps/{Town}.xodr')
param carla_map = Town
model scenic.simulators.carla.model
EGO_MODEL = "vehicle.lincoln.mkz_2017"
ADV_MODEL = "walker.pedestrian.0009"

ego = Car at EgoSpawnPt,
    with heading yaw,
    with regionContainedIn None,
    with blueprint EGO_MODEL

# Obstacle (parked van) parameters
param OPT_OBSTACLE_X_OFFSET = Range(1, 3)
param OPT_GEO_Y_DISTANCE = Range(20, 35)

IntSpawnPt = OrientedPoint following roadDirection from EgoSpawnPt for globalParameters.OPT_GEO_Y_DISTANCE

# Place parked van to obscure pedestrian
VanObstacle = Car right of IntSpawnPt by globalParameters.OPT_OBSTACLE_X_OFFSET,
    with heading IntSpawnPt.heading + 180 deg,  # Face away from traffic for better obscuring
    with regionContainedIn None

# Adversarial behavior definition
param OPT_SPRINT_SPEED = Range(4, 6)          # Sprint speed (m/s)
param OPT_STOP_DISTANCE = Range(15, 20)       # Mid-road stopping threshold

behavior AdvBehavior():
    do CrossingBehavior(ego, globalParameters.OPT_SPRINT_SPEED, 0) until (distance from self to egoTrajectory) < globalParameters.OPT_STOP_DISTANCE
    while True:
        take SetWalkingSpeedAction(0)

# Position pedestrian initially obscured by the van
param OPT_PED_X_OFFSET = Range(5, 9)
AdvAgent = Pedestrian right of IntSpawnPt by (globalParameters.OPT_PED_X_OFFSET),
    with heading IntSpawnPt.heading - 90 deg,   # Face towards road center
    with regionContainedIn None,
    with behavior AdvBehavior(),
    with blueprint ADV_MODEL

# Safety constraints to ensure obscuring condition and valid positioning
require (distance from AdvAgent to VanObstacle) < 4.5
require (distance from AdvAgent to ego) > 25
