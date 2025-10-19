import json, os, tempfile, time
import azure.functions as func
import requests
import numpy as np
import librosa

def analyze_audio(file_path, frame_length=1024, hop_length=256,
                  min_silence_len=2.0, threshold_factor=0.4):
    # y, sr 読み込み（sr=None で原本のサンプルレートを維持）
    y, sr = librosa.load(file_path, sr=None, mono=True)

    # RMS
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    # 閾値（平均*0.4 → “平均の60%未満を静か”）
    threshold = float(np.mean(rms) * threshold_factor)

    # 無音判定
    silence = rms < threshold

    # 連続無音を min_silence_len 秒以上で除外
    frame_time = hop_length / sr
    min_silence_frames = int(min_silence_len / frame_time)

    active_frames = np.ones_like(silence, dtype=bool)
    count = 0
    for i, s in enumerate(silence):
        if s:
            count += 1
        else:
            if count >= min_silence_frames:
                active_frames[i - count : i] = False
            count = 0
    # 末尾が無音で終わる場合の処理
    if count >= min_silence_frames:
        active_frames[len(silence) - count : len(silence)] = False

    speech_duration = float(np.sum(active_frames) * frame_time)
    total_duration = float(len(y) / sr)

    return {
        "total_sec": round(total_duration, 3),
        "speech_sec": round(speech_duration, 3),
        "silence_removed_sec": round(total_duration - speech_duration, 3),
        "sr": int(sr),
        "frame_length": int(frame_length),
        "hop_length": int(hop_length),
        "threshold_factor": float(threshold_factor),
        "min_silence_sec": float(min_silence_len)
    }

def download_to_tmp(url: str) -> str:
    # SAS/共有リンクを想定。Power Automate から渡す。
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    suffix = os.path.splitext(url.split('?')[0])[1] or ".bin"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    return tmp

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        # 受け取る想定のJSON
        # {
        #   "file_url": "https://...SAS...",
        #   "file_name": "abc.m4a",
        #   "frame_length": 1024, "hop_length": 256,
        #   "min_silence_len": 2.0, "threshold_factor": 0.4
        # }

        file_url = data["file_url"]
        file_name = data.get("file_name", "unknown")

        params = {
            "frame_length": int(data.get("frame_length", 1024)),
            "hop_length": int(data.get("hop_length", 256)),
            "min_silence_len": float(data.get("min_silence_len", 2.0)),
            "threshold_factor": float(data.get("threshold_factor", 0.4)),
        }

        path = download_to_tmp(file_url)
        try:
            metrics = analyze_audio(path, **params)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        # Power Automate が Excel に書けるよう、メタも返す
        result = {
            "file_name": file_name,
            "file_url": file_url,
            "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **metrics
        }
        return func.HttpResponse(json.dumps(result), status_code=200,
                                 mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500, mimetype="application/json"
        )
