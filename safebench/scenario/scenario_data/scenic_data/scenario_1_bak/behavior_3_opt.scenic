# Description: The ego vehicle travels straight on a road when a pedestrian suddenly steps out from behind a delivery van parked on the right front, walks directly into the travel lane, then freezes in place mid-path obstructing the ego's trajectory. 
# AdvType: pedestrian
# AdvPos: right front
# AdvBehavior: Suddenly emerges from behind a parked vehicle and stops abruptly in the path of the approaching ego vehicle.

Town = globalParameters.town
EgoSpawnPt = globalParameters.spawnPt
yaw = globalParameters.yaw
lanePts = globalParameters.lanePts
egoTrajectory = PolylineRegion(globalParameters.waypoints)
param map = localPath(f'../maps/{Town}.xodr') 
param carla_map = Town
model scenic.simulators.carla.model
EGO_MODEL = "vehicle.lincoln.mkz_2017"
ADV_MODEL = "walker.pedestrian.0009"
BLOCKER_MODEL = "vehicle.volkswagen.t2"

ego = Car at EgoSpawnPt,
    with heading yaw,
    with regionContainedIn None,
    with blueprint EGO_MODEL

behavior AdvBehavior():
    do CrossingBehavior(ego, globalParameters.OPT_ADV_SPEED, globalParameters.OPT_ADV_DISTANCE) until (distance from self to egoTrajectory) < globalParameters.OPT_STOP_DISTANCE
    while True:
        take SetWalkingSpeedAction(0)

param OPT_GEO_BLOCKER_X_DISTANCE = Range(2, 8)
param OPT_GEO_BLOCKER_Y_DISTANCE = Range(15, 50)
param OPT_PED_X = Range(-2, 2)
param OPT_PED_Y = Range(-3, 0)
param OPT_ADV_SPEED = Range(0, 5)
param OPT_ADV_DISTANCE = Range(0, 15)
param OPT_STOP_DISTANCE = Range(0.5, 2)

IntSpawnPt = OrientedPoint following roadDirection from EgoSpawnPt for globalParameters.OPT_GEO_BLOCKER_Y_DISTANCE
Blocker = Car right of IntSpawnPt by globalParameters.OPT_GEO_BLOCKER_X_DISTANCE,
    with heading IntSpawnPt.heading,
    with regionContainedIn None,
    with blueprint BLOCKER_MODEL

SHIFT_PED = globalParameters.OPT_PED_X @ globalParameters.OPT_PED_Y
AdvAgent = Pedestrian at Blocker offset along IntSpawnPt.heading by SHIFT_PED,
    with heading IntSpawnPt.heading + 90 deg,
    with regionContainedIn None,
    with behavior AdvBehavior(),
    with blueprint ADV_MODEL

require (distance from AdvAgent to intersection) > 10
