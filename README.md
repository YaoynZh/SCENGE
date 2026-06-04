# ScenGE-AAAI

> [AAAI 2026] Adversarial Generation and Collaborative Evolution of
> Safety-Critical Scenarios for Autonomous Vehicles.

This repository runs five scenario-generation methods against three ego
policies inside CARLA + SafeBench:

| Family            | Methods                              | Runner          |
|-------------------|--------------------------------------|-----------------|
| Traditional       | LC, CS, AdvSim, AdvTraj              | `CarlaRunner`   |
| Scenic / ChatScene | `train_scenario_scenic` + `eval_scenic` | `ScenicRunner` |
| ScenGE (ours)     | `msgen` → `train_scenario` → `select_traj` → replay-eval | `ScenicRunner` + `safebench.scenge` |

Ego (被测) policies: **SAC**, **PPO**, **TD3**, all dispatched through
`RLAgent` and differentiated only by the per-yaml `policy_name` and
`load_dir`.

---

## 1. Layout

```
safebench/
  agent/
    safe_rl/                       # the only ego implementation kept
    config/{sac,ppo,td3}.yaml      # policy_type=rl, load_dir → safe_rl ckpt
    model_ckpt/safe_rl/{sac_0,ppo_0,td3_0}/
  scenario/
    scenario_definition/{standard, advsim, adv_trajectory, adv_init_state,
                         adv_behavior_single, scenic, ...}
    scenario_policy/{dummy_policy, hardcode_policy, reinforce_continuous}
    config/{lc, cs, advsim, advtraj, train_scenario_scenic, eval_scenic}.yaml
    config/scenario_type/{standard, advsim, advtraj,
                          adv_init_state, adv_behavior_single}.json
  gym_carla/                       # CarlaEnv (no lidar) + VectorWrapper
  runner/                          # BaseRunner + CarlaRunner + ScenicRunner
  scenge/                          # ScenGE-only logic
    msgen/                         # LLM + RAG → Scenic scripts
      knowledge_docs/              # phase-1 RAG: base scenarios, patterns
      scenic_docs/                 # phase-2 RAG: Scenic snippets
      prompts/                     # phase-1/2 LLM prompt templates
    threat/{attention, pgd, losses, io}.py
  util/{logger, run_util, metric_util, launch, ...}.py
scripts/
  train_scenario.py                # Scenic-side training (top-N selection)
  eval.py                          # CarlaRunner / ScenicRunner auto-pick
  scenge_pipeline.py               # msgen → train → select → replay-eval
  select_traj.py                   # CLI wrapper around scenge.threat
  calc_metrics.py                  # post-eval pkl → metrics
```

---

## 2. Install

