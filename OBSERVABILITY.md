# Observability & Monitoring Roadmap

## Current State

| Tool | Status | Notes |
|------|--------|-------|
| **monit** | Basic | Watches 3 services, restarts on failure |
| **VictoriaMetrics** | Basic | Storing data, 100yr retention |
| **Vector** | Basic | MQTT → VictoriaMetrics pipeline |
| **HiveMQ** | Basic | MQTT broker (temporary until CircuitPython port) |
| **Grafana Cloud** | Connected | Dashboards, basic IRM setup |
| **Alloy** | Minimal | Running but not configured |
| **vmalert** | Not configured | |
| **M/Monit** | Not set up | Just local monit |

---

## Architecture Decisions

### Tool Responsibilities

Each tool has ONE primary job to avoid overlap and confusion:

| Job | Tool | Notes |
|-----|------|-------|
| Metrics storage | VictoriaMetrics | 100yr retention, InfluxDB line protocol |
| Metric-based alerts | vmalert | "Is data present? Is temp in range?" |
| Data pipeline | Vector | Transforms, routing, aggregation |
| Pipeline debugging | Vector tap/top | Real-time inspection |
| Service restart | monit | "Is it running? Restart if not" |
| Self-monitoring trends | M/Monit | Historical view of service health |
| Device health | Alloy | Pi CPU, memory, disk, temp |
| Visualization | Grafana Cloud | Dashboards, AI investigation |
| Alert routing | Grafana Cloud IRM | All alerts funnel here |

### Local vs Cloud

- **Everything to cloud** - Grafana Cloud is reliable enough
- **Local self-healing only** - monit restarts services, no local notifications
- **Alert labels from the start** - `type: shop` vs `type: system` for future routing

### Alert Types (Future Product)

| Type | Recipient | Examples |
|------|-----------|----------|
| **Shop alerts** | Owner/Artist | Furnace too cold/hot, flame out, no data |
| **System alerts** | Product support | Container restarted, disk full, pipeline errors |

### Dropped Tools

- **Bindplane** - Removed. Grafana can provide pipeline visualization with proper Alloy/Vector metrics config. Can revisit if needed.

---

## Roadmap

### Phase 1: Foundation (Current)
- [x] VictoriaMetrics running via quadlet
- [x] Vector pipeline working
- [x] HiveMQ MQTT broker
- [x] Basic monit service watching
- [x] pyinfra as single source of truth
- [ ] Finish data migration from InfluxDB
- [ ] Commit repo with current state

### Phase 2: Alerting
- [ ] Configure vmalert with basic rules:
  - Furnace temp out of range
  - No data for N minutes
  - Flame voltage erratic
- [ ] Connect vmalert to Grafana Cloud IRM
- [ ] Test alert routing
- [ ] Add Michael as recipient (shop alerts only)

### Phase 3: Self-Monitoring
- [ ] Set up M/Monit central server
- [ ] Configure trending and historical analysis
- [ ] Expand monit checks (data flow validation)

### Phase 4: Device Health
- [ ] Configure Alloy properly
- [ ] Collect Pi metrics (CPU, memory, disk, temp)
- [ ] Create device health dashboard
- [ ] Set alerts for resource issues

### Phase 5: Advanced Pipeline
- [ ] Vector transforms (data enrichment)
- [ ] Vector routing (different destinations by type)
- [ ] Explore tap/top for debugging
- [ ] Pipeline visualization in Grafana

### Phase 6: AI/ML Integration
- [ ] Leverage Grafana Cloud AI investigation
- [ ] Feed recommendations back into data collection
- [ ] Pattern recognition across larger dataset

---

## Migration Checklist

- [ ] All historical InfluxDB data pushed to VictoriaMetrics
- [ ] Verify data integrity (row counts, time ranges)
- [ ] Remove InfluxDB container
- [ ] Update any remaining references to old stack

---

## Tool Capabilities Reference

### VictoriaMetrics + vmalert
- Multitenant queries (future: per-studio isolation)
- Replay rules on historical data (test before enabling)
- Anomaly detection (flame voltage drift)
- Alerting on logs (if logging added later)

### Vector
- Transforms: reshape, enrich, filter in-flight
- Routing: different destinations based on rules
- Aggregation: combine high-frequency samples
- tap/top: real-time inspection and performance

### monit / M/Monit
- Custom program checks (data flow validation)
- Alert aggregation (reduce noise)
- Trend analysis and forecasting
- REST API for integration
- Centralized dashboard across hosts

### Alloy
- Multi-signal: metrics, logs, traces, profiles
- Live graph UI for pipeline visualization
- 120+ configurable components
- Fleet management for scaling

### Grafana Cloud IRM
- Custom incident statuses
- Automated escalation chains
- Custom metadata fields (studio ID, location)
- Post-incident analysis and trends
- Declare incidents from dashboards

---

## Quick Reference

### Deploy system
```bash
cd ~/sensor-pipeline/pyinfra && pyinfra @local deploy.py -y
```

### Check services
```bash
systemctl --user status hivemq victoriametrics vector
sudo systemctl status monit
```

### Query current data
```bash
curl -s "http://127.0.0.1:8428/api/v1/query?query=furnace_furnace_temp"
```

### Health checks
```bash
curl -s http://127.0.0.1:8428/health  # VictoriaMetrics
curl -s http://127.0.0.1:8686/health  # Vector
```
