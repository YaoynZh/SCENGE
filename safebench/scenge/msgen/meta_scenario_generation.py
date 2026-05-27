import os
import re
import sys
import pickle
import shutil
import argparse
import traceback
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

# --- Core LlamaIndex Imports (Safe for older PyTorch) ---
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM

scenario_dict = {
    1: "Straight Obstacle",
    2: "Turning Obstacle",
    3: "Lane Changing",
    4: "Vehicle Passing",
    5: "Red-light Running",
    6: "Unprotected Left-turn",
    7: "Right-turn",
    8: "Crossing Negotiation",
}

# Same default CARLA world model as Safebench `ScenicSimulator` / scenic CLI.
DEFAULT_SCENIC_MODEL = "scenic.simulators.carla.model"

SAFEBENCH_SCENIC_CHECKLIST = """
Safebench 对齐要点（生成/修复时必须满足）：
1) 从 globalParameters 读取外部注入：至少包含 town、spawnPt、yaw、waypoints；若脚本使用 lanePts 则也需 globalParameters.lanePts。
2) 地图：param map = localPath(f'../maps/{Town}.xodr')，且 param carla_map = Town（与仓库内 Safebench 示例一致）。
3) model scenic.simulators.carla.model
4) 可调超参：param OPT_xxx = Range(...) 并在逻辑中用 globalParameters.OPT_xxx 引用。
5) 对抗行为名建议包含 Adv（如 AdvBehavior），便于 Safebench 侧识别 adversarial actor。
6) ego 一般为 Car，with regionContainedIn None，with blueprint EGO_MODEL。
"""


def _msgen_root() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def _repo_root() -> str:
    # safebench/scenge/msgen -> safebench/scenge -> safebench -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(_msgen_root())))


def load(file_path: str) -> Any:
    suffix = file_path.split(".")[-1]
    if suffix == "txt":
        with open(file_path, "r") as file:
            return file.read()
    elif suffix == "pkl":
        with open(file_path, "rb") as file:
            return pickle.load(file)
    else:
        raise Exception("Only txt and pkl file suffixes are supported.")


def clean_qwq_output(text: str) -> str:
    """Helper function: remove QwQ's <redacted_thinking> tags"""
    if "</redacted_thinking>" in text:
        return text.split("</redacted_thinking>")[-1].strip()
    return text


def ensure_scenic_maps_symlink(work_dir: str, repo_root: str) -> None:
    """
    Generated files live under work_dir/scenario_k/behavior_*.scenic.
    Safebench-style scripts use ``localPath('../maps/{Town}.xodr')`` → need work_dir/maps.
    """
    maps_dst = os.path.join(work_dir, "maps")
    src = os.path.join(
        repo_root,
        "safebench",
        "scenario",
        "scenario_data",
        "scenic_data",
        "maps",
    )
    if not os.path.isdir(src):
        return
    if os.path.lexists(maps_dst):
        return
    try:
        os.symlink(os.path.abspath(src), maps_dst, target_is_directory=True)
    except OSError:
        try:
            shutil.copytree(src, maps_dst)
        except OSError:
            pass


