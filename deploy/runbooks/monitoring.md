# Runbook — Monitoring (CloudWatch + Sentry + Prometheus)

Three layers: infra/host (CloudWatch), application errors (Sentry), application
metrics (Prometheus via the app's `/metrics`).

## CloudWatch (provisioned by Terraform)
**Logs:** the CloudWatch agent (installed via user-data) ships host + container
logs to `/wedfind/<env>/app`. App logs are structured JSON (`LOG_JSON=true`) with
a correlation/request id — query in Logs Insights:
```
fields @timestamp, request_id, level, message
| filter level = "ERROR"
| sort @timestamp desc
```

**Alarms → SNS topic `wedfind-<env>-alarms`** (subscribe email/Slack):
| Alarm | Trigger |
|---|---|
| `app-cpu-high` | EC2 CPU > 85% / 15m (face matching saturation) |
| `app-status-failed` | EC2 status check failing |
| `rds-storage-low` | RDS free storage < 2 GB |
| `rds-cpu-high` | RDS CPU > 85% / 15m |
| `redis-mem-high` | Redis memory > 80% |

Verify state:
```bash
aws cloudwatch describe-alarms --alarm-name-prefix wedfind-<env> \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' --output table
```

## Sentry (application errors)
- Set `SENTRY_DSN` in the secret (empty = disabled). The backend already wires
  Sentry (Phase 3-A). After setting, redeploy.
- Verify: trigger a handled test error or watch first real exception appear in
  the Sentry project. Confirm release/environment tags = `<env>`.
- Recommended: alert rules for new-issue + error-rate spikes → same ops channel.

## Prometheus (application metrics)
- The app exposes `/metrics` (`ENABLE_METRICS=true`) — HTTP latency/throughput,
  plus app counters. It is **internal-network only** (no auth), reached on
  `api:8000/metrics` inside the compose network.
- Scrape options:
  1. **Managed:** AWS Managed Prometheus (AMP) + a scraper sidecar, or
  2. **Self-hosted:** add a `prometheus` service to the compose stack scraping
     `api:8000/metrics`, and Grafana for dashboards.
- Minimal scrape config:
  ```yaml
  scrape_configs:
    - job_name: wedfind-api
      metrics_path: /metrics
      static_configs: [{ targets: ["api:8000"] }]
  ```
- Do NOT expose `/metrics` publicly. Keep it behind the compose network / a
  private scraper; Caddy does not route `/metrics`.

## What to watch during beta
- API p95 latency + 5xx rate (Prometheus).
- Celery queue depth / task failures (worker logs; consider a queue-length metric).
- Face-match throughput vs CPU (app-cpu-high alarm is the early warning).
- RDS connections + storage growth (photos/embeddings).
- Sentry error volume after each studio onboards.
