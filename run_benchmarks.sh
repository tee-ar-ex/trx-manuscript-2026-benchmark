#!/usr/bin/env bash
# Entry point for the tractography benchmark execution pipeline.

set -euo pipefail

# Find path of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "============================================================"
echo "Starting Multi-Language Tractography Benchmark Orchestrator"
echo "============================================================"

# Check if environment variable is set
if [ -z "${TRX_BENCHMARK_DATA_DIR:-}" ]; then
    echo "[INFO] environment variable TRX_BENCHMARK_DATA_DIR is not set."
    # Attempt default location in current workspace directory
    DEFAULT_DATA_DIR="$(cd "${SCRIPT_DIR}/../trx_benchmark_04_2026" && pwd || echo "")"
    if [ -d "${DEFAULT_DATA_DIR}" ]; then
        echo "[INFO] Found default benchmark dataset at ${DEFAULT_DATA_DIR}"
        export TRX_BENCHMARK_DATA_DIR="${DEFAULT_DATA_DIR}"
    else
        echo "[ERROR] Could not auto-detect data directory."
        echo "Please set TRX_BENCHMARK_DATA_DIR environment variable before running this script."
        exit 1
    fi
fi

echo "[INFO] TRX_BENCHMARK_DATA_DIR is set to: ${TRX_BENCHMARK_DATA_DIR}"

if [ "${1:-}" == "clean" ]; then
    echo "Cleaning build directories..."
    rm -rf cpp/build rust/target results/ js/node_modules
    echo "Cleaning temporary test data..."
    rm -f test_data/tmp* test_data/relay*
    exit 0
fi

# Run orchestrator
python3 orchestrate.py "$@"
