import os
import sys
import json
import time
import socket
import platform
from pathlib import Path

import psutil
import requests
import keyring

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QGroupBox, QFormLayout, QCheckBox,
    QScrollArea
)


APP_NAME = "CloudMonitor"
VERSION = "1.1.0"
INTERVAL = 15
POLICY_INTERVAL = 60

APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME
CONFIG_FILE = APP_DIR / "config.json"

SCOPES = {
    "system_metrics": "CPU and RAM usage",
    "disk_metrics": "Disk usage",
    "battery_metrics": "Battery information",
    "uptime_metrics": "System uptime",
    "process_metadata": "Running process names and resource usage",
}


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    return {}


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temp.replace(CONFIG_FILE)


class CloudMonitor(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CloudMonitor Desktop")
        self.setMinimumSize(540, 650)

        self.config = load_config()
        self.device_token = None
        self.user_token = None
        self.permissions = {}
        self.monitoring_enabled = False

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"CloudMonitor/{VERSION}"
        })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.heartbeat)

        self.policy_timer = QTimer(self)
        self.policy_timer.timeout.connect(self.refresh_policy)

        self.build_ui()

    def build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        heading = QLabel("CloudMonitor")
        heading.setStyleSheet(
            "font-size: 26px; font-weight: bold;"
        )

        subtitle = QLabel(
            "Windows Device Monitoring"
        )

        layout.addWidget(heading)
        layout.addWidget(subtitle)

        # Login section
        self.login_box = QGroupBox("Employee Login")
        login_layout = QFormLayout(self.login_box)

        self.server_input = QLineEdit(
            self.config.get("server_url", "https://your-api.com")
        )
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.enrollment_input = QLineEdit()
        self.enrollment_input.setPlaceholderText(
            "Required for first device enrollment"
        )

        login_layout.addRow("Backend URL:", self.server_input)
        login_layout.addRow("Username:", self.username_input)
        login_layout.addRow("Password:", self.password_input)
        login_layout.addRow("Enrollment code:", self.enrollment_input)

        self.login_button = QPushButton("Login and Connect")
        self.login_button.clicked.connect(self.login)

        login_layout.addRow(self.login_button)
        layout.addWidget(self.login_box)

        # Device section
        self.device_box = QGroupBox("Device Information")
        device_layout = QFormLayout(self.device_box)

        self.hostname_label = QLabel(socket.gethostname())
        self.os_label = QLabel(
            f"{platform.system()} {platform.release()}"
        )
        self.device_id_label = QLabel("Not enrolled")

        device_layout.addRow("Computer:", self.hostname_label)
        device_layout.addRow("Operating system:", self.os_label)
        device_layout.addRow("Device ID:", self.device_id_label)

        layout.addWidget(self.device_box)

        # Monitoring section
        self.monitor_box = QGroupBox("Monitoring Status")
        monitor_layout = QVBoxLayout(self.monitor_box)

        self.status_label = QLabel("Not connected")
        self.cpu_label = QLabel("CPU: --")
        self.ram_label = QLabel("RAM: --")
        self.disk_label = QLabel("Disk: --")
        self.uptime_label = QLabel("Uptime: --")

        monitor_layout.addWidget(self.status_label)
        monitor_layout.addWidget(self.cpu_label)
        monitor_layout.addWidget(self.ram_label)
        monitor_layout.addWidget(self.disk_label)
        monitor_layout.addWidget(self.uptime_label)

        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)

        monitor_layout.addWidget(self.stop_button)
        layout.addWidget(self.monitor_box)

        # Permission section
        self.permission_box = QGroupBox(
            "Administrator Permission Requests"
        )
        self.permission_layout = QVBoxLayout(
            self.permission_box
        )

        self.permission_info = QLabel(
            "Log in to retrieve permission requests."
        )
        self.permission_layout.addWidget(self.permission_info)

        layout.addWidget(self.permission_box)

        self.setCentralWidget(container)

    def api_url(self, path):
        server = self.config.get("server_url", "")
        return server.rstrip("/") + path

    def request(self, method, path, token=None, **kwargs):
        headers = {}

        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = self.session.request(
            method,
            self.api_url(path),
            headers=headers,
            timeout=15,
            **kwargs
        )

        response.raise_for_status()

        if response.status_code == 204:
            return {}

        return response.json()

    def login(self):
        server = self.server_input.text().strip().rstrip("/")
        username = self.username_input.text().strip()
        password = self.password_input.text()
        enrollment_code = self.enrollment_input.text().strip()

        if not server.startswith("https://") and not (
            server.startswith("http://127.0.0.1")
            or server.startswith("http://localhost")
        ):
            QMessageBox.warning(
                self, "Security",
                "Use HTTPS for your backend URL."
            )
            return

        if not username or not password:
            QMessageBox.warning(
                self, "Login",
                "Enter your username and password."
            )
            return

        self.login_button.setEnabled(False)

        try:
            self.config["server_url"] = server

            # Authenticate employee
            result = self.request(
                "POST",
                "/api/v1/auth/login",
                json={
                    "username": username,
                    "password": password
                }
            )

            self.user_token = result["access_token"]

            device_id = self.config.get("device_id")

            if device_id:
                self.device_token = keyring.get_password(
                    APP_NAME, device_id
                )

            # Enroll a new computer
            if not device_id or not self.device_token:
                if not enrollment_code:
                    raise ValueError(
                        "Enter an administrator-generated "
                        "enrollment code."
                    )

                enrolled = self.request(
                    "POST",
                    "/api/v1/agent/enroll",
                    token=self.user_token,
                    json={
                        "code": enrollment_code,
                        "hostname": socket.gethostname(),
                        "os_name": (
                            f"{platform.system()} "
                            f"{platform.release()}"
                        ),
                        "agent_version": VERSION
                    }
                )

                device_id = enrolled["device_id"]
                self.device_token = enrolled["device_token"]

                keyring.set_password(
                    APP_NAME,
                    device_id,
                    self.device_token
                )

                self.config["device_id"] = device_id

            save_config(self.config)

            self.device_id_label.setText(str(device_id))
            self.status_label.setText("Connected")

            self.refresh_policy()
            self.refresh_requests()

            self.timer.start(INTERVAL * 1000)
            self.policy_timer.start(POLICY_INTERVAL * 1000)

            self.stop_button.setEnabled(True)

            self.login_box.setEnabled(False)
            self.status_label.setText(
                "Connected - checking permissions"
            )

            QMessageBox.information(
                self,
                "CloudMonitor",
                "Your device has connected successfully."
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Connection failed",
                str(exc)
            )

        finally:
            self.login_button.setEnabled(True)

    def refresh_policy(self):
        if not self.device_token:
            return

        try:
            policy = self.request(
                "GET",
                "/api/v1/agent/policy",
                token=self.device_token
            )

            self.permissions = policy.get("permissions", {})
            self.monitoring_enabled = policy.get(
                "monitoring_enabled", False
            )

            if not self.monitoring_enabled:
                self.status_label.setText(
                    "Monitoring disabled by policy"
                )
                return

            self.status_label.setText(
                "Monitoring authorized"
            )

        except Exception as exc:
            self.status_label.setText(
                f"Policy refresh failed: {exc}"
            )

    def collect_metrics(self):
        metrics = {}

        if self.permissions.get("system_metrics"):
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()

            metrics.update({
                "cpu_percent": cpu,
                "ram_percent": memory.percent,
                "ram_used_mb": round(
                    memory.used / (1024 ** 2), 2
                )
            })

            self.cpu_label.setText(f"CPU: {cpu:.1f}%")
            self.ram_label.setText(
                f"RAM: {memory.percent:.1f}%"
            )

        if self.permissions.get("disk_metrics"):
            disk = psutil.disk_usage(
                os.environ.get("SystemDrive", "C:\\")
            )

            metrics.update({
                "disk_percent": disk.percent,
                "disk_used_gb": round(
                    disk.used / (1024 ** 3), 2
                )
            })

            self.disk_label.setText(
                f"Disk: {disk.percent:.1f}%"
            )

        if self.permissions.get("battery_metrics"):
            battery = psutil.sensors_battery()

            metrics.update({
                "battery_percent": (
                    battery.percent if battery else None
                ),
                "battery_plugged_in": (
                    battery.power_plugged if battery else None
                )
            })

        if self.permissions.get("uptime_metrics"):
            metrics["uptime_seconds"] = max(
                0,
                int(time.time() - psutil.boot_time())
            )

            self.uptime_label.setText(
                f"Uptime: {metrics['uptime_seconds'] // 3600} hours"
            )

        if self.permissions.get("process_metadata"):
            processes = []

            for process in psutil.process_iter(
                ["name", "memory_percent"]
            ):
                try:
                    info = process.info

                    processes.append({
                        "name": info["name"],
                        "memory_percent": round(
                            info["memory_percent"] or 0, 2
                        )
                    })

                except (psutil.NoSuchProcess,
                        psutil.AccessDenied):
                    continue

            metrics["processes"] = processes[:100]

        return metrics

    def heartbeat(self):
        if not self.device_token:
            return

        if not self.monitoring_enabled:
            return

        try:
            metrics = self.collect_metrics()

            if not metrics:
                return

            self.request(
                "POST",
                "/api/v1/agent/heartbeat",
                token=self.device_token,
                json=metrics
            )

            self.status_label.setText(
                "Monitoring active - synchronized"
            )

        except Exception as exc:
            self.status_label.setText(
                f"Synchronization error: {exc}"
            )

    def refresh_requests(self):
        if not self.device_token:
            return

        try:
            result = self.request(
                "GET",
                "/api/v1/agent/permission-requests",
                token=self.device_token
            )

            # Clear old permission request widgets
            while self.permission_layout.count():
                item = self.permission_layout.takeAt(0)

                if item.widget():
                    item.widget().deleteLater()

            requests_list = result.get("requests", [])

            if not requests_list:
                self.permission_layout.addWidget(
                    QLabel("No pending permission requests.")
                )
                return

            for item in requests_list:
                scope = item.get("scope", "")
                description = item.get(
                    "description",
                    SCOPES.get(scope, scope)
                )

                group = QGroupBox(description)
                row = QHBoxLayout(group)

                approve = QPushButton("Approve")
                deny = QPushButton("Deny")

                approve.clicked.connect(
                    lambda checked=False, rid=item["id"]:
                    self.respond_to_request(rid, "approved")
                )

                deny.clicked.connect(
                    lambda checked=False, rid=item["id"]:
                    self.respond_to_request(rid, "denied")
                )

                row.addWidget(approve)
                row.addWidget(deny)

                self.permission_layout.addWidget(group)

        except Exception as exc:
            self.permission_layout.addWidget(
                QLabel(f"Could not load requests: {exc}")
            )

    def respond_to_request(self, request_id, decision):
        try:
            self.request(
                "POST",
                "/api/v1/agent/permission-responses",
                token=self.device_token,
                json={
                    "request_id": request_id,
                    "decision": decision
                }
            )

            QMessageBox.information(
                self,
                "Permission",
                f"Request {decision} successfully."
            )

            self.refresh_policy()
            self.refresh_requests()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Permission error",
                str(exc)
            )

    def stop_monitoring(self):
        self.timer.stop()
        self.policy_timer.stop()

        self.monitoring_enabled = False

        self.status_label.setText(
            "Monitoring paused by user"
        )

        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        self.timer.stop()
        self.policy_timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CloudMonitor()
    window.show()

    sys.exit(app.exec())
