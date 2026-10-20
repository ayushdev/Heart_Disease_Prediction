# Submission Gates

| Requirement | Implementation/evidence | Verified status |
| --- | --- | --- |
| Acquisition and EDA (5) | Official raw/clean CSV, checksum, schema, five plots | Executed locally |
| Features and two models (8) | Fold-local Pipeline, 18 candidates, five-fold CV, holdout metrics | Executed locally |
| Experiment tracking (5) | MLflow candidate/winner/parent runs, parameters, metrics, models, plots | Executed locally |
| Reproducibility (7) | Full and serving dependency locks, metadata, deterministic split, round-trip parity | Fresh Windows/Ubuntu CI environments and Linux serving verified |
| CI/CD and tests (8) | Ruff, pytest, Windows/Ubuntu Actions, model/image artifacts | 39 local tests pass; hosted workflow passed and published a tested digest |
| Docker (5) | Non-root image, packaged model, isolated smoke script | Built and verified locally and in CI; actual prediction screenshot saved |
| Kubernetes (7) | Two replicas, probes/resources, digest deployment, LoadBalancer | Deployment and localhost:8080 prediction verified; capture and resource inventory saved |
| Monitoring (3) | Safe logs, /metrics, pod discovery, provisioned Grafana | 120 real requests; two healthy pod targets; actual request-rate chart captured |
| Documentation (2) | README, architecture, original narrative, ten-page report | Draft generated; final requires evidence |
| Extra deliverables | Repository URL, real screenshots, narrated video, access instructions | Repository, author details and screenshots present; author will record video later |

Verified release: model `24f056bb0011`, produced by
[CI run 39396167399](https://github.com/ayushdev/Heart_Disease_Prediction/actions/runs/39396167399).
See `reports/evidence/` for the actual release, LoadBalancer, and monitoring checks.

Before submission:

- [ ] Review and personalize explanations; follow course assistance/disclosure rules.
- [x] Publish the repository, run Actions, and preserve the successful run URL/artifacts.
- [x] Build/run Docker locally and save genuine container prediction proof.
- [x] Deploy the tested image, verify actual LoadBalancer access, and capture resources.
- [x] Generate monitoring traffic and capture a populated Grafana request-rate chart.
- [ ] Record the narrated demo and verify the submission link/file is accessible.
- [ ] Add the video to screenshots/evidence.json and run the report builder with --final.
- [ ] Confirm exactly ten final pages, inspect every page, and verify that report results,
  model metadata, image release, and deployment identify the same experiment.
- [x] Exercise fresh hosted checkouts, locked installs, training and isolated serving.

Production-readiness checks are not waived by a draft report or a valid YAML file.
The supplied training data is historical and small; externally validated clinical
performance, authentication/TLS, durable storage, capacity testing, backups, and
drift evaluation are outside this local educational deployment and must be addressed
before real-world use.