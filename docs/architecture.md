# Architecture

```mermaid
flowchart LR
    UCI[Official UCI snapshot] --> HASH[Checksum and schema validation]
    HASH --> SPLIT[Clean CSV and stratified split]
    SPLIT --> EDA[Training-only EDA]
    SPLIT --> CV[Fold-local pipelines and LR/RF search]
    CV --> TRACK[MLflow SQLite and artifacts]
    CV --> MODEL[Locked winner and model metadata]
    MODEL --> CI[CI tests and isolated Docker smoke]
    CI --> GHCR[GHCR immutable digest]
    GHCR --> DEPLOY[User-invoked local release]
    DEPLOY --> API[Two API replicas behind LoadBalancer]
    CLIENT[JSON client] --> API
    API --> METRICS[Per-pod metrics and safe logs]
    METRICS --> PROM[Prometheus pod discovery]
    PROM --> GRAF[Provisioned Grafana dashboard]
```

The report builder also renders [the diagram](../reports/figures/architecture.png)
as an original bitmap for the PDF. Tracking is not an inference dependency.
GitHub-hosted runners never receive a kubeconfig for the local machine. The release
manifest identifies the evaluated model and tested container; deployment does not
retrain. The local API has no authentication and is loopback-bound for demonstration.
The Kubernetes LoadBalancer is a local assignment endpoint, not a hardened public service.