def try_load_safebench_route_params(
    repo_root: str, scenario_id: int, route_id: int, pickle_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    candidates: List[str] = []
    if pickle_path:
        candidates.append(pickle_path)
    candidates.append(
        os.path.join(
            repo_root,
            "safebench",
            "scenario",
            "scenario_data",
            "route",
            "scenic_route.pickle",
        )
    )
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
        except Exception:
            continue
        key = f"scenario_id_{scenario_id}_route_id_{route_id}"
        if key not in data:
            continue
        row = data[key]
        spawn = row["spawnPt"]
        return {
            "town": row["town"],
            "weather": row.get("weather", "ClearNoon"),
            "waypoints": row["waypoints"],
            "lanePts": row.get("lanePts", []),
            "spawnPt": (float(spawn["x"]), float(spawn["y"])),
            "z": float(spawn["z"]),
            "yaw": float(spawn["yaw"]),
        }
    return None


def default_stub_global_params(scenario_id: int) -> Dict[str, Any]:
    """
    Minimal globals when scenic_route.pickle is missing.
    Coordinates are placeholders; compile may succeed while scene sampling fails — still useful feedback.
    """
    _ = scenario_id
    return {
        "town": "Town01",
        "weather": "ClearNoon",
        "spawnPt": (335.0, 273.5),
        "z": 0.5,
        "yaw": 180.0,
        "waypoints": [(335.0, 273.5), (360.0, 273.5)],
        "lanePts": [],
    }


def format_scenic_exception(exc: BaseException) -> str:
    lines = [f"exception_type: {type(exc).__name__}", f"message: {exc}"]
    for name in ("filename", "lineno", "offset", "end_lineno", "end_offset", "text", "msg", "loc"):
        if hasattr(exc, name):
            try:
                lines.append(f"{name}: {getattr(exc, name)!r}")
            except Exception:
                pass
    return "\n".join(lines)


def validate_scenic_for_safebench(
    scenic_path: str,
    params: Dict[str, Any],
    model: str = DEFAULT_SCENIC_MODEL,
    try_sample_scene: bool = True,
) -> Tuple[bool, str]:
    """
    Tier 1: same entry as Safebench — scenarioFromFile(..., params=params, model=model).
    Tier 2: one scene sample — catches many issues that compile alone misses.
    """
    try:
        import scenic.syntax.translator as translator
        import scenic.core.errors as errors
    except ImportError as e:
        return False, f"Scenic not importable: {e}\nInstall the same scenic as Safebench uses."

    notes: List[str] = []

    try:
        scenario = errors.callBeginningScenicTrace(
            lambda: translator.scenarioFromFile(
                scenic_path, params=params, model=model, scenario=None
            )
        )
        notes.append("[compile] OK: Scenario object built.")
    except Exception:
        notes.append("[compile] FAILED")
        notes.append(traceback.format_exc())
        notes.append(format_scenic_exception(sys.exc_info()[1]))
        return False, "\n".join(notes)

    if not try_sample_scene:
        return True, "\n".join(notes)

    try:
        scene, iterations = errors.callBeginningScenicTrace(
            lambda: scenario.generate(verbosity=0)
        )
        notes.append(
            f"[sample] OK: generated scene (dynamicScenario={scene.dynamicScenario!r}, iterations={iterations})."
        )
        return True, "\n".join(notes)
    except Exception:
        notes.append(
            "[sample] FAILED (often what Safebench hits even when compile passes)"
        )
        notes.append(traceback.format_exc())
        notes.append(format_scenic_exception(sys.exc_info()[1]))
        return False, "\n".join(notes)


def extract_scenic_from_llm_output(text: str) -> str:
    patterns = [
        r"<redacted_thinking>.*?</redacted_thinking>\s*```Scenic\s*(.*?)```",
        r"```Scenic\s*(.*?)```",
        r"```scenic\s*(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    raise ValueError("LLM 输出中未找到 ```Scenic ... ``` 代码块")


def build_scenic_file_content(phase1_dict: Dict[str, str], phase2_body: str) -> str:
    return "\n".join(
        [
            f'# Description: {phase1_dict["Description"]}',
            f'# AdvType: {phase1_dict["AdvType"]}',
            f'# AdvPos: {phase1_dict["AdvPos"]}',
            f'# AdvBehavior: {phase1_dict["AdvBehavior"]}',
            phase2_body.strip(),
        ]
    )


def repair_scenic_with_llm(
    scenic_code: str,
    validation_feedback: str,
    phase1_dict: Dict[str, str],
) -> str:
    prompt = f"""你正在修复用于 CARLA + Safebench 管线的 Scenic 2.x 脚本。

{SAFEBENCH_SCENIC_CHECKLIST}

下面是静态/采样校验器的输出（可能同时包含 compile 与 sample 阶段）：
---
{validation_feedback}
---

当前完整文件内容（保留头部 # 注释；请输出同样带注释的完整文件）：
---
{scenic_code}
---

场景语义字段（不要改事件含义，只修正语法、API、与 Safebench 约束）：
- Description: {phase1_dict.get("Description", "")}
- AdvType: {phase1_dict.get("AdvType", "")}
- AdvPos: {phase1_dict.get("AdvPos", "")}
- AdvBehavior: {phase1_dict.get("AdvBehavior", "")}

只输出一个 Markdown 代码块，格式严格为：
```Scenic
（此处为完整 scenic 源码）
```
"""
    response = Settings.llm.complete(prompt)
    text = getattr(response, "text", None) or str(response)
    text = clean_qwq_output(text)
    body = extract_scenic_from_llm_output(text)
    return build_scenic_file_content(phase1_dict, body)


def run(
    llm_name: str,
    embed_name: str,
    scenario_ids: List[int],
    max_repair_rounds: int = 4,
    scenario_route_id: int = 1,
    route_pickle: Optional[str] = None,
    scenic_try_sample: bool = True,
):
    repo_root = _repo_root()
    msgen_root = _msgen_root()
    work_dir = os.path.join(
        repo_root, "safebench", "scenario", "scenario_data", "scenic_data"
    )
    print(f"输出 Scenic 文件到：{work_dir}")
    for i in sorted(set(scenario_ids)):
        scenario_dir = os.path.join(work_dir, f"scenario_{i}")
        if os.path.exists(scenario_dir):
            shutil.rmtree(scenario_dir)

    ensure_scenic_maps_symlink(work_dir, repo_root)

    Settings.llm = HuggingFaceLLM(model_name=llm_name, tokenizer_name=llm_name)
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_name)

    print("加载RAG中...")
    phase1_docs = SimpleDirectoryReader(
        input_dir=os.path.join(msgen_root, "knowledge_docs"),
        recursive=True,
    ).load_data()
    phase1_prompt = load(
        os.path.join(msgen_root, "prompts", "description_generate_extract.txt")
    )
    phase1_index = VectorStoreIndex.from_documents(phase1_docs)
    phase1_query_engine = phase1_index.as_query_engine()

    phase2_docs = SimpleDirectoryReader(
        input_dir=os.path.join(msgen_root, "scenic_docs"),
        recursive=True,
    ).load_data()
    phase2_prompt = load(os.path.join(msgen_root, "prompts", "scenic_generate.txt"))
    phase2_index = VectorStoreIndex.from_documents(phase2_docs)
    phase2_query_engine = phase2_index.as_query_engine()

    scenario_counter: Dict[int, int] = {}

    custom_bar_format = "{desc}: {bar} {n_fmt}/{total_fmt} | {postfix}"
    with tqdm(
        enumerate(scenario_ids), total=len(scenario_ids), bar_format=custom_bar_format
    ) as pbar:
        for idx, scenario_id in pbar:
            if scenario_id not in scenario_dict:
                print(f"编号 {scenario_id} 无效，请输入 1 到 8 的数字。")
                continue
            scenario_dir = os.path.join(work_dir, f"scenario_{scenario_id}")
            os.makedirs(scenario_dir, exist_ok=True)
            scenario_counter.setdefault(scenario_id, 0)
            scenario_counter[scenario_id] += 1
            scenario_idx = scenario_counter[scenario_id]

            while True:
                try:
                    pbar.set_description(
                        f"第{idx + 1}个基础场景为：{scenario_dict[scenario_id]}, Generating Phase 1!"
                    )
                    phase1_output = phase1_query_engine.query(
                        phase1_prompt.format(base_scenario=scenario_dict[scenario_id])
                    ).response
                    phase1_match = re.search(
                        r"<redacted_thinking>(.*?)</redacted_thinking>(.*?)```Text(.*?)```",
                        phase1_output,
                        re.DOTALL,
                    )
                    phase1_output = phase1_match.group(3)
                    phase1_dict = dict()
                    for sentence in phase1_output.splitlines():
                        if sentence:
                            parts = sentence.split(": ")
                            phase1_dict[parts[0]] = parts[1]
                    break
                except Exception as e:
                    pbar.set_postfix(
                        retry_reason=f"Error occurred in phase 1: {e}, retrying..."
                    )
            pbar.set_postfix({})

            while True:
                try:
                    pbar.set_description(
                        f"第{idx + 1}个基础场景为：{scenario_dict[scenario_id]}, Generating Phase 2!"
                    )
                    phase2_output = phase2_query_engine.query(
                        phase2_prompt.format(
                            Description=f'[{phase1_dict["Description"]}]',
                            AdvType=f'[{phase1_dict["AdvType"]}]',
                            AdvPos=f'[{phase1_dict["AdvPos"]}]',
                            AdvBehavior=f'[{phase1_dict["AdvBehavior"]}]',
                        )
                    ).response
                    phase2_match = re.search(
                        r"<redacted_thinking>(.*?)</redacted_thinking>(.*?)```Scenic(.*?)```",
                        phase2_output,
                        re.DOTALL,
                    )
                    phase2_output = phase2_match.group(3)
                    break
                except Exception as e:
                    pbar.set_postfix(
                        retry_reason=f"Error occurred in phase 2: {e}, retrying..."
                    )
            pbar.set_postfix({})

            scenic_code = build_scenic_file_content(phase1_dict, phase2_output)
            file_path = os.path.join(
                scenario_dir, f"behavior_{scenario_idx}_opt.scenic"
            )

            params = try_load_safebench_route_params(
                repo_root, scenario_id, scenario_route_id, route_pickle
            )
            if params is None:
                params = default_stub_global_params(scenario_id)
                pbar.set_postfix_str("using stub globalParameters (no route pickle)")

            # attempt = 已执行的 LLM 纠错次数；每次先写盘再校验，失败则最多再调用 max_repair_rounds 次 repair LLM
            repair_attempt = 0
            last_feedback = ""
            while True:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(scenic_code)

                ok, last_feedback = validate_scenic_for_safebench(
                    file_path,
                    params,
                    model=DEFAULT_SCENIC_MODEL,
                    try_sample_scene=scenic_try_sample,
                )
                if ok:
                    pbar.set_postfix(
                        scenic_ok=(
                            f"ok (llm_repairs={repair_attempt})"
                            if repair_attempt
                            else "ok"
                        )
                    )
                    break

                if repair_attempt >= max_repair_rounds:
                    print(
                        f"\n[warn] {file_path} 在 {max_repair_rounds} 次 LLM 纠错后仍失败，已保存最后一次版本。\n"
                        f"{last_feedback[:2000]}"
                    )
                    break

                repair_attempt += 1
                pbar.set_description(
                    f"第{idx + 1}个场景 Scenic LLM纠错 {repair_attempt}/{max_repair_rounds}"
                )
                try:
                    scenic_code = repair_scenic_with_llm(
                        scenic_code, last_feedback, phase1_dict
                    )
                except Exception as e:
                    pbar.set_postfix(repair_err=str(e))

            pbar.set_postfix({})


def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--llm_name", type=str, default="../weights/QwQ-32B")
    parser.add_argument("-e", "--embed_name", type=str, default="../weights/bge-m3")
    parser.add_argument(
        "-id",
        "--scenario_ids",
        nargs="*",
        type=int,
        default=[1, 1, 2, 3, 4, 5, 6, 7, 8],
    )
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=4,
        help="首次校验失败后，调用 LLM 纠错的最大次数（每次纠错后重新校验）。",
    )
    parser.add_argument(
        "--scenario-route-id",
        type=int,
        default=1,
        help="从 scenic_route.pickle 取数时的 route_id（与 Safebench 一致）。",
    )
    parser.add_argument(
        "--route-pickle",
        type=str,
        default=None,
        help="可选：显式指定 scenic_route.pickle 路径。",
    )
    parser.add_argument(
        "--no-scenic-sample",
        action="store_true",
        help="仅做 scenarioFromFile，不调用 scenario.generate（更快但更接近你原先的弱校验）。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    opt = parse_opt()
    run(
        llm_name=opt.llm_name,
        embed_name=opt.embed_name,
        scenario_ids=opt.scenario_ids,
        max_repair_rounds=opt.max_repair_rounds,
        scenario_route_id=opt.scenario_route_id,
        route_pickle=opt.route_pickle,
        scenic_try_sample=not opt.no_scenic_sample,
    )
