import numpy as np
import pandas as pd
import joblib
from scipy.stats import mannwhitneyu
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

FEATURES_CSV = r"C:\Users\lenovo\Desktop\DSP\Data\MDVR-KCL\mdvr_kcl_features.csv"

MODEL_OUT = "pd_model.joblib"
SCALER_OUT = "pd_scaler.joblib"
FEATURES_OUT = "pd_model_features.joblib"
MEDIAN_OUT = "pd_model_median.joblib"

MUST_KEEP = ["jitter", "shimmer", "hnr", "f0_mean", "f0_std"]
CORR_THRESHOLD = 0.90
TOP_N = 20


def select_features(df, feature_cols):
    """Same logic as the nested pipeline, but run once on the full dataset.
    This is safe here ONLY because this model is the final deployment artifact,
    not something being evaluated for accuracy afterward — your reported
    accuracy comes from nested_loso_pipeline.py, not from this script."""
    X = df[feature_cols].copy()
    median = X.median()
    X = X.fillna(median)

    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = [c for c in upper.columns if any(upper[c] > CORR_THRESHOLD) and c not in MUST_KEEP]
    reduced = [c for c in feature_cols if c not in to_drop]

    sig_rows = []
    for col in reduced:
        hc = df.loc[df.label == "HC", col].fillna(median[col])
        pdv = df.loc[df.label == "PD", col].fillna(median[col])
        try:
            _, p = mannwhitneyu(hc, pdv)
        except ValueError:
            p = 1.0
        sig_rows.append((col, p))
    sig_df = pd.DataFrame(sig_rows, columns=["feature", "p_value"])

    y = (df.label == "PD").astype(int)
    scaler_tmp = StandardScaler()
    Xr_s = scaler_tmp.fit_transform(X[reduced])
    rf_tmp = RandomForestClassifier(n_estimators=300, random_state=42)
    rf_tmp.fit(Xr_s, y)
    importance = pd.Series(rf_tmp.feature_importances_, index=reduced)

    combined = sig_df.copy()
    combined["importance"] = combined["feature"].map(importance)
    combined["p_rank"] = combined["p_value"].rank()
    combined["imp_rank"] = combined["importance"].rank(ascending=False)
    combined["combined_rank"] = combined["p_rank"] + combined["imp_rank"]
    combined = combined.sort_values("combined_rank")

    final = combined["feature"].head(TOP_N).tolist()
    for must in MUST_KEEP:
        if must in reduced and must not in final:
            final.append(must)

    return final, median


def main():
    df = pd.read_csv(FEATURES_CSV)
    meta = ["subject_id", "label", "filename"]
    feature_cols = [c for c in df.columns if c not in meta]

    selected, median = select_features(df, feature_cols)
    print(f"Final feature set ({len(selected)} features):")
    print(selected)

    X = df[selected].fillna(median[selected])
    y = (df["label"] == "PD").astype(int)

    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    n_pos = int(y.sum())
    n_neg = int((y == 0).sum())
    spw = n_neg / max(n_pos, 1)

    model = XGBClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=1.0, reg_lambda=1.0,
        eval_metric="logloss", random_state=42,
        scale_pos_weight=spw,
    )
    model.fit(X_s, y)

    joblib.dump(model, MODEL_OUT)
    joblib.dump(scaler, SCALER_OUT)
    joblib.dump(selected, FEATURES_OUT)
    joblib.dump(median[selected], MEDIAN_OUT)  # needed at inference time to impute missing features the same way

    print("\nSaved:")
    print(" ", MODEL_OUT)
    print(" ", SCALER_OUT)
    print(" ", FEATURES_OUT)
    print(" ", MEDIAN_OUT)
    print("\nDecision threshold: 0.5 (default). Nested LOSO showed threshold tuning does not")
    print("improve on this given the sample size — see xgb vs xgb-tuned comparison.")
    print("\nReported accuracy for this model = the nested LOSO XGBoost numbers, NOT a re-evaluation of this file.")


if __name__ == "__main__":
    main()
