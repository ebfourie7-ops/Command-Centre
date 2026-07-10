#!/usr/bin/env python3
import json
import html
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QFileSystemModel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from command_intel import AdvancedCommandIntelPage


STATE_FILE = Path.home() / ".local/state/telemetry/telemetry.json"
TELEMETRY_URL = "http://127.0.0.1:9090/telemetry"
CONFIG_DIR = Path.home() / ".config/command-centre"
OFFLINE_CONFIG = CONFIG_DIR / "offline_knowledge.json"
CODEX_USAGE_CONFIG = CONFIG_DIR / "codex_usage.json"
USER_DEPLOYMENTS_CONFIG = CONFIG_DIR / "deployment_profiles.json"
INTEL_CONFIG = CONFIG_DIR / "command_intel.json"
APP_DIR = Path(__file__).resolve().parent
LOGO_FILE = APP_DIR / "ChatGPT Image Jul 9, 2026, 09_59_59 PM.png"
SPLASH_FILE = Path.home() / "Desktop/splash screen.png"
INVENTORY_DIR = APP_DIR / "inventory"
DEFAULT_DEPLOYMENTS_FILE = APP_DIR / "deployments/default_deployments.json"


MODULES = [
    ("dashboard", "SY", "System Dashboard"),
    ("control", "SC", "System Control"),
    ("tools", "TL", "Tool Library"),
    ("command_code", "CT", "Command Terminal"),
    ("intel", "CI", "Command Intel"),
    ("offline", "OK", "Offline Knowledge"),
    ("deployment", "DP", "Deployment Centre"),
    ("software", "SW", "Software Centre"),
]


MODULE_CARDS = {
    "software": [
        ("Packages", "Official repos, AUR queue, package export, Flatpak and AppImage inventory."),
        ("Maintenance", "Cache cleanup, package database repair, mirror refresh, and update review."),
        ("Libraries", "Installed tools grouped by category with docs and install state."),
    ],
    "tools": [
        ("Operations Tools", "Networking, diagnostics, recovery, storage, hardware, radio/SDR, and field launch groups."),
        ("Security & Forensics", "Authorized workflow tools for cases, evidence drives, hashing, imaging, metadata, and packet captures."),
        ("AI & Development", "Local AI, development tools, electronics, CAD, 3D printing, and documentation links."),
    ],
    "command_code": [
        ("Command Terminal", "Workspace files, terminal output, Codex chat, and command execution in one operations surface."),
        ("Build & Test", "Run checks, open project folders, review logs, and prepare command previews before execution."),
        ("Codex Modes", "Switch between Ask, Agent, Edit, and Review behavior before sending a workspace prompt."),
    ],
    "offline": [
        ("Indexes", "Arch Wiki mirrors, manuals, maps, repair docs, and technical references."),
        ("Libraries", "Wikipedia, Gutenberg, PDFs, electronics docs, and offline assets."),
        ("Search", "Future unified offline search with tags and full-text indexes."),
    ],
    "deployment": [
        ("ISO Profiles", "Stable, Testing, and Development CommandOS build presets."),
        ("Manifests", "Package lists, offline repository, branding, installer config, and presets."),
        ("Builds", "Build ISO, validate, checksum, write USB, and archive releases."),
    ],
}


INTEL_PROVIDERS = {
    "Username": [
        ("WhatsMyName", "https://whatsmyname.app/?q={q}"),
        ("GitHub", "https://github.com/search?q={q}&type=users"),
        ("Reddit", "https://www.reddit.com/search/?q={q}"),
        ("Google", 'https://www.google.com/search?q=%22{q}%22'),
        ("Bing", 'https://www.bing.com/search?q=%22{q}%22'),
    ],
    "Email": [
        ("Have I Been Pwned", "https://haveibeenpwned.com/account/{q}"),
        ("Gravatar", "https://www.google.com/search?q=site%3Agravatar.com+%22{q}%22"),
        ("Google", 'https://www.google.com/search?q=%22{q}%22'),
        ("Bing", 'https://www.bing.com/search?q=%22{q}%22'),
    ],
    "Domain": [
        ("VirusTotal", "https://www.virustotal.com/gui/domain/{q}"),
        ("SecurityTrails", "https://securitytrails.com/domain/{q}/history/a"),
        ("crt.sh", "https://crt.sh/?q={q}"),
        ("Wayback Machine", "https://web.archive.org/web/*/{q}"),
        ("Google", "https://www.google.com/search?q=site%3A{q}"),
    ],
    "IP Address": [
        ("Shodan", "https://www.shodan.io/host/{q}"),
        ("VirusTotal", "https://www.virustotal.com/gui/ip-address/{q}"),
        ("AbuseIPDB", "https://www.abuseipdb.com/check/{q}"),
        ("IPinfo", "https://ipinfo.io/{q}"),
    ],
    "Phone": [
        ("Google", 'https://www.google.com/search?q=%22{q}%22'),
        ("Bing", 'https://www.bing.com/search?q=%22{q}%22'),
        ("Truecaller", "https://www.truecaller.com/search/za/{q}"),
    ],
    "Person / Company": [
        ("Google", 'https://www.google.com/search?q=%22{q}%22'),
        ("Bing", 'https://www.bing.com/search?q=%22{q}%22'),
        ("LinkedIn", "https://www.linkedin.com/search/results/all/?keywords={q}"),
        ("OpenCorporates", "https://opencorporates.com/companies?q={q}"),
    ],
}

INTEL_CATEGORIES = [
    ("Search Engines", "SE", [("Google Advanced", "https://www.google.com/advanced_search"), ("Bing", "https://www.bing.com"), ("DuckDuckGo", "https://duckduckgo.com"), ("Brave Search", "https://search.brave.com"), ("Internet Archive", "https://archive.org")]),
    ("People & Identity", "PI", [("Webmii", "https://webmii.com"), ("PeekYou", "https://www.peekyou.com"), ("FamilySearch", "https://www.familysearch.org/search"), ("OpenCorporates", "https://opencorporates.com"), ("Google Scholar", "https://scholar.google.com")]),
    ("Usernames", "UN", [("WhatsMyName", "https://whatsmyname.app"), ("Namechk", "https://namechk.com"), ("NameCheckup", "https://namecheckup.com"), ("GitHub Search", "https://github.com/search"), ("Reddit Search", "https://www.reddit.com/search")]),
    ("Email & Phone", "EP", [("Have I Been Pwned", "https://haveibeenpwned.com"), ("Hunter", "https://hunter.io"), ("EmailRep", "https://emailrep.io"), ("Truecaller", "https://www.truecaller.com"), ("Phone Validator", "https://www.ipqualityscore.com/phone-number-validator")]),
    ("Social Media", "SM", [("Facebook", "https://www.facebook.com"), ("X / Twitter", "https://x.com/search"), ("LinkedIn", "https://www.linkedin.com/search/results/all/"), ("Instagram", "https://www.instagram.com"), ("Mastodon", "https://mastodon.social")]),
    ("Domains & IP", "DI", [("Shodan", "https://www.shodan.io"), ("VirusTotal", "https://www.virustotal.com/gui/home/search"), ("SecurityTrails", "https://securitytrails.com"), ("crt.sh", "https://crt.sh"), ("IPinfo", "https://ipinfo.io"), ("urlscan.io", "https://urlscan.io")]),
    ("Archives & Websites", "AW", [("Wayback Machine", "https://web.archive.org"), ("Archive.today", "https://archive.ph"), ("BuiltWith", "https://builtwith.com"), ("Wappalyzer", "https://www.wappalyzer.com/lookup/"), ("Whois", "https://who.is")]),
    ("Images & Metadata", "IM", [("Google Images", "https://images.google.com"), ("TinEye", "https://tineye.com"), ("Bing Visual Search", "https://www.bing.com/visualsearch"), ("Yandex Images", "https://yandex.com/images/"), ("FotoForensics", "https://fotoforensics.com"), ("Exif.tools", "https://exif.tools")]),
    ("Maps & Geolocation", "MG", [("Google Maps", "https://maps.google.com"), ("OpenStreetMap", "https://www.openstreetmap.org"), ("Bing Maps", "https://www.bing.com/maps"), ("Mapillary", "https://www.mapillary.com/app"), ("SunCalc", "https://www.suncalc.org"), ("GeoHints", "https://geohints.com")]),
    ("News & Verification", "NV", [("Google News", "https://news.google.com"), ("Reuters", "https://www.reuters.com"), ("AP News", "https://apnews.com"), ("Snopes", "https://www.snopes.com"), ("FactCheck.org", "https://www.factcheck.org"), ("Media Bias/Fact Check", "https://mediabiasfactcheck.com")]),
    ("Files & Documents", "FD", [("Google File Search", "https://www.google.com/search?q=filetype%3Apdf"), ("DocumentCloud", "https://www.documentcloud.org"), ("VirusTotal Files", "https://www.virustotal.com/gui/home/upload"), ("PDF Examiner", "https://pdfexaminer.com"), ("Metadata2Go", "https://www.metadata2go.com")]),
    ("Transport & Tracking", "TT", [("FlightRadar24", "https://www.flightradar24.com"), ("ADS-B Exchange", "https://globe.adsbexchange.com"), ("MarineTraffic", "https://www.marinetraffic.com"), ("VesselFinder", "https://www.vesselfinder.com"), ("NHTSA VIN Decoder", "https://vpic.nhtsa.dot.gov/decoder/")]),
    ("Threat Intelligence", "TI", [("AlienVault OTX", "https://otx.alienvault.com"), ("AbuseIPDB", "https://www.abuseipdb.com"), ("PhishTank", "https://phishtank.org"), ("GreyNoise", "https://viz.greynoise.io"), ("Censys", "https://search.censys.io")]),
    ("Frameworks & Training", "FT", [("OSINT Framework", "https://osintframework.com"), ("Bellingcat Toolkit", "https://bellingcat.gitbook.io/toolkit"), ("Trace Labs", "https://www.tracelabs.org"), ("IntelTechniques", "https://inteltechniques.com/tools/"), ("SANS OSINT", "https://www.sans.org/blog/list-of-resource-links-from-open-source-intelligence-summit-2024/")]),
]


class IntelAdBlocker(QWebEngineUrlRequestInterceptor):
    """Small privacy-focused blocker for the Command Intel embedded browser."""

    BLOCKED_HOST_PARTS = (
        "doubleclick.net", "googlesyndication.com", "googleadservices.com",
        "adservice.google.", "amazon-adsystem.com", "adsystem.com",
        "advertising.com", "adnxs.com", "adsrvr.org", "adroll.com",
        "criteo.com", "criteo.net", "taboola.com", "outbrain.com",
        "pubmatic.com", "rubiconproject.com", "openx.net", "yieldmo.com",
        "scorecardresearch.com", "quantserve.com", "moatads.com",
        "zedo.com", "revcontent.com", "mgid.com", "media.net",
        "hotjar.com", "fullstory.com", "mouseflow.com", "clarity.ms",
        "google-analytics.com", "googletagmanager.com", "analytics.google.com",
        "segment.io", "segment.com", "mixpanel.com", "amplitude.com",
        "facebook.net", "connect.facebook.net", "bat.bing.com",
        "branch.io", "appsflyer.com", "onesignal.com",
        "cookielaw.org", "onetrust.com", "trustarc.com",
    )

    def interceptRequest(self, info):
        host = info.requestUrl().host().lower()
        if any(part in host for part in self.BLOCKED_HOST_PARTS):
            info.block(True)


TOOL_GROUPS = [
    (
        "System & Diagnostics",
        [
            ("System Monitor", "plasma-systemmonitor", "KDE process, resource, and sensor monitor.", "plasma-systemmonitor"),
            ("Info Centre", "kinfocenter", "Hardware, driver, OpenGL, and system information.", "kinfocenter"),
            ("Partition Manager", "partitionmanager", "Disk and partition management.", "partitionmanager"),
            ("KDiskMark", "kdiskmark", "Storage benchmark utility.", "kdiskmark"),
        ],
    ),
    (
        "Networking",
        [
            ("Wireshark", "wireshark", "Packet capture and protocol analysis.", "wireshark-qt"),
            ("Nmap", "nmap", "Network discovery and service enumeration.", "nmap"),
            ("Remmina", "remmina", "Remote desktop client.", "remmina"),
            ("FileZilla", "filezilla", "FTP/SFTP transfer client.", "filezilla"),
        ],
    ),
    (
        "Security & Forensics",
        [
            ("Autopsy", "autopsy", "Digital forensics case analysis.", "autopsy"),
            ("Sleuth Kit", "fls", "Filesystem forensics command suite.", "sleuthkit"),
            ("ExifTool", "exiftool", "Metadata inspection and reporting.", "perl-image-exiftool"),
            ("Hashdeep", "hashdeep", "Recursive hashing and audit sets.", "hashdeep"),
        ],
    ),
    (
        "Radio & SDR",
        [
            ("GNU Radio Companion", "gnuradio-companion", "Signal flowgraph design and execution.", "gnuradio"),
            ("Gqrx", "gqrx", "SDR receiver and spectrum viewer.", "gqrx"),
            ("CubicSDR", "cubicsdr", "General SDR receiver.", "cubicsdr"),
            ("Dire Wolf", "direwolf", "APRS packet modem and decoder.", "direwolf"),
        ],
    ),
    (
        "Development & AI",
        [
            ("VS Code", "code", "Code editor and development workspace.", "code"),
            ("Git", "git", "Version control command line.", "git"),
            ("Docker", "docker", "Container runtime and tooling.", "docker"),
            ("Ollama", "ollama", "Local model runner.", "ollama"),
        ],
    ),
    (
        "Creation & CAD",
        [
            ("Blender", "blender", "3D modelling, rendering, and animation.", "blender"),
            ("FreeCAD", "freecad", "Parametric CAD design.", "freecad"),
            ("KiCad", "kicad", "Electronics schematic and PCB design.", "kicad"),
            ("PrusaSlicer", "prusa-slicer", "3D print slicing workflow.", "prusa-slicer"),
        ],
    ),
]


def run_text(command, timeout=2):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return "", str(error), 127


def read_telemetry():
    try:
        with urllib.request.urlopen(TELEMETRY_URL, timeout=0.8) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass

    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def command_exists(command):
    return shutil.which(command) is not None


