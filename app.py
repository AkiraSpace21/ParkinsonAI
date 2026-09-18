import warnings

import numpy as np
import joblib
import librosa
import parselmouth
from parselmouth.praat import call
import gradio as gr

warnings.filterwarnings("ignore")

# ---- EDIT THESE to point at your saved artifacts from train_final_model.py ----
MODEL_PATH = "pd_model.joblib"
SCALER_PATH = "pd_scaler.joblib"
FEATURES_PATH = "pd_model_features.joblib"
MEDIAN_PATH = "pd_model_median.joblib"

# ---- Audio quality gate ----
MIN_DURATION_SEC = 1.0
MIN_RAW_PEAK_AMPLITUDE = 0.01  # below this, the clip is effectively silence/near-silent

model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
selected_features = joblib.load(FEATURES_PATH)
train_median = joblib.load(MEDIAN_PATH)


def parkinson_features(sound):
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
    if len(y) == 0:
        return "The uploaded file appears to be empty."

    raw_peak = float(np.max(np.abs(y)))
    if raw_peak < MIN_RAW_PEAK_AMPLITUDE:
        return "This recording is too quiet or silent to analyze reliably. Please upload a clearer recording."

    y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    duration = len(y_trimmed) / sr
    if duration < MIN_DURATION_SEC:
        return (
            f"Only {duration:.2f}s of clear speech detected after trimming silence "
            f"(minimum {MIN_DURATION_SEC}s needed). Please upload a longer sample of "
            f"sustained, clearly audible speech."
        )

    return None  # passed


def predict(audio_path):
    if audio_path is None:
        return "Please upload an audio file first."

    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except Exception as e:
        return f"Could not read this audio file ({type(e).__name__}). Please try a different file (.wav preferred)."

    quality_issue = check_quality(y, sr)
    if quality_issue:
        return f"**Recording quality check failed:**\n\n{quality_issue}"

    y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    y_trimmed = y_trimmed - np.mean(y_trimmed)
    peak = np.max(np.abs(y_trimmed))
    if peak > 0:
        y_trimmed = y_trimmed / peak

    sound = parselmouth.Sound(y_trimmed, sampling_frequency=sr)

    feats = {}
    feats.update(parkinson_features(sound))
    feats.update(spectral_and_mfcc_features(y_trimmed, sr))

    missing = [f for f in selected_features if f not in feats]
    if missing:
        return f"Internal error: extractor did not produce required features: {missing}"

    row = np.array([[feats[f] for f in selected_features]], dtype=np.float64)
    for i, f in enumerate(selected_features):
        if np.isnan(row[0, i]):
            row[0, i] = train_median[f]

    row_scaled = scaler.transform(row)
    prob_pd = float(model.predict_proba(row_scaled)[0, 1])
    label = "Parkinsonian voice pattern" if prob_pd >= 0.5 else "Typical/healthy voice pattern"

    return (
        f"### Result: {label}\n\n"
        f"**Estimated probability of Parkinsonian voice pattern: {prob_pd*100:.1f}%**\n\n"
        f"---\n"
        f"*This is a research/screening tool trained on a small dataset (37 subjects). "
        f"It is not a medical diagnosis. If you have concerns about Parkinson's disease "
        f"symptoms, please consult a qualified healthcare professional.*"
    )


demo = gr.Interface(
    fn=predict,
    inputs=gr.Audio(type="filepath", sources=["upload"], label="Upload a voice recording (.wav preferred)"),
    outputs=gr.Markdown(label="Result"),
    title="Parkinson's Voice Screening (Research Prototype)",
    description=(
        "Upload a recording of sustained speech (reading a short passage aloud works best). "
        "The system extracts acoustic/DSP features (jitter, shimmer, HNR, MFCCs, spectral "
        "descriptors) and runs them through a model trained on the MDVR-KCL dataset. "
        "**Not a diagnostic tool** — for research and demonstration purposes only."
    ),
    allow_flagging="never",
)

if __name__ == "__main__":
    demo.launch()
