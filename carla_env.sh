export CARLA_ROOT=/home/raykr/projects/ScenGE-AAAI/CARLA_0.9.13_safebench
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.13-py3.8-linux-x86_64.egg
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/agents
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
# CARLA 0.9.13 egg 依赖 libtiff.so.5；conda 默认提供 .so.6，需软链
if [ -f "${CONDA_PREFIX}/lib/libtiff.so.6" ] && [ ! -e "${CONDA_PREFIX}/lib/libtiff.so.5" ]; then
  ln -sf libtiff.so.6 "${CONDA_PREFIX}/lib/libtiff.so.5"
fi
# 无图形界面时用 dummy 驱动，避免 pygame 初始化失败
export SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-dummy}