def vscode_codex_candidates():
    extension_dir = Path.home() / ".vscode/extensions"
    candidates = extension_dir.glob("openai.chatgpt-*/bin/linux-x86_64/codex")
    return sorted(
        (path for path in candidates if path.exists() and os.access(path, os.X_OK)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def codex_binary_path():
    found = shutil.which("codex")
    if found:
        return found

    for candidate in vscode_codex_candidates():
        return str(candidate)

    return ""


def ensure_codex_on_path():
    command = codex_binary_path()
    if not command:
        return ""

    codex_dir = str(Path(command).parent)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if codex_dir not in path_parts:
        os.environ["PATH"] = os.pathsep.join([codex_dir, *path_parts])
    return command


def free_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch_terminal(title, command):
    terminal_commands = [
        ["konsole", "--new-tab", "--hold", "-p", f"tabtitle={title}", "-e", "bash", "-lc", command],
        ["alacritty", "-t", title, "-e", "bash", "-lc", command],
        ["kitty", "--title", title, "bash", "-lc", command],
        ["xterm", "-T", title, "-e", "bash", "-lc", command],
    ]

    for candidate in terminal_commands:
        if command_exists(candidate[0]):
            subprocess.Popen(candidate)
            return True, candidate[0]

    return False, "No supported terminal found."


def confirm(parent, title, message):
    answer = QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No)
    return answer == QMessageBox.Yes


def metric_value(data, key, fallback="--"):
    value = data.get(key)
    return fallback if value in (None, "") else str(value)


class MetricCard(QFrame):
    def __init__(self, title, color="#43d17a"):
        super().__init__()
        self.setObjectName("card")
        self.title = QLabel(title)
        self.title.setObjectName("muted")
        self.value = QLabel("--")
        self.value.setObjectName("metricValue")
        self.meta = QLabel("--")
        self.meta.setObjectName("muted")
        self.bar = QFrame()
        self.bar.setObjectName("bar")
        self.fill = QFrame(self.bar)
        self.fill.setStyleSheet(f"background: {color}; border-radius: 4px;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.meta)
        layout.addWidget(self.bar)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = int(self.bar.width() * getattr(self, "_percent", 0) / 100)
        self.fill.setGeometry(0, 0, width, self.bar.height())

    def set_metric(self, value, meta, percent):
        self.value.setText(value)
        self.meta.setText(meta)
        self._percent = max(0, min(100, float(percent or 0)))
        self.resizeEvent(None)


class CockpitCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        self.title = QLabel(title)
        self.title.setObjectName("panelTitle")
        self.body = QLabel("--")
        self.body.setObjectName("muted")
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.body)

    def set_text(self, text):
        self.body.setText(text)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.header = QLabel("--")
        self.header.setObjectName("healthHeader")
        self.hero_logo = QLabel()
        self.hero_logo.setObjectName("heroLogo")
        self.hero_logo.setFixedSize(168, 126)
        self.hero_logo.setAlignment(Qt.AlignCenter)
        if SPLASH_FILE.exists():
            pixmap = QPixmap(str(SPLASH_FILE))
            self.hero_logo.setPixmap(pixmap.scaled(168, 126, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.hero_logo.setText("C>")

        self.cpu = CockpitCard("CPU")
        self.gpu = CockpitCard("GPU")
        self.memory = CockpitCard("MEMORY")
        self.storage_summary = CockpitCard("STORAGE")
        self.health = CockpitCard("SYSTEM HEALTH")
        self.network = CockpitCard("NETWORK")
        self.processes = CockpitCard("TOP PROCESSES")
        self.storage = CockpitCard("STORAGE")
        self.alerts = CockpitCard("ALERTS & RECOMMENDATIONS")
        self.activity = CockpitCard("RECENT ACTIVITY")

        metrics = QGridLayout()
        for index, card in enumerate([self.cpu, self.gpu, self.memory, self.storage_summary]):
            metrics.addWidget(card, 0, index)

        middle = QGridLayout()
        middle.addWidget(self.health, 0, 0)
        middle.addWidget(self.network, 0, 1)
        middle.addWidget(self.processes, 1, 0)
        middle.addWidget(self.storage, 1, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.hero_panel())
        layout.addLayout(metrics)
        layout.addLayout(middle)
        layout.addWidget(self.alerts)
        layout.addWidget(self.activity)

    def hero_panel(self):
        frame = QFrame()
        frame.setObjectName("hero")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(18)

        copy = QVBoxLayout()
        eyebrow = QLabel("COMMAND CENTRE")
        eyebrow.setObjectName("heroEyebrow")
        title = QLabel("COMMAND OS")
        title.setObjectName("heroTitle")
        subtitle = QLabel("ONE SYSTEM, ONE MISSION")
        subtitle.setObjectName("heroSubtitle")
        copy.addStretch()
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        copy.addWidget(self.header)
        copy.addStretch()

        layout.addLayout(copy, 1)
        layout.addWidget(self.hero_logo)
        return frame

    def refresh(self, data, system):
        issues = self.issue_list(data, system)
        health = "HEALTHY"
        if len(issues) >= 4:
            health = "CRITICAL"
        elif len(issues) >= 2:
            health = "DEGRADED"
        elif issues:
            health = "WARNING"

        updates = system.get("updates")
        updates_text = "updates unknown" if updates is None else f"{updates} updates"
        self.header.setText(
            f"COMMANDOS    {health}    {metric_value(data, 'power_profile_label', 'Unknown').upper()}    "
            f"UPTIME {system.get('uptime', '--').replace('up ', '').upper()}    {updates_text.upper()}"
        )

        self.cpu.set_text(
            f"{float(data.get('cpu_usage') or 0):.1f}%   {metric_value(data, 'cpu_temp', 'n/a')}C\n"
            f"{metric_value(data, 'cpu_frequency', 'n/a')}\n"
            f"Load {system.get('load', '--')}"
        )
        self.gpu.set_text(
            f"{float(data.get('gpu_usage') or 0):.0f}%   {metric_value(data, 'gpu_temp', 'n/a')}C\n"
            f"{metric_value(data, 'gpu_vram', 'VRAM n/a')} VRAM\n"
            f"{metric_value(data, 'gpu_name', 'GPU')}"
        )
        self.memory.set_text(
            f"{metric_value(data, 'ram_info', '--')}\n"
            f"{float(data.get('ram_usage') or 0):.1f}% used\n"
            f"Swap {system.get('swap', '--')}"
        )
        self.storage_summary.set_text(
            f"{metric_value(data, 'storage_percent', '--')}%\n"
            f"{metric_value(data, 'storage_usage', '--')}\n"
            f"R {metric_value(data, 'storage_read', '0 B/s')}  W {metric_value(data, 'storage_write', '0 B/s')}"
        )

        self.health.set_text("\n".join(self.health_lines(data, system)))
        self.network.set_text(
            f"{metric_value(data, 'network_iface', 'offline')}    {system.get('connection', 'Connected')}\n"
            f"Down {metric_value(data, 'network_down', '0 B/s')}    Up {metric_value(data, 'network_up', '0 B/s')}\n"
            f"VPN {metric_value(data, 'vpn_status', 'VPN OFF')}\n"
            f"IP {system.get('local_ip', '--')}\n"
            f"Firewall {system.get('firewall', 'unknown')}"
        )
        self.processes.set_text("\n".join(system.get("top_processes", ["No process data"])))
        self.storage.set_text(
            f"ROOT    {metric_value(data, 'storage_percent', '--')}%    {system.get('storage_health', 'UNKNOWN')}\n"
            f"{metric_value(data, 'storage_name', 'ROOT')}    {metric_value(data, 'storage_usage', '--')}\n"
            f"Read {metric_value(data, 'storage_read', '0 B/s')}    Write {metric_value(data, 'storage_write', '0 B/s')}"
        )
        self.alerts.set_text("\n".join(issues) if issues else "OK  No immediate recommendations.")
        self.activity.set_text("\n".join(system.get("activity", ["No recent activity recorded."])))

    def health_lines(self, data, system):
        return [
            ("OK  No failed services" if system.get("failed", 0) == 0 else f"WARN  {system.get('failed')} failed service(s)"),
            ("OK  Storage below warning threshold" if float(data.get("storage_percent") or 0) < 85 else "WARN  Storage usage is high"),
            ("OK  Temperatures normal" if max(float(data.get("cpu_temp") or 0), float(data.get("gpu_temp") or 0)) < 80 else "WARN  Temperature is high"),
            ("OK  Battery present" if data.get("battery_status") not in ("", None, "n/a") else "INFO  Battery not reported"),
            ("WARN  Updates available" if (system.get("updates") or 0) > 0 else "OK  No updates reported"),
        ]

    def issue_list(self, data, system):
        issues = []
        if system.get("failed", 0) > 0:
            issues.append(f"WARN  {system.get('failed')} failed service(s) detected. Review diagnostics.")
        if system.get("updates"):
            issues.append(f"WARN  {system.get('updates')} system update(s) available. Open Software Centre.")
        if float(data.get("cpu_temp") or 0) >= 80:
            issues.append(f"WARN  CPU temperature is high at {data.get('cpu_temp')}C. Investigate cooling/load.")
        if float(data.get("gpu_temp") or 0) >= 80:
            issues.append(f"WARN  GPU temperature is high at {data.get('gpu_temp')}C. Investigate cooling/load.")
        if float(data.get("storage_percent") or 0) >= 85:
            issues.append(f"WARN  Root storage is {data.get('storage_percent')}% full. Free space or move data.")
        if data.get("vpn_status") == "VPN OFF":
            issues.append("INFO  VPN is off.")
        return issues


class ControlPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.power_buttons = {}
        self.profile_buttons = {}
        self.wifi_status = QLabel("--")
        self.bluetooth_status = QLabel("--")
        self.audio_combo = QComboBox()
        self.apply_queue = []
        self.service_filter = QLineEdit()
        self.service_filter.setPlaceholderText("Search services")
        self.service_filter.textChanged.connect(self.refresh_services)
        self.services = QListWidget()
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")

        layout = QVBoxLayout(self)
        title = QLabel("SYSTEM CONTROL")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(self.quick_controls_panel())
        layout.addWidget(self.system_section())
        layout.addWidget(self.commandos_section())
        layout.addWidget(self.result)

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def quick_controls_panel(self):
        frame, layout = self.panel("Quick Controls")
        layout.addWidget(self.active_profile_panel())
        layout.addWidget(self.power_panel())
        layout.addLayout(self.device_panels())
        layout.addWidget(self.audio_panel())
        layout.addWidget(self.service_panel())
        return frame

    def active_profile_panel(self):
        frame, layout = self.panel("Active Profile")
        row = QHBoxLayout()
        for profile, label, target_power in [
            ("daily", "Daily Driver", "balanced"),
            ("power", "Power Saver", "power-saver"),
            ("performance", "Performance", "performance"),
            ("gaming", "Gaming", "performance"),
            ("ai", "AI / Compute", "performance"),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, p=profile, power=target_power: self.set_commandos_profile(p, power))
            self.profile_buttons[profile] = button
            row.addWidget(button)
        layout.addLayout(row)
        note = QLabel("Profiles can apply multiple settings together. This base version maps profile power behavior first.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        return frame

    def power_panel(self):
        frame, layout = self.panel("Power Mode")
        row = QHBoxLayout()
        for profile, label in [
            ("power-saver", "Power Saver"),
            ("balanced", "Balanced"),
            ("performance", "Performance"),
            ("gaming", "Gaming"),
            ("ai-compute", "AI / Compute"),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, p=profile: self.set_power(p))
            self.power_buttons[profile] = button
            row.addWidget(button)
        layout.addLayout(row)
        return frame

    def device_panels(self):
        row = QHBoxLayout()

        wifi, wifi_layout = self.panel("Wi-Fi")
        wifi_layout.addWidget(self.wifi_status)
        wifi_on = QPushButton("Turn On")
        wifi_off = QPushButton("Turn Off")
        wifi_on.clicked.connect(lambda: self.set_wifi(True))
        wifi_off.clicked.connect(lambda: self.set_wifi(False))
        wifi_buttons = QHBoxLayout()
        wifi_buttons.addWidget(wifi_on)
        wifi_buttons.addWidget(wifi_off)
        wifi_layout.addLayout(wifi_buttons)

        bluetooth, bluetooth_layout = self.panel("Bluetooth")
        bluetooth_layout.addWidget(self.bluetooth_status)
        bt_on = QPushButton("Turn On")
        bt_off = QPushButton("Turn Off")
        bt_on.clicked.connect(lambda: self.set_bluetooth(True))
        bt_off.clicked.connect(lambda: self.set_bluetooth(False))
        bt_buttons = QHBoxLayout()
        bt_buttons.addWidget(bt_on)
        bt_buttons.addWidget(bt_off)
        bluetooth_layout.addLayout(bt_buttons)

        row.addWidget(wifi)
        row.addWidget(bluetooth)
        return row

    def audio_panel(self):
        frame, layout = self.panel("Audio & Devices")
        self.audio_combo.currentIndexChanged.connect(self.set_audio_sink)
        layout.addWidget(self.audio_combo)
        return frame

    def service_panel(self):
        frame, layout = self.panel("Services")
        self.services.itemSelectionChanged.connect(self.service_selection_changed)
        layout.addWidget(self.service_filter)
        layout.addWidget(self.services)

        row = QHBoxLayout()
        for label, action in [("Start", "start"), ("Stop", "stop"), ("Restart", "restart"), ("Enable", "enable"), ("Disable", "disable"), ("Logs", "logs")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, a=action: self.service_action(a))
            row.addWidget(button)
        layout.addLayout(row)
        return frame

    def feature_card(self, title, body):
        frame, layout = self.panel(title)
        label = QLabel(body)
        label.setObjectName("muted")
        label.setWordWrap(True)
        layout.addWidget(label)
        actions = self.feature_actions(title)
        if actions:
            row = QHBoxLayout()
            for button_label, action, target in actions:
                button = QPushButton(button_label)
                button.clicked.connect(lambda checked=False, a=action, t=target: self.run_feature_action(a, t))
                row.addWidget(button)
            row.addStretch()
            layout.addLayout(row)
        return frame

    def feature_actions(self, title):
        return {
            "Performance & Power": [("Power Settings", "kcm", "kcm_powerdevilprofilesconfig"), ("CPU Info", "kcm", "kcm_cpu"), ("Sensors", "kcm", "kcm_sensors")],
            "Graphics & Displays": [("Displays", "kcm", "kcm_kscreen"), ("Night Light", "kcm", "kcm_nightlight"), ("GPU Info", "kcm", "kcm_glx")],
            "Network": [("Connections", "kcm", "kcm_networkmanagement"), ("Firewall", "kcm", "kcm_firewall"), ("Proxy", "kcm", "kcm_proxy")],
            "Startup & Boot": [("Autostart", "kcm", "kcm_autostart"), ("Background Services", "kcm", "kcm_kded"), ("Boot Analysis", "terminal", "systemd-analyze blame; echo; systemd-analyze critical-chain")],
            "Users & Permissions": [("Users", "kcm", "kcm_users"), ("Sessions", "terminal", "loginctl list-sessions; echo; loginctl user-status $USER")],
            "Storage & Mounting": [("Automount", "kcm", "kcm_device_automounter"), ("Block Devices", "kcm", "kcm_block_devices"), ("Partition Manager", "app", "partitionmanager")],
            "Appearance & Desktop": [("Global Theme", "kcm", "kcm_lookandfeel"), ("Colors", "kcm", "kcm_colors"), ("Wallpaper", "kcm", "kcm_wallpaper")],
            "Time, Locale & Input": [("Date & Time", "kcm", "kcm_clock"), ("Keyboard", "kcm", "kcm_keyboard"), ("Mouse", "kcm", "kcm_mouse")],
            "Profiles": [("Gaming", "profile", "gaming"), ("AI / Compute", "profile", "ai"), ("Field", "profile", "field")],
            "Security Controls": [("Firewall", "kcm", "kcm_firewall"), ("Firmware Security", "kcm", "kcm_firmware_security"), ("Listening Ports", "terminal", "ss -tulpn")],
            "Snapshots & Recovery": [("Create Snapshot", "terminal", "sudo snapper create --description 'Command Centre manual snapshot'"), ("List Snapshots", "terminal", "snapper list"), ("Repair Packages", "terminal", "sudo pacman -Syu")],
            "Apply Queue": [("Stage Power Saver", "stage", "powerprofilesctl set power-saver"), ("Stage Performance", "stage", "powerprofilesctl set performance"), ("Show Queue", "queue", "show"), ("Apply Queue", "queue", "apply"), ("Clear Queue", "queue", "clear")],
            "Change History": [("Show History", "history", "show")],
        }.get(title, [])

    def run_feature_action(self, action, target):
        if action == "kcm":
            self.open_kcm(target)
        elif action == "app":
            self.open_app(target)
        elif action == "terminal":
            self.run_terminal_action(target)
        elif action == "profile":
            profiles = {
                "gaming": ("Gaming", "performance"),
                "ai": ("AI / Compute", "performance"),
                "field": ("Field", "power-saver"),
            }
            label, power = profiles[target]
            self.set_commandos_profile(target, power)
            self.parent_window.add_history(f"CommandOS profile button used: {label}")
        elif action == "stage":
            self.apply_queue.append(target)
            self.set_result("Staged change:\n" + target + "\n\nPending queue:\n" + "\n".join(self.apply_queue))
        elif action == "queue":
            self.queue_action(target)
        elif action == "history":
            self.set_result("\n".join(self.parent_window.change_history) or "No change history yet.")

    def open_kcm(self, module):
        if not command_exists("kcmshell6"):
            self.set_result("kcmshell6 is not available.")
            return
        subprocess.Popen(["kcmshell6", module])
        self.set_result(f"Opened KDE settings module: {module}")

    def open_app(self, command):
        if not command_exists(command):
            self.set_result(f"{command} is not installed.")
            return
        subprocess.Popen([command])
        self.set_result(f"Opened {command}.")

    def run_terminal_action(self, command):
        if not confirm(self, "Run System Tool", f"Run this command in a terminal?\n\n{command}"):
            return
        terminal_command = (
            f"{command}; "
            "status=$?; echo; "
            "echo \"Command finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal("Command Centre System Tool", terminal_command)
        self.set_result(f"Started in {terminal}:\n{command}" if ok else terminal)

    def queue_action(self, action):
        if not hasattr(self, "apply_queue"):
            self.apply_queue = []
        if action == "show":
            self.set_result("\n".join(self.apply_queue) or "Apply Queue is empty.")
        elif action == "clear":
            self.apply_queue = []
            self.set_result("Apply Queue cleared.")
        elif action == "apply":
            if not self.apply_queue:
                self.set_result("Apply Queue is empty.")
                return
            command = " && ".join(self.apply_queue)
            if not confirm(self, "Apply Queue", f"Apply these staged changes?\n\n{chr(10).join(self.apply_queue)}"):
                return
            self.run_terminal_action(command)
            self.parent_window.add_history(f"Applied {len(self.apply_queue)} queued change(s)")
            self.apply_queue = []

    def system_section(self):
        frame, layout = self.panel("System")
        grid = QGridLayout()
        cards = [
            ("Performance & Power", "CPU governor, boost, battery limits, sleep, hibernate, lid-close, screen timeout, thermal and fan controls."),
            ("Graphics & Displays", "GPU state, drivers, displays, resolution, refresh, scaling, HDR/VRR, brightness, Night Light, and display profiles."),
            ("Network", "Wi-Fi, Ethernet, Bluetooth, Airplane Mode, VPN, firewall, DNS profiles, hotspot, proxy, and interface toggles."),
            ("Startup & Boot", "Startup applications, boot targets, kernels, bootloader entries, diagnostics, previous boot, and reboot-required state."),
            ("Users & Permissions", "Users, groups, sessions, admin privileges, Polkit rules, autologin, locked accounts, and elevated capabilities."),
            ("Storage & Mounting", "Automount, persistent mounts, encrypted volumes, swap/zram, TRIM, removable-device policies, and cleanup."),
            ("Appearance & Desktop", "KDE theme, icons, cursor, fonts, wallpaper, accent, panels, effects, notifications, and CommandOS presets."),
            ("Time, Locale & Input", "Timezone, NTP, language, keyboard layouts, shortcuts, mouse/touchpad, touchscreen, and accessibility."),
        ]
        for index, (title, body) in enumerate(cards):
            grid.addWidget(self.feature_card(title, body), index // 2, index % 2)
        layout.addLayout(grid)
        return frame

    def commandos_section(self):
        frame, layout = self.panel("CommandOS")
        grid = QGridLayout()
        cards = [
            ("Profiles", "Stage and apply Daily Driver, Gaming, AI/Compute, Field, Recovery, and custom multi-setting profiles."),
            ("Security Controls", "Firewall, Secure Boot, encryption, lock policy, security updates, USB policy, SSH, listening services, and security profiles."),
            ("Snapshots & Recovery", "Create snapshots before major changes, view/restore snapshots, repair package state, regenerate initramfs, and rebuild bootloader config."),
            ("Apply Queue", "Advanced changes can be staged, reviewed, privilege-marked, and applied together instead of firing immediately."),
            ("Change History", "Review applied settings, privileged operations, service changes, profile switches, and failed actions."),
        ]
        for index, (title, body) in enumerate(cards):
            grid.addWidget(self.feature_card(title, body), index // 2, index % 2)
        layout.addLayout(grid)
        return frame

    def set_result(self, text):
        self.result.setPlainText(text)

    def refresh(self):
        power = self.parent_window.power_state()
        active = power.get("active", "unknown")
        for profile, button in self.power_buttons.items():
            button_active = profile == active or (profile in ("gaming", "ai-compute") and active == "performance")
            button.setProperty("active", button_active)
            button.style().unpolish(button)
            button.style().polish(button)
        for profile, button in self.profile_buttons.items():
            button.setProperty("active", (profile == "power" and active == "power-saver") or (profile == "daily" and active == "balanced"))
            button.style().unpolish(button)
            button.style().polish(button)

        wifi = self.parent_window.wifi_state()
        self.wifi_status.setText(wifi)
        bluetooth = self.parent_window.bluetooth_state()
        self.bluetooth_status.setText(bluetooth)

        current_sink, sinks = self.parent_window.audio_state()
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        for sink in sinks:
            self.audio_combo.addItem(sink, sink)
        index = self.audio_combo.findData(current_sink)
        if index >= 0:
            self.audio_combo.setCurrentIndex(index)
        self.audio_combo.blockSignals(False)

        self.refresh_services()

    def refresh_services(self):
        selected = self.selected_service()
        needle = self.service_filter.text().strip().lower()
        self.services.clear()
        for service in self.parent_window.user_services():
            haystack = f"{service['name']} {service['active']} {service['sub']} {service['description']}".lower()
            if needle and needle not in haystack:
                continue
            item = QListWidgetItem(f"{service['name']}  [{service['active']}/{service['sub']}]\n{service['description']}")
            item.setData(Qt.UserRole, service["name"])
            self.services.addItem(item)
            if selected == service["name"]:
                item.setSelected(True)

    def set_power(self, profile):
        actual_profile = "performance" if profile in ("gaming", "ai-compute") else profile
        label = profile.replace("-", " ").title()
        if not confirm(self, "Set power mode", f"Set power mode to {label}?\n\nCommand: powerprofilesctl set {actual_profile}"):
            return
        out, err, code = run_text(["powerprofilesctl", "set", actual_profile], 5)
        self.set_result(out or err or f"Power mode set to {label}." if code == 0 else "Power mode change failed.")
        self.parent_window.add_history(f"Power mode changed to {label}")
        self.parent_window.refresh_all()

    def set_commandos_profile(self, profile, power_profile):
        label = profile.replace("-", " ").replace("_", " ").title()
        if not confirm(self, "Set CommandOS profile", f"Apply {label} profile?\n\nCurrent base action: powerprofilesctl set {power_profile}"):
            return
        out, err, code = run_text(["powerprofilesctl", "set", power_profile], 5)
        self.set_result(out or err or f"CommandOS profile applied: {label}." if code == 0 else "Profile change failed.")
        self.parent_window.add_history(f"CommandOS profile applied: {label}")
        self.parent_window.refresh_all()

    def set_wifi(self, enabled):
        if not confirm(self, "Wi-Fi", f"Turn Wi-Fi {'on' if enabled else 'off'}?"):
            return
        out, err, code = run_text(["nmcli", "radio", "wifi", "on" if enabled else "off"], 5)
        self.set_result(out or err or f"Wi-Fi turned {'on' if enabled else 'off'}." if code == 0 else "Wi-Fi change failed.")
        self.parent_window.add_history(f"Wi-Fi turned {'on' if enabled else 'off'}")
        self.parent_window.refresh_all()

    def set_bluetooth(self, enabled):
        if not confirm(self, "Bluetooth", f"Turn Bluetooth {'on' if enabled else 'off'}?"):
            return
        out, err, code = run_text(["bluetoothctl", "power", "on" if enabled else "off"], 5)
        self.set_result(out or err or f"Bluetooth turned {'on' if enabled else 'off'}." if code == 0 else "Bluetooth change failed.")
        self.parent_window.add_history(f"Bluetooth turned {'on' if enabled else 'off'}")
        self.parent_window.refresh_all()

    def set_audio_sink(self):
        sink = self.audio_combo.currentData()
        if not sink:
            return
        if not confirm(self, "Audio output", f"Set default audio output to:\n{sink}?"):
            return
        out, err, code = run_text(["pactl", "set-default-sink", sink], 5)
        self.set_result(out or err or "Default audio output changed." if code == 0 else "Audio output change failed.")
        self.parent_window.add_history("Default audio output changed")
        self.parent_window.refresh_all()

    def selected_service(self):
        items = self.services.selectedItems()
        return items[0].data(Qt.UserRole) if items else ""

    def service_selection_changed(self):
        pass

    def service_action(self, action):
        service = self.selected_service()
        if not service:
            self.set_result("Select a service first.")
            return
        if not re.match(r"^[A-Za-z0-9_.@:\\-]+\.service$", service):
            self.set_result("Blocked invalid service name.")
            return

        if action == "logs":
            command = f"journalctl -u {service} -n 120 --no-pager"
            self.run_terminal_action(command)
            return

        command = f"sudo systemctl {action} {service}"
        if not confirm(self, "System service", f"Run this service action?\n\n{command}"):
            return
        terminal_command = (
            f"{command}; "
            "status=$?; echo; "
            "systemctl status --no-pager "
            f"{service}; "
            "echo; echo \"Service action finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal("Command Centre Service Action", terminal_command)
        self.set_result(f"Started in {terminal}:\n{command}" if ok else terminal)
        self.parent_window.add_history(f"System service {action}: {service}")
        self.parent_window.refresh_all()


class SoftwarePage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.status = QLabel("--")
        self.status.setObjectName("muted")
        self.tools_status = QLabel("--")
        self.tools_status.setObjectName("muted")
        self.package_search = QLineEdit()
        self.package_search.setPlaceholderText("Search packages")
        self.package_search.returnPressed.connect(self.search_packages)
        self.package_list = QListWidget()
        self.package_list.itemDoubleClicked.connect(lambda _: self.install_selected_package())
        self.kernel_status = QLabel("--")
        self.kernel_status.setObjectName("muted")
        self.available_kernels = QComboBox()
        self.installed_kernels = QListWidget()
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")

        layout = QVBoxLayout(self)
        title = QLabel("SOFTWARE CENTRE")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(self.update_panel())
        layout.addWidget(self.package_panel())
        layout.addWidget(self.kernel_panel())
        layout.addWidget(self.maintenance_panel())
        layout.addWidget(self.result)

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def update_panel(self):
        frame, layout = self.panel("System Updates")
        body = QLabel("Update official repositories and AUR packages from a terminal session.")
        body.setWordWrap(True)
        body.setObjectName("muted")
        layout.addWidget(body)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        update = QPushButton("Update System")
        update.clicked.connect(self.update_system)
        check = QPushButton("Check Updates")
        check.clicked.connect(self.refresh)
        flatpak = QPushButton("Update Flatpaks")
        flatpak.clicked.connect(self.update_flatpaks)
        row.addWidget(update)
        row.addWidget(check)
        row.addWidget(flatpak)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def package_panel(self):
        frame, layout = self.panel("Packages")
        layout.addWidget(self.tools_status)
        layout.addWidget(self.package_search)
        layout.addWidget(self.package_list)

        row = QHBoxLayout()
        for label, handler in [
            ("Search", self.search_packages),
            ("Install Selected", self.install_selected_package),
            ("Remove Selected", self.remove_selected_package),
            ("Export Package List", self.export_package_list),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def kernel_panel(self):
        frame, layout = self.panel("Kernel Manager")
        body = QLabel("Manage installed kernels through chwd-kernel. Install/remove actions open in a terminal and require confirmation.")
        body.setWordWrap(True)
        body.setObjectName("muted")
        layout.addWidget(body)
        layout.addWidget(self.kernel_status)

        grid = QGridLayout()
        available_label = QLabel("Available kernels")
        available_label.setObjectName("muted")
        installed_label = QLabel("Installed kernels")
        installed_label.setObjectName("muted")
        grid.addWidget(available_label, 0, 0)
        grid.addWidget(installed_label, 0, 1)
        grid.addWidget(self.available_kernels, 1, 0)
        grid.addWidget(self.installed_kernels, 1, 1)
        layout.addLayout(grid)

        row = QHBoxLayout()
        for label, handler in [
            ("Refresh Kernels", self.refresh_kernels),
            ("Install Selected", self.install_selected_kernel),
            ("Remove Selected", self.remove_selected_kernel),
            ("Rebuild Initramfs", self.rebuild_initramfs),
            ("Update GRUB", self.update_grub),
            ("Install CachyOS GUI", self.install_kernel_gui),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def maintenance_panel(self):
        frame, layout = self.panel("Maintenance")
        body = QLabel("Prepare repair and cleanup actions in a terminal so privilege prompts and package confirmations stay visible.")
        body.setWordWrap(True)
        body.setObjectName("muted")
        layout.addWidget(body)

        row = QHBoxLayout()
        for label, command in [
            ("Clean Package Cache", "sudo pacman -Sc"),
            ("Refresh Databases", "sudo pacman -Syy"),
            ("Repair Keyring", "sudo pacman-key --refresh-keys"),
            ("List Orphans", "pacman -Qtdq || true"),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, l=label, c=command: self.run_maintenance(l, c))
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def refresh(self):
        self.refresh_tools_status()
        self.refresh_kernels()
        repo_updates = []
        aur_updates = []

        if command_exists("checkupdates"):
            output = run_text(["checkupdates"], 8)[0]
            repo_updates = [line for line in output.splitlines() if line.strip()]

        if command_exists("yay"):
            output = run_text(["yay", "-Qua"], 10)[0]
            aur_updates = [line for line in output.splitlines() if line.strip()]
        elif command_exists("paru"):
            output = run_text(["paru", "-Qua"], 10)[0]
            aur_updates = [line for line in output.splitlines() if line.strip()]

        total = len(repo_updates) + len(aur_updates)
        self.status.setText(f"Available updates: {total} ({len(repo_updates)} repo, {len(aur_updates)} AUR)")

        preview = []
        if repo_updates:
            preview.append("Repository updates:")
            preview.extend(repo_updates[:20])
        if aur_updates:
            preview.append("")
            preview.append("AUR updates:")
            preview.extend(aur_updates[:20])
        self.result.setPlainText("\n".join(preview) if preview else "No updates reported by available tools.")

    def refresh_tools_status(self):
        tools = []
        for tool, label in [
            ("pacman", "pacman"),
            ("checkupdates", "checkupdates"),
            ("yay", "yay"),
            ("paru", "paru"),
            ("flatpak", "Flatpak"),
        ]:
            tools.append(f"{label}: {'available' if command_exists(tool) else 'missing'}")
        self.tools_status.setText("    ".join(tools))

    def clean_ansi(self, text):
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def refresh_kernels(self):
        self.available_kernels.clear()
        self.installed_kernels.clear()
        if not command_exists("chwd-kernel"):
            self.kernel_status.setText("chwd-kernel unavailable")
            return

        installed_raw = self.clean_ansi(run_text(["chwd-kernel", "--list-installed"], 8)[0])
        available_raw = self.clean_ansi(run_text(["chwd-kernel", "--list"], 8)[0])
        running = self.clean_ansi(run_text(["chwd-kernel", "--running-kernel"], 4)[0] or "")
        if not running:
            match = re.search(r"Currently running:\s*(.+)", installed_raw)
            running = match.group(1).strip() if match else run_text(["uname", "-r"], 2)[0]

        installed = []
        for line in installed_raw.splitlines():
            match = re.match(r"(?:local/)?(linux[\w.+-]*)\s+(.+)", line.strip())
            if match:
                installed.append((match.group(1), match.group(2)))
        for package, version in installed:
            item = QListWidgetItem(f"{package}  {version}")
            item.setData(Qt.UserRole, package)
            self.installed_kernels.addItem(item)

        seen = set()
        for line in available_raw.splitlines():
            match = re.match(r"(?:[\w.+-]+/)?(linux[\w.+-]*)\s+(.+)", line.strip())
            if not match:
                continue
            package, version = match.group(1), match.group(2)
            if package in seen:
                continue
            seen.add(package)
            self.available_kernels.addItem(f"{package}  {version}", package)

        self.kernel_status.setText(f"Running: {running or '--'}    Installed kernels: {len(installed)}    Available kernels: {self.available_kernels.count()}")

    def selected_installed_kernel(self):
        selected = self.installed_kernels.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else ""

    def selected_available_kernel(self):
        return self.available_kernels.currentData() or ""

    def install_selected_kernel(self):
        package = self.selected_available_kernel()
        if not package:
            self.result.setPlainText("Select an available kernel first.")
            return
        command = f"sudo chwd-kernel --install {shlex.quote(package)}"
        if not confirm(self, "Install Kernel", f"Install this kernel?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Install Kernel {package}", command):
            self.parent_window.add_history(f"Kernel install started: {package}")

    def remove_selected_kernel(self):
        package = self.selected_installed_kernel()
        if not package:
            self.result.setPlainText("Select an installed kernel first.")
            return
        running = run_text(["uname", "-r"], 2)[0]
        if package in running:
            self.result.setPlainText("Refusing to remove the currently running kernel.")
            return
        command = f"sudo chwd-kernel --remove {shlex.quote(package)}"
        if not confirm(self, "Remove Kernel", f"Remove this installed kernel?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Remove Kernel {package}", command):
            self.parent_window.add_history(f"Kernel removal started: {package}")

    def rebuild_initramfs(self):
        command = "sudo mkinitcpio -P"
        if not confirm(self, "Rebuild Initramfs", f"Rebuild initramfs for all kernels?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Rebuild Initramfs", command):
            self.parent_window.add_history("Initramfs rebuild started")

    def update_grub(self):
        command = "sudo grub-mkconfig -o /boot/grub/grub.cfg"
        if not confirm(self, "Update GRUB", f"Regenerate GRUB configuration?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Update GRUB", command):
            self.parent_window.add_history("GRUB update started")

    def install_kernel_gui(self):
        command = self.package_install_command("cachyos-kernel-manager")
        if not confirm(self, "Install CachyOS Kernel Manager", f"Install the CachyOS Kernel Manager GUI?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Install CachyOS Kernel Manager", command):
            self.parent_window.add_history("CachyOS Kernel Manager install started")

    def update_command(self):
        if command_exists("yay"):
            return "yay -Syu"
        if command_exists("paru"):
            return "paru -Syu"
        return "sudo pacman -Syu"

    def update_system(self):
        command = self.update_command()
        message = (
            "Run a full system update in a terminal?\n\n"
            f"Command:\n{command}\n\n"
            "The terminal will handle password prompts and package confirmations."
        )
        if not confirm(self, "Update System", message):
            return

        terminal_command = (
            f"{command}; "
            "status=$?; "
            "echo; "
            "echo \"Command Centre update finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal("Command Centre Update", terminal_command)
        if ok:
            self.result.setPlainText(f"Started system update in {terminal}.\n\n{command}")
        else:
            self.result.setPlainText(terminal)

    def terminal_command(self, title, command):
        terminal_command = (
            f"{command}; "
            "status=$?; "
            "echo; "
            "echo \"Command Centre command finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal(title, terminal_command)
        self.result.setPlainText(f"Started in {terminal}:\n{command}" if ok else terminal)
        return ok

    def update_flatpaks(self):
        if not command_exists("flatpak"):
            self.result.setPlainText("Flatpak is not installed.")
            return
        command = "flatpak update"
        if not confirm(self, "Update Flatpaks", f"Run Flatpak updates?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Command Centre Flatpak Update", command):
            self.parent_window.add_history("Flatpak update started")

    def search_packages(self):
        query = self.package_search.text().strip()
        self.package_list.clear()
        if len(query) < 2:
            self.result.setPlainText("Type at least two characters to search packages.")
            return
        if not command_exists("pacman"):
            self.result.setPlainText("pacman is not available.")
            return

        output, err, code = run_text(["pacman", "-Ss", query], 12)
        if code != 0 and not output:
            self.result.setPlainText(err or "Package search failed.")
            return

        current_name = ""
        current_title = ""
        count = 0
        for line in output.splitlines():
            if not line.startswith(" "):
                parts = line.split(None, 1)
                if not parts:
                    continue
                current_name = parts[0].split("/", 1)[-1]
                current_title = line
            elif current_name:
                description = line.strip()
                item = QListWidgetItem(f"{current_title}\n{description}")
                item.setData(Qt.UserRole, current_name)
                self.package_list.addItem(item)
                current_name = ""
                current_title = ""
                count += 1
                if count >= 80:
                    break

        self.result.setPlainText(f"Found {count} package result(s) for '{query}'. Double-click a result to install it.")

    def selected_package(self):
        selected = self.package_list.selectedItems()
        if not selected:
            return ""
        package = selected[0].data(Qt.UserRole) or ""
        return package if re.match(r"^[A-Za-z0-9@._+:-]+$", package) else ""

    def package_install_command(self, package):
        if command_exists("yay"):
            return f"yay -S {shlex.quote(package)}"
        if command_exists("paru"):
            return f"paru -S {shlex.quote(package)}"
        return f"sudo pacman -S {shlex.quote(package)}"

    def install_selected_package(self):
        package = self.selected_package()
        if not package:
            self.result.setPlainText("Select a package result first.")
            return
        command = self.package_install_command(package)
        if not confirm(self, "Install Package", f"Install this package?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Install {package}", command):
            self.parent_window.add_history(f"Package install started: {package}")

    def remove_selected_package(self):
        package = self.selected_package()
        if not package:
            self.result.setPlainText("Select a package result first.")
            return
        command = f"sudo pacman -Rns {shlex.quote(package)}"
        if not confirm(self, "Remove Package", f"Remove this package and unused dependencies?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Remove {package}", command):
            self.parent_window.add_history(f"Package removal started: {package}")

    def export_package_list(self):
        timestamp = time.strftime("%Y%m%d-%H%M")
        destination = Path.home() / f"command-centre-package-list-{timestamp}.txt"
        sections = []
        if command_exists("pacman"):
            native, _, _ = run_text(["pacman", "-Qqe"], 12)
            sections.append("# Native explicitly installed packages\n" + (native or "Unavailable"))
        if command_exists("flatpak"):
            flatpak, _, _ = run_text(["flatpak", "list", "--app", "--columns=application,name,version"], 12)
            sections.append("# Flatpak applications\n" + (flatpak or "No Flatpak applications reported"))
        try:
            destination.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        except Exception as error:
            self.result.setPlainText(f"Unable to export package list:\n{error}")
            return
        self.result.setPlainText(f"Exported package list:\n{destination}")
        self.parent_window.add_history("Package list exported")

    def run_maintenance(self, label, command):
        if not confirm(self, label, f"Run this maintenance command in a terminal?\n\n{command}"):
            return
        if self.terminal_command(f"Command Centre - {label}", command):
            self.parent_window.add_history(f"Software maintenance started: {label}")


class ToolLibraryPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.tools = []
        self.filtered_tools = []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search installed packages, Flatpaks, launchers, and executable tools")
        self.search.textChanged.connect(self.render_tools)
        self.kind_filter = QComboBox()
        for label, value in [
            ("All", "all"),
            ("Packages", "package"),
            ("AUR / Foreign", "aur"),
            ("Flatpaks", "flatpak"),
            ("Desktop Apps", "desktop"),
            ("Executables", "executable"),
            ("Curated", "curated"),
        ]:
            self.kind_filter.addItem(label, value)
        self.kind_filter.currentIndexChanged.connect(self.render_tools)
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self.selection_changed)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("textPanel")
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")
        self.status = QLabel("--")
        self.status.setObjectName("muted")
        self.auto_refresh = QTimer(self)
        self.auto_refresh.timeout.connect(self.refresh_if_changed)
        self.auto_refresh.start(60000)

        layout = QVBoxLayout(self)
        title = QLabel("TOOL LIBRARY")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(self.status)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.kind_filter)
        refresh = QPushButton("Refresh Library")
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        layout.addLayout(controls)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.detail, 1)
        actions = QHBoxLayout()
        for label, handler in [
            ("Launch", self.launch_selected_tool),
            ("Open in Terminal", self.open_selected_terminal),
            ("Install", self.install_selected_tool),
            ("Guide", self.open_selected_guide),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        right_layout.addLayout(actions)
        right_layout.addWidget(self.result)
        split.addWidget(right)
        split.setSizes([420, 650])
        layout.addWidget(split, 1)
        self.refresh()

    def refresh(self):
        self.tools = self.build_library()
        self.render_tools()
        self.result.setPlainText("Tool Library refreshed from the live system.")

    def refresh_if_changed(self):
        updated = self.build_library()
        old_signature = {(tool["key"], tool.get("command", "")) for tool in self.tools}
        new_signature = {(tool["key"], tool.get("command", "")) for tool in updated}
        if old_signature == new_signature:
            return
        self.tools = updated
        self.render_tools()
        self.result.setPlainText("Tool Library auto-refreshed after installed apps/tools changed.")

    def live_command_lines(self, command, timeout=12):
        output, _, code = run_text(command, timeout)
        return [line.strip() for line in output.splitlines() if line.strip()] if code == 0 else []

    def live_or_inventory_lines(self, prefix, command, timeout=12):
        live = self.live_command_lines(command, timeout)
        return live or self.read_inventory_lines(prefix)

    def latest_inventory_file(self, prefix):
        files = sorted(INVENTORY_DIR.glob(f"{prefix}-*.txt"))
        return files[-1] if files else None

    def read_inventory_lines(self, prefix):
        file_path = self.latest_inventory_file(prefix)
        if not file_path:
            return []
        try:
            return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return []

    def curated_descriptions(self):
        descriptions = {}
        for group, tools in TOOL_GROUPS:
            for name, command, description, package in tools:
                descriptions[package] = {
                    "name": name,
                    "command": command,
                    "description": description,
                    "package": package,
                    "group": group,
                }
                descriptions[command] = descriptions[package]
        return descriptions

    def build_library(self):
        curated = self.curated_descriptions()
        explicit = self.live_or_inventory_lines("pacman-explicit", ["pacman", "-Qqe"]) if command_exists("pacman") else self.read_inventory_lines("pacman-explicit")
        aur = set(self.live_or_inventory_lines("pacman-foreign-aur", ["pacman", "-Qqm"]) if command_exists("pacman") else self.read_inventory_lines("pacman-foreign-aur"))
        flatpaks = self.live_or_inventory_lines("flatpak-apps", ["flatpak", "list", "--app", "--columns=application,name,version,branch,origin"]) if command_exists("flatpak") else self.read_inventory_lines("flatpak-apps")
        executables = set(self.live_executables() or self.read_inventory_lines("executable-tools"))
        desktop_apps = self.live_desktop_apps()
        tools = []
        seen = set()

        for package in explicit:
            info = curated.get(package, {})
            command = info.get("command") or (package if package in executables or command_exists(package) else "")
            kind = "aur" if package in aur else "package"
            tools.append(
                {
                    "key": f"{kind}:{package}",
                    "name": info.get("name") or package,
                    "package": package,
                    "command": command,
                    "kind": kind,
                    "group": info.get("group") or ("AUR / Foreign" if kind == "aur" else "Installed Package"),
                    "description": info.get("description") or f"Installed package from {'AUR/foreign source' if kind == 'aur' else 'pacman repositories'}.",
                    "installed": True,
                }
            )
            seen.add(command or package)

        for row in flatpaks:
            parts = row.split("\t")
            app_id = parts[0]
            name = parts[1] if len(parts) > 1 and parts[1] else app_id
            version = parts[2] if len(parts) > 2 else ""
            tools.append(
                {
                    "key": f"flatpak:{app_id}",
                    "name": name,
                    "package": app_id,
                    "command": f"flatpak run {shlex.quote(app_id)}",
                    "kind": "flatpak",
                    "group": "Flatpak",
                    "description": f"Flatpak application{f' version {version}' if version else ''}.",
                    "installed": True,
                }
            )

        for desktop in desktop_apps:
            command = desktop.get("command", "")
            executable = shlex.split(command)[0] if command else ""
            key_name = desktop.get("desktop_id") or desktop.get("name") or command
            if executable and executable in seen:
                continue
            tools.append(
                {
                    "key": f"desktop:{key_name}",
                    "name": desktop.get("name") or key_name,
                    "package": executable or desktop.get("desktop_id") or key_name,
                    "desktop_id": desktop.get("desktop_id", ""),
                    "command": command,
                    "kind": "desktop",
                    "group": "Desktop App",
                    "description": desktop.get("description") or "Installed desktop launcher discovered from application entries.",
                    "installed": True,
                }
            )
            if executable:
                seen.add(executable)

        for command in sorted(executables):
            if command in seen:
                continue
            info = curated.get(command, {})
            tools.append(
                {
                    "key": f"executable:{command}",
                    "name": info.get("name") or command,
                    "package": info.get("package") or command,
                    "command": command,
                    "kind": "curated" if info else "executable",
                    "group": info.get("group") or "Executable Tool",
                    "description": info.get("description") or "Executable command found in /usr/bin, /usr/local/bin, or ~/.local/bin.",
                    "installed": True,
                }
            )

        tools.sort(key=lambda item: (item["group"], item["name"].lower()))
        return tools

    def live_executables(self):
        names = set()
        for folder in [Path("/usr/bin"), Path("/usr/local/bin"), Path.home() / ".local/bin"]:
            if not folder.exists():
                continue
            try:
                for child in folder.iterdir():
                    if child.is_file() and os.access(child, os.X_OK):
                        names.add(child.name)
            except OSError:
                continue
        return sorted(names)

    def live_desktop_apps(self):
        apps = []
        folders = [Path("/usr/share/applications"), Path.home() / ".local/share/applications"]
        for folder in folders:
            if not folder.exists():
                continue
            try:
                files = sorted(folder.glob("*.desktop"))
            except OSError:
                continue
            for file_path in files:
                app = self.parse_desktop_file(file_path)
                if app:
                    apps.append(app)
        return apps

    def parse_desktop_file(self, file_path):
        name = ""
        exec_line = ""
        comment = ""
        no_display = False
        try:
            for raw in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("Name=") and not name:
                    name = line.split("=", 1)[1].strip()
                elif line.startswith("Exec=") and not exec_line:
                    exec_line = line.split("=", 1)[1].strip()
                elif line.startswith("Comment=") and not comment:
                    comment = line.split("=", 1)[1].strip()
                elif line.startswith("NoDisplay="):
                    no_display = line.split("=", 1)[1].strip().lower() == "true"
        except OSError:
            return None
        if not name or not exec_line or no_display:
            return None
        command = re.sub(r"\s+%[fFuUdDnNickvm]", "", exec_line).strip()
        return {"desktop_id": file_path.name, "name": name, "command": command, "description": comment}

    def render_tools(self):
        selected_key = self.selected_tool().get("key") if self.selected_tool() else ""
        needle = self.search.text().strip().lower()
        kind = self.kind_filter.currentData() or "all"
        self.list.clear()
        self.filtered_tools = []
        for tool in self.tools:
            haystack = f"{tool['name']} {tool['package']} {tool['command']} {tool['group']} {tool['description']}".lower()
            if needle and needle not in haystack:
                continue
            if kind != "all" and tool["kind"] != kind:
                continue
            self.filtered_tools.append(tool)
            item = QListWidgetItem(self.item_label(tool))
            item.setData(Qt.UserRole, tool)
            self.list.addItem(item)
            if selected_key and tool["key"] == selected_key:
                item.setSelected(True)
        if not self.list.selectedItems() and self.list.count():
            self.list.item(0).setSelected(True)
        self.status.setText(f"{len(self.filtered_tools)} shown / {len(self.tools)} live library entries loaded.")
        self.selection_changed()

    def item_label(self, tool):
        command = tool["command"] or "no launch command detected"
        return f"{tool['name']}  [{tool['group']}]\n{command}"

    def selected_tool(self):
        selected = self.list.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else None

    def selection_changed(self):
        tool = self.selected_tool()
        if not tool:
            self.detail.setPlainText("Select a tool.")
            return
        self.detail.setPlainText(self.guide_text(tool))

    def launch_selected_tool(self):
        tool = self.selected_tool()
        if not tool:
            return
        command = tool["command"]
        if not command:
            self.result.setPlainText(f"No launch command was detected for {tool['name']}.")
            return
        if tool["kind"] == "flatpak":
            subprocess.Popen(["bash", "-lc", command])
        elif command_exists(shlex.split(command)[0]):
            subprocess.Popen(shlex.split(command))
        else:
            self.result.setPlainText(f"{command} is not available.")
            return
        self.result.setPlainText(f"Launched {tool['name']}.\n{command}")
        self.parent_window.add_history(f"Tool launched: {tool['name']}")

    def open_selected_terminal(self):
        tool = self.selected_tool()
        if not tool:
            return
        command = tool["command"] or tool["package"]
        shell_command = (
            f"{command}; "
            "status=$?; echo; "
            "echo \"Tool finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal(f"Command Centre - {tool['name']}", shell_command)
        self.result.setPlainText(f"Started {tool['name']} in {terminal}." if ok else terminal)
        self.parent_window.add_history(f"Tool terminal opened: {tool['name']}")

    def install_selected_tool(self):
        tool = self.selected_tool()
        if not tool:
            return
        command = self.install_command(tool)
        if not command:
            self.result.setPlainText("No supported installer was detected for this entry.")
            return
        if not confirm(self, "Install Tool", f"Install or repair {tool['name']}?\n\nCommand:\n{command}"):
            return
        shell_command = (
            f"{command}; "
            "status=$?; echo; "
            "echo \"Install finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal(f"Install {tool['name']}", shell_command)
        self.result.setPlainText(f"Started install in {terminal}:\n{command}" if ok else terminal)
        self.parent_window.add_history(f"Tool install started: {tool['name']}")

    def install_command(self, tool):
        if tool["kind"] == "flatpak":
            return f"flatpak install flathub {shlex.quote(tool['package'])}" if command_exists("flatpak") else ""
        package = tool["package"]
        if command_exists("yay"):
            return f"yay -S --needed {shlex.quote(package)}"
        if command_exists("paru"):
            return f"paru -S --needed {shlex.quote(package)}"
        if command_exists("pacman"):
            return f"sudo pacman -S --needed {shlex.quote(package)}"
        return ""

    def open_selected_guide(self):
        tool = self.selected_tool()
        if not tool:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{tool['name']} Guide")
        dialog.resize(760, 620)
        layout = QVBoxLayout(dialog)
        guide = QTextEdit()
        guide.setReadOnly(True)
        guide.setObjectName("textPanel")
        guide.setPlainText(self.guide_text(tool))
        layout.addWidget(guide)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def guide_text(self, tool):
        command = tool["command"] or tool["package"]
        executable = command.split()[0] if command else ""
        install = self.install_command(tool) or "No supported install command detected."
        help_commands = []
        if tool["kind"] == "flatpak":
            help_commands = [
                f"flatpak info {tool['package']}",
                f"flatpak run {tool['package']}",
                f"flatpak update {tool['package']}",
            ]
        else:
            help_commands = [
                f"{executable} --help",
                f"man {executable}",
                f"{executable} --version",
                f"pacman -Qi {tool['package']}",
            ]
        return (
            f"{tool['name']}\n"
            f"{'=' * len(tool['name'])}\n\n"
            f"Group: {tool['group']}\n"
            f"Type: {tool['kind']}\n"
            f"Package/App ID: {tool['package']}\n"
            f"Launch command: {command or 'No command detected'}\n"
            f"Install command: {install}\n\n"
            f"Description\n"
            f"-----------\n{tool['description']}\n\n"
            f"Guide\n"
            f"-----\n"
            f"Use this entry to launch, inspect, install/repair, and learn the command. "
            f"For graphical tools, Launch opens the application. For terminal tools, Open in Terminal is usually the better first action.\n\n"
            f"Command Library\n"
            f"---------------\n"
            f"Launch:\n  {command or 'No launch command detected'}\n\n"
            f"Open in terminal:\n  {command or tool['package']}\n\n"
            f"Install / repair:\n  {install}\n\n"
            f"Useful guide commands:\n  " + "\n  ".join(help_commands) + "\n\n"
            f"Notes\n"
            f"-----\n"
            f"- Launch opens the app or command directly when possible.\n"
            f"- Terminal runs the command in a terminal and keeps the window open.\n"
            f"- Install uses yay/paru when available, then pacman as fallback. Flatpaks use flathub.\n"
            f"- For command-line tools, start with --help or man pages for full usage.\n"
        )


class ReaderFullscreenDialog(QDialog):
    def __init__(self, url, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))

        self.reader = QWebEngineView()
        self.reader.load(url)

        exit_button = QPushButton("Exit Full Screen")
        exit_button.clicked.connect(self.accept)

        top = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        top.addWidget(heading)
        top.addStretch()
        top.addWidget(exit_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addLayout(top)
        layout.addWidget(self.reader, 1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)


class OfflineKnowledgePage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.locations = []
        self.zim_files = []
        self.kiwix_process = None
        self.kiwix_port = None
        self.reader_url = None
        self.reader_title = "Offline Knowledge Reader"
        self.reader_started_at = 0
        self.library_button = QPushButton("Select ZIM Library Location")
        self.library_button.clicked.connect(self.select_library_location)
        self.fullscreen_button = QPushButton("Full Screen Reader")
        self.fullscreen_button.clicked.connect(self.open_fullscreen_reader)
        self.fullscreen_button.setEnabled(False)
        self.browser_button = QPushButton("Open in Browser")
        self.browser_button.clicked.connect(self.open_reader_browser)
        self.browser_button.setEnabled(False)
        self.library_label = QLabel("No ZIM library selected.")
        self.library_label.setObjectName("muted")
        self.zim_list = QListWidget()
        self.reader = QWebEngineView()
        self.reader.setMinimumHeight(420)
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")

        layout = QVBoxLayout(self)
        layout.addWidget(self.library_panel())
        layout.addWidget(self.zim_list)
        layout.addWidget(self.reader)
        layout.addWidget(self.result)

        self.zim_list.itemClicked.connect(lambda _: self.open_selected_zim())
        self.load_config()
        self.scan_locations()

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def library_panel(self):
        frame, layout = self.panel("Offline Knowledge")
        row = QHBoxLayout()
        row.addWidget(self.library_button)
        row.addWidget(self.fullscreen_button)
        row.addWidget(self.browser_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.library_label)
        return frame

    def load_config(self):
        try:
            data = json.loads(OFFLINE_CONFIG.read_text())
            self.locations = [Path(item) for item in data.get("locations", [])]
        except Exception:
            self.locations = []
        self.render_library_location()

    def save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        OFFLINE_CONFIG.write_text(json.dumps({"locations": [str(path) for path in self.locations]}, indent=2))

    def render_library_location(self):
        if self.locations:
            self.library_label.setText(str(self.locations[0]))
        else:
            self.library_label.setText("No ZIM library selected.")

    def select_library_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select ZIM library location", str(Path.home()))
        if folder:
            self.locations = [Path(folder).expanduser()]
            self.save_config()
            self.render_library_location()
            self.scan_locations()

    def scan_locations(self):
        files = []
        seen = set()
        for location in self.locations:
            if location.is_file() and location.suffix.lower() == ".zim":
                candidates = [location]
            elif location.is_dir():
                candidates = location.rglob("*.zim")
            else:
                candidates = []

            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                except OSError:
                    continue
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(resolved)

        self.zim_files = sorted(files, key=lambda item: item.name.lower())
        self.render_zim_files()
        self.result.setPlainText(f"Found {len(self.zim_files)} ZIM file(s).")

    def render_zim_files(self):
        self.zim_list.clear()
        for zim in self.zim_files:
            size_gb = zim.stat().st_size / 1073741824 if zim.exists() else 0
            item = QListWidgetItem(f"{zim.name}\n{size_gb:.2f} GB - {zim.parent}")
            item.setData(Qt.UserRole, zim)
            self.zim_list.addItem(item)

    def selected_zim(self):
        selected = self.zim_list.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else None

    def open_selected_zim(self):
        zim = self.selected_zim()
        if not zim:
            self.result.setPlainText("Select a ZIM file first.")
            return

        if not command_exists("kiwix-serve"):
            self.reader.setHtml(
                "<h2>Command Centre ZIM reader backend is not installed</h2>"
                "<p>Install <b>kiwix-tools</b> to open ZIM files inside Command Centre.</p>"
            )
            self.reader_url = None
            self.fullscreen_button.setEnabled(False)
            self.browser_button.setEnabled(False)
            self.result.setPlainText("Missing kiwix-serve. Command Centre needs kiwix-tools to read ZIM files internally.")
            self.install_zim_backend()
            return

        self.stop_kiwix_server()
        self.kiwix_port = free_local_port()
        self.reader_title = zim.name
        self.reader_url = QUrl(f"http://127.0.0.1:{self.kiwix_port}/")
        self.reader_started_at = time.time()
        self.fullscreen_button.setEnabled(False)
        self.browser_button.setEnabled(False)
        self.kiwix_process = subprocess.Popen(
            ["kiwix-serve", f"--port={self.kiwix_port}", str(zim)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        QTimer.singleShot(500, self.load_reader)
        self.result.setPlainText(f"Starting reader for:\n{zim}\n\nLarge ZIM files can take a few seconds to become ready.")

    def load_reader(self):
        if not self.kiwix_process or self.kiwix_process.poll() is not None:
            stderr = ""
            if self.kiwix_process and self.kiwix_process.stderr:
                stderr = self.kiwix_process.stderr.read()
            self.reader.setHtml("<h2>Unable to start ZIM reader</h2><p>kiwix-serve did not stay running.</p>")
            self.reader_url = None
            self.fullscreen_button.setEnabled(False)
            self.browser_button.setEnabled(False)
            self.result.setPlainText(stderr or "Unable to start kiwix-serve for the selected ZIM.")
            return

        if not self.reader_server_ready():
            elapsed = time.time() - self.reader_started_at
            if elapsed < 25:
                self.result.setPlainText(f"Waiting for ZIM reader to become ready... {elapsed:.0f}s")
                QTimer.singleShot(700, self.load_reader)
                return
            self.reader.setHtml("<h2>ZIM reader is still starting</h2><p>The Kiwix server did not respond within 25 seconds.</p>")
            self.result.setPlainText("kiwix-serve is running, but did not answer HTTP checks within 25 seconds. Try Open in Browser or select the ZIM again.")
            self.browser_button.setEnabled(True)
            return

        self.reader.load(self.reader_url)
        self.fullscreen_button.setEnabled(True)
        self.browser_button.setEnabled(True)
        self.result.setPlainText(f"Reader ready:\n{self.reader_url.toString()}")

    def reader_server_ready(self):
        if not self.reader_url:
            return False
        try:
            with urllib.request.urlopen(self.reader_url.toString(), timeout=0.8) as response:
                return response.status < 500
        except Exception:
            return False

    def open_fullscreen_reader(self):
        if not self.reader_url:
            self.result.setPlainText("Open a ZIM file first.")
            return
        dialog = ReaderFullscreenDialog(self.reader.url() if self.reader.url().isValid() else self.reader_url, self.reader_title, self)
        dialog.showFullScreen()
        dialog.exec()

    def open_reader_browser(self):
        if not self.reader_url:
            self.result.setPlainText("Open a ZIM file first.")
            return
        if command_exists("xdg-open"):
            subprocess.Popen(["xdg-open", self.reader_url.toString()])
            self.result.setPlainText(f"Opened reader in browser:\n{self.reader_url.toString()}")
        else:
            self.result.setPlainText(f"Reader URL:\n{self.reader_url.toString()}")

    def stop_kiwix_server(self):
        if self.kiwix_process and self.kiwix_process.poll() is None:
            self.kiwix_process.terminate()
            try:
                self.kiwix_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.kiwix_process.kill()
        self.kiwix_process = None
        self.kiwix_port = None

    def install_zim_backend(self):
        message = (
            "Install the ZIM backend for in-app reading?\n\n"
            "Command:\nsudo pacman -S --needed kiwix-tools zim-tools\n\n"
            "This will open a terminal for the password prompt."
        )
        if not confirm(self, "Install ZIM Backend", message):
            return
        command = (
            "sudo pacman -S --needed kiwix-tools zim-tools; "
            "status=$?; "
            "echo; "
            "echo \"ZIM backend install finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal("Install ZIM Backend", command)
        self.result.setPlainText(f"Started backend install in {terminal}." if ok else terminal)

    def open_selected_location(self):
        zim = self.selected_zim()
        if not zim:
            self.result.setPlainText("Select a ZIM file first.")
            return
        if command_exists("xdg-open"):
            subprocess.Popen(["xdg-open", str(zim.parent)])
            self.result.setPlainText(f"Opened folder:\n{zim.parent}")


class CommandCodePage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.workspace = Path.home()
        self.open_files = {}
        self.codex_process = None
        self.codex_last_message_path = None
        self.codex_log_buffer = ""
        self.codex_event_buffer = ""
        self.codex_answer_seen = False
        self.codex_current_answer = ""
        self.attached_files = []
        self.codex_usage = {"used": 0, "limit": 0, "last_run": 0}
        self.load_codex_usage()

        self.model = QFileSystemModel()
        self.model.setRootPath(str(self.workspace))
        self.model.setNameFilters(["*.py", "*.sh", "*.js", "*.ts", "*.json", "*.qml", "*.md", "*.txt", "*.css", "*.html", "*.toml", "*.yaml", "*.yml", "*.service", "*.desktop"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(self.workspace)))
        self.tree.doubleClicked.connect(self.open_tree_item)
        self.tree.setHeaderHidden(True)
        for column in range(1, 4):
            self.tree.hideColumn(column)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(180)
        self.output.setObjectName("codeOutput")
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Run command in workspace")
        self.command_input.returnPressed.connect(self.run_workspace_command)
        self.codex_output = QTextEdit()
        self.codex_output.setReadOnly(True)
        self.codex_output.setObjectName("codexChatLog")
        self.codex_prompt = QTextEdit()
        self.codex_prompt.setMaximumHeight(92)
        self.codex_prompt.setPlaceholderText("Message Codex")
        self.codex_prompt.setObjectName("codexComposer")
        self.codex_prompt.installEventFilter(self)
        self.attachment_label = QLabel("No files attached")
        self.attachment_label.setObjectName("muted")
        self.codex_mode = QComboBox()
        self.codex_mode.setObjectName("modeSelect")
        for label, value in [
            ("Agent", "agent"),
            ("Ask", "ask"),
            ("Edit", "edit"),
            ("Review", "review"),
        ]:
            self.codex_mode.addItem(label, value)
        self.codex_status = QLabel("Ready")
        self.codex_status.setObjectName("muted")
        self.codex_usage_label = QLabel("--")
        self.codex_usage_label.setObjectName("metricValue")
        self.codex_usage_detail = QLabel("--")
        self.codex_usage_detail.setObjectName("muted")
        self.codex_limit_input = QLineEdit()
        self.codex_limit_input.setPlaceholderText("Set local token limit")
        self.codex_limit_input.returnPressed.connect(self.save_codex_limit)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")

        layout = QVBoxLayout(self)
        layout.addLayout(self.toolbar())

        editor_split = QSplitter(Qt.Horizontal)
        editor_split.addWidget(self.explorer_panel())
        editor_split.addWidget(self.tabs)
        editor_split.addWidget(self.codex_panel())
        editor_split.setSizes([260, 720, 360])

        vertical = QSplitter(Qt.Vertical)
        vertical.addWidget(editor_split)
        vertical.addWidget(self.terminal_panel())
        vertical.setSizes([650, 180])
        layout.addWidget(vertical)
        layout.addWidget(self.status)

        self.open_workspace(Path("/home/eugene/Desktop/Code"))
        self.append_chat("system", "Command Terminal ready. Choose a mode, then send a workspace prompt.")

    def toolbar(self):
        row = QHBoxLayout()
        for label, handler in [
            ("Open Folder", self.choose_folder),
            ("Open File", self.choose_file),
            ("Save", self.save_current_file),
            ("Save All", self.save_all_files),
            ("New File", self.new_file),
            ("Terminal", self.open_terminal),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        link = QPushButton("Link ChatGPT")
        link.clicked.connect(self.link_chatgpt_account)
        row.addWidget(link)
        return row

    def explorer_panel(self):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        title = QLabel("EXPLORER")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self.tree)
        return frame

    def terminal_panel(self):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        title = QLabel("TERMINAL / OUTPUT")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self.output)
        layout.addWidget(self.command_input)
        return frame

    def codex_panel(self):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        title = QLabel("CODEX CHAT")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self.codex_chat_tab(), "Chat")
        tabs.addTab(self.codex_usage_tab(), "Usage")
        layout.addWidget(tabs)
        self.update_codex_usage_display()
        return frame

    def codex_chat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        top = QHBoxLayout()
        mode_label = QLabel("Mode")
        mode_label.setObjectName("muted")
        top.addWidget(mode_label)
        top.addWidget(self.codex_mode)
        top.addWidget(self.codex_status, 1)
        layout.addLayout(top)

        layout.addWidget(self.codex_output)

        prompt_frame = QFrame()
        prompt_frame.setObjectName("composerFrame")
        prompt_layout = QVBoxLayout(prompt_frame)
        prompt_layout.setContentsMargins(8, 8, 8, 8)
        prompt_layout.addWidget(self.codex_prompt)
        prompt_layout.addWidget(self.attachment_label)

        row = QHBoxLayout()
        attach = QPushButton("+")
        attach.setObjectName("attachButton")
        attach.setToolTip("Attach files")
        attach.setFixedWidth(38)
        attach.clicked.connect(self.attach_files)
        row.addWidget(attach)
        for label, handler in [
            ("Account Status", self.codex_account_status),
            ("Explain File", self.explain_current_file),
            ("Review", self.review_workspace),
            ("Stop", self.stop_codex),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        send = QPushButton("Send")
        send.setObjectName("primaryButton")
        send.clicked.connect(self.ask_codex)
        row.addWidget(send)
        row.addStretch()
        prompt_layout.addLayout(row)
        layout.addWidget(prompt_frame)
        return tab

    def codex_usage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title = QLabel("Current Codex Usage")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self.codex_usage_label)
        layout.addWidget(self.codex_usage_detail)
        layout.addWidget(self.codex_limit_input)
        row = QHBoxLayout()
        save = QPushButton("Save Limit")
        save.clicked.connect(self.save_codex_limit)
        reset = QPushButton("Reset Usage")
        reset.clicked.connect(self.reset_codex_usage)
        status = QPushButton("Account Status")
        status.clicked.connect(self.codex_account_status)
        row.addWidget(save)
        row.addWidget(reset)
        row.addWidget(status)
        row.addStretch()
        layout.addLayout(row)
        note = QLabel("Codex reports token usage for each run, but it does not expose your account-wide quota. Set your local limit here to display x of y.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return tab

    def open_workspace(self, folder):
        folder = Path(folder).expanduser()
        if not folder.exists() or not folder.is_dir():
            return
        self.workspace = folder
        self.model.setRootPath(str(folder))
        self.tree.setRootIndex(self.model.index(str(folder)))
        self.status.setText(f"Workspace: {folder}")
        self.codex_status.setText(f"Workspace: {folder.name}")
        self.append_chat("system", f"Workspace: {folder}")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open workspace folder", str(self.workspace))
        if folder:
            self.open_workspace(Path(folder))

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open file", str(self.workspace), "Text files (*);;All files (*)")
        if file_path:
            self.open_file(Path(file_path))

    def open_tree_item(self, index):
        path = Path(self.model.filePath(index))
        if path.is_dir():
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
        elif path.is_file():
            self.open_file(path)

    def make_editor(self, content):
        editor = QPlainTextEdit()
        editor.setPlainText(content)
        editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        editor.setFont(QFont("JetBrains Mono", 10))
        editor.textChanged.connect(self.mark_current_modified)
        return editor

    def open_file(self, path):
        path = Path(path)
        if path in self.open_files:
            self.tabs.setCurrentWidget(self.open_files[path])
            return
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        except Exception as error:
            self.output.appendPlainText(f"Unable to open {path}:\n{error}")
            return

        editor = self.make_editor(content)
        editor.setProperty("path", str(path))
        editor.setProperty("modified", False)
        self.open_files[path] = editor
        self.tabs.addTab(editor, path.name)
        self.tabs.setCurrentWidget(editor)
        self.status.setText(str(path))

    def new_file(self):
        editor = self.make_editor("")
        editor.setProperty("path", "")
        editor.setProperty("modified", True)
        self.tabs.addTab(editor, "Untitled")
        self.tabs.setCurrentWidget(editor)
        self.status.setText("Untitled")

    def current_editor(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QPlainTextEdit) else None

    def mark_current_modified(self):
        editor = self.sender()
        if not isinstance(editor, QPlainTextEdit):
            return
        editor.setProperty("modified", True)
        index = self.tabs.indexOf(editor)
        if index >= 0 and not self.tabs.tabText(index).startswith("*"):
            self.tabs.setTabText(index, "*" + self.tabs.tabText(index))

    def save_current_file(self):
        editor = self.current_editor()
        if not editor:
            return
        self.save_editor(editor)

    def save_all_files(self):
        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if isinstance(editor, QPlainTextEdit):
                self.save_editor(editor)

    def save_editor(self, editor):
        path_text = editor.property("path") or ""
        if not path_text:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save file", str(self.workspace / "untitled.txt"), "Text files (*);;All files (*)")
            if not file_path:
                return
            path_text = file_path
            editor.setProperty("path", path_text)

        path = Path(path_text)
        try:
            path.write_text(editor.toPlainText(), encoding="utf-8")
        except Exception as error:
            self.output.appendPlainText(f"Unable to save {path}:\n{error}")
            return
        editor.setProperty("modified", False)
        index = self.tabs.indexOf(editor)
        if index >= 0:
            self.tabs.setTabText(index, path.name)
        self.open_files[path] = editor
        self.status.setText(f"Saved: {path}")
        self.parent_window.add_history(f"Command Terminal saved {path.name}")

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if isinstance(editor, QPlainTextEdit) and editor.property("modified"):
            if not confirm(self, "Unsaved file", "Close this file without saving?"):
                return
        path_text = editor.property("path") if isinstance(editor, QPlainTextEdit) else ""
        if path_text:
            self.open_files.pop(Path(path_text), None)
        self.tabs.removeTab(index)
        editor.deleteLater()

    def update_status(self):
        editor = self.current_editor()
        if editor:
            self.status.setText(editor.property("path") or "Untitled")

    def run_workspace_command(self):
        command = self.command_input.text().strip()
        if not command:
            return
        self.command_input.clear()
        self.output.appendPlainText(f"$ {command}")
        try:
            result = subprocess.run(
                ["bash", "-lc", command],
                cwd=str(self.workspace),
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.stdout:
                self.output.appendPlainText(result.stdout.rstrip())
            if result.stderr:
                self.output.appendPlainText(result.stderr.rstrip())
            self.output.appendPlainText(f"[exit {result.returncode}]")
        except subprocess.TimeoutExpired:
            self.output.appendPlainText("[command timed out]")

    def open_terminal(self):
        ok, terminal = launch_terminal("Command Terminal", f"cd {json.dumps(str(self.workspace))}; exec bash")
        self.output.appendPlainText(f"Opened terminal in {terminal}." if ok else terminal)

    def codex_command(self):
        return ensure_codex_on_path()

    def link_chatgpt_account(self):
        command = self.codex_command()
        if not command:
            self.append_chat("system", "Codex CLI was not found.")
            return
        if not confirm(self, "Link ChatGPT Account", "Start the Codex login flow to link your ChatGPT/OpenAI account?"):
            return
        shell_command = (
            f"{json.dumps(command)} login; "
            "status=$?; echo; "
            "echo \"Codex login finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal("Link ChatGPT Account", shell_command)
        self.append_chat("system", f"Started Codex login in {terminal}." if ok else terminal)

    def codex_account_status(self):
        command = self.codex_command()
        if not command:
            self.append_chat("system", "Codex CLI was not found.")
            return
        out, err, code = run_text([command, "login", "status"], 8)
        self.append_chat("system", "Codex account status\n" + (out or err or f"codex login status exited with {code}"))

    def load_codex_usage(self):
        try:
            data = json.loads(CODEX_USAGE_CONFIG.read_text())
            self.codex_usage = {
                "used": int(data.get("used", 0)),
                "limit": int(data.get("limit", 0)),
                "last_run": int(data.get("last_run", 0)),
            }
        except Exception:
            self.codex_usage = {"used": 0, "limit": 0, "last_run": 0}

    def save_codex_usage(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CODEX_USAGE_CONFIG.write_text(json.dumps(self.codex_usage, indent=2))

    def save_codex_limit(self):
        text = self.codex_limit_input.text().strip()
        try:
            self.codex_usage["limit"] = max(0, int(text)) if text else 0
        except ValueError:
            self.codex_usage_detail.setText("Limit must be a number.")
            return
        self.save_codex_usage()
        self.update_codex_usage_display()

    def reset_codex_usage(self):
        self.codex_usage["used"] = 0
        self.codex_usage["last_run"] = 0
        self.save_codex_usage()
        self.update_codex_usage_display()

    def update_codex_usage_display(self):
        used = int(self.codex_usage.get("used", 0))
        limit = int(self.codex_usage.get("limit", 0))
        last_run = int(self.codex_usage.get("last_run", 0))
        if limit > 0:
            remaining = max(0, limit - used)
            self.codex_usage_label.setText(f"{used:,} / {limit:,}")
            self.codex_usage_detail.setText(f"Remaining: {remaining:,} tokens. Last run: {last_run:,} tokens.")
            self.codex_limit_input.setText(str(limit))
        else:
            self.codex_usage_label.setText(f"{used:,} / set limit")
            self.codex_usage_detail.setText(f"Last run: {last_run:,} tokens. Set a local limit to show remaining usage.")
            self.codex_limit_input.setText("")

    def current_file_context(self):
        editor = self.current_editor()
        if not editor:
            return ""
        path = editor.property("path") or "Untitled"
        content = editor.toPlainText()
        if len(content) > 12000:
            content = content[:12000] + "\n...[truncated]"
        return f"\n\nCurrent file: {path}\n\n```text\n{content}\n```"

    def attach_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Attach files", str(self.workspace), "All files (*)")
        if not files:
            return
        existing = {path.resolve() for path in self.attached_files if path.exists()}
        for file_path in files:
            path = Path(file_path).expanduser()
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved not in existing and resolved.exists() and resolved.is_file():
                existing.add(resolved)
                self.attached_files.append(resolved)
        self.update_attachment_label()
        self.append_chat("system", f"Attached {len(files)} file(s).")

    def update_attachment_label(self):
        if not self.attached_files:
            self.attachment_label.setText("No files attached")
            return
        names = [path.name for path in self.attached_files[:3]]
        suffix = "" if len(self.attached_files) <= 3 else f" + {len(self.attached_files) - 3} more"
        self.attachment_label.setText("Attached: " + ", ".join(names) + suffix)

    def clear_attachments(self):
        self.attached_files = []
        self.update_attachment_label()

    def image_attachments(self):
        image_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
        return [path for path in self.attached_files if path.suffix.lower() in image_suffixes]

    def attachment_context(self):
        if not self.attached_files:
            return ""
        sections = ["\n\nAttached files:"]
        text_budget = 24000
        image_paths = set(self.image_attachments())
        for path in self.attached_files:
            sections.append(f"\n- {path}")
            if path in image_paths:
                sections.append("  Image file attached to Codex CLI.")
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = path.read_text(encoding="latin-1")
                except Exception as error:
                    sections.append(f"  Unable to read file as text: {error}")
                    continue
            except Exception as error:
                sections.append(f"  Unable to read file: {error}")
                continue

            if text_budget <= 0:
                sections.append("  Text content omitted because attachment context budget is full.")
                continue
            clipped = content[:text_budget]
            text_budget -= len(clipped)
            if len(clipped) < len(content):
                clipped += "\n...[truncated]"
            sections.append(f"\n```text\n{clipped}\n```")
        return "\n".join(sections)

    def selected_codex_mode(self):
        return self.codex_mode.currentData() or "agent"

    def set_codex_mode(self, mode):
        index = self.codex_mode.findData(mode)
        if index >= 0:
            self.codex_mode.setCurrentIndex(index)

    def mode_prompt(self, user_prompt):
        mode = self.selected_codex_mode()
        instructions = {
            "agent": (
                "You are in Agent mode inside Command Terminal. Work like the VS Code Codex agent: "
                "inspect the workspace, make code edits when needed, run focused verification, and summarize the result."
            ),
            "ask": (
                "You are in Ask mode inside Command Terminal. Answer and explain using workspace context, "
                "but do not edit files or run changing commands unless the user explicitly asks you to switch modes."
            ),
            "edit": (
                "You are in Edit mode inside Command Terminal. Focus on implementing the requested change in the workspace. "
                "Keep edits scoped, preserve existing style, and run reasonable checks."
            ),
            "review": (
                "You are in Review mode inside Command Terminal. Use a code-review stance: findings first, ordered by severity, "
                "with file references where possible. Do not rewrite code unless explicitly requested."
            ),
        }
        return f"{instructions.get(mode, instructions['agent'])}\n\nUser request:\n{user_prompt}"

    def append_chat(self, role, message):
        role_labels = {
            "user": "You",
            "assistant": "Codex",
            "system": "Command Terminal",
            "tool": "Tool",
        }
        colors = {
            "user": "#dff5ff",
            "assistant": "#f3f8fb",
            "system": "#9fb2c2",
            "tool": "#a9cfe8",
        }
        border = {
            "user": "#2aa9ef",
            "assistant": "#3a5368",
            "system": "#263849",
            "tool": "#27516c",
        }
        safe_message = html.escape(message).replace("\n", "<br>")
        label = role_labels.get(role, role.title())
        self.codex_output.append(
            f"""
            <div style="margin:8px 0; padding:10px 11px; border:1px solid {border.get(role, '#263849')};
                 border-radius:7px; background:#071019;">
              <div style="color:#55bdff; font-size:11px; font-weight:800; letter-spacing:1px; margin-bottom:6px;">{label}</div>
              <div style="color:{colors.get(role, '#edf5fb')}; white-space:pre-wrap;">{safe_message}</div>
            </div>
            """
        )
        self.codex_output.verticalScrollBar().setValue(self.codex_output.verticalScrollBar().maximum())

    def ask_codex(self):
        prompt = self.codex_prompt.toPlainText().strip()
        if not prompt:
            self.append_chat("system", "Type a prompt for Codex first.")
            return
        self.codex_prompt.clear()
        self.run_codex(self.mode_prompt(prompt) + self.current_file_context() + self.attachment_context(), prompt)

    def explain_current_file(self):
        editor = self.current_editor()
        if not editor:
            self.append_chat("system", "Open a file first.")
            return
        self.set_codex_mode("ask")
        question = "Explain the current file."
        self.run_codex("Explain this file clearly and point out important functions, risks, and next improvements." + self.current_file_context(), question)

    def review_workspace(self):
        self.set_codex_mode("review")
        question = "Review this workspace."
        self.run_codex(self.mode_prompt("Review this workspace for likely bugs, missing tests, and risky implementation choices."), question)

    def run_codex(self, prompt, display_question=None):
        command = self.codex_command()
        if not command:
            self.append_chat("system", "Codex CLI was not found.")
            return
        if self.codex_process and self.codex_process.state() != QProcess.NotRunning:
            self.append_chat("system", "Codex is already running. Stop it first.")
            return

        mode_label = self.codex_mode.currentText()
        self.append_chat("user", f"[{mode_label}] {display_question or prompt.split(chr(10), 1)[0]}")
        self.append_chat("system", "Thinking...")
        self.codex_status.setText(f"Running in {mode_label} mode")
        temp = tempfile.NamedTemporaryFile(prefix="command-centre-codex-", suffix=".txt", delete=False)
        temp.close()
        self.codex_last_message_path = Path(temp.name)
        self.codex_log_buffer = ""
        self.codex_event_buffer = ""
        self.codex_answer_seen = False
        self.codex_current_answer = ""
        self.codex_process = QProcess(self)
        self.codex_process.setWorkingDirectory(str(self.workspace))
        self.codex_process.setProgram(command)
        args = [
            "exec",
            "--json",
            "-C",
            str(self.workspace),
            "--skip-git-repo-check",
            "--sandbox",
            "danger-full-access",
            "--color",
            "never",
            "--output-last-message",
            str(self.codex_last_message_path),
        ]
        for image in self.image_attachments():
            args.extend(["--image", str(image)])
        args.append(prompt)
        self.codex_process.setArguments(args)
        self.codex_process.readyReadStandardOutput.connect(self.read_codex_stdout)
        self.codex_process.readyReadStandardError.connect(self.read_codex_stderr)
        self.codex_process.finished.connect(self.codex_finished)
        self.codex_process.start()
        self.codex_process.closeWriteChannel()
        self.clear_attachments()

    def read_codex_stdout(self):
        data = bytes(self.codex_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.codex_log_buffer += data
            self.process_codex_events(data)

    def read_codex_stderr(self):
        data = bytes(self.codex_process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            self.codex_log_buffer += data
            self.process_codex_events(data)

    def process_codex_events(self, data):
        self.codex_event_buffer += data
        lines = self.codex_event_buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            self.codex_event_buffer = lines.pop()
        else:
            self.codex_event_buffer = ""

        for raw in lines:
            line = raw.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.render_codex_event(event)

    def render_codex_event(self, event):
        item = event.get("item") or {}
        item_type = item.get("type")
        event_type = event.get("type")

        if event_type == "turn.started":
            return
        if event_type == "turn.completed":
            usage = event.get("usage") or {}
            run_total = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
            self.codex_usage["last_run"] = run_total
            self.codex_usage["used"] = int(self.codex_usage.get("used", 0)) + run_total
            self.save_codex_usage()
            self.update_codex_usage_display()
            return
        if item_type == "command_execution":
            command = item.get("command", "")
            if event_type == "item.started":
                self.append_chat("tool", f"Running command:\n{command}")
            elif event_type == "item.completed":
                output = (item.get("aggregated_output") or "").strip()
                exit_code = item.get("exit_code")
                block = f"Executed command:\n{command}\nExit code: {exit_code}"
                if output:
                    block += f"\nOutput:\n{output}"
                self.append_chat("tool", block)
            return
        if item_type == "agent_message":
            text = (item.get("text") or "").strip()
            if text:
                self.codex_answer_seen = True
                self.codex_current_answer = text
                self.append_chat("assistant", text)

    def codex_finished(self, code, status):
        final = ""
        if self.codex_last_message_path and self.codex_last_message_path.exists():
            try:
                final = self.codex_last_message_path.read_text().strip()
            except Exception:
                final = ""
        if final and not self.codex_answer_seen:
            self.append_chat("assistant", final)
        elif self.codex_log_buffer.strip():
            if not self.codex_answer_seen:
                self.append_chat("system", "Codex finished, but no answer event was received.")
        else:
            self.append_chat("system", "Codex finished without output.")
        self.codex_status.setText("Ready")
        self.parent_window.add_history("Codex request completed in Command Terminal")

    def stop_codex(self):
        if self.codex_process and self.codex_process.state() != QProcess.NotRunning:
            self.codex_process.kill()
            self.codex_status.setText("Stopped")
            self.append_chat("system", "Codex stopped.")

    def eventFilter(self, watched, event):
        if watched is self.codex_prompt and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
                self.ask_codex()
                return True
        return super().eventFilter(watched, event)


class DeploymentEditorDialog(QDialog):
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deployment Editor")
        self.resize(860, 760)
        self.profile = profile or {}
        self.name = QLineEdit(self.profile.get("name", ""))
        self.summary = QLineEdit(self.profile.get("summary", ""))
        self.tier = QComboBox()
        for label, value in [("Custom", "custom"), ("Primary", "primary"), ("Optional", "optional")]:
            self.tier.addItem(label, value)
        self.tier.setCurrentIndex(max(0, self.tier.findData(self.profile.get("tier", "custom"))))
        self.warning = QTextEdit()
        self.warning.setMaximumHeight(70)
        self.warning.setPlainText(self.profile.get("warning", ""))
        self.environment = QPlainTextEdit()
        self.environment.setMaximumHeight(78)
        self.environment.setPlaceholderText("COMMANDOS_PROFILE=AI_DEV")
        self.environment.setPlainText(self.dict_to_lines(self.profile.get("environment", {})))
        self.apps = QPlainTextEdit()
        self.apps.setPlaceholderText("VS Code | code ~/Desktop/Code | visual-studio-code-bin\nOpen WebUI | xdg-open http://localhost:3000 |")
        self.apps.setPlainText(self.apps_to_lines(self.profile.get("apps", [])))
        self.terminals = QPlainTextEdit()
        self.terminals.setPlaceholderText("Project Terminal | ~/Desktop/Code | git status; exec bash")
        self.terminals.setPlainText(self.terminals_to_lines(self.profile.get("terminals", [])))
        self.services = QPlainTextEdit()
        self.services.setMaximumHeight(70)
        self.services.setPlaceholderText("ollama.service\ndocker.service")
        self.services.setPlainText("\n".join(self.profile.get("services", [])))
        self.folders = QPlainTextEdit()
        self.folders.setMaximumHeight(70)
        self.folders.setPlaceholderText("~/Desktop/Code\n~/Documents/Field")
        self.folders.setPlainText("\n".join(self.profile.get("folders", [])))
        self.urls = QPlainTextEdit()
        self.urls.setMaximumHeight(70)
        self.urls.setPlaceholderText("http://localhost:3000\nhttps://developer.mozilla.org")
        self.urls.setPlainText("\n".join(self.profile.get("urls", [])))
        self.quick_actions = QPlainTextEdit()
        self.quick_actions.setPlaceholderText("Docker Status | docker ps\nGPU Watch | watch -n 1 nvidia-smi")
        self.quick_actions.setPlainText(self.actions_to_lines(self.profile.get("quick_actions", [])))
        self.profiles = QPlainTextEdit()
        self.profiles.setMaximumHeight(70)
        self.profiles.setPlaceholderText("Python\nRust\nWeb")
        self.profiles.setPlainText("\n".join(self.profile.get("profiles", [])))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Summary", self.summary)
        form.addRow("Tier", self.tier)
        form.addRow("Warning", self.warning)
        form.addRow("Environment", self.environment)
        form.addRow("Apps", self.apps)
        form.addRow("Terminals", self.terminals)
        form.addRow("Services", self.services)
        form.addRow("Folders", self.folders)
        form.addRow("URLs", self.urls)
        form.addRow("Quick Actions", self.quick_actions)
        form.addRow("Sub-Profiles", self.profiles)
        layout.addLayout(form)

        hint = QLabel("Use one item per line. For Apps: Name | command | package. For Terminals: Title | cwd | command. For Quick Actions: Name | command.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def dict_to_lines(self, data):
        return "\n".join(f"{key}={value}" for key, value in data.items())

    def apps_to_lines(self, apps):
        return "\n".join(f"{item.get('name', '')} | {item.get('command', '')} | {item.get('package', '')}" for item in apps)

    def terminals_to_lines(self, terminals):
        return "\n".join(f"{item.get('title', '')} | {item.get('cwd', '~')} | {item.get('command', 'exec bash')}" for item in terminals)

    def actions_to_lines(self, actions):
        return "\n".join(f"{item.get('name', '')} | {item.get('command', '')}" for item in actions)

    def clean_lines(self, widget):
        return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]

    def parse_environment(self):
        data = {}
        for line in self.clean_lines(self.environment):
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        return data

    def parse_apps(self):
        apps = []
        for line in self.clean_lines(self.apps):
            parts = [part.strip() for part in line.split("|")]
            name = parts[0] if parts else ""
            command = parts[1] if len(parts) > 1 else name
            package = parts[2] if len(parts) > 2 else command.split()[0] if command else name
            if name or command:
                apps.append({"name": name or command, "command": command, "package": package, "optional": True})
        return apps

    def parse_terminals(self):
        terminals = []
        for line in self.clean_lines(self.terminals):
            parts = [part.strip() for part in line.split("|")]
            title = parts[0] if parts else "Terminal"
            cwd = parts[1] if len(parts) > 1 else "~"
            command = parts[2] if len(parts) > 2 else "exec bash"
            terminals.append({"title": title, "cwd": cwd, "command": command})
        return terminals

    def parse_actions(self):
        actions = []
        for line in self.clean_lines(self.quick_actions):
            parts = [part.strip() for part in line.split("|", 1)]
            if len(parts) == 2:
                actions.append({"name": parts[0], "command": parts[1]})
        return actions

    def profile_data(self):
        name = self.name.text().strip() or "Custom Deployment"
        profile_id = self.profile.get("id") or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or f"deployment_{int(time.time())}"
        return {
            "id": profile_id,
            "name": name,
            "tier": self.tier.currentData() or "custom",
            "summary": self.summary.text().strip(),
            "warning": self.warning.toPlainText().strip(),
            "environment": self.parse_environment(),
            "apps": self.parse_apps(),
            "terminals": self.parse_terminals(),
            "services": self.clean_lines(self.services),
            "folders": self.clean_lines(self.folders),
            "urls": self.clean_lines(self.urls),
            "quick_actions": self.parse_actions(),
            "profiles": self.clean_lines(self.profiles),
        }


class DeploymentPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.deployments = []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search deployments")
        self.search.textChanged.connect(self.render_deployments)
        self.tier_filter = QComboBox()
        for label, value in [("All", "all"), ("Primary", "primary"), ("Optional", "optional"), ("Custom", "custom")]:
            self.tier_filter.addItem(label, value)
        self.tier_filter.currentIndexChanged.connect(self.render_deployments)
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self.selection_changed)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("textPanel")
        self.actions = QListWidget()
        self.actions.itemDoubleClicked.connect(lambda _: self.run_quick_action())
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")
        self.status = QLabel("--")
        self.status.setObjectName("muted")

        layout = QVBoxLayout(self)
        title = QLabel("DEPLOYMENT CENTRE")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(self.status)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.tier_filter)
        reload_button = QPushButton("Reload Profiles")
        reload_button.clicked.connect(self.refresh)
        controls.addWidget(reload_button)
        new_button = QPushButton("New Deployment")
        new_button.clicked.connect(self.new_deployment)
        controls.addWidget(new_button)
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self.edit_selected_deployment)
        controls.addWidget(edit_button)
        duplicate_button = QPushButton("Duplicate")
        duplicate_button.clicked.connect(self.duplicate_selected_deployment)
        controls.addWidget(duplicate_button)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_selected_deployment)
        controls.addWidget(remove_button)
        save_button = QPushButton("Save Current Workspace")
        save_button.clicked.connect(self.save_current_workspace)
        controls.addWidget(save_button)
        layout.addLayout(controls)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.detail, 2)
        action_title = QLabel("QUICK ACTIONS")
        action_title.setObjectName("panelTitle")
        right_layout.addWidget(action_title)
        right_layout.addWidget(self.actions, 1)
        buttons = QHBoxLayout()
        for label, handler in [
            ("Launch Deployment", self.launch_selected_deployment),
            ("Run Quick Action", self.run_quick_action),
            ("Open Profile JSON", self.open_profiles_json),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch()
        right_layout.addLayout(buttons)
        right_layout.addWidget(self.result)
        split.addWidget(right)
        split.setSizes([360, 780])
        layout.addWidget(split, 1)
        self.refresh()

    def refresh(self):
        self.deployments = self.load_deployments()
        self.render_deployments()

    def load_json_file(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def custom_profiles(self):
        return self.load_json_file(USER_DEPLOYMENTS_CONFIG)

    def save_custom_profiles(self, profiles):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        USER_DEPLOYMENTS_CONFIG.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    def unique_profile_id(self, base, profiles):
        existing = {profile.get("id") for profile in profiles}
        candidate = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or f"deployment_{int(time.time())}"
        if candidate not in existing:
            return candidate
        index = 2
        while f"{candidate}_{index}" in existing:
            index += 1
        return f"{candidate}_{index}"

    def load_deployments(self):
        defaults = self.load_json_file(DEFAULT_DEPLOYMENTS_FILE)
        custom = self.load_json_file(USER_DEPLOYMENTS_CONFIG)
        for profile in defaults:
            profile.setdefault("tier", "primary")
            profile.setdefault("source", str(DEFAULT_DEPLOYMENTS_FILE))
        for profile in custom:
            profile["tier"] = "custom"
            profile.setdefault("source", str(USER_DEPLOYMENTS_CONFIG))
        return defaults + custom

    def new_deployment(self):
        dialog = DeploymentEditorDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        profiles = self.custom_profiles()
        profile = dialog.profile_data()
        profile["id"] = self.unique_profile_id(profile["name"], profiles)
        profile["tier"] = "custom"
        profiles.append(profile)
        self.save_custom_profiles(profiles)
        self.result.setPlainText(f"Created deployment: {profile['name']}")
        self.refresh()
        self.select_profile(profile["id"])

    def edit_selected_deployment(self):
        profile = self.selected_deployment()
        if not profile:
            return
        source = profile.get("source", "")
        editing_default = source == str(DEFAULT_DEPLOYMENTS_FILE)
        editable = dict(profile)
        if editing_default:
            editable["id"] = ""
            editable["name"] = f"{profile.get('name', 'Deployment')} Custom"
            editable["tier"] = "custom"
        dialog = DeploymentEditorDialog(editable, self)
        if dialog.exec() != QDialog.Accepted:
            return
        profiles = self.custom_profiles()
        updated = dialog.profile_data()
        updated["tier"] = "custom"
        if editing_default:
            updated["id"] = self.unique_profile_id(updated["name"], profiles)
            profiles.append(updated)
            message = f"Created editable custom copy: {updated['name']}"
        else:
            updated["id"] = profile.get("id")
            replaced = False
            for index, item in enumerate(profiles):
                if item.get("id") == updated["id"]:
                    profiles[index] = updated
                    replaced = True
                    break
            if not replaced:
                profiles.append(updated)
            message = f"Updated deployment: {updated['name']}"
        self.save_custom_profiles(profiles)
        self.result.setPlainText(message)
        self.refresh()
        self.select_profile(updated["id"])

    def duplicate_selected_deployment(self):
        profile = self.selected_deployment()
        if not profile:
            return
        profiles = self.custom_profiles()
        duplicate = json.loads(json.dumps(profile))
        duplicate["name"] = f"{profile.get('name', 'Deployment')} Copy"
        duplicate["id"] = self.unique_profile_id(duplicate["name"], profiles)
        duplicate["tier"] = "custom"
        duplicate.pop("source", None)
        profiles.append(duplicate)
        self.save_custom_profiles(profiles)
        self.result.setPlainText(f"Duplicated deployment: {duplicate['name']}")
        self.refresh()
        self.select_profile(duplicate["id"])

    def remove_selected_deployment(self):
        profile = self.selected_deployment()
        if not profile:
            return
        if profile.get("source") == str(DEFAULT_DEPLOYMENTS_FILE):
            self.result.setPlainText("Built-in deployments cannot be removed. Duplicate it first, then edit or remove the custom copy.")
            return
        if not confirm(self, "Remove Deployment", f"Remove this custom deployment?\n\n{profile.get('name')}"):
            return
        profiles = [item for item in self.custom_profiles() if item.get("id") != profile.get("id")]
        self.save_custom_profiles(profiles)
        self.result.setPlainText(f"Removed deployment: {profile.get('name')}")
        self.refresh()

    def select_profile(self, profile_id):
        for index in range(self.list.count()):
            item = self.list.item(index)
            profile = item.data(Qt.UserRole)
            if profile and profile.get("id") == profile_id:
                item.setSelected(True)
                self.list.scrollToItem(item)
                return

    def render_deployments(self):
        selected_id = self.selected_deployment().get("id") if self.selected_deployment() else ""
        needle = self.search.text().strip().lower()
        tier = self.tier_filter.currentData() or "all"
        self.list.clear()
        shown = 0
        for profile in self.deployments:
            haystack = f"{profile.get('name', '')} {profile.get('summary', '')} {profile.get('tier', '')}".lower()
            if needle and needle not in haystack:
                continue
            if tier != "all" and profile.get("tier") != tier:
                continue
            item = QListWidgetItem(f"{profile.get('name', 'Deployment')}  [{profile.get('tier', 'primary')}]\n{profile.get('summary', '')}")
            item.setData(Qt.UserRole, profile)
            self.list.addItem(item)
            shown += 1
            if selected_id and profile.get("id") == selected_id:
                item.setSelected(True)
        if not self.list.selectedItems() and self.list.count():
            self.list.item(0).setSelected(True)
        self.status.setText(f"{shown} shown / {len(self.deployments)} profile-driven deployments loaded.")
        self.selection_changed()

    def selected_deployment(self):
        selected = self.list.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else None

    def selection_changed(self):
        profile = self.selected_deployment()
        self.actions.clear()
        if not profile:
            self.detail.setPlainText("Select a deployment.")
            return
        for action in profile.get("quick_actions", []):
            item = QListWidgetItem(f"{action.get('name', 'Action')}\n{action.get('command', '')}")
            item.setData(Qt.UserRole, action)
            self.actions.addItem(item)
        self.detail.setPlainText(self.profile_detail(profile))

    def component_status(self, command):
        if not command:
            return "not configured"
        executable = shlex.split(command)[0] if command else ""
        if executable == "flatpak":
            parts = shlex.split(command)
            return "available" if len(parts) >= 3 and run_text(["flatpak", "info", parts[2]], 2)[2] == 0 else "missing"
        return "available" if command_exists(executable) else "missing"

    def profile_detail(self, profile):
        lines = [
            profile.get("name", "Deployment"),
            "=" * len(profile.get("name", "Deployment")),
            "",
            profile.get("summary", ""),
            "",
            f"Tier: {profile.get('tier', 'primary')}",
            f"Source: {profile.get('source', DEFAULT_DEPLOYMENTS_FILE)}",
        ]
        if profile.get("source") == str(DEFAULT_DEPLOYMENTS_FILE):
            lines.extend(["", "Template", "--------", "This is a built-in template. Edit creates a custom copy you can change freely."])
        if profile.get("warning"):
            lines.extend(["", "Warning", "-------", profile["warning"]])
        if profile.get("environment"):
            lines.extend(["", "Environment", "-----------"])
            lines.extend(f"{key}={value}" for key, value in profile["environment"].items())
        lines.extend(["", "Applications", "------------"])
        for app in profile.get("apps", []):
            command = app.get("command", "")
            lines.append(f"{app.get('name', command)}: {self.component_status(command)}  [{command}]")
        lines.extend(["", "Terminals", "---------"])
        for terminal in profile.get("terminals", []):
            lines.append(f"{terminal.get('title', 'Terminal')}: {terminal.get('cwd', '~')} -> {terminal.get('command', 'exec bash')}")
        lines.extend(["", "Services", "--------"])
        services = profile.get("services", [])
        lines.extend(services or ["No services configured."])
        lines.extend(["", "Folders", "-------"])
        lines.extend(profile.get("folders", []) or ["No folders configured."])
        lines.extend(["", "Browser Pages", "-------------"])
        lines.extend(profile.get("urls", []) or ["No URLs configured."])
        if profile.get("profiles"):
            lines.extend(["", "Sub-Profiles", "------------"])
            lines.extend(profile["profiles"])
        return "\n".join(lines)

    def launch_selected_deployment(self):
        profile = self.selected_deployment()
        if not profile:
            return
        warning = profile.get("warning", "")
        message = f"Launch deployment workspace?\n\n{profile.get('name')}\n\n{profile.get('summary', '')}"
        if warning:
            message += f"\n\nWARNING:\n{warning}"
        if not confirm(self, "Launch Deployment", message):
            return
        launched = []
        missing = []
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in profile.get("environment", {}).items()})

        for service in profile.get("services", []):
            self.launch_terminal_command(f"Start {service}", f"systemctl --user start {shlex.quote(service)} || sudo systemctl start {shlex.quote(service)}")
            launched.append(f"service: {service}")

        for folder in profile.get("folders", []):
            self.open_path(folder)
            launched.append(f"folder: {folder}")

        for url in profile.get("urls", []):
            if command_exists("xdg-open"):
                subprocess.Popen(["xdg-open", url], env=env)
                launched.append(f"url: {url}")

        for terminal in profile.get("terminals", []):
            cwd = Path(os.path.expanduser(terminal.get("cwd", "~")))
            command = terminal.get("command", "exec bash")
            launch_terminal(terminal.get("title", profile.get("name", "Deployment")), f"cd {shlex.quote(str(cwd))}; {command}")
            launched.append(f"terminal: {terminal.get('title', 'Terminal')}")

        for app in profile.get("apps", []):
            command = app.get("command", "")
            if not command:
                continue
            if self.component_status(command) == "missing":
                missing.append(f"{app.get('name', command)} ({command})")
                continue
            subprocess.Popen(["bash", "-lc", command], env=env)
            launched.append(f"app: {app.get('name', command)}")

        self.result.setPlainText(
            "Launched:\n" + ("\n".join(launched) if launched else "Nothing launched.")
            + ("\n\nMissing components:\n" + "\n".join(missing) if missing else "")
        )
        self.parent_window.add_history(f"Deployment launched: {profile.get('name')}")

    def open_path(self, folder):
        path = Path(os.path.expanduser(folder))
        path.mkdir(parents=True, exist_ok=True)
        if command_exists("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)])

    def launch_terminal_command(self, title, command):
        shell_command = (
            f"{command}; "
            "status=$?; echo; "
            "echo \"Deployment command finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        return launch_terminal(title, shell_command)

    def run_quick_action(self):
        profile = self.selected_deployment()
        selected = self.actions.selectedItems()
        if not profile or not selected:
            self.result.setPlainText("Select a quick action first.")
            return
        action = selected[0].data(Qt.UserRole)
        command = action.get("command", "")
        if not command:
            return
        if profile.get("warning"):
            message = f"Run quick action?\n\n{action.get('name')}\n\n{command}\n\nWARNING:\n{profile.get('warning')}"
        else:
            message = f"Run quick action?\n\n{action.get('name')}\n\n{command}"
        if not confirm(self, "Run Quick Action", message):
            return
        ok, terminal = self.launch_terminal_command(action.get("name", "Deployment Action"), command)
        self.result.setPlainText(f"Started in {terminal}:\n{command}" if ok else terminal)

    def open_profiles_json(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not USER_DEPLOYMENTS_CONFIG.exists():
            USER_DEPLOYMENTS_CONFIG.write_text("[]\n", encoding="utf-8")
        if command_exists("xdg-open"):
            subprocess.Popen(["xdg-open", str(USER_DEPLOYMENTS_CONFIG)])
        else:
            self.result.setPlainText(str(USER_DEPLOYMENTS_CONFIG))

    def save_current_workspace(self):
        name, ok = QInputDialog.getText(self, "Save Current Workspace", "Deployment name:")
        if not ok or not name.strip():
            return
        running = self.running_known_apps()
        profile = {
            "id": re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or f"deployment_{int(time.time())}",
            "name": name.strip(),
            "tier": "custom",
            "summary": "Captured workspace profile. Review commands and folders before relying on it.",
            "environment": {"COMMANDOS_PROFILE": re.sub(r"[^A-Z0-9]+", "_", name.strip().upper()).strip("_")},
            "apps": running,
            "terminals": [{"title": f"{name.strip()} Terminal", "cwd": str(Path.home()), "command": "exec bash"}],
            "folders": [str(Path.home())],
            "quick_actions": [],
        }
        profiles = self.custom_profiles()
        profile["id"] = self.unique_profile_id(profile["name"], profiles)
        profiles.append(profile)
        self.save_custom_profiles(profiles)
        self.result.setPlainText(f"Saved deployment profile:\n{USER_DEPLOYMENTS_CONFIG}\n\nCaptured apps:\n" + "\n".join(app["name"] for app in running))
        self.refresh()
        self.select_profile(profile["id"])

    def running_known_apps(self):
        known = {}
        for profile in self.deployments:
            for app in profile.get("apps", []):
                command = app.get("command", "")
                if command:
                    executable = shlex.split(command)[0]
                    known[executable] = app
        output = run_text(["ps", "-eo", "comm="], 2)[0]
        running = set(output.splitlines())
        captured = []
        for executable, app in sorted(known.items()):
            if executable in running:
                captured.append(dict(app))
        return captured[:20]


class CommandIntelPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.tabs = QTabWidget()
        self.target_type = QComboBox()
        self.target_type.addItems(INTEL_PROVIDERS.keys())
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search a username, email, domain, IP, phone, person or company")
        self.providers = QListWidget()
        self.providers.setSelectionMode(QListWidget.MultiSelection)
        self.tool_filter = QLineEdit()
        self.tool_filter.setPlaceholderText("Filter tools and categories…")
        self.cards_host = QWidget()
        self.cards_layout = QGridLayout(self.cards_host)
        self.case_name = QLineEdit()
        self.case_name.setPlaceholderText("Investigation name")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Record findings, source context, and verification notes…")
        self.history = QListWidget()
        self.browser = QWebEngineView()
        self.ad_blocker = IntelAdBlocker(self.browser)
        self.browser.page().profile().setUrlRequestInterceptor(self.ad_blocker)
        self.address = QLineEdit()

        dashboard = QWidget()
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(4, 4, 4, 4)
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_copy = QVBoxLayout()
        title = QLabel("COMMAND INTEL")
        title.setObjectName("heroTitle")
        subtitle = QLabel("OSINT RESOURCE & INVESTIGATION CENTRE")
        subtitle.setObjectName("heroSubtitle")
        notice = QLabel("Public-source research only · Verify findings independently · Respect privacy, terms, and local law")
        notice.setObjectName("muted")
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_copy.addWidget(notice)
        hero_layout.addLayout(hero_copy, 1)
        hero_layout.addWidget(self.tool_filter)
        dashboard_layout.addWidget(hero)

        search_frame = QFrame()
        search_frame.setObjectName("intelSearch")
        search_layout = QVBoxLayout(search_frame)
        fields = QHBoxLayout()
        fields.addWidget(self.target_type)
        fields.addWidget(self.query, 1)
        open_selected = QPushButton("Open selected")
        open_all = QPushButton("Run all")
        fields.addWidget(open_selected)
        fields.addWidget(open_all)
        search_layout.addLayout(fields)
        search_layout.addWidget(self.providers)
        dashboard_layout.addWidget(search_frame)
        dashboard_layout.addWidget(self.cards_host)
        dashboard_layout.addStretch()

        browser_page = QWidget()
        browser_layout = QVBoxLayout(browser_page)
        browser_bar = QHBoxLayout()
        back = QPushButton("←")
        forward = QPushButton("→")
        reload_button = QPushButton("↻")
        shield = QLabel("● AD BLOCK ON")
        shield.setObjectName("adBlockBadge")
        external = QPushButton("Open externally")
        browser_bar.addWidget(back)
        browser_bar.addWidget(forward)
        browser_bar.addWidget(reload_button)
        browser_bar.addWidget(shield)
        browser_bar.addWidget(self.address, 1)
        browser_bar.addWidget(external)
        browser_layout.addLayout(browser_bar)
        browser_layout.addWidget(self.browser, 1)

        workspace = QWidget()
        workspace_layout = QGridLayout(workspace)
        case_frame = QFrame(); case_frame.setObjectName("card")
        case_layout = QVBoxLayout(case_frame)
        case_heading = QLabel("INVESTIGATION NOTES"); case_heading.setObjectName("panelTitle")
        save = QPushButton("Save workspace")
        case_layout.addWidget(case_heading); case_layout.addWidget(self.case_name); case_layout.addWidget(self.notes, 1); case_layout.addWidget(save)
        history_frame = QFrame(); history_frame.setObjectName("card")
        history_layout = QVBoxLayout(history_frame)
        history_heading = QLabel("SEARCH HISTORY"); history_heading.setObjectName("panelTitle")
        history_layout.addWidget(history_heading); history_layout.addWidget(self.history)
        workspace_layout.addWidget(case_frame, 0, 0); workspace_layout.addWidget(history_frame, 0, 1)

        self.tabs.addTab(dashboard, "Resource Dashboard")
        self.tabs.addTab(browser_page, "Browser")
        self.tabs.addTab(workspace, "Workspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.tabs)
        self.target_type.currentTextChanged.connect(self.refresh_providers)
        self.tool_filter.textChanged.connect(self.render_cards)
        self.query.returnPressed.connect(self.open_selected)
        open_selected.clicked.connect(self.open_selected)
        open_all.clicked.connect(lambda: self.launch(True))
        save.clicked.connect(self.save_workspace)
        back.clicked.connect(self.browser.back)
        forward.clicked.connect(self.browser.forward)
        reload_button.clicked.connect(self.browser.reload)
        self.address.returnPressed.connect(lambda: self.open_in_browser(self.address.text()))
        external.clicked.connect(lambda: QDesktopServices.openUrl(self.browser.url()))
        self.browser.urlChanged.connect(lambda url: self.address.setText(url.toString()))
        self.refresh_providers()
        self.render_cards()
        self.load_workspace()

    def render_cards(self):
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        needle = self.tool_filter.text().strip().lower()
        visible = []
        for title, icon, tools in INTEL_CATEGORIES:
            filtered = [(name, url) for name, url in tools if not needle or needle in name.lower() or needle in title.lower()]
            if filtered:
                visible.append((title, icon, filtered))
        for index, (title, icon, tools) in enumerate(visible):
            card = QFrame(); card.setObjectName("intelCard")
            card_layout = QVBoxLayout(card)
            heading = QLabel(f"{icon}   {title}"); heading.setObjectName("intelCardTitle")
            card_layout.addWidget(heading)
            for name, url in tools:
                button = QPushButton(name)
                button.setObjectName("intelLink")
                button.setToolTip(url)
                button.clicked.connect(lambda checked=False, target=url: self.open_in_browser(target))
                card_layout.addWidget(button)
            card_layout.addStretch()
            self.cards_layout.addWidget(card, index // 3, index % 3)

    def open_in_browser(self, target):
        target = target.strip()
        if not target:
            return
        if not re.match(r"^https?://", target, re.I):
            target = "https://" + target
        self.browser.setUrl(QUrl(target))
        self.tabs.setCurrentIndex(1)

    def refresh_providers(self):
        self.providers.clear()
        for name, url in INTEL_PROVIDERS[self.target_type.currentText()]:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, url)
            item.setSelected(True)
            self.providers.addItem(item)

    def open_selected(self):
        self.launch(False)

    def launch(self, all_providers=False):
        query = self.query.text().strip()
        if not query:
            QMessageBox.information(self, "Command Intel", "Enter a target first.")
            return
        items = [self.providers.item(i) for i in range(self.providers.count())]
        chosen = items if all_providers else [item for item in items if item.isSelected()]
        if not chosen:
            QMessageBox.information(self, "Command Intel", "Select at least one provider.")
            return
        if len(chosen) > 1 and not confirm(self, "Open OSINT searches", f"Open {len(chosen)} public-source searches for:\n\n{query}"):
            return
        encoded = urllib.parse.quote(query, safe="")
        urls = [item.data(Qt.UserRole).format(q=encoded) for item in chosen]
        self.open_in_browser(urls[0])
        for url in urls[1:]:
            QDesktopServices.openUrl(QUrl(url))
        stamp = time.strftime("%Y-%m-%d %H:%M")
        self.history.insertItem(0, f"{stamp}  {self.target_type.currentText()}  {query}  ({len(chosen)} sources)")
        self.save_workspace(silent=True)

    def load_workspace(self):
        try:
            data = json.loads(INTEL_CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.case_name.setText(data.get("case_name", ""))
        self.notes.setPlainText(data.get("notes", ""))
        for entry in data.get("history", [])[:100]:
            self.history.addItem(str(entry))

    def save_workspace(self, silent=False):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "case_name": self.case_name.text().strip(),
            "notes": self.notes.toPlainText(),
            "history": [self.history.item(i).text() for i in range(min(100, self.history.count()))],
        }
        INTEL_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if not silent:
            QMessageBox.information(self, "Command Intel", "Investigation workspace saved locally.")


class PlaceholderPage(QWidget):
    def __init__(self, module_id):
        super().__init__()
        layout = QGridLayout(self)
        cards = MODULE_CARDS.get(module_id, [])
        for index, (title, body) in enumerate(cards):
            frame = QFrame()
            frame.setObjectName("card")
            card_layout = QVBoxLayout(frame)
            heading = QLabel(title)
            heading.setObjectName("panelTitle")
            text = QLabel(body)
            text.setWordWrap(True)
            text.setObjectName("muted")
            card_layout.addWidget(heading)
            card_layout.addWidget(text)
            layout.addWidget(frame, index // 3, index % 3)


class PaletteDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Command Palette")
        self.setMinimumWidth(620)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search modules")
        self.list = QListWidget()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.populate)
        self.list.itemDoubleClicked.connect(self.open_item)
        self.populate("")

    def populate(self, query):
        self.list.clear()
        needle = query.lower()
        for module_id, icon, title in MODULES:
            if needle in title.lower() or needle in module_id:
                item = QListWidgetItem(f"{icon}  {title}")
                item.setData(Qt.UserRole, module_id)
                self.list.addItem(item)

    def open_item(self, item):
        self.parent_window.open_module(item.data(Qt.UserRole))
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Command Centre")
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.resize(1280, 820)
        self.setMinimumSize(1120, 720)
        self.telemetry = {}
        self.system = {}
        self.pages = {}
        self.nav_buttons = {}
        self.update_cache = None
        self.update_cache_time = 0
        self.change_history = []

        root = QWidget()
        root.setObjectName("appRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = QVBoxLayout()
        self.stack = QStackedWidget()

        self.sidebar.addWidget(self.brand_widget())

        for module_id, icon, title in MODULES:
            button = QPushButton(f"{icon}  {title}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, m=module_id: self.open_module(m))
            self.nav_buttons[module_id] = button
            self.sidebar.addWidget(button)

            if module_id == "dashboard":
                page = DashboardPage()
            elif module_id == "control":
                page = ControlPage(self)
            elif module_id == "tools":
                page = ToolLibraryPage(self)
            elif module_id == "offline":
                page = OfflineKnowledgePage(self)
            elif module_id == "software":
                page = SoftwarePage(self)
            elif module_id == "command_code":
                page = CommandCodePage(self)
            elif module_id == "intel":
                page = AdvancedCommandIntelPage(self, INTEL_CATEGORIES, INTEL_PROVIDERS)
            elif module_id == "deployment":
                page = DeploymentPage(self)
            else:
                page = PlaceholderPage(module_id)
            self.pages[module_id] = page
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)

        self.sidebar.addStretch()
        side = QWidget()
        side.setObjectName("sidebar")
        side.setLayout(self.sidebar)
        side.setFixedWidth(292)
        shell.addWidget(side)
        shell.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_all)
        self.addAction(refresh_action)

        palette_action = QAction("Command Palette", self)
        palette_action.setShortcut("Ctrl+K")
        palette_action.triggered.connect(self.open_palette)
        self.addAction(palette_action)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(5000)

        self.open_module("dashboard")
        self.refresh_all()

    def brand_widget(self):
        frame = QFrame()
        frame.setObjectName("brand")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("brandLogo")
        logo.setFixedSize(44, 44)
        if LOGO_FILE.exists():
            pixmap = QPixmap(str(LOGO_FILE))
            logo.setPixmap(pixmap.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("CC")
            logo.setAlignment(Qt.AlignCenter)

        text = QLabel("COMMAND CENTRE\nOne system, one mission")
        text.setObjectName("brandText")
        layout.addWidget(logo)
        layout.addWidget(text, 1)
        return frame

    def open_module(self, module_id):
        geometry = self.geometry()
        ids = [item[0] for item in MODULES]
        self.stack.setCurrentIndex(ids.index(module_id))
        for key, button in self.nav_buttons.items():
            button.setChecked(key == module_id)
        if module_id == "control":
            self.pages["control"].refresh()
        if module_id == "software":
            self.pages["software"].refresh()
        if module_id == "tools":
            self.pages["tools"].refresh()
        self.setGeometry(geometry)
        QTimer.singleShot(0, lambda saved=geometry: self.setGeometry(saved))

    def open_palette(self):
        dialog = PaletteDialog(self)
        dialog.exec()

    def add_history(self, message):
        stamp = time.strftime("%H:%M")
        self.change_history.insert(0, f"{stamp}  {message}")
        self.change_history = self.change_history[:20]

    def refresh_all(self):
        self.telemetry = read_telemetry()
        kernel = run_text(["uname", "-r"])[0] or os.uname().release
        uptime = run_text(["uptime", "-p"])[0] or "--"
        failed = run_text(["systemctl", "--failed", "--no-legend", "--no-pager"], 2)[0]
        self.system = {
            "host": os.uname().nodename,
            "kernel": kernel,
            "uptime": uptime,
            "failed": len([line for line in failed.splitlines() if line.strip()]),
            "updates": self.update_count(),
            "load": os.getloadavg()[0] if hasattr(os, "getloadavg") else "--",
            "swap": self.swap_status(),
            "top_processes": self.top_processes(),
            "local_ip": self.local_ip(),
            "connection": self.connection_state(),
            "firewall": self.firewall_state(),
            "storage_health": self.storage_health(),
            "activity": self.recent_activity(),
        }
        self.pages["dashboard"].refresh(self.telemetry, self.system)
        if self.stack.currentWidget() and self.stack.currentIndex() == 1:
            self.pages["control"].refresh()

    def power_state(self):
        if not command_exists("powerprofilesctl"):
            return {"active": "unavailable"}
        return {"active": run_text(["powerprofilesctl", "get"], 1)[0] or "unknown"}

    def wifi_state(self):
        if not command_exists("nmcli"):
            return "nmcli unavailable"
        radio = run_text(["nmcli", "radio", "wifi"], 1)[0] or "unknown"
        devices = run_text(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], 2)[0]
        wifi_lines = [line for line in devices.splitlines() if ":wifi:" in line]
        return radio if not wifi_lines else f"{radio} - " + "; ".join(wifi_lines)

    def bluetooth_state(self):
        if not command_exists("bluetoothctl"):
            return "bluetoothctl unavailable"
        output = run_text(["bluetoothctl", "show"], 2)[0]
        if not output:
            return "not detected"
        powered = "enabled" if re.search(r"Powered:\s+yes", output, re.I) else "disabled"
        name = re.search(r"Name:\s+(.+)", output)
        return f"{powered} - {name.group(1) if name else 'Bluetooth'}"

    def audio_state(self):
        if not command_exists("pactl"):
            return "", []
        default = run_text(["pactl", "get-default-sink"], 1)[0]
        rows = run_text(["pactl", "list", "short", "sinks"], 2)[0]
        sinks = []
        for row in rows.splitlines():
            parts = row.split("\t")
            if len(parts) > 1:
                sinks.append(parts[1])
        return default, sinks

    def user_services(self):
        output = run_text(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"], 3)[0]
        services = []
        for line in output.splitlines()[:160]:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0].endswith(".service"):
                services.append(
                    {
                        "name": parts[0],
                        "active": parts[2],
                        "sub": parts[3],
                        "description": " ".join(parts[4:]),
                    }
                )
        return services

    def update_count(self):
        now = time.time()
        if self.update_cache is not None and now - self.update_cache_time < 180:
            return self.update_cache

        total = 0
        found = False
        if command_exists("checkupdates"):
            output = run_text(["checkupdates"], 8)[0]
            total += len([line for line in output.splitlines() if line.strip()])
            found = True
        if command_exists("yay"):
            output = run_text(["yay", "-Qua"], 8)[0]
            total += len([line for line in output.splitlines() if line.strip()])
            found = True
        elif command_exists("paru"):
            output = run_text(["paru", "-Qua"], 8)[0]
            total += len([line for line in output.splitlines() if line.strip()])
            found = True

        self.update_cache = total if found else None
        self.update_cache_time = now
        return self.update_cache

    def top_processes(self):
        output = run_text(["ps", "-eo", "comm,%cpu,%mem", "--sort=-%cpu"], 2)[0]
        lines = []
        for row in output.splitlines()[1:4]:
            parts = row.split()
            if len(parts) >= 3:
                lines.append(f"{parts[0][:18]:<18} CPU {parts[1]}%   RAM {parts[2]}%")
        return lines or ["No process data"]

    def local_ip(self):
        output = run_text(["hostname", "-I"], 1)[0]
        return output.split()[0] if output.split() else "--"

    def connection_state(self):
        if command_exists("nmcli"):
            output = run_text(["nmcli", "-t", "-f", "TYPE,STATE", "connection", "show", "--active"], 2)[0]
            if "wireless:activated" in output or "wifi:activated" in output:
                return "Wi-Fi connected"
            if "ethernet:activated" in output:
                return "Ethernet connected"
        return "Connected" if self.local_ip() != "--" else "Offline"

    def firewall_state(self):
        for service in ["firewalld.service", "ufw.service"]:
            state = run_text(["systemctl", "is-active", service], 1)[0]
            if state == "active":
                return "Enabled"
        return "Unknown"

    def storage_health(self):
        if command_exists("smartctl"):
            return "CHECKABLE"
        return "UNKNOWN"

    def swap_status(self):
        output = run_text(["free", "-h"], 1)[0]
        for line in output.splitlines():
            if line.startswith("Swap:"):
                parts = line.split()
                if len(parts) >= 3:
                    return f"{parts[2]} used / {parts[1]} total"
        return "--"

    def recent_activity(self):
        data = self.telemetry
        live = [
            f"{metric_value(data, 'timestamp', 'now')}  Telemetry refreshed",
            f"Power profile: {metric_value(data, 'power_profile_label', 'Unknown')}",
            f"Network: {metric_value(data, 'network_iface', 'offline')} / {metric_value(data, 'vpn_status', 'VPN OFF')}",
        ]
        return self.change_history[:5] + live

    def closeEvent(self, event):
        offline = self.pages.get("offline")
        if offline and hasattr(offline, "stop_kiwix_server"):
            offline.stop_kiwix_server()
        super().closeEvent(event)


def main():
    ensure_codex_on_path()
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget {
            background: #05080c;
            color: #edf5fb;
            font-family: Segoe UI, Inter, sans-serif;
            font-size: 13px;
            selection-background-color: #1677b9;
            selection-color: #ffffff;
        }
        #appRoot {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #020407, stop:0.58 #081018, stop:1 #020304);
        }
        #sidebar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #090d12, stop:0.45 #101822, stop:1 #05070a);
            border-right: 1px solid #203245;
        }
        #brand {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #101820, stop:0.55 #0b1118, stop:1 #07111a);
            border: 1px solid #284057;
            border-radius: 8px;
        }
        #brandLogo {
            background: #070b10;
            border: 1px solid #5b7182;
            border-radius: 8px;
        }
        #brandText {
            color: #f2f7fb;
            font-size: 16px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #hero {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #101823, stop:0.55 #080d13, stop:1 #020406);
            border: 1px solid #284963;
            border-radius: 8px;
        }
        #heroLogo {
            background: #020406;
            border: 1px solid #1b8bd2;
            border-radius: 8px;
        }
        #heroEyebrow {
            color: #4abfff;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 3px;
        }
        #heroTitle {
            color: #f6f9fb;
            font-size: 34px;
            font-weight: 900;
            letter-spacing: 5px;
        }
        #heroSubtitle {
            color: #55bdff;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 6px;
        }
        #healthHeader {
            background: rgba(3, 8, 14, 178);
            border: 1px solid #1e8fd5;
            border-radius: 7px;
            padding: 11px 13px;
            font-size: 15px;
            font-weight: 900;
            color: #dff5ff;
            letter-spacing: 1px;
        }
        #navButton {
            text-align: left;
            min-height: 40px;
            padding: 9px 11px;
            border: 1px solid transparent;
            border-radius: 7px;
            background: transparent;
            color: #b9c8d5;
            font-weight: 700;
        }
        #navButton:hover {
            background: #121c27;
            border-color: #2b4d68;
            color: #edf8ff;
        }
        #navButton:checked {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16334a, stop:1 #0d1823);
            border-color: #1e9be8;
            color: #ffffff;
        }
        #card, QFrame#card {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101821, stop:1 #090e14);
            border: 1px solid #25394a;
            border-radius: 8px;
        }
        #intelSearch {
            background: #07131d;
            border: 1px solid #1677a8;
            border-radius: 9px;
        }
        #intelCard {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101c27, stop:1 #080e15);
            border: 1px solid #284458;
            border-radius: 9px;
            min-width: 230px;
        }
        #intelCard:hover {
            border-color: #278fc4;
        }
        #intelCardTitle {
            color: #67d4ff;
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 1px;
            padding: 3px 2px 7px 2px;
            border-bottom: 1px solid #263c4d;
        }
        #intelLink {
            background: transparent;
            border: 0;
            border-radius: 5px;
            padding: 6px 8px;
            color: #d4e4ef;
            text-align: left;
            font-weight: 650;
        }
        #intelLink:hover {
            background: #173047;
            color: #ffffff;
        }
        #adBlockBadge {
            color: #62e394;
            background: #0b2518;
            border: 1px solid #257d4a;
            border-radius: 7px;
            padding: 7px 9px;
            font-size: 11px;
            font-weight: 900;
        }
        #toolRow {
            background: #0a1017;
            border: 1px solid #223344;
            border-radius: 7px;
        }
        #metricValue {
            color: #ffffff;
            font-size: 29px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #muted {
            color: #97a9b8;
        }
        #panelTitle {
            color: #f2f6fa;
            font-size: 15px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #bar {
            background: #111b25;
            border: 1px solid #23384c;
            border-radius: 4px;
            min-height: 8px;
            max-height: 8px;
        }
        #textPanel {
            background: #05080c;
            border: 1px solid #263849;
            border-radius: 7px;
            padding: 9px;
            color: #dcebf5;
        }
        #codexChatLog {
            background: #05080c;
            border: 1px solid #263849;
            border-radius: 7px;
            padding: 8px;
            color: #edf5fb;
        }
        #composerFrame {
            background: #071019;
            border: 1px solid #2d465a;
            border-radius: 8px;
        }
        #codexComposer {
            background: #05080c;
            border: 1px solid #1f3140;
            border-radius: 7px;
            padding: 8px;
            color: #edf5fb;
        }
        #codexComposer:focus {
            border-color: #2bb4ff;
        }
        #modeSelect {
            min-width: 112px;
            background: #10283a;
            border: 1px solid #2aa9ef;
            color: #dff5ff;
            font-weight: 800;
        }
        #primaryButton {
            background: #126aa0;
            border-color: #48c4ff;
            color: #ffffff;
        }
        #primaryButton:hover {
            background: #1688cb;
        }
        #attachButton {
            min-width: 38px;
            max-width: 38px;
            font-size: 20px;
            font-weight: 900;
            padding: 4px 0;
            color: #dff5ff;
            border-color: #2aa9ef;
            background: #0d2232;
        }
        #attachButton:hover {
            background: #15374f;
            border-color: #55bdff;
        }
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1b2734, stop:1 #0e151d);
            border: 1px solid #3a5368;
            border-radius: 7px;
            padding: 8px 11px;
            color: #e7f3fb;
            font-weight: 750;
        }
        QPushButton:hover {
            background: #1f3446;
            border-color: #2bb4ff;
            color: #ffffff;
        }
        QPushButton:pressed {
            background: #07131e;
            border-color: #71d4ff;
        }
        QPushButton:disabled {
            color: #657482;
            background: #11161c;
            border-color: #252f39;
        }
        QPushButton[active="true"] {
            color: #7bd7ff;
            border-color: #39bfff;
            background: #10283a;
        }
        QComboBox, QLineEdit, QListWidget {
            background: #05080c;
            border: 1px solid #263849;
            border-radius: 7px;
            padding: 7px;
            color: #edf5fb;
        }
        QComboBox:hover, QLineEdit:focus, QListWidget:focus {
            border-color: #238ed0;
        }
        QTreeView, QPlainTextEdit, QTabWidget::pane {
            background: #05080c;
            border: 1px solid #263849;
            color: #edf5fb;
        }
        QPlainTextEdit {
            selection-background-color: #1e78ad;
            font-family: JetBrains Mono, Cascadia Code, monospace;
        }
        QTabBar::tab {
            background: #0e151d;
            border: 1px solid #28394a;
            padding: 8px 12px;
            color: #b8c8d6;
        }
        QTabBar::tab:selected {
            background: #172536;
            color: #77d6ff;
            border-color: #259de3;
        }
        QScrollArea {
            border: 0;
            background: transparent;
        }
        QScrollBar:vertical {
            background: #060a0f;
            width: 10px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #27445a;
            border-radius: 4px;
            min-height: 32px;
        }
        QScrollBar::handle:vertical:hover {
            background: #2aa9ef;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QListWidget::item {
            padding: 9px;
            border-bottom: 1px solid #1a2631;
        }
        QListWidget::item:hover {
            background: #101c28;
        }
        QListWidget::item:selected {
            background: #173148;
            color: #ffffff;
        }
        """
    )
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
