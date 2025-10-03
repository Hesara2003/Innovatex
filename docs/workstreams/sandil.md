# Sandil — Data Engineering & Eval

Focus: schemas, joins, evaluation, and reproducibility.

## Scope
- Normalize incoming records and join with CSVs (`products_list.csv`, `customer_data.csv`).
- Create `src/pipeline/transform.py` & `src/pipeline/joiners.py`.
- Build evaluation script comparing produced events vs. reference taxonomy.
- Add `run_demo.py` glue to orchestrate end-to-end run into `./results/`.

## Deliverables
- Schema mappers for each dataset.
- Joiners that enrich events with product/customer metadata.
- Eval script: precision/recall on labeled examples if provided.
- Deterministic `run_demo.py` with seed and logging.

## Milestones
- M1: Transform + join functions with docstrings.
- M2: Demo script emits JSONL to `results/`.
- M3: Eval metrics printed at end of run.
