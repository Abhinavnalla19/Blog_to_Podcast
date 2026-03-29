from pathlib import Path
import wave, sys
p=Path("logs/audio-debug.wav")
print("exists", p.exists())
print("size", p.stat().st_size if p.exists() else None)
with p.open('rb') as f:
    h=f.read(64)
print("header:", h[:32])
try:
    with wave.open(str(p),'rb') as w:
        print("wave OK", w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype(), w.getcompname())
except Exception as e:
    print("wave error:", e)
