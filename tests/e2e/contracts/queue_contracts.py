"""
PolarSnap Queue & Subsystem Contracts & Oracles (Milestone 3: Features 15-19)
"""
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import List, Dict, Optional, Set


class TaskState(str, Enum):
    PENDING = "PENDING"
    FETCHING_METADATA = "FETCHING_METADATA"
    DOWNLOADING = "DOWNLOADING"
    REMASTERING = "REMASTERING"
    FINALIZING = "FINALIZING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DownloadPhase(str, Enum):
    IDLE = "Idle"
    FETCHING_METADATA = "FetchingMetadata"
    DOWNLOADING = "Downloading"
    REMASTERING = "Remastering"
    FINALIZING = "Finalizing"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass
class DownloadRequest:
    url: str
    title: Optional[str] = None
    custom_format: str = "MP4"
    turbo_acceleration: bool = True
    color_preset: str = "NONE"
    is_remaster_enabled: bool = False


@dataclass
class DownloadTask:
    id: str
    url: str
    title: str
    state: TaskState = TaskState.PENDING
    active_phase: DownloadPhase = DownloadPhase.IDLE
    progress: float = 0.0
    speed_bytes_per_sec: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    eta_seconds: int = 0
    assigned_slot: Optional[int] = None
    sub_sockets: int = 0
    error_message: Optional[str] = None


class BoundedQueueManagerContract:
    """
    Contract for bounded 2-slot concurrency queue with up to 16 aria2c sub-sockets per slot.
    """
    MAX_CONCURRENT_ACTIVE_SLOTS = 2
    MAX_SUB_SOCKETS_PER_SLOT = 16
    MAX_TOTAL_TCP_SOCKETS = 32

    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_slots: Dict[int, str] = {0: "", 1: ""}  # slot_id -> task_id

    def enqueue(self, request: DownloadRequest, task_id: str) -> DownloadTask:
        task = DownloadTask(
            id=task_id,
            url=request.url,
            title=request.title or f"Media_{task_id}",
            state=TaskState.PENDING,
            active_phase=DownloadPhase.IDLE,
            sub_sockets=self.MAX_SUB_SOCKETS_PER_SLOT if request.turbo_acceleration else 1
        )
        self.tasks[task_id] = task
        self._schedule()
        return task

    def _schedule(self):
        # Find free slots
        for slot in range(self.MAX_CONCURRENT_ACTIVE_SLOTS):
            if not self.active_slots[slot]:
                # find pending task
                for task in self.tasks.values():
                    if task.state == TaskState.PENDING:
                        task.state = TaskState.DOWNLOADING
                        task.active_phase = DownloadPhase.DOWNLOADING
                        task.assigned_slot = slot
                        self.active_slots[slot] = task.id
                        break

    def pause(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.state != TaskState.DOWNLOADING:
            return False
        task.state = TaskState.PAUSED
        if task.assigned_slot is not None:
            self.active_slots[task.assigned_slot] = ""
            task.assigned_slot = None
        self._schedule()
        return True

    def resume(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.state != TaskState.PAUSED:
            return False
        task.state = TaskState.PENDING
        self._schedule()
        return True

    def cancel(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.assigned_slot is not None:
            self.active_slots[task.assigned_slot] = ""
            task.assigned_slot = None
        task.state = TaskState.CANCELLED
        task.active_phase = DownloadPhase.IDLE
        self._schedule()
        return True

    def complete(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.assigned_slot is not None:
            self.active_slots[task.assigned_slot] = ""
            task.assigned_slot = None
        task.state = TaskState.COMPLETED
        task.active_phase = DownloadPhase.COMPLETED
        task.progress = 1.0
        self._schedule()
        return True

    def get_total_active_sub_sockets(self) -> int:
        total = 0
        for slot, tid in self.active_slots.items():
            if tid and tid in self.tasks:
                total += self.tasks[tid].sub_sockets
        return total


class MediaStorePublisherContract:
    """
    Contract for Android 14 Scoped Storage MediaStore two-phase publishing:
    Phase 1: Insert record with IS_PENDING = 1
    Phase 2: Write media bytes to Uri
    Phase 3: Update IS_PENDING = 0 to reveal in Gallery/Music
    """
    @dataclass
    class MediaRecord:
        uri: str
        display_name: str
        mime_type: str
        relative_path: str
        is_pending: int
        byte_size: int = 0

    def __init__(self):
        self.published_records: Dict[str, MediaStorePublisherContract.MediaRecord] = {}

    def phase1_create_pending(self, display_name: str, is_audio: bool) -> str:
        uri = f"content://media/external/{'audio' if is_audio else 'video'}/media/{len(self.published_records) + 1}"
        rel_path = "Music/PolarSnap" if is_audio else "Movies/PolarSnap"
        mime = "audio/flac" if is_audio else "video/mp4"

        record = self.MediaRecord(
            uri=uri,
            display_name=display_name,
            mime_type=mime,
            relative_path=rel_path,
            is_pending=1,
            byte_size=0
        )
        self.published_records[uri] = record
        return uri

    def phase2_write_bytes(self, uri: str, byte_count: int) -> bool:
        if uri not in self.published_records:
            return False
        record = self.published_records[uri]
        if record.is_pending != 1:
            return False
        record.byte_size = byte_count
        return True

    def phase3_publish_commit(self, uri: str) -> bool:
        if uri not in self.published_records:
            return False
        record = self.published_records[uri]
        if record.is_pending != 1 or record.byte_size <= 0:
            return False
        record.is_pending = 0
        return True


class ForegroundServiceContract:
    """
    Contract for Android 14 FOREGROUND_SERVICE_DATA_SYNC notification.
    """
    FOREGROUND_SERVICE_TYPE = "dataSync"
    PERMISSION_NAME = "android.permission.FOREGROUND_SERVICE_DATA_SYNC"

    @staticmethod
    def is_notification_throttled(last_update_ts: float, current_ts: float, min_interval_sec: float = 1.0) -> bool:
        """Throttles notifications to at most 1 update per second."""
        return (current_ts - last_update_ts) < min_interval_sec
