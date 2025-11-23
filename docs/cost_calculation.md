# Cost Calculation

The analyzer estimates cost using:

```
cost = (bytes_emitted / 1024^3) * price_per_gb
```

Default prices (`logcost.analyzer.PRICING_PER_GB`):

- GCP: $0.50/GB
- AWS: $0.57/GB
- Azure: $0.63/GB

Override pricing via `CostAnalyzer(..., price_per_gb=custom_value)` or pass `--provider` in the CLI.

Anti-pattern detectors flag:

- Statements executed >1,000 times (likely tight loops).
- DEBUG logs producing non-zero cost.
- Payloads exceeding 5 KB per call.

ROI estimates (`estimate` command) use:

```
potential_savings = total_cost * reduction_percent
effort_cost = hours_to_fix * hourly_rate
roi = (potential_savings - effort_cost) / effort_cost
```

Tune thresholds by forking `logcost/analyzer.py` or contributing configuration support.
