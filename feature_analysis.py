import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

FEATURES_CSV = r"C:\Users\lenovo\Desktop\DSP\Data\MDVR-KCL\mdvr_kcl_features.csv"

# Features you keep no matter what the statistics say on this small sample,
# because they are the clinically validated PD speech biomarkers.
MUST_KEEP = ["jitter", "shimmer", "hnr", "f0_mean", "f0_std"]

CORR_THRESHOLD = 0.90
TOP_N_FINAL = 30


def main():
    df = pd.read_csv(FEATURES_CSV)
    meta = ["subject_id", "label", "filename"]
    feature_cols = [c for c in df.columns if c not in meta]

    # --- Subject-wise split FIRST, so feature selection never sees test subjects ---
    subject_ids = df["subject_id"].unique()
    train_ids, test_ids = train_test_split(subject_ids, test_size=0.2, random_state=42)
    train_df = df[df["subject_id"].isin(train_ids)].copy()

    # --- 1. Missing values ---
    missing = train_df[feature_cols].isna().sum()
    missing = missing[missing > 0]
    if len(missing):
        print("Missing values (train split):")
        print(missing.sort_values(ascending=False))
    train_df[feature_cols] = train_df[feature_cols].fillna(train_df[feature_cols].median())

    # --- 2. Correlation pruning ---
    corr = train_df[feature_cols].corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = [c for c in upper.columns if any(upper[c] > CORR_THRESHOLD) and c not in MUST_KEEP]
    reduced_cols = [c for c in feature_cols if c not in to_drop]
    print(f"\nDropped {len(to_drop)} highly correlated features (>{CORR_THRESHOLD})")
    print(f"Remaining: {len(reduced_cols)}")

    # --- 3. Group significance (Mann-Whitney U), train split only ---
    sig_rows = []
    for col in reduced_cols:
        hc = train_df.loc[train_df.label == "HC", col]
        pd_ = train_df.loc[train_df.label == "PD", col]
        try:
            _, p = mannwhitneyu(hc, pd_)
        except ValueError:
            p = 1.0
        sig_rows.append((col, p))
    sig_df = pd.DataFrame(sig_rows, columns=["feature", "p_value"]).sort_values("p_value")
    print("\nTop 15 by group separation (train split):")
    print(sig_df.head(15).to_string(index=False))

    # --- 4. Model-based importance, train split only ---
    X = train_df[reduced_cols]
    y = (train_df.label == "PD").astype(int)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    rf = RandomForestClassifier(n_estimators=400, random_state=42)
    rf.fit(X_scaled, y)
    importance = pd.Series(rf.feature_importances_, index=reduced_cols).sort_values(ascending=False)
    print("\nTop 15 by RF importance (train split):")
    print(importance.head(15).to_string())

    # --- 5. Combine: rank-average p_value rank + importance rank, force MUST_KEEP in ---
    combined = pd.DataFrame({"feature": reduced_cols})
    combined = combined.merge(sig_df, on="feature")
    combined["importance"] = combined["feature"].map(importance)
    combined["p_rank"] = combined["p_value"].rank()
    combined["imp_rank"] = combined["importance"].rank(ascending=False)
    combined["combined_rank"] = combined["p_rank"] + combined["imp_rank"]
    combined = combined.sort_values("combined_rank")

    final_features = combined["feature"].head(TOP_N_FINAL).tolist()
    for must in MUST_KEEP:
        if must in reduced_cols and must not in final_features:
            final_features.append(must)

    print(f"\nFinal shortlist ({len(final_features)} features):")
    print(final_features)

    pd.Series(final_features).to_csv("selected_features.csv", index=False, header=["feature"])
    print("\nSaved shortlist to selected_features.csv")


if __name__ == "__main__":
    main()
