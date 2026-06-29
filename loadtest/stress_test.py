"""
Stress test: submits N jobs in parallel, waits for all to complete, prints timing report.

Usage:
    python loadtest/stress_test.py --jobs 5 --file audio_short_15s.mp3
    python loadtest/stress_test.py --jobs 10 --file audio_short_15s.mp3 --speakers 1
"""

import argparse
import time
import threading
import urllib.request
import urllib.parse
import json
import ssl
import os

API_BASE = "https://localhost"
API_KEY  = "test-admin-key-123456789"

# skip TLS verification for self-signed cert
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def _request(method, path, data=None, content_type=None, timeout=60):
    url = API_BASE + path
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as r:
        return json.loads(r.read())


def submit_job(audio_path, max_speakers=None):
    """Upload audio and return job_id."""
    filename = os.path.basename(audio_path)
    boundary = "----StressBoundary"
    with open(audio_path, "rb") as f:
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

    result = _request(
        "POST", "/v1/transcriptions/upload",
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    return result["job_id"]


def wait_for_job(job_id, poll_interval=5):
    """Poll until job is done/failed/partial. Returns (status, elapsed_sec)."""
    start = time.time()
    time.sleep(poll_interval * (0.5 + hash(job_id) % 10 / 20))  # jitter to spread requests
    while True:
        try:
            result = _request("GET", f"/v1/jobs/{job_id}", timeout=30)
            status = result.get("status")
            if status in ("done", "failed", "partial"):
                return status, round(time.time() - start, 1)
        except Exception:
            pass
        time.sleep(poll_interval)


def run_one(job_num, audio_path, max_speakers, results):
    """Submit + wait for one job. Stores result in shared dict."""
    try:
        t0 = time.time()
        job_id = submit_job(audio_path, max_speakers)
        submit_time = round(time.time() - t0, 2)
        print(f"  [#{job_num}] submitted {job_id[:8]}... ({submit_time}s)")

        status, wait_sec = wait_for_job(job_id)
        total = round(time.time() - t0, 1)
        results[job_num] = {"job_id": job_id, "status": status, "total_sec": total}
        icon = "OK" if status == "done" else "!!"
        print(f"  [{icon} #{job_num}] {status} in {total}s")
    except Exception as e:
        results[job_num] = {"job_id": "?", "status": "error", "total_sec": -1, "error": str(e)}
        print(f"  [!! #{job_num}] ERROR: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs",     type=int, default=5,    help="Number of parallel jobs")
    parser.add_argument("--file",     type=str, default="audio_short_15s.mp3", help="Audio file name")
    parser.add_argument("--speakers", type=int, default=None, help="max_speakers param (1 = skip diarization)")
    args = parser.parse_args()

    audio_path = args.file if os.path.isabs(args.file) else os.path.join(os.getcwd(), args.file)
    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        return

    print("\n=== STRESS TEST ===")
    print(f"File:      {os.path.basename(audio_path)}")
    print(f"Jobs:      {args.jobs} (parallel)")
    print(f"max_speakers: {args.speakers or 'auto'}")
    print("Workers:   2 (concurrency=2)\n")

    results = {}
    threads = []
    wall_start = time.time()

    for i in range(1, args.jobs + 1):
        t = threading.Thread(target=run_one, args=(i, audio_path, args.speakers, results))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    wall_total = round(time.time() - wall_start, 1)

    done   = [r for r in results.values() if r["status"] == "done"]
    failed = [r for r in results.values() if r["status"] != "done"]

    times = sorted([r["total_sec"] for r in done])
    avg   = round(sum(times) / len(times), 1) if times else 0
    mn    = times[0]  if times else 0
    mx    = times[-1] if times else 0

    print("\n" + "="*40)
    print("RESULT")
    print("="*40)
    print(f"Total jobs:    {args.jobs}")
    print(f"Done (done):   {len(done)}")
    print(f"Errors:        {len(failed)}")
    print(f"Wall time:     {wall_total}s  (first submit -> last done)")
    print(f"Min job time:  {mn}s")
    print(f"Max job time:  {mx}s")
    print(f"Avg job time:  {avg}s")
    print("="*40 + "\n")


if __name__ == "__main__":
    main()