Download [CARLA_0.9.13](https://drive.google.com/file/d/139vLRgXP90Zk6Q_du9cRdOLx7GJIw_0v/view?usp=sharing) and extract it to your folder;
this repo only handles the Python side.

```bash
conda env create -f environment.yaml
conda activate scenge-env

# Lean install (LC / CS / AdvSim / AdvTraj / ChatScene / Scenic eval):
pip install -e .

# Add the LLM-driven msgen step (heavy: transformers, llama-index, ...):
pip install -e .[msgen]

cd Scenic && pip install . && cd -
```

Bring up CARLA on the ports you intend to pass to `--port` / `--tm_port`:

```bash
./CarlaUE4.sh -prefernvidia -RenderOffScreen -carla-port=2000
```

---

## 3. Common runs

### 3.1 Four traditional baselines

```bash
python scripts/eval.py --agent_cfg sac.yaml --scenario_cfg lc.yaml \
    --scenario_id 1 --port 2002 --tm_port 8002

python scripts/eval.py --agent_cfg sac.yaml --scenario_cfg cs.yaml \
    --scenario_id 1 --port 2002 --tm_port 8002

python scripts/eval.py --agent_cfg sac.yaml --scenario_cfg advsim.yaml \
    --scenario_id 1 --port 2002 --tm_port 8002

python scripts/eval.py --agent_cfg sac.yaml --scenario_cfg advtraj.yaml \
    --scenario_id 1 --port 2002 --tm_port 8002
```

`scripts/eval.py` looks at the loaded scenario's `scenario_category` to
auto-pick `CarlaRunner` for the four baselines and `ScenicRunner` for the
Scenic-style scenarios.

### 3.2 ChatScene / Scenic path

```bash
# 1) 50 simulations -> top-2 per route, persisted into scenic_data/scenario_1/.
python scripts/train_scenario.py --agent_cfg sac.yaml \
    --scenario_cfg train_scenario_scenic.yaml --scenario_id 1 \
    --port 2002 --tm_port 8002

# 2) Evaluate the persisted top-2 across the three ego policies.
for ego in sac ppo td3; do
  python scripts/eval.py --agent_cfg ${ego}.yaml \
      --scenario_cfg eval_scenic.yaml --scenario_id 1 \
      --port 2002 --tm_port 8002
done
```

### 3.3 ScenGE end-to-end

```bash
python scripts/scenge_pipeline.py --scenario_id 1 --port 2002 --tm_port 8002
```

The pipeline runs each step in its own subprocess so a CARLA / pygame
hiccup in one step does not corrupt the next:

1. `safebench/scenge/msgen/meta_scenario_generation.py` — RAG generation
   of Scenic scripts. Skip with `--skip_msgen` if you already have them.
2. `scripts/train_scenario.py` — pick the most threatening scenes.
3. `scripts/train_scenario.py --record_traj --traj_root ...` — while
   selecting top scenes, dump per-scene actor trajectories to
   `${traj_root}/traj_dir/<scene>.json`.
4. `scripts/select_traj.py --folder ...` — attention + PGD on env actor
   trajectory segments. Output goes to
   `${traj_root}/perturbed_traj/perturbed_<scene>/<actor>.csv`.
5. `scripts/eval.py --replay --traj_root ...` — replay the perturbed
   env-actor CSVs against each ego (`sac`/`ppo`/`td3` by default).

---

## 4. Checkpoints

The three ego policies use `pretrain_dir` for the model loaded at policy
construction time. The default paths are:

```
safebench/agent/model_ckpt/safe_rl/sac_0/model_save/model.pt
safebench/agent/model_ckpt/safe_rl/ppo_0/model_save/model.pt
safebench/agent/model_ckpt/safe_rl/td3_0/model_save/model.pt
```

`load_dir` may point either at the same model file (current default) or at
a directory containing `model.sac.<epoch>.torch` files for explicit
`--test_epoch` loading. Drop your own ckpts into the yaml paths to swap the
backing weights.

---

## 5. Utility scripts

`scripts/calc_metrics.py` aggregates Scenic eval pkl outputs. It defaults
to behaviors `1-5` and routes `0-9`, and can be narrowed:

```bash
python scripts/calc_metrics.py --folder log/eval/sac/scenario_1 \
    --behaviors 1-5 --routes 0,1,8,9
```

---

## 6. Where to read next

- `safebench/runner/base_runner.py` — shared scaffolding + step-loop helpers.
- `safebench/runner/{carla,scenic}_runner.py` — only the actual differences.
- `safebench/scenge/threat/losses.py` — the configurable `ThreatLoss`
  with weight-driven term selection.
- `scripts/scenge_pipeline.py` — the canonical end-to-end orchestration.
- `safebench/util/launch.py` — argparse → `LaunchArgs` →
  `prepare_run_kwargs` → runner hand-off.



如果要在终端中交互式python中看pkl：

```bash
(scenge-env) ~/workspace/paper_code/ScenGE-AAAI $ python
Python 3.8.20 | packaged by conda-forge | (default, Sep 30 2024, 17:52:49) 
[GCC 13.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import joblib
>>> records = joblib.load('log/eval/sac/scenario_1/scenario_1_rl_lc_seed_19980321/eval_results/ROUTE-0_results.pkl')
>>> records.keys()
dict_keys(['collision_rate', 'avg_red_light_freq', 'avg_stop_sign_freq', 'out_of_road_length', 'route_following_stability', 'route_completion', 'avg_time_spent', 'avg_acceleration', 'avg_yaw_velocity', 'avg_lane_invasion_freq', 'safety_os', 'task_os', 'comfort_os', 'final_score'])
>>> 
```