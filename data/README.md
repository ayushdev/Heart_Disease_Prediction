# Dataset Contract and Attribution

Source: [UCI Heart Disease](https://archive.ics.uci.edu/dataset/45/heart+disease),
`processed.cleveland.data` from the official archive. Citation: Janosi, A., Steinbrunn,
W., Pfisterer, M., and Detrano, R. (1989), Heart Disease [Dataset],
[DOI 10.24432/C52P4X](https://doi.org/10.24432/C52P4X).
License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Changes: assign documented column names, convert question marks to nulls, validate
types/categories, map original num severity 0 to target=0 and 1-4 to target=1,
deduplicate exact rows (zero removed in the official snapshot). Data is not globally
imputed. Original bytes and SHA-256 are included; the split manifest binds indices
to the cleaned CSV digest. Full source: 303 records, 164 absent/139 present.

| Field | Meaning and accepted original coding |
| --- | --- |
| age | Age in years, positive |
| sex | Source sex coding: 0=female, 1=male |
| cp | 1=typical angina, 2=atypical angina, 3=non-anginal pain, 4=asymptomatic |
| trestbps | Resting blood pressure in mm Hg, positive |
| chol | Serum cholesterol in mg/dl, positive |
| fbs | Fasting blood sugar >120 mg/dl: 0=false, 1=true |
| restecg | 0=normal, 1=ST-T abnormality, 2=probable/definite LV hypertrophy |
| thalach | Maximum heart rate achieved in bpm, positive |
| exang | Exercise-induced angina: 0=no, 1=yes |
| oldpeak | Exercise-induced ST depression, nonnegative |
| slope | 1=upsloping, 2=flat, 3=downsloping |
| ca | Number of major vessels: 0-3; nullable |
| thal | 3=normal, 6=fixed defect, 7=reversible defect; nullable |
| target | Binary training label, never supplied to the API as a feature |

The official subset has 13 predictors plus its label, despite the assignment's
"14+ features" wording. Encoded feature count increases after one-hot encoding.
These basic input constraints enforce the source representation, not clinical
plausibility or medical eligibility. No data source is substituted silently.