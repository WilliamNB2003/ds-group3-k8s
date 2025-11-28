import requests
import time
import subprocess

# 1. Configuration
URL = "http://localhost:8080"  # Minikube Service URL
POD_NAME = "bully-app-6576f786c6-4vb94"   # Pod name from Minikube
NAMESPACE = "default"

def check_endpoint(label):
    """Helper function to make a single request and print the time."""
    try:
        start = time.perf_counter()
        response = requests.get(URL, timeout=5)
        ttfb = response.elapsed.total_seconds()
        total = time.perf_counter() - start
        print(f"[{label}] Status: {response.status_code} | TTFB: {ttfb:.8f}s | Total: {total:.8f}s")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[{label}] Failed: {e}")
        return False

def trigger_pod_failure():
    """Executes the kubectl delete command."""
    print(f"\n!!! Killing Pod: {POD_NAME} !!!")
    try:
        # This runs: kubectl delete pod <name> -n <namespace>
        # We use --wait=false so Python doesn't pause waiting for the pod to disappear completely
        cmd = [
            "kubectl", "delete", "pod", POD_NAME, 
            "-n", NAMESPACE, 
            "--wait=false" 
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        print("!!! Delete command sent !!!\n")
    except subprocess.CalledProcessError as e:
        print(f"Error deleting pod: {e}")

# --- Main Test Sequence ---

# 1. Establish Baseline
print("1. Measuring Baseline...")
check_endpoint("Baseline")

# 2. Kill the Pod
trigger_pod_failure()

# 3. Measure Recovery (Loop until it succeeds)
print("3. Measuring Reaction/Recovery...")
start_fail_time = time.time()

for i in range(20):  # Try 20 times
    success = check_endpoint(f"Attempt {i+1}")
    
    if success:
        print(f"\nRECOVERED in {time.time() - start_fail_time:.8f} seconds!")
        break
    
    time.sleep(0.5) # Wait half a second before retrying