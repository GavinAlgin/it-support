
import json
import os
import platform
import socket
import time
from pathlib import Path

import psutil
import requests

API_URL = os.getenv("HELPDESK_API_URL", "http://127.0.0.1:8000").rstrip("/")
INTERVAL = int(os.getenv("HELPDESK_INTERVAL", "15"))

STATE_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "HelpdeskAgent"
STATE_FILE = STATE_DIR / "agent.json"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")

    # Restrict the credential directory on Windows.
    if os.name == "nt":
        import subprocess
        subprocess.run([
            "icacls", str(STATE_DIR),
            "/inheritance:r",
            "/grant:r", "*S-1-5-18:(OI)(CI)F",
            "/grant:r", "*S-1-5-32-544:(OI)(CI)F",
        ], check=True, capture_output=True)


def enroll():
    code = os.getenv("HELPDESK_ENROLLMENT_CODE")
    if not code:
        raise RuntimeError("Set HELPDESK_ENROLLMENT_CODE for initial enrollment.")

    memory = psutil.virtual_memory()
    response = requests.post(
        f"{API_URL}/agent/enroll",
        json={
            "code": code,
            "hostname": socket.gethostname(),
            "os_version": f"{platform.system()} {platform.release()}",
            "cpu_model": platform.processor() or "Unknown",
            "cpu_count": psutil.cpu_count(logical=True) or 1,
            "total_ram_mb": round(memory.total / (1024 ** 2), 2),
        },
        timeout=15,
    )
    response.raise_for_status()

    state = response.json()
    save_state(state)
    print(f"Device enrolled: {state['device_id']}")
    return state


def battery_info():
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return None, None
        return battery.percent, battery.power_plugged
    except (AttributeError, OSError):
        return None, None


def temperature():
    try:
        sensors = psutil.sensors_temperatures()
        values = [
            sensor.current
            for group in sensors.values()
            for sensor in group
            if sensor.current is not None
        ]
        return max(values) if values else None
    except (AttributeError, OSError):
        return None


def top_processes():
    results = []
    for process in psutil.process_iter(
        ["pid", "name", "memory_percent", "cpu_percent"]
    ):
        try:
            item = process.info
            results.append({
                "pid": item["pid"],
                "name": (item["name"] or "Unknown")[:100],
                "cpu_percent": round(item["cpu_percent"] or 0, 1),
                "memory_percent": round(item["memory_percent"] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(
        results, key=lambda item: item["cpu_percent"], reverse=True
    )[:20]


def collect():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
    network = psutil.net_io_counters()
    battery_percent, battery_plugged = battery_info()

    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": memory.percent,
        "ram_used_mb": round(memory.used / (1024 ** 2), 2),
        "ram_total_mb": round(memory.total / (1024 ** 2), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "battery_percent": battery_percent,
        "battery_plugged": battery_plugged,
        "cpu_temp_c": temperature(),
        "uptime_seconds": max(0, time.time() - psutil.boot_time()),
        "network_sent_bytes": network.bytes_sent,
        "network_recv_bytes": network.bytes_recv,
        "top_processes": top_processes(),
    }


def main():
    if not 5 <= INTERVAL <= 300:
        raise ValueError("HELPDESK_INTERVAL must be between 5 and 300 seconds")

    state = load_state() or enroll()
    print(f"Monitoring {socket.gethostname()} every {INTERVAL} seconds.")

    while True:
        started = time.monotonic()
        try:
            response = requests.post(
                f"{API_URL}/agent/report",
                json=collect(),
                headers={
                    "Authorization": f"Bearer {state['device_token']}"
                },
                timeout=10,
            )

            if response.status_code in (401, 403):
                raise RuntimeError(
                    "Device token rejected or device disabled. "
                    "Contact the administrator to re-enroll."
                )

            response.raise_for_status()
            print("Metrics reported successfully.")

        except RuntimeError:
            raise
        except (requests.RequestException, OSError, ValueError) as error:
            print(f"Report failed: {type(error).__name__}: {error}")

        time.sleep(max(1, INTERVAL - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
