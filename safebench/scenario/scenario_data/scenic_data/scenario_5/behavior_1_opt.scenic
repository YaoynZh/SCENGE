# Description: The ego vehicle drives straight through a green light when a car runs a red light from the oncoming left and accelerates into the intersection, forcing the ego to brake abruptly.
# AdvType: car
# AdvPos: oncoming left
# AdvBehavior: Runs red light and accelerates into intersection
Town = globalParameters.town
EgoSpawnPt = globalParameters.spawnPt
yaw = globalParameters.yaw
egoTrajectory = PolylineRegion(globalParameters.waypoints)

param map = localPath(f'../maps/{Town}.xodr')
param carla_map = Town
model scenic.simulators.carla.model

EGO_MODEL = "vehicle.lincoln.mkz_2017"

param OPT_GEO_X_DISTANCE = Range(3, 5)
param OPT_GEO_Y_DISTANCE = Range(10, 15)
param OPT_ACCEL = Range(3, 6)

ego = Car at EgoSpawnPt,
    with heading yaw,
    with regionContainedIn None,
    with blueprint EGO_MODEL

IntSpawnPt = OrientedPoint following roadDirection from EgoSpawnPt for globalParameters.OPT_GEO_Y_DISTANCE

behavior AdvBehavior():
    take FollowTrajectoryBehavior(acceleration=globalParameters.OPT_ACCEL)

AdvAgent = Car left of IntSpawnPt by globalParameters.OPT_GEO_X_DISTANCE,
    with heading IntSpawnPt.heading,
    with regionContainedIn None,
    with behavior AdvBehavior()