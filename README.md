# Heart Risk MLOps

A reproducible UCI Cleveland classifier with MLflow experiments, a validated FastAPI API,
hash-locked environments, CI image delivery, and Docker Desktop Kubernetes monitoring.
Educational use only: this predicts the dataset's recorded disease-presence label, not
prospective clinical risk. Do not use it to diagnose or treat patients.

## Current Evidence

The official data, EDA, two-model experiment, model bundle, unit tests, and local API
have been executed here. Measured results are in [reports/results.json](reports/results.json).
The isolated Docker image was built and verified on Linux with no host mounts;
[container evidence](reports/evidence/container.json) records prediction parity,
HTTP 422 validation, and exposed metrics. All 36 tests and both Ruff gates pass locally.
Kubernetes execution, hosted GitHub Actions, remaining screenshots, and the narrated
video remain submission gates. [The report](reports/assignment_report_DRAFT.pdf)
is explicitly a ten-page draft until these gates are satisfied.

| Model | CV ROC-AUC mean (SD) | Test accuracy | Test precision | Test recall | Test ROC-AUC |
| --- | --- | --- | --- | --- | --- |
| Logistic Regression, selected | 0.911 (0.030) | 0.885 | 0.839 | 0.929 | 0.965 |
| Random Forest | 0.909 (0.035) | 0.869 | 0.812 | 0.929 | 0.953 |

Selection uses CV only. The test set has 61 records; the small CV difference is not
evidence of statistically established superiority. Recompute the table when changing
the experiment, and do not tune using the test results.

## Clean Setup

Use **64-bit Python 3.11** and Git. Run commands from this repository root. For Docker,
install Docker Desktop from its official site, select Linux containers, and enable
Kubernetes. Managed machines may require organizational permission for WSL2,
virtualization, installation, and Docker licensing. Do not reset existing clusters.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pip check
```

On Linux, create the environment with `python3.11 -m venv .venv` and substitute
`.venv/bin/python` for the Windows executable. No environment activation is required.
The Python package installation is separate from dependency installation so hashed
requirements do not need an unhashed editable-project entry. Locks were generated
under Python 3.11; Windows-only pywin32 is guarded by an environment marker, and
Gunicorn is pinned for the Linux MLflow runtime.

Readable dependency inputs are [requirements.in](requirements.in) and
[requirements-serving.in](requirements-serving.in). To deliberately update locks:

```powershell
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --strip-extras --output-file requirements.txt requirements.in
.\.venv\Scripts\pip-compile.exe --generate-hashes --allow-unsafe --strip-extras --output-file requirements-serving.txt requirements-serving.in
```

Rerun all validation after dependency updates and retrain the model. Do not update a
serving library independently of training. Generated environments/tracking data may
be large in OneDrive; avoid concurrent sync writes to an active MLflow SQLite database.

## Reproduce the Experiment

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest test -q --junitxml=reports/tests.xml --cov=heart_risk --cov-report=xml
.\.venv\Scripts\python.exe -m heart_risk.data
.\.venv\Scripts\python.exe -m heart_risk.eda
.\.venv\Scripts\python.exe -m heart_risk.train
.\.venv\Scripts\python.exe -m heart_risk.inference
.\.venv\Scripts\python.exe scripts/build_report.py
```

Alternatively run `./scripts/run_pipeline.ps1`; it checks exit codes and stops on
failures. The data command normally verifies the bundled raw snapshot. Use
`python -m heart_risk.data --download-again` to fetch from UCI and require the same
recorded checksum. Network failures never generate replacement data. The seed,
fold count, search grids, and fixed threshold are in [configs/training.json](configs/training.json).

Outputs: cleaned data and split manifests, five EDA plots, per-family CV tables,
holdout plots, [reports/results.json](reports/results.json), MLflow SQLite/artifacts,
and the generated `models/` serving bundle. Models/tracking are ignored in Git and
recreated by CI; the original and cleaned attributed data are included.

To inspect experiments in a separate terminal:

```powershell
.\.venv\Scripts\python.exe -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000 --no-serve-artifacts
```

Open http://localhost:5000 and select `cleveland-heart-risk`. A complete run contains
18 candidate child runs, two locked family winners, and their parent. Failed runs
remain visible. SQLite stores metadata; the `mlartifacts/` directory stores artifacts.
CI archives both plus portable JSON/CSV/model outputs. Moving the SQLite database
does not rewrite absolute artifact locations; inspect local tracking in place or
reproduce it from the recorded configuration.

## Run and Verify the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn heart_risk.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open http://localhost:8000/docs. In another terminal:

```powershell
.\.venv\Scripts\python.exe scripts/verify_api.py --url http://127.0.0.1:8000 --model-dir models --output reports/evidence/local-api.json
Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -ContentType application/json -Body (Get-Content examples/patient.json -Raw)
```

`/healthz` reports process health; `/readyz` confirms model readiness; `/metrics`
exposes Prometheus text. `/predict` requires all 13 documented keys. `ca` and `thal`
can be null; unknown keys, wrong types, missing keys, non-finite values, and invalid
UCI categories produce HTTP 422. See [data/README.md](data/README.md) for units/codes.
The Swagger example should use the supplied patient JSON, not placeholder zeros.

The response contains `prediction`, `disease_probability`, `confidence`,
`model_version`, and `request_id`. Confidence is the returned class probability,
not guaranteed correctness. Request logs exclude patient measurements. Model files
must come from a trusted producer: a checksum alone does not make pickle/joblib safe.
The smoke verifier bypasses inherited HTTP proxies only for loopback destinations.

## Isolated Docker Proof

After Docker Desktop is installed and running:

