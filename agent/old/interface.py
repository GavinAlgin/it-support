import os
import sys
import json
import time
import socket
import platform
import secrets
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QGroupBox, QFormLayout,
    QLineEdit
)

APP_NAME = "CloudMonitor"
VERSION = "1.3.0"
PORT = 8765
INTERVAL = 5
APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME
CONFIG_FILE = APP_DIR / "config.json"


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    except (ValueError, OSError):
        return {}


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


class AgentHTTPServer:
    """Local API used directly by the admin web application."""

    def __init__(self, window, port=PORT):
        self.window = window
        if not self.window.config.get("api_token"):
            self.window.config["api_token"] = secrets.token_urlsafe(32)
            save_config(self.window.config)
        self.token = self.window.config["api_token"]
        self.allowed_origins = {
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:4173", "http://127.0.0.1:4173",
        }
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def send_json(self, status, data):
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                origin = self.headers.get("Origin", "")
                if origin in outer.allowed_origins:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                origin = self.headers.get("Origin", "")
                if origin not in outer.allowed_origins:
                    self.send_json(403, {"detail": "Origin not allowed"})
                    return
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Vary", "Origin")
                self.end_headers()

            def authorized(self):
                origin = self.headers.get("Origin", "")
                if origin and origin not in outer.allowed_origins:
                    self.send_json(403, {"detail": "Origin not allowed"})
                    return False
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                if not secrets.compare_digest(supplied, outer.token):
                    self.send_json(401, {"detail": "Unauthorized. Check the agent token."})
                    return False
                return True

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/health":
                    self.send_json(200, {"status": "online", "agent": APP_NAME, "version": VERSION})
                    return
                if not self.authorized():
                    return
                if path in ("/api/v1/device", "/api/v1/devices"):
                    device = outer.window.get_device_data()
                    if path.endswith("/devices"):
                        self.send_json(200, {"devices": [device]})
                    else:
                        self.send_json(200, device)
                    return
                self.send_json(404, {"detail": "Endpoint not found"})

            def do_POST(self):
                if not self.authorized():
                    return
                path = urlparse(self.path).path
                if path != "/api/v1/commands":
                    self.send_json(404, {"detail": "Endpoint not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    self.send_json(400, {"detail": "Invalid JSON body"})
                    return
                command = payload.get("command")
                if command == "pause":
                    outer.window.set_monitoring(False)
                elif command == "resume":
                    outer.window.set_monitoring(True)
                elif command == "refresh":
                    outer.window.refresh_metrics()
                elif command == "metadata":
                    allowed = ("display_name", "assigned_user", "user_email", "organisation")
                    for key in allowed:
                        if key in payload and isinstance(payload[key], str):
                            outer.window.config[key] = payload[key][:120]
                    save_config(outer.window.config)
                else:
                    self.send_json(400, {"detail": "Unsupported command"})
                    return
                self.send_json(200, {
                    "success": True, "command": command,
                    "device": outer.window.get_device_data()
                })

            def log_message(self, fmt, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class CloudMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CloudMonitor Desktop Agent")
        self.setMinimumSize(560, 560)
        self.config = load_config()
        self.config.setdefault("device_id", str(uuid.uuid4()))
        self.config.setdefault("display_name", socket.gethostname())
        save_config(self.config)
        self.monitoring_enabled = True
        self.latest_metrics = {}
        self.http_server = None
        self.build_ui()
        try:
            self.http_server = AgentHTTPServer(self)
            self.token_input.setText(self.config["api_token"])
            self.api_status.setText(f"Agent API running at http://127.0.0.1:{PORT}")
            self.refresh_metrics()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh_metrics)
            self.timer.start(INTERVAL * 1000)
        except OSError as exc:
            QMessageBox.critical(self, "Agent API error", f"Could not start local API on port {PORT}: {exc}")
            self.api_status.setText(f"API failed: {exc}")

    def build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        heading = QLabel("CloudMonitor")
        heading.setStyleSheet("font-size:26px;font-weight:bold;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Local desktop monitoring agent — no backend or account login required."))

        connection = QGroupBox("Frontend connection")
        form = QFormLayout(connection)
        self.device_id_label = QLabel(self.config.get("device_id", "Initialising"))
        self.hostname_label = QLabel(socket.gethostname())
        self.os_label = QLabel(f"{platform.system()} {platform.release()}")
        self.api_status = QLabel("Starting local API...")
        self.token_input = QLineEdit()
        self.token_input.setReadOnly(True)
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        reveal = QPushButton("Show / hide token")
        reveal.clicked.connect(lambda: self.token_input.setEchoMode(
            QLineEdit.EchoMode.Normal if self.token_input.echoMode() == QLineEdit.EchoMode.Password
            else QLineEdit.EchoMode.Password
        ))
        token_row = QWidget()
        token_layout = QHBoxLayout(token_row)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.addWidget(self.token_input)
        token_layout.addWidget(reveal)
        form.addRow("Device ID:", self.device_id_label)
        form.addRow("Hostname:", self.hostname_label)
        form.addRow("Operating system:", self.os_label)
        form.addRow("API status:", self.api_status)
        form.addRow("Frontend API token:", token_row)
        layout.addWidget(connection)

        monitor = QGroupBox("Live monitoring")
        mlay = QVBoxLayout(monitor)
        self.status_label = QLabel("Starting...")
        self.cpu_label = QLabel("CPU: --")
        self.ram_label = QLabel("RAM: --")
        self.disk_label = QLabel("Disk: --")
        self.battery_label = QLabel("Battery: --")
        self.uptime_label = QLabel("Uptime: --")
        for widget in (self.status_label, self.cpu_label, self.ram_label,
                       self.disk_label, self.battery_label, self.uptime_label):
            mlay.addWidget(widget)
        buttons = QHBoxLayout()
        self.pause_button = QPushButton("Pause monitoring")
        self.pause_button.clicked.connect(lambda: self.set_monitoring(not self.monitoring_enabled))
        refresh = QPushButton("Refresh now")
        refresh.clicked.connect(self.refresh_metrics)
        buttons.addWidget(self.pause_button)
        buttons.addWidget(refresh)
        mlay.addLayout(buttons)
        layout.addWidget(monitor)
        self.setCentralWidget(container)

    def collect_metrics(self):
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        root = os.environ.get("SystemDrive", "C:\\") if os.name == "nt" else "/"
        try:
            disk = psutil.disk_usage(root)
            disk_data = {
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            }
        except OSError:
            disk_data = {"disk_percent": 0, "disk_used_gb": 0, "disk_total_gb": 0}
        battery = psutil.sensors_battery()
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                processes.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "Unknown",
                    "cpu_percent": round(proc.cpu_percent(None), 2),
                    "memory_mb": round((info["memory_info"].rss if info.get("memory_info") else 0) / 1048576, 2),
                    "category": "Process",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        processes.sort(key=lambda item: item["cpu_percent"], reverse=True)
        return {
            "cpu_percent": round(cpu, 1),
            "cpu_model": platform.processor() or platform.machine() or "Unknown",
            "ram_percent": round(mem.percent, 1),
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            **disk_data,
            "battery_percent": battery.percent if battery else None,
            "battery_plugged_in": battery.power_plugged if battery else None,
            "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
            "ip_address": self.get_ip_address(),
            "serial": "",
            "processes": processes[:100],
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

    def refresh_metrics(self):
        if not self.monitoring_enabled:
            return
        try:
            self.latest_metrics = self.collect_metrics()
            m = self.latest_metrics
            self.cpu_label.setText(f"CPU: {m['cpu_percent']}%")
            self.ram_label.setText(f"RAM: {m['ram_percent']}% ({m['ram_used_gb']}/{m['ram_total_gb']} GB)")
            self.disk_label.setText(f"Disk: {m['disk_percent']}% ({m['disk_used_gb']}/{m['disk_total_gb']} GB)")
            self.battery_label.setText(f"Battery: {m['battery_percent']}%" if m["battery_percent"] is not None else "Battery: Not available")
            self.uptime_label.setText(f"Uptime: {m['uptime_seconds'] // 3600} hours")
            self.status_label.setText("Monitoring active · telemetry available to frontend")
        except Exception as exc:
            self.status_label.setText(f"Metric collection failed: {exc}")

    def get_device_data(self):
        return {
            "id": self.config["device_id"],
            "hostname": socket.gethostname(),
            "display_name": self.config.get("display_name", socket.gethostname()),
            "assigned_user": self.config.get("assigned_user", "Unassigned"),
            "user_email": self.config.get("user_email", ""),
            "organisation": self.config.get("organisation", "Unassigned organisation"),
            "os_name": f"{platform.system()} {platform.release()}",
            "agent_version": VERSION,
            "monitoring_enabled": self.monitoring_enabled,
            **(self.latest_metrics or self.collect_metrics()),
        }

    def set_monitoring(self, enabled):
        self.monitoring_enabled = bool(enabled)
        if self.monitoring_enabled:
            self.refresh_metrics()
            self.timer.start(INTERVAL * 1000)
            self.pause_button.setText("Pause monitoring")
        else:
            self.timer.stop()
            self.status_label.setText("Monitoring paused by administrator")
            self.pause_button.setText("Resume monitoring")

    @staticmethod
    def get_ip_address():
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return ""

    def closeEvent(self, event):
        if hasattr(self, "timer"):
            self.timer.stop()
        if self.http_server:
            self.http_server.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CloudMonitor()
    window.show()
    sys.exit(app.exec())