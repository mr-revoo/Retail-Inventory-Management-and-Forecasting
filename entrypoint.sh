#!/bin/bash
set -e

echo "============================================"
echo "  Retail Analytics ETL Pipeline Starting"
echo "============================================"

# Wait for PostgreSQL to be ready
echo "[WAIT] Waiting for PostgreSQL..."
until nc -z db 5432; do
  echo "[WAIT] PostgreSQL not ready yet, retrying in 2s..."
  sleep 2
done
echo "[OK] PostgreSQL is accepting connections."

# Run the ETL pipeline
echo "[ETL] Running ETL pipeline..."
python src/etl.py
ETL_EXIT=$?

if [ $ETL_EXIT -ne 0 ]; then
  echo "[FAIL] ETL pipeline failed with exit code $ETL_EXIT"
  exit $ETL_EXIT
fi

echo "[OK] ETL pipeline completed successfully."

# Start the Streamlit app
echo "[APP] Starting Streamlit dashboard..."
exec streamlit run src/app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
