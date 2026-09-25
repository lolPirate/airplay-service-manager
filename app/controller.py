from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from . import config


@dataclass(frozen=True)
class SessionSpec:
    profile: str = "av"          # av | audio
    flip_horizontal: bool = False
    flip_vertical: bool = False

    @classmethod
    def from_payload(cls, payload: dict | None) -> "SessionSpec":
        payload = payload or {}
        profile = payload.get("profile", "av")
        if profile not in {"av", "audio"}:
            raise ValueError("profile must be 'av' or 'audio'")

        return cls(
            profile=profile,
            flip_horizontal=bool(payload.get("flip_horizontal", False)),
            flip_vertical=bool(payload.get("flip_vertical", False)),
        )


class UxPlayController:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def _read_state(self) -> dict | None:
        try:
            return json.loads(config.PROCESS_STATE.read_text())
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return None

    def _write_state(self, pid: int, spec: SessionSpec) -> None:
        config.PROCESS_STATE.write_text(
            json.dumps({"pid": pid, "spec": asdict(spec)})
        )

    def _clear_state(self) -> None:
        try:
            config.PROCESS_STATE.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    @staticmethod
    def _is_uxplay(pid: int) -> bool:
        """Protect against stale PID reuse before killing anything."""
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            return b"uxplay" in cmdline
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return False

    def _running_state(self) -> tuple[int | None, SessionSpec | None]:
        state = self._read_state()
        if not state:
            return None, None

        try:
            pid = int(state["pid"])
            spec = SessionSpec(**state["spec"])
        except (KeyError, TypeError, ValueError):
            self._clear_state()
            return None, None

        if self._pid_exists(pid) and self._is_uxplay(pid):
            return pid, spec

        self._clear_state()
        return None, None

    @staticmethod
    def _flip_args(spec: SessionSpec) -> list[str]:
        if spec.flip_horizontal and spec.flip_vertical:
            return ["-f", "I"]
        if spec.flip_horizontal:
            return ["-f", "H"]
        if spec.flip_vertical:
            return ["-f", "V"]
        return []

    @staticmethod
    def _command(spec: SessionSpec) -> list[str]:
        if spec.profile == "av":
            args = list(config.AV_ARGS)
        else:
            args = list(config.AUDIO_ARGS)

        # Flips only affect video. Keeping them in the audio profile is harmless,
        # but omit them because there is no mirrored video in that mode.
        if spec.profile == "av":
            args.extend(UxPlayController._flip_args(spec))

        return [config.UXPLAY_BIN, *args]

    def status(self) -> dict:
        with self._lock:
            pid, spec = self._running_state()
            return {
                "running": pid is not None,
                "pid": pid,
                "spec": asdict(spec) if spec else None,
                "wayland_ready": config.WAYLAND_SOCKET.is_socket(),
            }

    def start(self, spec: SessionSpec) -> dict:
        """Idempotent start.

        Same requested spec + already running => no-op.
        Different spec + running => replace the session atomically under a lock.
        """
        with self._lock:
            pid, current = self._running_state()

            if pid is not None and current == spec:
                return {
                    "ok": True,
                    "changed": False,
                    "running": True,
                    "pid": pid,
                    "spec": asdict(spec),
                }

            if not config.WAYLAND_SOCKET.is_socket():
                raise RuntimeError(
                    f"Wayland socket {config.WAYLAND_SOCKET} is not available; "
                    "labwc is not ready"
                )

            if pid is not None:
                self._stop_locked(pid)

            command = self._command(spec)
            config.UXPLAY_LOG.parent.mkdir(parents=True, exist_ok=True)
            log = open(config.UXPLAY_LOG, "a", buffering=1)

            process = subprocess.Popen(
                command,
                env=config.BASE_ENV,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )

            # Catch immediate startup failures while keeping the API responsive.
            time.sleep(0.35)
            if process.poll() is not None:
                log.close()
                raise RuntimeError(
                    f"UxPlay exited during startup with code {process.returncode}; "
                    f"see {config.UXPLAY_LOG}"
                )

            self._write_state(process.pid, spec)
            return {
                "ok": True,
                "changed": True,
                "running": True,
                "pid": process.pid,
                "spec": asdict(spec),
            }

    def _stop_locked(self, pid: int) -> None:
        if not self._pid_exists(pid) or not self._is_uxplay(pid):
            self._clear_state()
            return

        try:
            # start_new_session=True makes the child the leader of its process group.
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._clear_state()
            return

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not self._pid_exists(pid):
                self._clear_state()
                return
            time.sleep(0.1)

        if self._pid_exists(pid) and self._is_uxplay(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        self._clear_state()

    def stop(self) -> dict:
        """Idempotent stop: stopping an already-stopped receiver succeeds."""
        with self._lock:
            pid, previous = self._running_state()
            if pid is None:
                return {
                    "ok": True,
                    "changed": False,
                    "running": False,
                    "spec": None,
                }

            self._stop_locked(pid)
            return {
                "ok": True,
                "changed": True,
                "running": False,
                "spec": asdict(previous) if previous else None,
            }
