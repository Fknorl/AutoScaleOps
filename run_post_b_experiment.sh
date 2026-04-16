#!/bin/bash
echo "=== Post Mode B Experiment Script ==="
echo "Started at: $(date)"

cd "/c/Users/furka/Desktop/AutoScaleOps-Product - with Claude"

# Kill traffic simulator
kill $(ps aux | grep traffic_simulator | grep -v grep | awk '{print $1}') 2>/dev/null
echo "Traffic simulator killed"
sleep 5

# Check CSV size
echo "Mode B v4 CSV rows: $(wc -l < results_B_v4.csv)"

# Quick analysis
echo "Running analiz.py on results_B_v4.csv..."
python analiz.py --input results_B_v4.csv --no-plot 2>&1 | grep -E "MAPE|MAE|RMSE|Cold-start|pod|Scale" | head -15

echo ""
echo "=== Starting Spike Test ==="
python spike_test.py --mode B --target http://localhost:8080 --output spike_results_v4.csv 2>&1 &
SPIKE_PID=$!
echo "spike_test.py PID: $SPIKE_PID"

# Wait 30 min for spike test
sleep 1800
echo "Spike test completed"

# Run Mode A experiment
echo "=== Starting Mode A Experiment ==="
# Suspend KEDA
kubectl patch scaledobject autoscaleops-keda -n autoscaleops-74068768 --type=json \
  -p='[{"op": "replace", "path": "/spec/paused", "value": true}]' 2>&1

# Scale to 4 fixed pods (average expected)
kubectl scale deployment autoscaleops-app-deployment -n autoscaleops-74068768 --replicas=4 2>&1
sleep 30

# Start traffic + metrics
python traffic_simulator.py --mode A --duration 1800 --target http://localhost:8080 &
python metrics_logger.py --mode A --output results_A_v4.csv --duration 1800 > metrics_A_v4.log 2>&1
wait

echo "=== All experiments done: $(date) ==="
