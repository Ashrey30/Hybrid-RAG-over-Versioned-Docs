PY=python
setup:        ; pip install -r requirements.txt
qdrant:       ; docker compose up -d qdrant
ingest:       ; $(PY) -m ingest.index
golden-draft: ; $(PY) -m eval.build_golden
baseline:     ; $(PY) -m eval.run_baseline
ablation:     ; $(PY) -m eval.ablation
ksweep:       ; $(PY) -m eval.ksweep
router:       ; $(PY) -m eval.router_eval
bench-data:   ; $(PY) -m bench.prepare_data
bench:        ; $(PY) -m bench.run_bench
bench-capped: ; docker compose -f docker-compose.bench-capped.yml up -d && $(PY) -m bench.run_bench --capped
bench-plots:  ; $(PY) -m bench.plots
injection:    ; $(PY) -m eval.injection_eval
cache-pairs:  ; $(PY) -m eval.cache_eval --make
cache-eval:   ; $(PY) -m eval.cache_eval
leak-qs:      ; $(PY) -m eval.leak_test --make
leak:         ; $(PY) -m eval.leak_test
final:        ; $(PY) -m eval.final_eval --faithfulness
serve:        ; uvicorn api.main:app --port 8000
latency:      ; $(PY) -m eval.latency_report
test:         ; pytest -q
lint:         ; ruff check .
