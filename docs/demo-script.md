# Record the Actual Pipeline (4-6 Minutes)

Use OBS Studio, Windows screen recording, or an approved equivalent. Record only
assignment windows; hide unrelated corporate content, account details, and secrets.
Use your own narration and explain decisions, not just commands. A script is not the video.

| Time | Show | Explain |
| --- | --- | --- |
| 0:00-0:40 | Repository, data manifest, source citation | 13 predictors, binary target, checksum, no global imputation |
| 0:40-1:20 | EDA and fixed split | Class balance, missingness, training-only decisions |
| 1:20-2:05 | MLflow candidates and selected run | Two models, same folds, CV selection, holdout metrics and limitations |
| 2:05-2:50 | Actual green GitHub Actions and artifacts | Lint/tests gate training; model included in tested image; digest identity |
| 2:50-3:35 | Docker build/run proof and Kubernetes resources | No host model mount, two ready replicas, localhost LoadBalancer |
| 3:35-4:15 | Swagger prediction and invalid category | Confidence semantics, 422 validation, request/model IDs |
| 4:15-5:10 | Grafana during traffic; safe JSON logs | Per-pod scrape targets, latency/errors, patient features not logged |
| 5:10-5:40 | Ten-page final PDF and evidence checklist | Reproduction instructions, local URL, outstanding limitations |

Record completed runs with timestamps; lengthy installs/training can be shown via
their real logs and artifacts. Do not create fake workflow successes or deployment
screens. Save an MP4 according to the course's size limit, or upload privately to an
approved service and test the assessor's access. Enter the real file/URL in the
evidence manifest and regenerate the final PDF.