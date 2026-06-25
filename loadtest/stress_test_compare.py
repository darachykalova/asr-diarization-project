"""
Runs 2 jobs without diarization, then 2 jobs with diarization.
Reports per-job ratio (audio_duration / processing_time) and overall averages.
"""

import time
import threading
import urllib.request
import json
import ssl
import os

API_BASE  = "https://localhost"
API_KEY   = "test-admin-key-123456789"
AUDIO     = os.path.join(os.path.dirname(__file__), "audio_short_15s.mp3")
AUDIO_SEC = 15.02  # known duration of the test file

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE


def _request(method, path, data=None, content_type=None, timeout=60):
    url     = API_BASE + path
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as r:
        return json.loads(r.read())


def submit(max_speakers=None):
    filename = os.path.basename(AUDIO)
    boundary = "----StressBoundary"
    with open(AUDIO, "rb") as f:
        audio_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n"
    ).encode() + audio_bytes + f"\r\n--{boundary}".encode()

    if max_speakers:
        body += (
            f"\r\nContent-Disposition: form-data; name=\"max_speakers\"\r\n\r\n{max_speakers}"
            f"\r\n--{boundary}"
        ).encode()

    body += b"--\r\n"

    result = _request("POST", "/v1/transcriptions/upload",
                      data=body,
                      content_type=f"multipart/form-data; boundary={boundary}")
    return result["job_id"]


def wait(job_id, poll=5):
    time.sleep(3)
    while True:
        try:
            r = _request("GET", f"/v1/jobs/{job_id}", timeout=30)
            if r.get("status") in ("done", "failed", "partial"):
                return r.get("status")
        except Exception:
            pass
        time.sleep(poll)


def run_job(label, job_num, max_speakers, results):
    t0 = time.time()
    try:
        job_id = submit(max_speakers)
        print(f"  [{label} #{job_num}] submitted {job_id[:8]}...")
        status = wait(job_id)
        elapsed = round(time.time() - t0, 1)
        ratio   = round(elapsed / AUDIO_SEC, 2)
        results.append({
            "label":      label,
            "num":        job_num,
            "status":     status,
            "elapsed":    elapsed,
            "ratio":      ratio,
        })
        print(f"  [{label} #{job_num}] {status} | {elapsed}s | audio {AUDIO_SEC}s -> x{ratio} slower")
    except Exception as e:
        results.append({"label": label, "num": job_num, "status": "error", "elapsed": -1, "ratio": -1})
        print(f"  [{label} #{job_num}] ERROR: {e}")


def run_batch(label, max_speakers, batch_size, results):
    threads = []
    for i in range(1, batch_size + 1):
        t = threading.Thread(target=run_job, args=(label, i, max_speakers, results))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def print_stats(title, rows):
    ok = [r for r in rows if r["elapsed"] > 0]
    if not ok:
        print(f"  {title}: no successful jobs")
        return
    avg_time  = round(sum(r["elapsed"] for r in ok) / len(ok), 1)
    avg_ratio = round(sum(r["ratio"]   for r in ok) / len(ok), 2)
    mn = min(r["elapsed"] for r in ok)
    mx = max(r["elapsed"] for r in ok)
    print(f"  {title}")
    print(f"    Jobs done:       {len(ok)}")
    print(f"    Avg proc time:   {avg_time}s")
    print(f"    Min / Max:       {mn}s / {mx}s")
    print(f"    Avg ratio:       x{avg_ratio}  (1 sec audio = {avg_ratio}s processing)")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("STRESS TEST: 2x no-diarization + 2x diarization")
    print(f"Audio file: {os.path.basename(AUDIO)}  ({AUDIO_SEC}s)")
    print("="*50)

    no_diar_results  = []
    diar_results     = []

    print("\n[ROUND 1] 2 jobs WITHOUT diarization (max_speakers=1)")
    run_batch("NO-DIAR", max_speakers=1, batch_size=2, results=no_diar_results)

    print("\n[ROUND 2] 2 jobs WITH diarization (auto speaker detection)")
    run_batch("DIAR", max_speakers=None, batch_size=2, results=diar_results)

    all_results = no_diar_results + diar_results

    print("\n" + "="*50)
    print("RESULTS")
    print("="*50)
    print_stats("Without diarization (max_speakers=1)", no_diar_results)
    print()
    print_stats("With diarization (auto)", diar_results)
    print()
    print_stats("ALL 4 JOBS COMBINED", all_results)
    print("="*50 + "\n")
