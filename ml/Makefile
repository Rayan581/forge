# FORGE ML pipeline. Run from the repository root:  make -f ml/Makefile <target> [CONFIG=...]
# (No make on Windows? Every target is just "python -m ml.pipeline <stage> --config <file>".)
PY ?= python
CONFIG ?= ml/configs/default.json
RUN = $(PY) -m ml.pipeline

.PHONY: test smoke player judge sim ppo policy-shap baselines report all status

test:         ; $(PY) -m pytest ml/tests -v
smoke:        ; $(RUN) all --config ml/configs/smoke.json
player:       ; $(RUN) player --config $(CONFIG)
judge:        ; $(RUN) judge --config $(CONFIG)
sim:          ; $(RUN) sim --config $(CONFIG)
ppo:          ; $(RUN) ppo --config $(CONFIG)
policy-shap:  ; $(RUN) policy-shap --config $(CONFIG)
baselines:    ; $(RUN) baselines --config $(CONFIG)
report:       ; $(RUN) report --config $(CONFIG)
all:          ; $(RUN) all --config $(CONFIG)
status:       ; $(RUN) status --config $(CONFIG)
