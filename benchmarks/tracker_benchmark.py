"""
Simple benchmark to estimate tracker overhead.

Run:
    python benchmarks/tracker_benchmark.py --iterations 100000
"""
import argparse
import logging
import time

import logcost


def run(iterations: int) -> float:
    logger = logging.getLogger("logcost.benchmark")
    logger.setLevel(logging.INFO)
    start = time.perf_counter()
    for i in range(iterations):
        logger.info("Benchmark message %s", i)
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100000)
    args = parser.parse_args()
    logcost.reset()
    elapsed = run(args.iterations)
    print(f"{args.iterations} logs in {elapsed:.3f}s ({args.iterations/elapsed:.1f} logs/sec)")


if __name__ == "__main__":
    main()
