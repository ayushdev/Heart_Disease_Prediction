# Submission Gates

| Requirement | Implementation/evidence | Verified status |
| --- | --- | --- |
| Acquisition and EDA (5) | Official raw/clean CSV, checksum, schema, five plots | Executed locally |
| Features and two models (8) | Fold-local Pipeline, 18 candidates, five-fold CV, holdout metrics | Executed locally |
| Experiment tracking (5) | MLflow candidate/winner/parent runs, parameters, metrics, models, plots | Executed locally |
| Reproducibility (7) | Full and serving dependency locks, metadata, deterministic split, round-trip parity | Windows environments and Linux serving verified; hosted training pending |
| CI/CD and tests (8) | Ruff, pytest, Windows/Ubuntu Actions, model/image artifacts | 36 local tests and Ruff gates pass; hosted run pending |
| Docker (5) | Non-root image, packaged model, isolated smoke script | Linux image built; no-mount prediction parity, HTTP 422 and metrics verified; screenshot pending |
| Kubernetes (7) | Two replicas, probes/resources, digest deployment, LoadBalancer | Actual cluster deployment/screenshots pending |
| Monitoring (3) | Safe logs, /metrics, pod discovery, provisioned Grafana | Local API metrics checked; cluster dashboard pending |
| Documentation (2) | README, architecture, original narrative, ten-page report | Draft generated; final requires evidence |
| Extra deliverables | Repository URL, real screenshots, narrated video, access instructions | Repository configured; remaining screenshots/recording pending |

Before submission:

- Review and personalize explanations; follow course assistance/disclosure rules.
- Publish the repository, run Actions, and preserve the successful run URL/artifacts.
- Build/run Docker locally and save actual build/prediction proof.
- Deploy the tested image, verify actual LoadBalancer access, and capture resources.
- Generate monitoring traffic and capture populated Grafana panels.
- Record the narrated demo and verify the submission link/file is accessible.
- Complete screenshots/evidence.json and run the report builder with --final.
- Confirm exactly ten pages, inspect every page, and verify that report results,
  model metadata, image release, and deployment identify the same experiment.
- Rehearse setup from a clean clone. Do not submit virtual environments or secrets.

Production-readiness checks are not waived by a draft report or a valid YAML file.
The supplied training data is historical and small; externally validated clinical
performance, authentication/TLS, durable storage, capacity testing, backups, and
drift evaluation are outside this local educational deployment and must be addressed
before real-world use.