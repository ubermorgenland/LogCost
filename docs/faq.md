# FAQ

**Does LogCost change my logging behavior?**  
No. It wraps `logging.Logger._log` and `print` but always calls the original implementation after recording stats.

**What about other logging libs (structlog, loguru)?**  
Most of them delegate to `logging`; if not, you can wrap their log call to invoke `logcost.tracker._track_call` manually. Adapters are planned.

**How often should I export?**  
For scripts, rely on the built-in `atexit` export. For services, call `logcost.export()` on intervals (cron thread, signal handler, sidecar) to avoid losing stats on crashes.

**Is tracking configurable?**  
Use `logcost.ignore_module("module.prefix")` to skip helper frames. Thresholds for analyzer anti-patterns are constants in `logcost/analyzer.py`.

**Performance impact?**  
Designed for low overhead (lock-protected dict updates + string formatting). Run `python benchmarks/tracker_benchmark.py --iterations 100000` to measure on your hardware before enabling in latency-sensitive paths.
