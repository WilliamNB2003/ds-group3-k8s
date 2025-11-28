import requests
import time
import numpy as np

url = "http://localhost:8080/get_cookie"

NUMBER_OF_REQUESTS = 100
times = []

for i in range(NUMBER_OF_REQUESTS):
    start = time.perf_counter()
    response = requests.get(url)
    response.raise_for_status()
    end = time.perf_counter()

    times.append(end - start)

average = sum(times) / len(times)
p95 = np.percentile(times, 95)
print("Average time: ", average)
print("P95: ", p95)