PYTHON ?= python
.PHONY: help test reproduce predict figures feature-check
help:
	@echo 'make reproduce  Verify saved evidence and recompute three benchmark summaries'
	@echo 'make predict    Run the default pretrained model on cached arithmetic features'
	@echo 'make figures    Regenerate the model and improvement diagrams'
	@echo 'make feature-check  Replay the matched feature comparison without training'
	@echo 'make test       Run current implementation and replay tests'
test:
	$(PYTHON) -m pytest -q
reproduce:
	$(PYTHON) scripts/reproduce.py --check
predict:
	$(PYTHON) scripts/predict.py --model base --candidates results/arithmetic-stress/candidates.json --features results/arithmetic-stress/features.json --output generated/predictions.json
figures:
	$(PYTHON) scripts/render_research_figures.py
	$(PYTHON) scripts/render_feature_comparison.py

feature-check:
	$(PYTHON) scripts/replay_feature_comparison.py
