"""
Standalone research prototype. Not part of the production application.
Demonstrates the federated averaging concept described in docs/federated_anomaly_design.md.
"""
import numpy as np

# Set random seed for reproducibility
np.random.seed(42)

def train_local_model(data, epochs=50, lr=0.1):
    """
    Trains a simple 1D linear model (a single weight representing the expected normal value).
    Using gradient descent to minimize Mean Squared Error (MSE).
    """
    w = np.random.randn() # Initialize weight randomly
    for _ in range(epochs):
        grad = 0
        for x in data:
            grad += -2 * (x - w)
        w -= lr * (grad / len(data))
    return w

def compute_anomaly_score(w, x):
    """Simple anomaly score: absolute deviation from the learned expected value."""
    return abs(x - w)

def main():
    print("--- Federated Anomaly Learning PoC ---\n")
    
    # Simulate data for 3 PharmacyNodes.
    # Most shops buy the medicine at ~100.
    # Shop 3 bought one grey-market batch at 60.
    # Because Shop 3's volume is low, the 60 skews its local model heavily.
    
    node1_data = np.array([100, 102, 99, 101])
    node2_data = np.array([98, 100, 101, 99])
    node3_data = np.array([100, 60]) # The 60 is the grey-market anomaly
    
    # 1. Local Training
    w1 = train_local_model(node1_data)
    w2 = train_local_model(node2_data)
    w3 = train_local_model(node3_data)
    
    print("Local Model Weights (Expected Normal Rate):")
    print(f"Node 1: {w1:.2f}")
    print(f"Node 2: {w2:.2f}")
    print(f"Node 3 (with grey-market batch): {w3:.2f}\n")
    
    # 2. Local Outlier Detection at Node 3
    # Anomaly threshold set to 25.0
    threshold = 25.0
    local_score = compute_anomaly_score(w3, 60)
    print(f"Node 3 LOCAL Anomaly Score for rate 60: {local_score:.2f} (Threshold: {threshold})")
    print("Result: MISSED. The local model was skewed by the anomaly.\n")
    
    # 3. Federated Averaging (Aggregator step)
    # Weights are averaged, weighted by the number of samples at each node
    n1, n2, n3 = len(node1_data), len(node2_data), len(node3_data)
    total_samples = n1 + n2 + n3
    
    global_w = (w1 * n1 + w2 * n2 + w3 * n3) / total_samples
    print(f"Aggregator computes Global Model Weight: {global_w:.2f}\n")
    
    # 4. Global Outlier Detection at Node 3
    global_score = compute_anomaly_score(global_w, 60)
    print(f"Node 3 GLOBAL Anomaly Score for rate 60: {global_score:.2f} (Threshold: {threshold})")
    print("Result: DETECTED! The global model correctly flags the grey-market rate.")

if __name__ == "__main__":
    main()
