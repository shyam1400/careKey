# CareKey local model inventory

Inventory updated 2026-11-10. `ML-models/` contains six local artifacts and no training scripts, inference scripts, readmes, configuration files, dataset files, or standalone metrics reports. The input/output contracts below are supplied and verified by the project owner for this integration; they are treated as authoritative.

| Model | Artifacts / architecture | Dataset and evaluation | Output and limits |
|---|---|---|---|
| Diabetes | `diabetes_model.keras`, `diabetes_scaler.pkl`; Keras Sequential, 21 inputs, Dense 64/ReLU, Dropout 0.3, Dense 32/ReLU, Dropout 0.2, Dense 1/sigmoid; `StandardScaler`; input order is the exact scaler feature order below. | CDC Diabetes Health Indicators (BRFSS), 253,680 rows. Test ROC-AUC 0.8237; positive recall 0.79. | Single sigmoid score, 0–1. Integration labels `>=0.5` High Risk and `<0.5` Low Risk as requested. Research/educational output, not a diagnosis or calibrated clinical prediction. |
| Heart disease | `heart_model.keras`, `heart_scaler.pkl`; Keras Sequential, 21 inputs, Dense 64/ReLU, Dropout 0.3, Dense 32/ReLU, Dropout 0.2, Dense 1/sigmoid; `StandardScaler`; exact scaler feature order below. | CDC Heart Disease / BRFSS Indicators, 253,680 rows; target `HeartDiseaseorAttack`. Test ROC-AUC approximately 0.83. | Single sigmoid score, 0–1. Integration labels `>=0.5` High Risk and `<0.5` Low Risk as requested. Research/educational output, not a diagnosis or calibrated clinical prediction. |
| Lung cancer | `cancer_model.keras`, `cancer_scaler.pkl`; Keras Sequential, 15 inputs, Dense 32/ReLU, Dropout 0.2, Dense 16/ReLU, Dense 1/sigmoid; `StandardScaler`; exact scaler feature order below. | Lung Cancer Survey Dataset; target `LUNG_CANCER` (`1`=Yes, `0`=No). No metric was supplied. | Single sigmoid score, 0–1. Integration labels `>=0.5` High Risk and `<0.5` Low Risk as requested. This is an experimental survey classifier, not a diagnostic test or a substitute for clinical assessment. |

## Exact input contracts

All three services create a one-row pandas DataFrame with the exact listed order before applying `StandardScaler.transform`; the transformed row is passed to the matching Keras model's `predict` method. The defaults also populate the patient form's “Not sure” action, and are explicitly recorded in each assessment snapshot as defaulted values.

### Diabetes (21 fields)

Default values in exact order: `HighBP=0`, `HighChol=0`, `CholCheck=1`, `BMI=27.0`, `Smoker=0`, `Stroke=0`, `HeartDiseaseorAttack=0`, `PhysActivity=1`, `Fruits=1`, `Veggies=1`, `HvyAlcoholConsump=0`, `AnyHealthcare=1`, `NoDocbcCost=0`, `GenHlth=2`, `MentHlth=0`, `PhysHlth=0`, `DiffWalk=0`, `Sex=0`, `Age=8`, `Education=5`, `Income=7`.

Encodings: binary flags (`0`=No, `1`=Yes); `Sex` (`0`=Female, `1`=Male); `GenHlth` (`1`=Excellent through `5`=Poor); `Age` (`1`=18–24 through `13`=80+); `Education` (`1`–`6`); `Income` (`1`–`8`).

### Heart disease (21 fields)

Default values in exact order: `HighBP=0`, `HighChol=0`, `CholCheck=1`, `BMI=27.0`, `Smoker=0`, `Stroke=0`, `PhysActivity=1`, `Fruits=1`, `Veggies=1`, `HvyAlcoholConsump=0`, `AnyHealthcare=1`, `NoDocbcCost=0`, `GenHlth=2`, `MentHlth=0`, `PhysHlth=0`, `DiffWalk=0`, `Sex=0`, `Age=8`, `Education=5`, `Income=7`, `Diabetes_binary=0`.

Encodings are identical to Diabetes, with `Diabetes_binary` (`0`=No, `1`=Yes).

### Lung cancer (15 fields)

Default values in exact order: `GENDER=0`, `AGE=50`, `SMOKING=0`, `YELLOW_FINGERS=0`, `ANXIETY=0`, `PEER_PRESSURE=0`, `CHRONIC DISEASE=0`, `FATIGUE=0`, `ALLERGY=0`, `WHEEZING=0`, `ALCOHOL CONSUMING=0`, `COUGHING=0`, `SHORTNESS OF BREATH=0`, `SWALLOWING DIFFICULTY=0`, `CHEST PAIN=0`.

Encodings: `GENDER` (`0`=Female, `1`=Male); `AGE` is years; all remaining fields (`0`=No, `1`=Yes).

The service version is derived from the SHA-256 digests of each model/scaler pair. Historical assessments retain the version used at execution. Model files stay local and are excluded from Git.

## Backend runtime used for verification

The active backend environment is `backend/.venv` on Python 3.13. Inference was smoke-tested with TensorFlow 2.21.0 (CPU on native Windows), scikit-learn 1.6.1, joblib 1.6.0, pandas 3.1.1, and NumPy 2.5.4. scikit-learn is pinned to the scaler pickle's recorded training version. The same dependencies are listed in `backend/requirements.txt`.
