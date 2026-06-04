Town = globalParameters.town
EgoSpawnPt = globalParameters.spawnPt
yaw = globalParameters.yaw
egoTrajectory = PolylineRegion(globalParameters.waypoints)
param map = localPath(f'../maps/{Town}.xodr')
param carla_map = Town
model scenic.simulators.carla.model
EGO_MODEL = "vehicle.lincoln.mkz_2017"
ADV_MODEL = "walker.pedestrian.0009"
BLOCKER_MODEL = "vehicle.volkswagen.t2"

param OPT_GEO_BLOCKER_X_DISTANCE = Range(2, 8)
param OPT_GEO_BLOCKER_Y_DISTANCE = Range(15, 50)
param OPT_GEO_X_DISTANCE = Range(-2, 2)
param OPT_GEO_Y_DISTANCE = Range(2, 6)
param OPT_ADV_SPEED = Range(0, 5)
param OPT_ADV_DISTANCE = Range(0, 15)
param OPT_STOP_DISTANCE = Range(0, 1)

behavior AdvBehavior():
    do CrossingBehavior(ego, globalParameters.OPT_ADV_SPEED, globalParameters.OPT_ADV_DISTANCE) until (distance from self to egoTrajectory) < globalParameters.OPT_STOP_DISTANCE
    while True:
        take SetWalkingSpeedAction(0)

ego = Car at EgoSpawnPt,
    with heading yaw,
    with regionContainedIn None,
    with blueprint EGO_MODEL

IntSpawnPt = OrientedPoint following roadDirection from EgoSpawnPt for globalParameters.OPT_GEO_BLOCKER_Y_DISTANCE
Blocker = Car right of IntSpawnPt by globalParameters.OPT_GEO_BLOCKER_X_DISTANCE,
    with heading IntSpawnPt.heading,
    with regionContainedIn None,
    with blueprint BLOCKER_MODEL

SHIFT = globalParameters.OPT_GEO_X_DISTANCE @ globalParameters.OPT_GEO_Y_DISTANCE
AdvAgent = Pedestrian at Blocker offset along IntSpawnPt.heading by SHIFT,
    with heading IntSpawnPt.heading + 90 deg,
    with regionContainedIn None,
    with behavior AdvBehavior(),
    with blueprint ADV_MODEL

require (distance from AdvAgent to intersection) > 10
