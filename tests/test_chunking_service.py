"""
Unit tests for audio chunking helpers (services/chunking_service.py).

Covers the pure-logic parts — VAD cut selection and temp-file cleanup.
The heavy split_audio path (soundfile / pyannote) is exercised separately;
here we test the deterministic logic that has no ML or audio I/O deps.
"""
from services.chunking_service import (
    SILENCE_WINDOW_SEC,
    _find_cut_vad,
    delete_chunk_files,
)


# --------------------------------------------------------------------------
# _find_cut_vad — pick centre of nearest silence region within ±window
# --------------------------------------------------------------------------

def test_returns_centre_of_silence_region_at_target():
    # silence 295–305 s, target 300 s -> centre 300 s
    assert _find_cut_vad(300.0, [(295.0, 305.0)]) == 300.0


def test_returns_none_when_no_region_in_window():
    # nearest centre is 105 s, target 300 s -> 195 s away, far outside window
    assert _find_cut_vad(300.0, [(100.0, 110.0)]) is None


def test_returns_none_for_empty_regions():
    assert _find_cut_vad(300.0, []) is None


def test_picks_closest_region_among_several():
    regions = [(100.0, 110.0), (290.0, 310.0), (500.0, 520.0)]
    # centres: 105, 300, 510 — target 300 -> closest is 300
    assert _find_cut_vad(300.0, regions) == 300.0


def test_region_at_window_edge_is_accepted():
    # centre exactly SILENCE_WINDOW_SEC away from target is within (<=) the window
    target = 300.0
    edge_centre = target + SILENCE_WINDOW_SEC
    assert _find_cut_vad(target, [(edge_centre - 1.0, edge_centre + 1.0)]) == edge_centre


def test_region_just_past_window_is_rejected():
    target = 300.0
    far_centre = target + SILENCE_WINDOW_SEC + 1.0
    assert _find_cut_vad(target, [(far_centre - 1.0, far_centre + 1.0)]) is None


# --------------------------------------------------------------------------
# delete_chunk_files — remove temp chunks, keep the original
# --------------------------------------------------------------------------

def test_deletes_temp_chunks_but_keeps_original(tmp_path):
    original = tmp_path / "original.wav"
    chunk1 = tmp_path / "chunk1.wav"
    chunk2 = tmp_path / "chunk2.wav"
    for f in (original, chunk1, chunk2):
        f.write_bytes(b"x")

    chunks = [(str(chunk1), 0.0), (str(chunk2), 300.0), (str(original), 0.0)]
    delete_chunk_files(chunks, str(original))

    assert not chunk1.exists()
    assert not chunk2.exists()
    assert original.exists()  # original must survive


def test_missing_file_does_not_raise(tmp_path):
    missing = tmp_path / "gone.wav"
    # Should silently ignore a file that is already gone.
    delete_chunk_files([(str(missing), 0.0)], str(tmp_path / "original.wav"))


def test_single_file_result_keeps_file(tmp_path):
    # split_audio returns [(wav_path, 0.0)] when it does not split — that path
    # must never be deleted by cleanup.
    original = tmp_path / "audio.wav"
    original.write_bytes(b"x")

    delete_chunk_files([(str(original), 0.0)], str(original))

    assert original.exists()
