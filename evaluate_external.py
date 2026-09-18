import pandas as pd
import joblib
from sklearn.metrics import (
    balanced_accuracy_score, roc_auc_score, f1_score,
    confusion_matrix, recall_score,
)

# CSV produced by running the SAME feature-extraction script on the new dataset.
# Must contain the same feature columns plus 'label' ("HC"/"PD") and 'subject_id'.
EXTERNAL_FEATURES_CSV = r"C:\Users\lenovo\Desktop\DSP\Data\MDVR-KCL\mdvr_kcl_features2.csv"

MODEL_IN = "pd_model.joblib"
SCALER_IN = "pd_scaler.joblib"
FEATURES_IN = "pd_model_features.joblib"
MEDIAN_IN = "pd_model_median.joblib"


def main():
    model = joblib.load(MODEL_IN)
    scaler = joblib.load(SCALER_IN)
    selected = joblib.load(FEATURES_IN)
    median = joblib.load(MEDIAN_IN)

    df = pd.read_csv(EXTERNAL_FEATURES_CSV)

    missing_cols = [c for c in selected if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"External dataset is missing {len(missing_cols)} required features: {missing_cols}\n"
            "This means the extraction script used on the new dataset produced different "
            "columns than the training run — check they ran the identical extractor."
        )

    X = df[selected].fillna(median)  # impute with TRAINING medians, not the new data's own
    y = (df["label"] == "PD").astype(int)

    X_s = scaler.transform(X)  # transform only — never fit on external data
    probs = model.predict_proba(X_s)[:, 1]
    preds = (probs >= 0.5).astype(int)  # same fixed threshold decided during training

    print(f"External subjects: {df['subject_id'].nunique()} | Recordings: {len(df)}")
    print("\n=== External validation (frozen model, no refitting) ===")
    print("Balanced accuracy:", round(balanced_accuracy_score(y, preds), 4))
    print("ROC-AUC:", round(roc_auc_score(y, probs), 4))
    print("Sensitivity (PD recall):", round(recall_score(y, preds, pos_label=1), 4))
    print("Specificity (HC recall):", round(recall_score(y, preds, pos_label=0), 4))
    print("F1:", round(f1_score(y, preds), 4))
    print("Confusion matrix:\n", confusion_matrix(y, preds))


if __name__ == "__main__":
    main()
