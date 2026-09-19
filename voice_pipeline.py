"""
Voice feature extraction + Parkinson's screening pipeline.

This is a direct refactor of the prediction logic from the original app.py.
The feature extraction, quality gate, imputation, scaling and model call are
UNCHANGED from the original — only the return type changed, from a single
markdown string to a structured dict, so a frontend can render real numbers
instead of parsing text.

Do not alter the numeric logic in this file without re-validating against
evaluate_external.py / train_final_model.py, since the trained artifacts
were fit against this exact feature computation.
"""

import warnings
from pathlib import Path

import numpy as np
import joblib
import librosa
import parselmouth
from parselmouth.praat import call

warnings.filterwarnings("ignore")

ARTIFACT_DIR = Path(__file__).parent

MODEL_PATH = ARTIFACT_DIR / "pd_model.joblib"
SCALER_PATH = ARTIFACT_DIR / "pd_scaler.joblib"
FEATURES_PATH = ARTIFACT_DIR / "pd_model_features.joblib"
MEDIAN_PATH = ARTIFACT_DIR / "pd_model_median.joblib"

# ---- Audio quality gate (identical thresholds to original app.py) ----
MIN_DURATION_SEC = 1.0
MIN_RAW_PEAK_AMPLITUDE = 0.01

# Acoustic biomarkers we surface to the UI. These are always computed by
# parkinson_features() regardless of which subset the model actually uses
# (selected_features may be a further-reduced list chosen at training time).
DISPLAY_FEATURES = ["f0_mean", "f0_std", "jitter", "shimmer", "hnr"]

DISPLAY_LABELS = {
    "f0_mean": "Fundamental frequency (mean)",
    "f0_std": "Fundamental frequency (variability)",
    "jitter": "Jitter",
    "shimmer": "Shimmer",
    "hnr": "Harmonics-to-noise ratio",
}

DISPLAY_UNITS = {
    "f0_mean": "Hz",
    "f0_std": "Hz",
    "jitter": "",
    "shimmer": "",
    "hnr": "dB",
}


class ModelNotLoadedError(RuntimeError):
    pass


class _Pipeline:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.selected_features = None
        self.train_median = None
        self.loaded = False
        self.load_error = None

    def load(self):
        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.selected_features = joblib.load(FEATURES_PATH)
            self.train_median = joblib.load(MEDIAN_PATH)
            self.loaded = True
            self.load_error = None
        except Exception as e:  # noqa: BLE001
            self.loaded = False
            self.load_error = f"{type(e).__name__}: {e}"


pipeline = _Pipeline()
pipeline.load()


def parkinson_features(sound):
    """Jitter, shimmer, HNR, F0 stats via Praat (parselmouth). Unchanged from app.py."""
    f = {}
    try:
        pitch = call(sound, "To Pitch", 0.0, 75, 600)
        f0 = pitch.selected_array["frequency"]
        f0 = f0[f0 > 0]
        if len(f0):
            f["f0_mean"], f["f0_std"] = float(np.mean(f0)), float(np.std(f0))
        else:
            f["f0_mean"] = f["f0_std"] = np.nan
    except Exception:
        f["f0_mean"] = f["f0_std"] = np.nan

    try:
        pp = call(sound, "To PointProcess (periodic, cc)", 75, 600)
        f["jitter"] = float(call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3))
        f["shimmer"] = float(call([sound, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6))
        harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        f["hnr"] = float(call(harmonicity, "Get mean", 0, 0))
    except Exception:
        f["jitter"] = f["shimmer"] = f["hnr"] = np.nan

    return f


def spectral_and_mfcc_features(y, sr):
    """MFCCs + deltas + basic spectral descriptors via librosa. Unchanged from app.py."""
    f = {}
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    delta = librosa.feature.delta(mfcc)

    for i in range(13):
        f[f"mfcc_{i+1}_mean"] = float(np.mean(mfcc[i]))
        f[f"mfcc_{i+1}_std"] = float(np.std(mfcc[i]))
        f[f"delta_mfcc_{i+1}_mean"] = float(np.mean(delta[i]))
        f[f"delta_mfcc_{i+1}_std"] = float(np.std(delta[i]))

    f["rms_mean"] = float(np.mean(librosa.feature.rms(y=y)))
    f["zcr_mean"] = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    f["centroid_mean"] = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    f["bandwidth_mean"] = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    f["rolloff_mean"] = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))

    return f


