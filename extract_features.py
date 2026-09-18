import os
import re
import warnings

import numpy as np
import pandas as pd
import librosa
import parselmouth
from parselmouth.praat import call

warnings.filterwarnings("ignore")

DATASET_PATH = r"C:\Users\lenovo\Desktop\DSP\Data\MDVR-KCL\SpontaneousDialogue"
OUTPUT_FILE = r"C:\Users\lenovo\Desktop\DSP\Data\MDVR-KCL\mdvr_kcl_features2.csv"


def parkinson_features(sound):
    """Jitter, shimmer, HNR, F0 stats via Praat (parselmouth)."""
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
    """MFCCs + deltas + basic spectral descriptors via librosa."""
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


def process_file(path, label):
    fname = os.path.basename(path)
    print("Processing:", fname)

    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        y, _ = librosa.effects.trim(y, top_db=25)

        if len(y) < int(0.5 * sr):
            print("  Skipped: too short")
            return None

        sound = parselmouth.Sound(y, sampling_frequency=sr)

        feats = {}
        feats.update(parkinson_features(sound))
        feats.update(spectral_and_mfcc_features(y, sr))

        match = re.search(r"(ID\d+)", fname, re.IGNORECASE)
        feats["subject_id"] = match.group(1).upper() if match else "UNKNOWN"
        feats["label"] = label
        feats["filename"] = fname

        return feats

    except Exception as e:
        print("  ERROR:", type(e).__name__, e)
        return None


def main():
    rows = []

    for label in ["HC", "PD"]:
        folder = os.path.join(DATASET_PATH, label)
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".wav"))
        print(f"\n{label}: {len(files)} files")

        for fname in files:
            result = process_file(os.path.join(folder, fname), label)
            if result is not None:
                rows.append(result)

    if not rows:
        print("No recordings were successfully processed.")
        return

    df = pd.DataFrame(rows)
    meta = ["subject_id", "label", "filename"]
    df = df[meta + [c for c in df.columns if c not in meta]]
    df.to_csv(OUTPUT_FILE, index=False)

    print("\nFeature extraction complete.")
    print("Total recordings:", len(df))
    print("Healthy:", int((df["label"] == "HC").sum()))
    print("Parkinson's:", int((df["label"] == "PD").sum()))
    print("Unique subjects:", df["subject_id"].nunique())
    print("Feature count:", len(df.columns) - 3)
    print("Missing values:", int(df.drop(columns=meta).isna().sum().sum()))
    print("\nSaved to:", OUTPUT_FILE)
    print(df.head())


if __name__ == "__main__":
    main()