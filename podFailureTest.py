import requests
import time

def check_endpoint(url):
    try:
        # Start total timer
        start_time = time.perf_counter()
        
        # Make the request
        response = requests.get(url, timeout=10)
        
        # End total timer
        end_time = time.perf_counter()
        
        # 1. Time to First Byte (TTFB) - The "Reaction"
        # requests.elapsed is a timedelta object measuring time to headers
        ttfb = response.elapsed.total_seconds()
        
        # 2. Total Request Time (including download)
        total_time = end_time - start_time
        
        # 3. Download Time
        download_time = total_time - ttfb

        print(f"--- Results for {url} ---")
        print(f"Status Code:  {response.status_code}")
        print(f"TTFB (React): {ttfb:.8f}s")
        print(f"Total Time:   {total_time:.8f}s")
        print(f"Download:     {download_time:.8f}s")

    except requests.exceptions.RequestException as e:
        print(f"Error reaching endpoint: {e}")

# Usage
check_endpoint("http://localhost:8080/get_cookie")