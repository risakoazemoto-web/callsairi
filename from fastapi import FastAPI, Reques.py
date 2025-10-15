from fastapi import FastAPI, Request
from pydub import AudioSegment, silence
from io import BytesIO
import requests

app = FastAPI()

@app.post("/analyze")
async def analyze_audio(request: Request):
    data = await request.json()
    file_url = data.get("file_url")
    if not file_url:
        return {"error": "Missing file_url"}
    audio_data = requests.get(file_url).content
    sound = AudioSegment.from_file(BytesIO(audio_data))
    nonsilent = silence.detect_nonsilent(sound, min_silence_len=500, silence_thresh=-50)
    speaking_time = sum([(e - s) for s, e in nonsilent]) / 1000
    total_time = len(sound) / 1000
    return {"speaking_time": speaking_time, "total_time": total_time}
