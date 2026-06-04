# msgen — LLM + RAG Scenic script generation

This folder implements ScenGE **step 1**: generate adversarial Scenic scripts via two-phase RAG.

## Layout

```
msgen/
  meta_scenario_generation.py   # entry point
  prompts/
    description_generate_extract.txt   # phase 1 prompt
    scenic_generate.txt                # phase 2 prompt
  knowledge_docs/               # phase 1 RAG corpus (scenario semantics)
  scenic_docs/                  # phase 2 RAG corpus (Scenic snippets)
```

## Two phases

| Phase | RAG index | Prompt | Output |
|-------|-----------|--------|--------|
| 1 | `knowledge_docs/` | `description_generate_extract.txt` | `Description`, `AdvType`, `AdvPos`, `AdvBehavior` |
| 2 | `scenic_docs/` | `scenic_generate.txt` | Scenic script body → `scenic_data/scenario_{id}/behavior_*_opt.scenic` |

Generated files are written to `safebench/scenario/scenario_data/scenic_data/scenario_{id}/`.

## Run (offline, no CARLA)

```bash
conda activate scenge-env
pip install -e .[msgen]
source carla_env.sh

# Option A: OpenAI-compatible API (LLM + RAG embedding, no HuggingFace download)
export OPENAI_API_KEY=sk-...
# optional: export OPENAI_BASE_URL=https://your-proxy/v1

python safebench/scenge/msgen/meta_scenario_generation.py \
  --llm-backend openai \
  --llm_name gpt-4o-mini \
  --embed-backend openai \
  --scenario_ids 1

# Option B: local HuggingFace LLM
python safebench/scenge/msgen/meta_scenario_generation.py \
  --llm-backend huggingface \
  --llm_name Qwen/Qwen2.5-7B-Instruct \
  --embed_name BAAI/bge-small-en-v1.5 \
  --scenario_ids 1
```

Pipeline (step 1 only) with OpenAI:

```bash
python scripts/scenge_pipeline.py --scenario_id 1 \
  --skip_train --skip_select --skip_eval \
  --llm_backend openai --llm_name gpt-4o-mini
```

## Notes

- Default pipeline msgen model is `gpt-4o-mini` with `--llm_backend openai` when using the API; set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL` for compatible proxies).
- For local weights, use `--llm_backend huggingface --llm_name <path-or-hf-id>`.
- `--no-scenic-sample` skips `scenario.generate()` validation (faster, weaker check).
- Expand RAG quality by adding more `.txt` files under `knowledge_docs/` and `scenic_docs/` (description ↔ snippet pairs).
