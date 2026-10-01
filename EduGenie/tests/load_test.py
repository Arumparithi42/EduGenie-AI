"""Simple concurrent load test for a running EduGenie server (not collected by pytest).

Usage (server must be running, e.g. `uvicorn main:app`):
    python tests/load_test.py                       # default scenarios against http://127.0.0.1:8000
    python tests/load_test.py --users 20 --duration 30 --url http://127.0.0.1:8000

Each scenario starts N virtual users that send requests back-to-back for the given
duration and reports average / p95 / max response time, throughput and error rate.
Note: the AI endpoints call Gemini, so their numbers mostly reflect Gemini latency and
your API quota (free-tier keys are rate-limited, which shows up as errors).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

SCENARIOS = {
    "home": ("GET", "/", None),
    "health": ("GET", "/health", None),
    "qa": ("GET", "/qa?question=Which%20is%20the%20largest%20ocean%3F", None),
    "explain": ("POST", "/explain", {"topic": "Photosynthesis"}),
    "quiz": ("POST", "/quiz", {"text": "The Pythagoras Theorem"}),
    "summarize": ("POST", "/summarize", {"text": "The water cycle describes how water evaporates, condenses and falls as rain. " * 5}),
    "path": ("GET", "/learn/recommendations?topic=SQL", None),
}


async def virtual_user(client, method, path, body, deadline, timings, errors):
    while time.perf_counter() < deadline:
        start = time.perf_counter()
        try:
            response = await client.request(method, path, json=body)
            ok = response.status_code < 400
        except httpx.HTTPError:
            ok = False
        timings.append(time.perf_counter() - start)
        if not ok:
            errors.append(1)


async def run_scenario(url, name, users, duration):
    method, path, body = SCENARIOS[name]
    timings: list[float] = []
    errors: list[int] = []
    async with httpx.AsyncClient(base_url=url, timeout=120) as client:
        deadline = time.perf_counter() + duration
        started = time.perf_counter()
        await asyncio.gather(*(virtual_user(client, method, path, body, deadline, timings, errors) for _ in range(users)))
        elapsed = time.perf_counter() - started
    if not timings:
        return None
    timings.sort()
    return {
        "scenario": name,
        "users": users,
        "requests": len(timings),
        "avg_ms": statistics.mean(timings) * 1000,
        "p95_ms": timings[int(len(timings) * 0.95) - 1] * 1000 if len(timings) > 1 else timings[0] * 1000,
        "max_ms": timings[-1] * 1000,
        "rps": len(timings) / elapsed,
        "error_pct": 100 * len(errors) / len(timings),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=10, help="virtual users per scenario")
    parser.add_argument("--duration", type=float, default=15, help="seconds per scenario")
    parser.add_argument("--scenarios", default=",".join(SCENARIOS), help="comma-separated: " + ",".join(SCENARIOS))
    args = parser.parse_args()

    header = f"{'Scenario':<10}{'Users':>6}{'Requests':>10}{'Avg ms':>10}{'p95 ms':>10}{'Max ms':>10}{'Req/s':>9}{'Errors':>9}"
    print(f"EduGenie load test against {args.url}\n{header}\n{'-' * len(header)}")
    for name in args.scenarios.split(","):
        result = asyncio.run(run_scenario(args.url, name.strip(), args.users, args.duration))
        if result:
            print(
                f"{result['scenario']:<10}{result['users']:>6}{result['requests']:>10}{result['avg_ms']:>10.1f}"
                f"{result['p95_ms']:>10.1f}{result['max_ms']:>10.1f}{result['rps']:>9.1f}{result['error_pct']:>8.1f}%"
            )


if __name__ == "__main__":
    main()
