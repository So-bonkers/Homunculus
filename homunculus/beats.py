"""The beat grid of a clip from its own sound (no librosa): onset strength from the spectrogram, then the tempo and first beat that put the most onset energy on the beats, and which of four beats opens a bar.

grid(video)            -> {"bpm", "period", "first_beat", "bar_start", "bar_seconds"}   times in seconds from the start of the video
bar_boundaries(g, n)   -> the times a bar starts, from the first one at or after 0, up to n seconds
The tempo is searched between 85 and 170 BPM (a dance is rarely outside it; the autocorrelation of the onset strength also peaks at 2/3 and 2x of the true tempo). Measured on one clip (Kinjaz, 19 s, Post Malone "Wow"): 100.05 BPM, as the song is.
Which of the four beats is the downbeat is a guess (the beat with the most onset energy)."""
import os, subprocess, tempfile
import numpy as np


def _onsets(video):
    from scipy.io import wavfile
    from scipy.signal import stft
    tmp = tempfile.mkdtemp(prefix="beats_"); wav = os.path.join(tmp, "a.wav")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "22050", wav], check=True)
        sr, x = wavfile.read(wav)
    finally:
        try: os.remove(wav); os.rmdir(tmp)
        except OSError: pass
    x = x.astype(np.float32); x /= np.abs(x).max() + 1e-9; hop = 512
    f, t, Z = stft(x, sr, nperseg=2048, noverlap=2048 - hop); M = np.log1p(30 * np.abs(Z)); band = (f > 30) & (f < 8000)
    d = np.maximum(0, np.diff(M[band], axis=1)).sum(0); d = np.concatenate([[0], d]); d = np.maximum(d - np.convolve(d, np.ones(21) / 21, mode="same"), 0)
    return t, d


def grid(video, bpm=None, lo=85, hi=170):
    """Tempo (searched in [lo, hi], or the one given) and the first beat; None if the video has no usable sound."""
    try: t, d = _onsets(video)
    except Exception: return None
    if len(d) < 50 or d.max() <= 0: return None
    def score(B):
        P = 60 / B; best = (-1, 0)
        for off in np.arange(0, P, 0.01):
            v = np.interp(np.arange(off, t[-1], P), t, d).mean()
            if v > best[0]: best = (v, off)
        return best
    if bpm is None:
        coarse = max(((score(B)[0], B) for B in np.arange(lo, hi, 0.5)))[1]; cands = np.arange(max(lo, coarse - 1), min(hi, coarse + 1) + 0.01, 0.05)
    else: cands = [float(bpm)]
    v, B = max(((score(B)[0], B) for B in cands)); P = 60 / B; off = score(B)[1]
    beats = np.arange(off, t[-1], P); strength = np.interp(beats, t, d)
    k = int(np.argmax([strength[i::4].mean() if len(strength[i::4]) else 0 for i in range(4)]))        # the beat of the four that opens a bar
    return {"bpm": round(float(B), 2), "period": P, "first_beat": float(off), "bar_start": float(off + k * P), "bar_seconds": 4 * P}


def bar_boundaries(g, seconds):
    """Times (from the first at or after 0) at which a bar starts, up to `seconds`."""
    b0 = g["bar_start"] % g["bar_seconds"]; out = []; t = b0
    while t < seconds - 0.2: out.append(round(t, 3)); t += g["bar_seconds"]
    return out
