.PHONY: install dev-install ingest validate preview clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install the package in development mode"
	@echo "  dev-install  - Install dependencies for development"
	@echo "  ingest       - Run ingestion on the Excel file"
	@echo "  validate     - Validate the Excel file structure"
	@echo "  preview      - Preview the Excel file contents"
	@echo "  clean        - Clean up generated files"

# Install the package in development mode
install:
	python3 -m pip install -e .

# Install development dependencies
dev-install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install -e .

# Run ingestion on the Excel file
ingest:
	austin-excel ingest AustinTXEnvironmentalCriteriaManualEXPORT20250102.xlsx

# Validate the Excel file
validate:
	austin-excel validate AustinTXEnvironmentalCriteriaManualEXPORT20250102.xlsx

# Preview the Excel file
preview:
	austin-excel preview AustinTXEnvironmentalCriteriaManualEXPORT20250102.xlsx

# Clean up generated files
clean:
	rm -f *.jsonl *.parquet *.json
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Prettify JSON output
prettify:
	python3 -c "import json; data = [json.loads(line) for line in open('AustinTXEnvironmentalCriteriaManualEXPORT20250102.jsonl')]; print(json.dumps(data, indent=2))" > prettified_output.json

# Prettify semantic JSON output
prettify-semantic:
	python3 -c "import json; data = [json.loads(line) for line in open('AustinTXEnvironmentalCriteriaManualEXPORT20250102_semantic.jsonl')]; print(json.dumps(data, indent=2))" > prettified_semantic_output.json

# Prettify chunked semantic JSON output
prettify-chunked:
	python3 -c "import json; data = [json.loads(line) for line in open('AustinTXEnvironmentalCriteriaManualEXPORT20250102_semantic_chunked.jsonl')]; print(json.dumps(data, indent=2))" > prettified_chunked_output.json

# Apply hierarchical chunking
chunk:
	austin-excel chunk AustinTXEnvironmentalCriteriaManualEXPORT20250102.jsonl --max-tokens 300

# Add semantic paths
semantic:
	austin-excel semantic-path AustinTXEnvironmentalCriteriaManualEXPORT20250102.jsonl

# Complete workflow: semantic paths + chunking
workflow:
	python3 process_workflow.py AustinTXEnvironmentalCriteriaManualEXPORT20250102.jsonl 