"""Simple local load test for key Finch endpoints.

It can check rate limiting on the API ping endpoint and provide a rough
distribution of response codes and timings for a small set of URLs.
"""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request
import threading
import time
from collections import Counter, defaultdict


def run_worker(base_url, paths, requests_to_send, results):
    for _ in range(requests_to_send):
        for path in paths:
            started = time.perf_counter()
            try:
                request = urllib.request.Request(base_url + path)
                with urllib.request.urlopen(request, timeout=10) as response:
                    status_code = response.getcode()
                    retry_after = response.headers.get("Retry-After")
                elapsed_ms = (time.perf_counter() - started) * 1000
                results.append((path, status_code, elapsed_ms, retry_after))
            except urllib.error.HTTPError as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                results.append((path, exc.code, elapsed_ms, exc.headers.get("Retry-After")))
            except Exception as exc:
                results.append((path, "error", 0.0, str(exc)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["/", "/health/", "/api/ping/"],
    )
    args = parser.parse_args()

    results = []
    start = time.perf_counter()
    threads = []
    per_thread = max(1, args.requests // args.concurrency)

    for _ in range(args.concurrency):
        thread = threading.Thread(
            target=run_worker,
            args=(args.base_url, args.paths, per_thread, results),
        )
        thread.start()
        threads.append(thread)

    remainder = args.requests - (per_thread * args.concurrency)
    if remainder:
        thread = threading.Thread(
            target=run_worker,
            args=(args.base_url, args.paths, remainder, results),
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    elapsed = time.perf_counter() - start
    print(f"Sent {len(results)} requests across {len(args.paths)} paths in {elapsed:.2f}s")

    status_counts = Counter(status for _, status, _, _ in results)
    print("Status code distribution:")
    for code, count in sorted(status_counts.items(), key=lambda item: str(item[0])):
        print(f"  {code}: {count}")

    timings = defaultdict(list)
    for path, status, elapsed_ms, _ in results:
        if isinstance(status, int):
            timings[path].append(elapsed_ms)

    print("Average latency:")
    for path in args.paths:
        samples = timings.get(path, [])
        if samples:
            print(f"  {path}: {sum(samples) / len(samples):.2f} ms")
        else:
            print(f"  {path}: n/a")

    throttled = [item for item in results if item[1] == 429]
    if throttled:
        print("Rate limiting observed.")
        for path, _, _, retry_after in throttled[:5]:
            print(f"  {path} Retry-After={retry_after}")


if __name__ == "__main__":
    main()