```powershell
docker build --tag heart-risk:local .
docker run -d --name heart-risk-local -p 127.0.0.1:8001:8000 heart-risk:local
.\.venv\Scripts\python.exe scripts/verify_api.py --url http://127.0.0.1:8001 --model-dir models --output reports/evidence/container.json
docker inspect heart-risk-local
docker logs heart-risk-local
```

There are intentionally **no model bind mounts**. Capture the build, container,
and successful prediction in `screenshots/docker.png`, then remove only this test
container with `docker rm -f heart-risk-local`. Port 8001 avoids the local Python API.

## GitHub Actions and Image Delivery

Repository: https://github.com/ayushdev/Heart_Disease_Prediction.
Review files before publishing changes: do not publish credentials, virtual
environments, or unrelated work.
Enter the real repository URL in [screenshots/evidence.json](screenshots/evidence.json).
Use a `main` branch for image promotion and enable Actions/package permissions.
No repository, branch, or commit is created automatically by these scripts.

[The workflow](.github/workflows/ci.yml) runs Windows/Ubuntu checks, then training,
then isolated Docker verification. Each stage depends on the preceding gate. Failed
steps block release; artifacts are retained even on failure. On trusted pushes to
main, GHCR receives the same tested image and a digest-based release manifest is
uploaded in `delivery-evidence`. Pull requests never publish images. GITHUB_TOKEN
is supplied by Actions; no personal token is committed. Capture the green workflow
and uploaded artifacts in `screenshots/github-actions.png`.

Download `delivery-evidence` into the project, retaining its contents under
`reports/evidence/`, especially `release.json`. Download `experiment` for the exact
model and measured outputs corresponding to that CI run. The manifest associates
the image digest, model/data hashes, source revision, and actual CI URL. Keep the
report's results and deployment evidence tied to the same released model.

## Docker Desktop Kubernetes

```powershell
./scripts/check_prereqs.ps1
kubectl --context docker-desktop create namespace heart-risk
```

If the namespace already exists, leave it intact. Before deploying, create a
`grafana-admin` Secret in that namespace with a `password` key. Use your local
secret-management procedure or a local password file kept outside the repository:

```powershell
kubectl --context docker-desktop -n heart-risk create secret generic grafana-admin --from-file=password=C:\private\grafana-password.txt
```

The file should contain your chosen password without a trailing newline. Never send
it to chat or commit it. Delete the temporary file after safely recording the password.
GHCR packages can be public for unauthenticated pulls; private packages require a
locally created imagePullSecret. Do not put registry credentials into manifests.

```powershell
./scripts/deploy_local.ps1 -ReleaseManifest reports/evidence/release.json
# For a private package, add: -ImagePullSecret your-existing-secret-name
kubectl --context docker-desktop -n heart-risk get deployments,pods,services
```

The script replaces the intentionally non-deployable image placeholder with the
release digest. Do not directly apply the unrendered API template. Access the
LoadBalancer at http://localhost:8080/docs. Docker Desktop image-store differences
do not matter because Kubernetes pulls the registry digest. If the LoadBalancer
does not receive ingress, diagnose Docker Desktop networking before claiming
deployment complete; a port-forward alone is not LoadBalancer proof. Save the real
cluster/service/prediction screenshot as `screenshots/kubernetes.png`.

Rollback: rerun the deployment script with the previous successful release manifest.
It changes the image without retraining. Inspect rollout and smoke results. To remove
this assignment only, explicitly delete its namespace when finished; never reset
the Docker Desktop cluster or delete other namespaces.

## Monitoring

Run these in separate terminals after deployment:

```powershell
kubectl --context docker-desktop -n heart-risk port-forward --address 127.0.0.1 service/prometheus 9090:9090
kubectl --context docker-desktop -n heart-risk port-forward --address 127.0.0.1 service/grafana 3000:3000
```

Open http://localhost:3000, log in as `admin` with your Secret's password, and open
**Heart Risk | Serving Operations**. Prometheus is at http://localhost:9090.

```powershell
.\.venv\Scripts\python.exe scripts/verify_monitoring.py --count 120
kubectl --context docker-desktop -n heart-risk logs -l app=heart-risk-api --prefix=true --tail=100
```

The two-minute traffic demonstration sends one request per second, including
controlled 422 responses, and verifies healthy per-pod scrape targets and populated
request rates. Capture Grafana as `screenshots/grafana.png`. Monitoring storage is
ephemeral with six-hour Prometheus retention. No online accuracy or drift claim is
made without ground-truth labels. For real production use add authenticated TLS
ingress, durable storage, backups, rate limits, resource/load testing, model approval,
calibration validation, and controlled access to telemetry.

## Final Report and Video

The narrative is [docs/report_content.json](docs/report_content.json); personalize
its explanations to reflect your own understanding. The builder reads real measured
results and emits a ten-page PDF with page-count and overflow checks.

1. Complete the real Docker, CI, Kubernetes, and monitoring executions above.
2. Collect every genuine capture listed in [screenshots/evidence.json](screenshots/evidence.json).
3. Fill the repository URL, author details, and actual video path or accessible URL.
4. Follow [docs/demo-script.md](docs/demo-script.md) and record the working pipeline.
5. Regenerate the final report:

```powershell
.\.venv\Scripts\python.exe scripts/build_report.py --final
```

Final mode refuses missing required evidence. A narrative, script, mocked screenshot,
or generated demonstration plan is not proof that execution occurred. Submit the
resulting final PDF, repository link, actual video, and local access instructions.
Review all ten pages visually. Consult [docs/submission-checklist.md](docs/submission-checklist.md)
for the rubric-to-deliverable mapping. Follow the institution's rules on assistance
disclosure, demonstrate independent understanding, and do not claim copied work as original.