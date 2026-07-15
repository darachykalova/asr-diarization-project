"""Тесты самолечения зависших задач на старте worker'а.

on_worker_ready должен запускать requeue_stuck_jobs ровно один раз при
старте (сигнал worker_ready срабатывает в главном процессе один раз,
в отличие от worker_process_init, который стреляет на каждый форк —
с --concurrency=2 это задвоило бы перезапуск задач).
"""
from unittest.mock import MagicMock, patch

from tasks.audio_tasks import on_worker_ready


def test_on_worker_ready_calls_requeue_stuck_jobs():
    fake_db = MagicMock()
    with patch("tasks.audio_tasks.SessionLocal", return_value=fake_db), \
         patch("tasks.recovery.requeue_stuck_jobs", return_value=["job-1"]) as mock_requeue:
        on_worker_ready()

    mock_requeue.assert_called_once_with(fake_db)


def test_on_worker_ready_closes_db_session():
    fake_db = MagicMock()
    with patch("tasks.audio_tasks.SessionLocal", return_value=fake_db), \
         patch("tasks.recovery.requeue_stuck_jobs", return_value=[]):
        on_worker_ready()

    fake_db.close.assert_called_once()


def test_on_worker_ready_survives_requeue_failure():
    """Сбой самолечения не должен ронять запуск worker'а."""
    fake_db = MagicMock()
    with patch("tasks.audio_tasks.SessionLocal", return_value=fake_db), \
         patch("tasks.recovery.requeue_stuck_jobs", side_effect=RuntimeError("db boom")):
        on_worker_ready()  # не должно бросить исключение

    fake_db.close.assert_called_once()