def check_quality(y, sr):
    """Identical logic/thresholds to original app.py."""
    if len(y) == 0:
        return "The uploaded file appears to be empty."

    raw_peak = float(np.max(np.abs(y)))
    if raw_peak < MIN_RAW_PEAK_AMPLITUDE:
        return "This recording is too quiet or silent to analyze reliably. Please provide a clearer recording."

    y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    duration = len(y_trimmed) / sr
    if duration < MIN_DURATION_SEC:
        return (
            f"Only {duration:.2f}s of clear speech detected after trimming silence "
            f"(minimum {MIN_DURATION_SEC}s needed). Please provide a longer sample of "
            f"sustained, clearly audible speech."
        )

    return None


def run_screening(audio_path: str) -> dict:
    """
    Runs the full pipeline on a saved audio file and returns a structured result.

    Return shape (status is always one of "ok" | "rejected" | "error"):
      {
        "status": "ok",
        "audio": {"duration_sec": float},
        "result": {"label": "parkinsonian"|"typical", "label_display": str, "probability": float},
        "features": {name: {"value": float, "label": str, "unit": str}, ...}
      }
      {"status": "rejected", "message": str}
      {"status": "error", "message": str}
    """
    if not pipeline.loaded:
        return {
            "status": "error",
            "message": (
                "Model artifacts are not loaded on the server "
                f"({pipeline.load_error}). Place pd_model.joblib, pd_scaler.joblib, "
                "pd_model_features.joblib and pd_model_median.joblib in the backend "
                "directory and restart the server."
            ),
        }

    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Could not read this audio file ({type(e).__name__}). Please try a different file (.wav preferred).",
        }

    quality_issue = check_quality(y, sr)
    if quality_issue:
        return {"status": "rejected", "message": quality_issue}

    raw_duration_sec = len(y) / sr

    y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    y_trimmed = y_trimmed - np.mean(y_trimmed)
    peak = np.max(np.abs(y_trimmed))
    if peak > 0:
        y_trimmed = y_trimmed / peak

    sound = parselmouth.Sound(y_trimmed, sampling_frequency=sr)

    feats = {}
    feats.update(parkinson_features(sound))
    feats.update(spectral_and_mfcc_features(y_trimmed, sr))

    missing = [f for f in pipeline.selected_features if f not in feats]
    if missing:
        return {
            "status": "error",
            "message": f"Internal error: extractor did not produce required features: {missing}",
        }

    row = np.array([[feats[f] for f in pipeline.selected_features]], dtype=np.float64)
    for i, fname in enumerate(pipeline.selected_features):
        if np.isnan(row[0, i]):
            row[0, i] = pipeline.train_median[fname]

    row_scaled = pipeline.scaler.transform(row)
    prob_pd = float(pipeline.model.predict_proba(row_scaled)[0, 1])
    label = "parkinsonian" if prob_pd >= 0.5 else "typical"
    label_display = (
        "Parkinsonian voice pattern" if label == "parkinsonian" else "Typical/healthy voice pattern"
    )

    display_features = {}
    for name in DISPLAY_FEATURES:
        if name in feats and not np.isnan(feats[name]):
            display_features[name] = {
                "value": round(feats[name], 4),
                "label": DISPLAY_LABELS[name],
                "unit": DISPLAY_UNITS[name],
            }

    return {
        "status": "ok",
        "audio": {"duration_sec": round(raw_duration_sec, 2)},
        "result": {
            "label": label,
            "label_display": label_display,
            "probability": round(prob_pd, 4),
        },
        "features": display_features,
    }
