import time
import requests
import numpy as np
from multiprocessing import Pool

url = "http://localhost:8080/get_cookie"   # your server URL

# ---------------- Config ----------------
NUMBER_OF_REQUESTS = 1000
NUMBER_OF_REQUEST_PER_WORKER = 100
NUMBER_OF_WORKERS = 10
REQUEST_TIMEOUT = 2  # seconds

# ---------------- Worker Function ----------------
def worker(task_id):
    """Worker for multi-process load test. Returns a list of request times."""
    local_times = []
    for i in range(NUMBER_OF_REQUEST_PER_WORKER):
        start = time.time()
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except Exception as e:
            print(f"[Worker {task_id}] Request failed: {e}")
            continue
        end = time.time()
        local_times.append(end - start)
    return local_times

# ---------------- Main ----------------
if __name__ == "__main__":
    # ---------------- Single-threaded test ----------------
    times = []

    for i in range(NUMBER_OF_REQUESTS):
        start = time.perf_counter()
        response = requests.get(url)
        response.raise_for_status()
        end = time.perf_counter()

        times.append(end - start)

    average = sum(times) / len(times)
    p95 = np.percentile(times, 95)
    print("Singleprocess")
    print("Average time:", average)
    print("P95: ", p95)

    # ---------------- Multi-process load test ----------------
    print("\nStarting multi-process load test...")
    with Pool(NUMBER_OF_WORKERS) as pool:
        try:
            results = pool.map(worker, range(NUMBER_OF_WORKERS))
        except KeyboardInterrupt:
            print("KeyboardInterrupt received. Terminating workers...")
            pool.terminate()
            pool.join()
            exit(1)

    # Flatten results
    all_times = [t for sublist in results for t in sublist]

    average = sum(all_times) / len(all_times)
    p95 = np.percentile(all_times, 95)
    print("Multiprocess")
    print("Average time:", average)
    print("P95: ", p95)
