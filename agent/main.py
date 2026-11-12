import os
import sys
import json
import time
import socket
import platform
import secrets
import uuid
import threading
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, urlencode

import psutil

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QLineEdit, QTextEdit, QComboBox,
    QStackedWidget, QFrame, QFormLayout, QProgressBar, QSpacerItem,
    QSizePolicy, QScrollArea
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME = "CloudMonitor"
VERSION = "2.0.0"
PORT = 8765
INTERVAL = 5

APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME
CONFIG_FILE = APP_DIR / "config.json"

# Change this to the URL where your API is hosted.
BACKEND_URL = os.getenv("CLOUDMONITOR_API", "http://localhost:8000").rstrip("/")

# Expected backend routes (adjust these constants if your API uses other paths).
LOGIN_ENDPOINT = "/api/v1/auth/login"
TICKET_ENDPOINT = "/api/v1/tickets"
ENROLL_ENDPOINT = "/api/v1/agents/request-connection"
CLAIM_ENDPOINT = "/api/v1/agents/claim"
TELEMETRY_ENDPOINT = "/api/v1/telemetry"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    except (ValueError, OSError):
        return {}


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = CONFIG_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temp_file.replace(CONFIG_FILE)


def api_request(path, method="GET", payload=None, token=None, timeout=12):
    """Send a JSON request to the central API and return its JSON response."""
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=body,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
            parsed = json.loads(detail) if detail else {}
            message = parsed.get("detail") or parsed.get("message") or detail
        except Exception:
            message = str(exc)
        raise RuntimeError(f"API error ({exc.code}): {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to {BACKEND_URL}: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Signals for safe UI updates from worker threads
# ---------------------------------------------------------------------------
class AgentSignals(QObject):
    telemetry_done = Signal(bool, str)


# ---------------------------------------------------------------------------
# Local agent API
# ---------------------------------------------------------------------------
class AgentHTTPServer:
    """Local read-only device API for the admin dashboard."""

    def __init__(self, window, port=PORT):
        self.window = window
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
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Vary", "Origin")
                self.end_headers()

            def authorized(self):
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                token = outer.window.config.get("api_token", "")
                if not token or not secrets.compare_digest(supplied, token):
                    self.send_json(401, {"detail": "Unauthorized"})
                    return False
                return True

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/health":
                    self.send_json(200, {
                        "status": "online", "agent": APP_NAME, "version": VERSION
                    })
                    return
                if not self.authorized():
                    return
                if path == "/api/v1/device":
                    self.send_json(200, outer.window.get_device_data())
                    return
                if path == "/api/v1/devices":
                    self.send_json(200, {"devices": [outer.window.get_device_data()]})
                    return
                self.send_json(404, {"detail": "Endpoint not found"})

            def log_message(self, fmt, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class CloudMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CloudMonitor | Desktop Agent")
        self.setMinimumSize(900, 680)
        self.resize(1080, 760)

        self.config = load_config()
        self.config.setdefault("device_id", str(uuid.uuid4()))
        self.config.setdefault("display_name", socket.gethostname())
        self.config.setdefault("organisation", "")
        if not self.config.get("claim_secret"):
            self.config["claim_secret"] = secrets.token_urlsafe(32)
        save_config(self.config)

        self.monitoring_enabled = True
        self.latest_metrics = {}
        self.http_server = None

        # User session token is deliberately kept in memory, not config.json.
        self.user_token = None
        self.current_user = {}

        self.signals = AgentSignals()
        self.signals.telemetry_done.connect(self.on_telemetry_done)

        self.build_ui()
        self.show_login_page()

        try:
            self.http_server = AgentHTTPServer(self)
            self.api_status_label.setText(f"Local API active · 127.0.0.1:{PORT}")
        except OSError as exc:
            self.api_status_label.setText(f"Local API unavailable: {exc}")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_metrics)
        self.timer.start(INTERVAL * 1000)
        self.refresh_metrics()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------
    def build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                color: #172033;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QFrame#Sidebar { background: #101828; border: none; }
            QLabel#Brand { color: white; font-size: 21pt; font-weight: 700; }
            QLabel#BrandSub { color: #98A2B3; font-size: 9pt; }
            QLabel#SidebarItem { color: #D0D5DD; padding: 11px 13px; }
            QLabel#SidebarItemActive {
                color: white; background: #344054; border-radius: 8px;
                padding: 11px 13px; font-weight: 600;
            }
            QLabel#PageTitle { font-size: 23pt; font-weight: 700; color: #101828; }
            QLabel#Muted { color: #667085; }
            QLabel#CardTitle { font-size: 11pt; font-weight: 650; color: #344054; }
            QFrame#Card {
                background: white; border: 1px solid #EAECF0; border-radius: 12px;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: white; border: 1px solid #D0D5DD; border-radius: 7px;
                padding: 10px 11px; min-height: 20px; selection-background-color: #155EEF;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #528BFF; }
            QPushButton {
                background: #155EEF; color: white; border: none; border-radius: 7px;
                padding: 10px 16px; font-weight: 600; min-height: 20px;
            }
            QPushButton:hover { background: #004EEB; }
            QPushButton:disabled { background: #A4BCFD; color: #F8FAFC; }
            QPushButton#Secondary {
                background: white; color: #344054; border: 1px solid #D0D5DD;
            }
            QPushButton#Secondary:hover { background: #F2F4F7; }
            QPushButton#Link {
                background: transparent; color: #155EEF; padding: 4px;
            }
            QProgressBar {
                background: #EAECF0; border: none; border-radius: 4px;
                height: 8px; text-align: center;
            }
            QProgressBar::chunk { background: #2E90FA; border-radius: 4px; }
        """)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(225)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(18, 25, 18, 20)
        side.setSpacing(12)

        brand = QLabel("CloudMonitor")
        brand.setObjectName("Brand")
        brand_sub = QLabel("DESKTOP AGENT")
        brand_sub.setObjectName("BrandSub")
        side.addWidget(brand)
        side.addWidget(brand_sub)
        side.addSpacing(28)

        self.nav_dashboard = QLabel("▦   Overview")
        self.nav_dashboard.setObjectName("SidebarItem")
        self.nav_ticket = QLabel("＋   Submit a ticket")
        self.nav_ticket.setObjectName("SidebarItem")
        side.addWidget(self.nav_dashboard)
        side.addWidget(self.nav_ticket)
        side.addStretch()

        self.sidebar_user = QLabel("Not signed in")
        self.sidebar_user.setStyleSheet("color:#D0D5DD; padding:8px 2px;")
        side.addWidget(self.sidebar_user)
        self.logout_button = QPushButton("Sign out")
        self.logout_button.setObjectName("Secondary")
        self.logout_button.clicked.connect(self.logout)
        side.addWidget(self.logout_button)

        self.pages = QStackedWidget()
        self.login_page = self.create_login_page()
        self.dashboard_page = self.create_dashboard_page()
        self.ticket_page = self.create_ticket_page()

        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.ticket_page)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.sidebar.hide()

    def page_container(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(20)
        return page, layout

    def card(self, title=None):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            layout.addWidget(label)
        return frame, layout

    def create_login_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, layout = self.card()
        card.setMaximumWidth(440)

        brand = QLabel("CloudMonitor")
        brand.setStyleSheet("font-size:25pt;font-weight:700;color:#101828;")
        subtitle = QLabel("Sign in to your organisation's desktop support workspace.")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)

        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("name@company.com")
        self.login_email.setClearButtonEnabled(True)
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter your password")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.returnPressed.connect(self.login)

        self.login_error = QLabel("")
        self.login_error.setStyleSheet("color:#D92D20;")
        self.login_error.setWordWrap(True)

        self.login_button = QPushButton("Sign in")
        self.login_button.clicked.connect(self.login)

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(14)
        layout.addWidget(QLabel("Email address"))
        layout.addWidget(self.login_email)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.login_password)
        layout.addWidget(self.login_error)
        layout.addWidget(self.login_button)
        outer.addWidget(card)
        return page

    def create_dashboard_page(self):
        page, layout = self.page_container()

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Device overview")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Your workstation's health and connection status.")
        subtitle.setObjectName("Muted")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.clicked.connect(self.refresh_metrics)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        status_card, status_layout = self.card("Agent connection")
        self.enrollment_status_label = QLabel("Checking registration…")
        self.api_status_label = QLabel("Starting local API…")
        self.device_id_label = QLabel(self.config["device_id"])
        self.device_id_label.setObjectName("Muted")
        self.action_btn = QPushButton("Connect this device")
        self.action_btn.clicked.connect(self.handle_enrollment_action)
        status_layout.addWidget(self.enrollment_status_label)
        status_layout.addWidget(self.api_status_label)
        status_layout.addWidget(QLabel("Device ID"))
        status_layout.addWidget(self.device_id_label)
        status_layout.addWidget(self.action_btn)
        layout.addWidget(status_card)

        metrics_row = QHBoxLayout()
        self.cpu_value, self.cpu_bar = self.metric_card("CPU usage")
        self.ram_value, self.ram_bar = self.metric_card("Memory usage")
        self.disk_value, self.disk_bar = self.metric_card("Disk usage")
        metrics_row.addWidget(self.cpu_value[0])
        metrics_row.addWidget(self.ram_value[0])
        metrics_row.addWidget(self.disk_value[0])
        layout.addLayout(metrics_row)

        monitor_card, monitor_layout = self.card("Monitoring")
        self.status_label = QLabel("Waiting for first reading…")
        self.uptime_label = QLabel("System uptime: —")
        self.ip_label = QLabel("IP address: —")
        self.pause_button = QPushButton("Pause monitoring")
        self.pause_button.setObjectName("Secondary")
        self.pause_button.clicked.connect(
            lambda: self.set_monitoring(not self.monitoring_enabled)
        )
        monitor_layout.addWidget(self.status_label)
        monitor_layout.addWidget(self.uptime_label)
        monitor_layout.addWidget(self.ip_label)
        monitor_layout.addWidget(self.pause_button)
        layout.addWidget(monitor_card)

        layout.addStretch()
        self.check_enrollment_status()
        return page

    def metric_card(self, title):
        card, layout = self.card(title)
        value = QLabel("—%")
        value.setStyleSheet("font-size:22pt;font-weight:700;color:#101828;")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        layout.addWidget(value)
        layout.addWidget(bar)
        return (card, value), bar

    def create_ticket_page(self):
        page, layout = self.page_container()

        title = QLabel("Submit a support ticket")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Describe the issue and our support team will follow up.")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card, form = self.card("Ticket details")
        form.addWidget(QLabel("Subject"))
        self.ticket_subject = QLineEdit()
        self.ticket_subject.setPlaceholderText("Briefly describe the issue")
        form.addWidget(self.ticket_subject)

        form.addWidget(QLabel("Category"))
        self.ticket_category = QComboBox()
        self.ticket_category.addItems([
            "Hardware", "Software", "Network", "Account / Access",
            "Performance", "Other"
        ])
        form.addWidget(self.ticket_category)

        form.addWidget(QLabel("Priority"))
        self.ticket_priority = QComboBox()
        self.ticket_priority.addItems(["Low", "Normal", "High", "Urgent"])
        self.ticket_priority.setCurrentText("Normal")
        form.addWidget(self.ticket_priority)

        form.addWidget(QLabel("Description"))
        self.ticket_description = QTextEdit()
        self.ticket_description.setPlaceholderText(
            "Explain what happened, when it started, and any error message shown…"
        )
        self.ticket_description.setMinimumHeight(150)
        form.addWidget(self.ticket_description)

        self.ticket_feedback = QLabel("")
        self.ticket_feedback.setWordWrap(True)
        form.addWidget(self.ticket_feedback)

        actions = QHBoxLayout()
        actions.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("Secondary")
        clear_btn.clicked.connect(self.clear_ticket_form)
        self.ticket_submit_button = QPushButton("Submit ticket")
        self.ticket_submit_button.clicked.connect(self.submit_ticket)
        actions.addWidget(clear_btn)
        actions.addWidget(self.ticket_submit_button)
        form.addLayout(actions)

        layout.addWidget(card)
        layout.addStretch()
        return page

    # -----------------------------------------------------------------------
    # Navigation and authentication
    # -----------------------------------------------------------------------
    def show_login_page(self):
        self.sidebar.hide()
        self.pages.setCurrentWidget(self.login_page)
        self.login_email.setFocus()

    def show_app_page(self, page="dashboard"):
        self.sidebar.show()
        self.sidebar_user.setText(
            self.current_user.get("name")
            or self.current_user.get("email")
            or "Signed in"
        )
        if page == "ticket":
            self.pages.setCurrentWidget(self.ticket_page)
            self.nav_ticket.setObjectName("SidebarItemActive")
            self.nav_dashboard.setObjectName("SidebarItem")
        else:
            self.pages.setCurrentWidget(self.dashboard_page)
            self.nav_dashboard.setObjectName("SidebarItemActive")
            self.nav_ticket.setObjectName("SidebarItem")
        self.nav_dashboard.style().unpolish(self.nav_dashboard)
        self.nav_dashboard.style().polish(self.nav_dashboard)
        self.nav_ticket.style().unpolish(self.nav_ticket)
        self.nav_ticket.style().polish(self.nav_ticket)

    def login(self):
        email = self.login_email.text().strip()
        password = self.login_password.text()

        if not email or not password:
            self.login_error.setText("Enter your email address and password.")
            return

        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in…")
        self.login_error.clear()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            data = api_request(
                LOGIN_ENDPOINT,
                method="POST",
                payload={"email": email, "password": password}
            )
            token = (
                data.get("access_token")
                or data.get("token")
                or (data.get("data") or {}).get("access_token")
            )
            if not token:
                raise RuntimeError(
                    "The login response did not contain an access_token. "
                    "Check the backend response format."
                )

            self.user_token = token
            self.current_user = data.get("user") or data.get("data", {}).get("user") or {
                "email": email
            }
            self.login_password.clear()
            self.show_app_page("dashboard")
        except Exception as exc:
            self.login_error.setText(str(exc))
        finally:
            QApplication.restoreOverrideCursor()
            self.login_button.setEnabled(True)
            self.login_button.setText("Sign in")

    def logout(self):
        self.user_token = None
        self.current_user = {}
        self.login_password.clear()
        self.sidebar_user.setText("Not signed in")
        self.show_login_page()

    def open_dashboard(self):
        self.show_app_page("dashboard")

    def open_ticket(self):
        self.show_app_page("ticket")

    # -----------------------------------------------------------------------
    # Ticket submission
    # -----------------------------------------------------------------------
    def submit_ticket(self):
        if not self.user_token:
            QMessageBox.warning(self, "Sign in required", "Please sign in before submitting a ticket.")
            self.show_login_page()
            return

        subject = self.ticket_subject.text().strip()
        description = self.ticket_description.toPlainText().strip()

        if not subject or not description:
            self.ticket_feedback.setStyleSheet("color:#D92D20;")
            self.ticket_feedback.setText("Subject and description are required.")
            return

        payload = {
            "subject": subject,
            "category": self.ticket_category.currentText(),
            "priority": self.ticket_priority.currentText().lower(),
            "description": description,
            "device_id": self.config["device_id"],
            "hostname": socket.gethostname(),
            "device_name": self.config.get("display_name"),
            "os_name": f"{platform.system()} {platform.release()}",
            "agent_version": VERSION
        }

        self.ticket_submit_button.setEnabled(False)
        self.ticket_submit_button.setText("Submitting…")
        self.ticket_feedback.setStyleSheet("color:#667085;")
        self.ticket_feedback.setText("Sending your ticket to the support team…")

        try:
            data = api_request(
                TICKET_ENDPOINT,
                method="POST",
                payload=payload,
                token=self.user_token
            )
            ticket = data.get("ticket") or data.get("data") or data
            ticket_number = (
                ticket.get("ticket_number")
                or ticket.get("reference")
                or ticket.get("id")
            )
            confirmation = "Ticket submitted successfully."
            if ticket_number:
                confirmation += f" Reference: {ticket_number}"
            self.ticket_feedback.setStyleSheet("color:#027A48;font-weight:600;")
            self.ticket_feedback.setText(confirmation)
            self.clear_ticket_fields_only()
        except Exception as exc:
            self.ticket_feedback.setStyleSheet("color:#D92D20;")
            self.ticket_feedback.setText(f"Ticket could not be submitted: {exc}")
        finally:
            self.ticket_submit_button.setEnabled(True)
            self.ticket_submit_button.setText("Submit ticket")

    def clear_ticket_fields_only(self):
        self.ticket_subject.clear()
        self.ticket_description.clear()
        self.ticket_category.setCurrentIndex(0)
        self.ticket_priority.setCurrentText("Normal")

    def clear_ticket_form(self):
        self.clear_ticket_fields_only()
        self.ticket_feedback.clear()

    # -----------------------------------------------------------------------
    # Device enrollment
    # -----------------------------------------------------------------------
    def check_enrollment_status(self):
        if not hasattr(self, "enrollment_status_label"):
            return
        if self.config.get("api_token"):
            self.enrollment_status_label.setText("Device registered and authorised")
            self.action_btn.setText("Re-check device registration")
        elif self.config.get("request_id"):
            self.enrollment_status_label.setText("Connection request pending admin approval")
            self.action_btn.setText("Check approval")
        else:
            self.enrollment_status_label.setText("This device is not yet registered")
            self.action_btn.setText("Connect this device")

    def handle_enrollment_action(self):
        if self.config.get("api_token"):
            QMessageBox.information(
                self, "Device registered",
                "This device already has an agent token. Contact an administrator if it needs to be re-enrolled."
            )
            return

        if not self.config.get("request_id"):
            payload = {
                "device_id": self.config["device_id"],
                "hostname": socket.gethostname(),
                "display_name": self.config.get("display_name"),
                "os_name": f"{platform.system()} {platform.release()}",
                "agent_version": VERSION,
                "organisation": self.config.get("organisation"),
                "user_email": self.current_user.get("email", ""),
                "claim_secret": self.config["claim_secret"]
            }
            try:
                data = api_request(ENROLL_ENDPOINT, "POST", payload)
                if not data.get("success"):
                    raise RuntimeError(data.get("detail") or data.get("message") or "Request was not accepted.")
                self.config["request_id"] = data.get("request_id")
                save_config(self.config)
                self.check_enrollment_status()
                QMessageBox.information(
                    self, "Request submitted",
                    "The device connection request has been sent. An administrator must approve it."
                )
            except Exception as exc:
                QMessageBox.critical(self, "Connection failed", str(exc))
        else:
            query = urlencode({
                "request_id": self.config["request_id"],
                "claim_secret": self.config["claim_secret"]
            })
            try:
                data = api_request(f"{CLAIM_ENDPOINT}?{query}", method="POST")
                if not data.get("success") or not data.get("api_token"):
                    raise RuntimeError(data.get("detail") or "Approval is still pending.")
                self.config["api_token"] = data["api_token"]
                save_config(self.config)
                self.check_enrollment_status()
                QMessageBox.information(self, "Device connected", "This device is now registered.")
            except Exception as exc:
                QMessageBox.information(self, "Approval pending", str(exc))

    # -----------------------------------------------------------------------
    # Monitoring
    # -----------------------------------------------------------------------
    def collect_metrics(self):
        cpu = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory()
        root = os.environ.get("SystemDrive", "C:\\") if os.name == "nt" else "/"
        try:
            disk_percent = psutil.disk_usage(root).percent
        except OSError:
            disk_percent = 0.0

        battery = psutil.sensors_battery()
        return {
            "device_id": self.config["device_id"],
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(memory.percent, 1),
            "disk_percent": round(disk_percent, 1),
            "battery_percent": round(battery.percent, 1) if battery else None,
            "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
            "ip_address": self.get_ip_address(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def transmit_telemetry(self, metrics):
        token = self.config.get("api_token")
        if not token:
            return
        try:
            api_request(
                TELEMETRY_ENDPOINT,
                method="POST",
                payload={"metrics": metrics},
                token=token,
                timeout=5
            )
            self.signals.telemetry_done.emit(True, "Telemetry synced")
        except Exception as exc:
            self.signals.telemetry_done.emit(False, str(exc))

    def on_telemetry_done(self, success, message):
        if success:
            self.status_label.setText("Monitoring active · device telemetry synced")
        elif self.config.get("api_token"):
            self.status_label.setText("Monitoring active · backend currently unreachable")

    def refresh_metrics(self):
        if not self.monitoring_enabled:
            return
        try:
            self.latest_metrics = self.collect_metrics()
            metrics = self.latest_metrics
            self.cpu_value[1].setText(f"{metrics['cpu_percent']}%")
            self.ram_value[1].setText(f"{metrics['ram_percent']}%")
            self.disk_value[1].setText(f"{metrics['disk_percent']}%")
            self.cpu_bar.setValue(int(metrics["cpu_percent"]))
            self.ram_bar.setValue(int(metrics["ram_percent"]))
            self.disk_bar.setValue(int(metrics["disk_percent"]))
            self.uptime_label.setText(
                f"System uptime: {metrics['uptime_seconds'] // 3600} hours"
            )
            self.ip_label.setText(f"IP address: {metrics['ip_address'] or 'Unavailable'}")
            if self.config.get("api_token"):
                self.status_label.setText("Monitoring active · syncing device telemetry")
                threading.Thread(
                    target=self.transmit_telemetry,
                    args=(dict(metrics),),
                    daemon=True
                ).start()
            else:
                self.status_label.setText("Monitoring active · device not registered with backend")
        except Exception as exc:
            self.status_label.setText(f"Metric collection failed: {exc}")

    def get_device_data(self):
        return {
            "id": self.config["device_id"],
            "hostname": socket.gethostname(),
            "display_name": self.config.get("display_name"),
            "os_name": f"{platform.system()} {platform.release()}",
            "agent_version": VERSION,
            "monitoring_enabled": self.monitoring_enabled,
            **self.latest_metrics
        }

    def set_monitoring(self, enabled):
        self.monitoring_enabled = bool(enabled)
        if enabled:
            self.refresh_metrics()
            self.timer.start(INTERVAL * 1000)
            self.pause_button.setText("Pause monitoring")
        else:
            self.timer.stop()
            self.status_label.setText("Monitoring paused")
            self.pause_button.setText("Resume monitoring")

    @staticmethod
    def get_ip_address():
        try:
            # UDP socket discovers the preferred local interface without sending data.
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("192.0.2.1", 80))
                return sock.getsockname()[0]
            finally:
                sock.close()
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
    app.setApplicationName(APP_NAME)
    window = CloudMonitor()
    window.show()
    sys.exit(app.exec())
