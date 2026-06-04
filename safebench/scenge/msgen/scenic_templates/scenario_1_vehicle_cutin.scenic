Town = globalParameters.town
EgoSpawnPt = globalParameters.spawnPt
yaw = globalParameters.yaw
egoTrajectory = PolylineRegion(globalParameters.waypoints)
param map = localPath(f'../maps/{Town}.xodr')
param carla_map = Town
model scenic.simulators.carla.model
EGO_MODEL = "vehicle.lincoln.mkz_2017"

param OPT_GEO_X_DISTANCE = Range(2, 8)
param OPT_GEO_Y_DISTANCE = Range(10, 40)
param OPT_ADV_SPEED = Range(5, 15)
param OPT_ADV_DISTANCE = Range(0, 15)
param OPT_THROTTLE = Range(0.5, 1)

behavior AdvBehavior():
    do FollowLaneBehavior(target_speed=globalParameters.OPT_ADV_SPEED) until (distance to self) < globalParameters.OPT_ADV_DISTANCE
    while True:
        take SetThrottleAction(globalParameters.OPT_THROTTLE)
        take SetSpeedAction(0)

ego = Car at EgoSpawnPt,
    with heading yaw,
    with regionContainedIn None,
    with blueprint EGO_MODEL

IntSpawnPt = OrientedPoint following roadDirection from EgoSpawnPt for globalParameters.OPT_GEO_Y_DISTANCE
AdvAgent = Car left of IntSpawnPt by globalParameters.OPT_GEO_X_DISTANCE,
    with heading IntSpawnPt.heading,
    with regionContainedIn None,
    with behavior AdvBehavior()

require (distance from AdvAgent to intersection) > 10
