import requests
import time
import numpy as np

url = "http://localhost:8080/get_cookie"   # your server URL

NUMBER_OF_REQUEST = 1000
times = []

for i in range(NUMBER_OF_REQUEST):
    start = time.time()
    response = requests.get(url)
    response.raise_for_status()
    end = time.time()
    times.append(end - start)

p95 = np.percentile(times, 95)
print("Average time: ", sum(times)/NUMBER_OF_REQUEST)
print("P95: ", p95)