"""
Generates PLACEHOLDER pd_model.joblib / pd_scaler.joblib / pd_model_features.joblib /
pd_model_median.joblib so the API and frontend can be run and demoed end-to-end
before your real trained artifacts (from train_final_model.py) are dropped in.

This model is fit on random synthetic data. Its predictions are meaningless —
it exists ONLY to exercise the pipeline shape (same feature names, same
scaler/model/median interface) that app.py and voice_pipeline.py expect.

Delete these four .joblib files and copy in your real ones (same filenames)
to go live with the actual trained model. Nothing else needs to change.
"""

from pathlib import Path

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ARTIFACT_DIR = Path(__file__).parent

# Same MUST_KEEP biomarkers as feature_analysis.py / train_final_model.py, plus
# a handful of spectral/MFCC features, to mirror a realistic selected_features
# list of the kind train_final_model.py would produce (TOP_N=20 + must-keep).
SELECTED_FEATURES = [
    "jitter", "shimmer", "hnr", "f0_mean", "f0_std",
    "mfcc_1_mean", "mfcc_1_std", "mfcc_2_mean", "mfcc_2_std",
    "mfcc_3_mean", "mfcc_3_std", "mfcc_4_mean",
    "delta_mfcc_1_mean", "delta_mfcc_2_mean",
    "rms_mean", "zcr_mean", "centroid_mean", "bandwidth_mean", "rolloff_mean",
]

N_SYNTHETIC = 200
RNG = np.random.default_rng(42)


def main():
    X = RNG.normal(loc=0.0, scale=1.0, size=(N_SYNTHETIC, len(SELECTED_FEATURES)))
    y = RNG.integers(0, 2, size=N_SYNTHETIC)

    median = {name: float(np.median(X[:, i])) for i, name in enumerate(SELECTED_FEATURES)}

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_scaled, y)

    joblib.dump(model, ARTIFACT_DIR / "pd_model.joblib")
    joblib.dump(scaler, ARTIFACT_DIR / "pd_scaler.joblib")
    joblib.dump(SELECTED_FEATURES, ARTIFACT_DIR / "pd_model_features.joblib")
    joblib.dump(median, ARTIFACT_DIR / "pd_model_median.joblib")

    print("Placeholder artifacts written to", ARTIFACT_DIR)
    print("Features:", SELECTED_FEATURES)
    print("\nThese predictions are RANDOM and for UI/demo wiring only.")
    print("Replace the four .joblib files with your real trained artifacts when ready.")


if __name__ == "__main__":
    main()
