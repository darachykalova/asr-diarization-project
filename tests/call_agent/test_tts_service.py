import os
import wave
import numpy as np
import call_agent.config as cfg
from call_agent.tts_service import TTSService


class FakeModel:
    def __init__(self):
        self.calls = 0
    def apply_tts(self, text, speaker, sample_rate):
        self.calls += 1
        # 0.5s of silence at the requested rate, float32 in [-1, 1]
        return np.zeros(int(sample_rate * 0.5), dtype=np.float32)


def _service(tmp_path, model):
    s = cfg.Settings()
    s.tts_cache_dir = str(tmp_path)
    return TTSService(s, model=model)


def test_synthesize_writes_16k_mono_int16_wav(tmp_path):
    svc = _service(tmp_path, FakeModel())
    path = svc.synthesize("привет")
    assert os.path.exists(path)
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2


def test_cache_hit_skips_model(tmp_path):
    model = FakeModel()
    svc = _service(tmp_path, model)
    svc.synthesize("одна фраза")
    svc.synthesize("одна фраза")
    assert model.calls == 1
