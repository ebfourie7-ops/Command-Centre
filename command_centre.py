#!/usr/bin/env python3
import json
import html
import hashlib
import math
import os
import re
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import urllib.parse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.shell_actions import (
    AUDIT_LOG, ActionValidationError, audited_launch, audited_shell_script,
    parse_program_command, run_argv, validate_environment, validate_package,
    validate_service, validate_url, validate_user_path,
)
from core.config_schema import ConfigValidationError, validate_agent_config, validate_deployment_profiles
from core.events import SystemEventStore
from core.telemetry import read_telemetry

from PySide6.QtCore import (QEasingCurve, QFileSystemWatcher, QPointF, Property,
                            QPropertyAnimation, QRectF, QSize, Qt, QProcess,
                            QProcessEnvironment, QTimer, QUrl)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplashScreen,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from command_intel import AdvancedCommandIntelPage


APP_VERSION = "1.1.0"
CONFIG_DIR = Path.home() / ".config/command-centre"
OFFLINE_CONFIG = CONFIG_DIR / "offline_knowledge.json"
OFFLINE_DB_FILE = CONFIG_DIR / "offline_knowledge.db"
CODEX_USAGE_CONFIG = CONFIG_DIR / "codex_usage.json"
CHAT_LOG_DIR = CONFIG_DIR / "chat-logs"
AGENT_TASK_DIR = CONFIG_DIR / "agent-tasks"
AGENT_CONFIG_FILE = CONFIG_DIR / "agent_hub.json"
USER_DEPLOYMENTS_CONFIG = CONFIG_DIR / "deployment_profiles.json"
INTEL_CONFIG = CONFIG_DIR / "command_intel.json"
CONTROL_QUEUE_FILE = CONFIG_DIR / "control_queue.json"
TOOL_STATE_FILE = CONFIG_DIR / "tool_library_state.json"
SOFTWARE_HISTORY_FILE = CONFIG_DIR / "software_history.json"
SYSTEM_EVENTS_DB = CONFIG_DIR / "system_events.db"
COMMANDOS_CURATED_CATALOG = {
    "Audio": [
        "strawberry", "lollypop", "audacious", "elisa", "kwave", "audacity", "ardour", "lmms",
        "mixxx", "musescore", "rosegarden",
    ],
    "Browsers": [
        "librewolf-bin", "firefox", "firefox-esr-bin", "firefox-pure", "chromium",
        "ungoogled-chromium-bin", "vivaldi + vivaldi-ffmpeg-codecs", "torbrowser-launcher",
        "brave-bin", "floorp-bin", "falkon", "qutebrowser + python-adblock",
    ],
    "Communication": [
        "telegram-desktop", "discord", "neochat", "fractal", "element-desktop", "wire-desktop",
        "signal-desktop", "mumble",
    ],
    "Development": [
        "vim", "code", "emacs", "qtcreator", "gnome-builder", "kdevelop", "netbeans",
        "intellij-idea-community-edition", "pycharm-community-edition",
        "cockpit + cockpit-machines", "ansible", "docker + docker-compose",
        "podman-docker + podman-compose + crun", "jenkins", "puppet", "prometheus", "terraform",
    ],
    "Games": [
        "cachyos-gaming-applications + cachyos-gaming-meta", "aisleriot", "mari0", "kapman",
        "knights", "kmahjongg", "supertuxkart", "supertux", "extremetuxracer", "0ad",
        "teeworlds", "xonotic", "hedgewars",
    ],
    "Graphics": [
        "krita + krita-plugin-gmic + opencolorio", "gimp", "inkscape", "blender", "digikam",
        "darktable", "luminancehdr", "kolourpaint", "mypaint", "sweethome3d", "freecad",
        "librecad", "kicad", "pencil2d", "synfigstudio", "opentoonz", "fontforge", "birdfont",
    ],
    "Hardware Tools": [
        "amdgpu_top", "cachyos-benchmarker", "coolercontrol", "cpu-x", "gparted", "kdiskmark",
        "lact", "nvtop", "occt", "openlinkhub", "openrgb", "rog-control-center",
    ],
    "Internet": [
        "xdman", "freedownloadmanager", "deluge-gtk", "qbittorrent", "nextcloud-client", "remmina",
        "filezilla", "putty", "warpinator", "nitroshare", "jdownloader2",
    ],
    "Mail": ["thunderbird", "kmail", "evolution", "geary", "mailspring", "claws-mail"],
    "Multimedia": [
        "hypnotix", "shortwave", "converseen", "handbrake", "transmageddon", "soundconverter",
        "kodi + kodi-platform + kodi-eventclients", "mediaelch", "kid3", "easytag",
        "k3b + cdparanoia + cdrdao + dvd+rw-tools + emovix + vcdimager + cdrtools",
        "brasero", "xfburn",
    ],
    "Office": [
        "libreoffice-fresh + libmythes", "libreoffice-still + libmythes", "joplin", "onlyoffice-bin",
        "wps-office + wps-office-mime", "yozo-office + yozo-office-fonts", "calligra", "skrooge",
        "kmymoney", "abiword", "gnumeric", "gnucash", "homebank",
    ],
    "Other": ["scrcpy", "variety"],
    "Video": [
        "kdenlive + movit + sox + opus-tools + frei0r-plugins + opentimelineio + dvgrab + opencv",
        "dragon", "shotcut", "pitivi + frei0r-plugins", "obs-studio", "vlc",
        "smplayer + smplayer-skins + smplayer-themes", "baka-mplayer",
    ],
    "Virtualization": ["virtualbox", "gnome-boxes", "virt-manager"],
}
CURATED_CATEGORY_DESCRIPTIONS = {
    "Audio": "Music playback, recording, production, DJ, notation, or audio editing application.",
    "Browsers": "Web browser selected for privacy, compatibility, or specialized workflows.",
    "Communication": "Messaging, collaboration, voice, or secure communication client.",
    "Development": "Development, automation, container, infrastructure, or operations tooling.",
    "Games": "Game or curated gaming platform package for CommandOS.",
    "Graphics": "Graphics, photography, animation, CAD, publishing, or creative-design application.",
    "Hardware Tools": "Hardware monitoring, configuration, benchmarking, or diagnostics utility.",
    "Internet": "Download, remote access, file transfer, synchronization, or network utility.",
    "Mail": "Desktop email and personal-information management client.",
    "Multimedia": "Media conversion, playback, tagging, streaming, or optical-disc application.",
    "Office": "Documents, notes, finance, spreadsheets, or office productivity suite.",
    "Other": "Useful desktop utility selected for CommandOS.",
    "Video": "Video playback, capture, editing, streaming, or production application.",
    "Virtualization": "Virtual machine creation and management platform.",
}
DEPLOYMENT_STATE_FILE = CONFIG_DIR / "deployment_state.json"
APP_DIR = Path(__file__).resolve().parent
DEVELOPMENT_LOGO_FILE = APP_DIR / "command-centre-icon.png"
INSTALLED_LOGO_FILE = APP_DIR / "logo.png"
LOGO_FILE = DEVELOPMENT_LOGO_FILE if DEVELOPMENT_LOGO_FILE.exists() else INSTALLED_LOGO_FILE
SPLASH_FILE = APP_DIR / "splash.png"
INVENTORY_DIR = APP_DIR / "inventory"
DEFAULT_DEPLOYMENTS_FILE = APP_DIR / "deployments/default_deployments.json"
CURATED_TOOLS_FILE = APP_DIR / "tools/curated_tools.json"
FCC_REPOSITORY = "https://github.com/Alishahryar1/free-claude-code.git"
FCC_AUDITED_COMMIT = "5ffa47fbc39d5d7b9ea82987c49ff79985be140f"
RESOURCE_DIR = APP_DIR / "resources"
COMMAND_WIDGET_DIR = RESOURCE_DIR / "command-widget"
COMMAND_PDF_DIR = RESOURCE_DIR / "command-pdf"
COMMAND_WIDGET_VERSION_FILE = COMMAND_WIDGET_DIR / "VERSION"
COMMAND_WIDGET_VERSION = COMMAND_WIDGET_VERSION_FILE.read_text(encoding="utf-8").strip() if COMMAND_WIDGET_VERSION_FILE.is_file() else "Unknown"


def safe_read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def harden_private_storage():
    """Restrict Command Centre state, chats, tasks, and investigations to this user."""
    roots = [CONFIG_DIR, Path.home() / ".local/share/command-centre", Path.home() / ".local/state/command-centre"]
    for root in roots:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try: root.chmod(0o700)
        except OSError: pass
        for path in root.rglob("*"):
            try:
                if path.is_symlink(): continue
                path.chmod(0o700 if path.is_dir() else 0o600)
            except OSError: pass


MODULES = [
    ("dashboard", "dashboard", "System Dashboard"),
    ("software", "package", "Software Centre"),
    ("tools", "tools", "Tool Library"),
    ("command_code", "terminal", "Command Terminal"),
    ("offline", "book", "Offline Knowledge"),
    ("command_apps", "apps", "Command Apps"),
    ("intel", "brain", "Command Intel"),
]

MODULE_DESCRIPTIONS = {
    "dashboard": "Health & telemetry",
    "software": "Updates & packages",
    "tools": "Installed utilities",
    "command_code": "Command shell",
    "offline": "Documentation",
    "command_apps": "Built-in modules",
    "intel": "AI recommendations",
}

MODULE_SECTIONS = [
    ("SYSTEM", ("dashboard",)),
    ("SOFTWARE", ("software",)),
    ("TOOLS", ("tools", "command_code", "offline")),
    ("APPLICATIONS", ("command_apps", "intel")),
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
        result = run_argv(command, action="read-only probe", timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return "", str(error), 127


def command_exists(command):
    return shutil.which(command) is not None


def detected_gpu_devices():
    """Return every DRM GPU, including hybrid-system integrated graphics."""
    devices = []
    seen_slots = set()
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        if not re.fullmatch(r"card\d+", card.name):
            continue
        device = card / "device"
        try:
            slot = device.resolve().name
            vendor = (device / "vendor").read_text().strip().lower()
        except (OSError, FileNotFoundError):
            continue
        if slot in seen_slots:
            continue
        seen_slots.add(slot)

        output = run_text(["lspci", "-s", slot], 2)[0] if command_exists("lspci") else ""
        match = re.search(r"(?:VGA compatible|3D|Display) controller:\s*(.+?)(?:\s+\(rev\s+[0-9a-f]+\))?$", output, re.I)
        name = match.group(1).strip() if match else {
            "0x1002": "AMD GPU",
            "0x8086": "Intel GPU",
            "0x10de": "NVIDIA GPU",
        }.get(vendor, "Graphics device")
        devices.append({"name": name, "vendor": vendor, "slot": slot})

    if len(devices) > 1:
        for gpu in devices:
            gpu["type"] = "Discrete" if gpu["vendor"] == "0x10de" else "Integrated"
    elif devices:
        devices[0]["type"] = "GPU"
    return devices


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
    try:
        audited_shell_script(command, action=f"terminal: {title}", trusted=True)
    except ActionValidationError as error:
        return False, str(error)
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
    def __init__(self, title, icon="◇", accent="#00AEEF"):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("accent", accent)
        self.title = QLabel(f"{icon}   {title}")
        self.title.setObjectName("panelTitle")
        self.body = QLabel("--")
        self.body.setObjectName("muted")
        self.body.setWordWrap(True)
        self.body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.click_handler = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(4)
        self.content_layout = layout
        layout.addWidget(self.title)
        layout.addWidget(self.body)

    def set_text(self, text):
        self.body.setText(text)

    def set_click_handler(self, handler):
        self.click_handler = handler
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Open details")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.click_handler:
            self.click_handler()
        super().mousePressEvent(event)


class Sparkline(QWidget):
    def __init__(self, color="#49bfff", parent=None):
        super().__init__(parent)
        # Five-second samples retained for a rolling ten-minute dashboard view.
        self.values = deque(maxlen=120)
        self.color = QColor(color)
        self.setMinimumHeight(42)
        self.setMaximumHeight(42)

    def add_value(self, value):
        try:
            self.values.append(float(value))
        except (TypeError, ValueError):
            self.values.append(None)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#081019"))
        painter.setPen(QPen(QColor("#21384a"), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        if len(self.values) < 2:
            return
        valid = [value for value in self.values if value is not None]
        if not valid:
            return
        high = max(100.0, max(valid))
        step = self.width() / max(1, self.values.maxlen - 1)
        painter.setPen(QPen(self.color, 2))
        segment = []
        for index, value in enumerate(self.values):
            if value is None:
                if len(segment) > 1:
                    painter.drawPolyline(QPolygonF(segment))
                segment = []
                continue
            y = self.height() - 4 - (value / high) * (self.height() - 8)
            segment.append(QPointF(index * step, y))
        if len(segment) > 1:
            painter.drawPolyline(QPolygonF(segment))


class RadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.setFixedSize(220, 94)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(50)

    def advance(self):
        self.angle = (self.angle + 2) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPointF(50, 47)
        painter.setPen(QPen(QColor("#164968"), 1))
        for radius in (18, 34, 47):
            painter.drawEllipse(center, radius, radius)
        painter.drawLine(3, 47, 97, 47)
        painter.drawLine(50, 0, 50, 94)
        radians = self.angle * 3.14159265 / 180
        endpoint = QPointF(center.x() + 47 * math.cos(radians), center.y() - 47 * math.sin(radians))
        painter.setPen(QPen(QColor("#00AEEF"), 2))
        painter.drawLine(center, endpoint)
        painter.setBrush(QColor("#35D66B"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(76, 30), 2.5, 2.5)
        painter.setPen(QColor("#E9F3FB"))
        painter.setFont(QFont("Inter", 18, QFont.Bold))
        painter.drawText(108, 35, time.strftime("%H:%M"))
        painter.setFont(QFont("Inter", 9, QFont.DemiBold))
        painter.setPen(QColor("#B5BDC6"))
        painter.drawText(108, 55, time.strftime("%d %b %Y").upper())
        painter.drawText(108, 73, "CAPE TOWN")


class ReadinessGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 0
        self.setFixedSize(142, 142)

    def set_score(self, score):
        self.score = max(0, min(100, int(score)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(12, 12, -12, -12)
        painter.setPen(QPen(QColor("#16344D"), 10))
        painter.drawArc(rect, 0, 360 * 16)
        color = QColor("#35D66B" if self.score >= 85 else "#00AEEF" if self.score >= 70 else "#F4B942")
        painter.setPen(QPen(color, 10, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self.score / 100))
        painter.setPen(QColor("#F4F7FA"))
        painter.setFont(QFont("Inter", 29, QFont.Bold))
        painter.drawText(0, 39, self.width(), 42, Qt.AlignCenter, f"{self.score}%")
        painter.setPen(QColor("#B5BDC6"))
        painter.setFont(QFont("Inter", 9, QFont.DemiBold))
        painter.drawText(0, 78, self.width(), 25, Qt.AlignCenter, "MISSION READY")


class SoftwareHealthGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 0
        self.status = "CHECKING"
        self.setFixedSize(116, 116)

    def set_score(self, score):
        self.score = max(0, min(100, int(score)))
        self.status = "HEALTHY" if self.score >= 85 else "GOOD" if self.score >= 65 else "ATTENTION"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(9, 9, -9, -9)
        painter.setPen(QPen(QColor("#16344D"), 11))
        painter.drawArc(rect, 0, 360 * 16)
        color = "#42E978" if self.score >= 85 else "#22C8FF" if self.score >= 65 else "#FFBF32" if self.score >= 40 else "#FF5B64"
        painter.setPen(QPen(QColor(color), 11, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self.score / 100))
        painter.setPen(QColor("#F2F6FA"))
        painter.setFont(QFont("Inter", 25, QFont.Bold))
        painter.drawText(QRectF(0, self.height() / 2 - 25, self.width(), 34), Qt.AlignCenter, f"{self.score}%")
        painter.setPen(QColor("#42E978" if self.score >= 65 else "#FFBF32"))
        painter.setFont(QFont("Inter", 8, QFont.Bold))
        painter.drawText(QRectF(0, self.height() / 2 + 8, self.width(), 18), Qt.AlignCenter, self.status)


class SoftwareMetricCard(QFrame):
    def __init__(self, icon, title, accent):
        super().__init__()
        self.setObjectName("softwareMetricCard")
        self.setProperty("accent", accent)
        self.setMaximumHeight(132)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(3)
        self.icon = QLabel(icon)
        self.icon.setObjectName("softwareMetricIcon")
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setFixedSize(34, 34)
        self.title = QLabel(title)
        self.title.setObjectName("softwareMetricTitle")
        self.value = QLabel("—")
        self.value.setObjectName("softwareMetricValue")
        self.detail = QLabel("Checking…")
        self.detail.setObjectName("softwareMetricDetail")
        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_state(self, value, detail, state="info"):
        self.value.setText(str(value))
        self.detail.setText(detail)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class TelemetryCard(QFrame):
    def __init__(self, title, color="#49bfff", icon="◈"):
        super().__init__()
        self.setObjectName("card")
        self.setMaximumHeight(180)
        self.click_handler = None
        self.setProperty("accent", color)
        self.title = QLabel(f"{icon}   {title}")
        self.title.setObjectName("panelTitle")
        self.value = QLabel("--")
        self.value.setObjectName("metricValue")
        self.detail = QLabel("Waiting for telemetry")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.usage_bar = QProgressBar()
        self.usage_bar.setObjectName("metricBar")
        self.usage_bar.setProperty("accent", color)
        self.usage_bar.setRange(0, 100)
        self.usage_bar.setTextVisible(False)
        self.usage_bar.setFixedHeight(7)
        self.sparkline = Sparkline(color)
        self.sparkline.setMinimumHeight(22)
        self.sparkline.setMaximumHeight(22)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(3)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.usage_bar)
        layout.addWidget(self.detail)
        layout.addWidget(self.sparkline)

    def set_metric(self, value, detail, history_value):
        self.value.setText(value)
        self.detail.setText(detail)
        self.usage_bar.setValue(max(0, min(100, int(float(history_value or 0)))))
        self.sparkline.add_value(history_value)

    def set_click_handler(self, handler):
        self.click_handler = handler
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Open details")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.click_handler:
            self.click_handler()
        super().mousePressEvent(event)


class DashboardPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.last_telemetry_timestamp = None
        self.header = QLabel("--")
        self.header.setObjectName("heroStatus")
        self.header.setWordWrap(True)
        self.header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.cpu = TelemetryCard("CPU", "#00AEEF", "▣")
        self.gpu = TelemetryCard("GPU", "#35D66B", "▤")
        self.memory = TelemetryCard("MEMORY", "#A55DFF", "▥")
        self.storage_summary = TelemetryCard("STORAGE", "#F0B230", "▧")
        self.health = CockpitCard("SYSTEM HEALTH", "♥", "#35D66B")
        self.health.setMaximumHeight(150)
        self.readiness = CockpitCard("COMMAND STATUS", "◎", "#00AEEF")
        self.readiness.setMinimumHeight(245)
        self.readiness.setMaximumHeight(260)
        self.readiness_gauge = ReadinessGauge()
        self.readiness.content_layout.removeWidget(self.readiness.body)
        readiness_content = QHBoxLayout()
        readiness_content.setSpacing(18)
        readiness_content.addWidget(self.readiness_gauge)
        readiness_content.addWidget(self.readiness.body, 1)
        self.readiness.body.setObjectName("readinessDetail")
        self.readiness.content_layout.addLayout(readiness_content)
        self.readiness_bar = QProgressBar()
        self.readiness_bar.setRange(0, 100)
        self.readiness_bar.setTextVisible(True)
        self.readiness.content_layout.addWidget(self.readiness_bar)
        readiness_details = QPushButton("VIEW SCORE BREAKDOWN")
        readiness_details.clicked.connect(self.show_readiness_breakdown)
        self.readiness.content_layout.addWidget(readiness_details)
        self.intelligence = CockpitCard("COMMAND INTELLIGENCE", "✦", "#A55DFF")
        self.intelligence.setMinimumHeight(245)
        self.intelligence.setMaximumHeight(260)
        self.intelligence.body.setTextFormat(Qt.RichText)
        self.power = CockpitCard("BATTERY & POWER", "▥", "#35D66B")
        self.network = CockpitCard("NETWORK HEALTH", "≋", "#00AEEF")
        self.security = CockpitCard("SECURITY POSTURE", "◆", "#35D66B")
        self.storage_health = CockpitCard("DISK & SNAPSHOT HEALTH", "▨", "#00AEEF")
        self.kernel_state = CockpitCard("KERNEL & DRIVER STATE", ">_", "#8CB7D7")
        for card in (self.power, self.network, self.security, self.storage_health, self.kernel_state):
            card.setMinimumHeight(112)
            card.setMaximumHeight(122)
        self.activity = CockpitCard("RECENT ACTIVITY", "◷", "#00AEEF")
        self.activity.setMinimumHeight(301)
        self.activity.content_layout.removeWidget(self.activity.body)
        self.activity.body.hide()
        self.activity_rows = QVBoxLayout()
        self.activity_rows.setSpacing(3)
        self.activity.content_layout.addLayout(self.activity_rows)
        timeline_button = QPushButton("VIEW FULL SYSTEM TIMELINE")
        timeline_button.clicked.connect(self.parent_window.show_system_timeline)
        self.activity.content_layout.addWidget(timeline_button)
        self.alerts_frame, self.alerts_layout = self.panel("⚠   ALERTS & RECOMMENDATIONS")
        self.alerts_frame.setMinimumHeight(150)
        self.alerts_frame.setMaximumHeight(160)
        self.alerts_layout.setContentsMargins(12, 7, 12, 7)
        self.alerts_layout.setSpacing(4)
        self.alerts_details = QPushButton("OPEN ACTION CENTRE")
        self.alerts_details.setObjectName("alertAction")
        self.alerts_details.setFixedHeight(22)
        self.alerts_details.clicked.connect(lambda: self.open_detail("alerts"))
        self.quick_frame, quick_layout = self.panel("◈   QUICK ACTIONS")
        self.quick_frame.setMaximumHeight(130)
        actions = QGridLayout()
        actions.setSpacing(8)
        for index, (label, standard_icon, callback) in enumerate([
            ("CHECK UPDATES", QStyle.SP_BrowserReload, lambda: self.parent_window.open_module("software")),
            ("OPEN TERMINAL", QStyle.SP_ComputerIcon, lambda: self.parent_window.open_module("command_code")),
            ("SYSTEM INFORMATION", QStyle.SP_MessageBoxInformation, self.open_system_information),
            ("TELEMETRY STATUS", QStyle.SP_DriveNetIcon, self.show_telemetry_status),
        ]):
            button = QToolButton()
            button.setText(label)
            button.setObjectName("quickActionButton")
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setIcon(self.style().standardIcon(standard_icon))
            button.setIconSize(QSize(28, 28))
            button.setMinimumHeight(62)
            button.clicked.connect(callback)
            actions.addWidget(button, 0, index)
        quick_layout.addLayout(actions)

        for key, card in {
            "cpu": self.cpu, "gpu": self.gpu, "memory": self.memory,
            "storage": self.storage_summary, "power": self.power,
            "network": self.network, "security": self.security,
            "disk": self.storage_health, "kernel": self.kernel_state,
            "readiness": self.readiness,
        }.items():
            card.set_click_handler(lambda selected=key: self.open_detail(selected))

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(11)
        metrics.setVerticalSpacing(11)
        for index, card in enumerate([self.cpu, self.gpu, self.memory, self.storage_summary]):
            metrics.addWidget(card, 0, index)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(11)
        status_grid.setVerticalSpacing(11)
        status_grid.addWidget(self.power, 0, 0)
        status_grid.addWidget(self.network, 0, 1)
        status_grid.addWidget(self.kernel_state, 0, 2)
        status_grid.addWidget(self.security, 1, 0)
        status_grid.addWidget(self.storage_health, 1, 1)
        status_grid.addWidget(self.health, 1, 2)
        for column in range(3):
            status_grid.setColumnStretch(column, 1)

        command_overview = QGridLayout()
        command_overview.setHorizontalSpacing(11)
        command_overview.addWidget(self.readiness, 0, 0)
        command_overview.addWidget(self.intelligence, 0, 1)
        command_overview.setColumnStretch(0, 2)
        command_overview.setColumnStretch(1, 1)

        lower_console = QGridLayout()
        lower_console.setHorizontalSpacing(11)
        lower_console.setVerticalSpacing(11)
        lower_console.addWidget(self.activity, 0, 0, 2, 1)
        lower_console.addWidget(self.alerts_frame, 0, 1)
        lower_console.addWidget(self.quick_frame, 1, 1)
        lower_console.setColumnStretch(0, 1)
        lower_console.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(11)
        layout.addWidget(self.hero_panel())
        layout.addLayout(command_overview)
        layout.addLayout(metrics)
        layout.addLayout(status_grid)
        layout.addLayout(lower_console, 1)

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(7)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def hero_panel(self):
        frame = QFrame()
        frame.setObjectName("hero")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 7, 16, 7)
        layout.setSpacing(4)

        copy = QVBoxLayout()
        eyebrow = QLabel("⌖  WELCOME, COMMANDER")
        eyebrow.setObjectName("heroEyebrow")
        title = QLabel("COMMAND CENTRE")
        title.setObjectName("heroTitle")
        subtitle = QLabel("ONE SYSTEM  •  ONE MISSION")
        subtitle.setObjectName("heroSubtitle")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        self.mission_status = QHBoxLayout()
        self.mission_status.setSpacing(7)
        self.status_labels = {}
        for key, text, state in [
            ("system", "●  SYSTEM\nCHECKING", "warning"),
            ("power", "⚡  POWER\nCHECKING", "success"),
            ("uptime", "◷  UPTIME\n--", "info"),
            ("updates", "↑  UPDATES\n--", "info"),
            ("telemetry", "●  TELEMETRY\nCHECKING", "success"),
            ("vpn", "◆  VPN\nCHECKING", "info"),
            ("battery", "▥  BATTERY\nCHECKING", "success"),
        ]:
            label = QLabel(text)
            label.setObjectName("missionChip")
            label.setProperty("state", state)
            self.status_labels[key] = label
            self.mission_status.addWidget(label)
        self.mission_status.addStretch()
        copy.addLayout(self.mission_status)

        layout.addLayout(copy, 1)
        layout.addWidget(RadarWidget())
        return frame

    def refresh(self, data, system):
        self.latest_data = dict(data)
        self.latest_system = dict(system)
        issues = self.issue_list(data, system)
        health = "HEALTHY"
        if any(issue[0] == "CRITICAL" for issue in issues):
            health = "CRITICAL"
        elif sum(issue[0] == "WARNING" for issue in issues) >= 2:
            health = "DEGRADED"
        elif issues:
            health = "WARNING"

        updates = system.get("updates")
        updates_text = "updates unknown" if updates is None else f"{updates} updates"
        telemetry_state = "LIVE" if data else "UNAVAILABLE"
        self.status_labels["system"].setText(f"●  SYSTEM\n{health}")
        self.status_labels["power"].setText(f"⚡  POWER\n{metric_value(data, 'power_profile_label', 'Unknown').upper()}")
        self.status_labels["uptime"].setText(f"◷  UPTIME\n{system.get('uptime', '--').replace('up ', '').upper()}")
        self.status_labels["updates"].setText(f"↑  UPDATES\n{updates_text.upper()}")
        self.status_labels["telemetry"].setText(f"●  TELEMETRY\n{telemetry_state}")
        self.status_labels["vpn"].setText(f"◆  VPN\n{str(data.get('vpn_status', 'UNKNOWN')).upper()}")
        self.status_labels["battery"].setText(f"▥  BATTERY\n{data.get('battery_percent', '--')}%")
        self.status_labels["system"].setProperty("state", "success" if health == "HEALTHY" else "critical" if health == "CRITICAL" else "warning")
        for label in self.status_labels.values():
            label.style().unpolish(label)
            label.style().polish(label)

        self.cpu.set_metric(
            f"{float(data.get('cpu_usage') or 0):.1f}%",
            f"{metric_value(data, 'cpu_temp', 'n/a')}°C  ·  {metric_value(data, 'cpu_frequency', 'n/a')}  ·  Load {system.get('load', '--')}\n"
            f"Governor {system.get('cpu_governor', 'unknown')}  ·  Profile {metric_value(data, 'power_profile_label', 'unknown')}",
            data.get("cpu_usage") if data else None,
        )
        self.gpu.set_metric(
            f"{float(data.get('gpu_usage') or 0):.0f}%",
            f"{metric_value(data, 'gpu_temp', 'n/a')}°C  ·  {metric_value(data, 'gpu_vram', 'VRAM n/a')} VRAM\n"
            + ("\n".join(f"{gpu['type']}: {gpu['name']}" for gpu in data.get("gpu_devices", []))
               or metric_value(data, 'gpu_name', 'GPU not reported'))
            + f"\nDriver {system.get('gpu_driver', 'unknown')}  ·  {system.get('gpu_state', 'state unknown')}  ·  {system.get('gpu_power', '--')}",
            data.get("gpu_usage") if data else None,
        )
        self.memory.set_metric(
            f"{float(data.get('ram_usage') or 0):.1f}%",
            f"{metric_value(data, 'ram_info', '--')}\nSwap {system.get('swap', '--')}",
            data.get("ram_usage") if data else None,
        )
        self.storage_summary.set_metric(
            f"{metric_value(data, 'storage_percent', '--')}%",
            f"{metric_value(data, 'storage_usage', '--')}\nR {metric_value(data, 'storage_read', '0 B/s')}  ·  W {metric_value(data, 'storage_write', '0 B/s')}",
            data.get("storage_percent") if data else None,
        )

        self.health.set_text("\n".join(self.health_lines(data, system)))
        score, deductions, readiness = self.readiness_result(data, system)
        self.readiness_bar.setValue(score)
        self.readiness_gauge.set_score(score)
        self.readiness.set_text("\n".join(readiness))
        self.readiness_deductions = deductions
        self.intelligence.set_text(self.intelligence_summary(data, system, issues))
        battery = system.get("battery", {})
        self.power.set_text(
            f"{data.get('battery_percent', '--')}% · {battery.get('status', data.get('battery_status', 'Unknown'))}\n"
            f"Health {battery.get('health', '--')} · Draw {battery.get('power', data.get('battery_watts', '--'))}\n"
            f"Profile {metric_value(data, 'power_profile_label', 'Unknown')}"
        )
        self.network.set_text(
            f"{system.get('connection', 'Unknown')} · {system.get('local_ip', '--')}\n"
            f"VPN {data.get('vpn_status', 'Unknown')} · Latency {system.get('latency', '--')}\n"
            f"↓ {data.get('network_down', '0 B/s')} · ↑ {data.get('network_up', '0 B/s')} · DNS {system.get('dns', 'Unknown')}"
        )
        security = system.get("security", {})
        self.security.set_text(
            f"Firewall {system.get('firewall', 'Unknown')} · Secure Boot {security.get('secure_boot', 'Unknown')}\n"
            f"Disk encryption {security.get('encryption', 'Unknown')} · SSH {security.get('ssh', 'Unknown')}\n"
            f"Listening ports {security.get('ports', '--')} · Updates {system.get('updates', 'unknown')}"
        )
        self.storage_health.set_text(
            f"Root {data.get('storage_percent', '--')}% · {system.get('storage_health', 'Unknown')}\n"
            f"Snapshots {system.get('snapshot', 'Unavailable')}\nFilesystem {system.get('filesystem', 'Unknown')}"
        )
        boot_time = str(system.get("boot_time", "--"))
        boot_total = re.search(r"=\s*(.+)$", boot_time)
        boot_summary = boot_total.group(1) if boot_total else boot_time
        self.kernel_state.set_text(
            f"Kernel {system.get('kernel', '--')}\nNVIDIA {system.get('gpu_driver', 'not detected')} · {system.get('gpu_state', 'unknown')}\n"
            f"Boot {boot_summary} · Reboot {system.get('reboot_required', 'not required')}"
        )
        self.render_alerts(issues)
        self.render_activity(system.get("activity", ["No recent activity recorded."]))

    def intelligence_summary(self, data, system, issues):
        updates = system.get("updates") or 0
        snapshot = system.get("snapshot", "Unavailable")
        gpu_power = system.get("gpu_power", "--")
        battery = system.get("battery", {})
        battery_percent = data.get("battery_percent", "--")
        if updates:
            estimate = max(2, round(updates * 0.25))
            reboot = "No reboot is currently expected" if system.get("reboot_required") != "required" else "A reboot is already pending"
            recommendation = f"Install {updates} available updates"
            estimate_text = f"Estimated time: {estimate} minutes · {reboot}"
        elif issues:
            recommendation = issues[0][1]
            estimate_text = "Review the evidence before applying changes"
        else:
            recommendation = "No immediate action required"
            estimate_text = "The system is within its operating thresholds"
        backup_note = "Create a Btrfs snapshot before updating" if snapshot in ("Unavailable", "None found") else "Snapshot protection is available"
        return (
            "<div style='line-height:125%;'>"
            "<span style='color:#A55DFF; font-weight:700;'>✦ RECOMMENDATION</span><br>"
            f"<span style='color:#F2F6FA; font-size:15px; font-weight:700;'>{html.escape(recommendation)}</span><br>"
            f"<span style='color:#B5BDC6;'>{html.escape(estimate_text)}</span>"
            "<hr style='color:#16344D;'>"
            "<span style='color:#35D66B; font-weight:700;'>⚡ POWER</span><br>"
            f"Battery {battery_percent}% · GPU idle draw {html.escape(str(gpu_power))}"
            "<hr style='color:#16344D;'>"
            "<span style='color:#00AEEF; font-weight:700;'>◎ NEXT ACTION</span><br>"
            f"<span style='color:#F2F6FA; font-weight:700;'>{html.escape(backup_note)}</span>"
            "</div>"
        )

    def render_activity(self, entries):
        while self.activity_rows.count():
            item = self.activity_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for entry in entries[:5]:
            parts = str(entry).split(maxsplit=2)
            stamp = parts[0] if parts and re.fullmatch(r"\d{1,2}:\d{2}", parts[0]) else "--:--"
            category = parts[1] if len(parts) > 1 else "SYSTEM"
            message = parts[2] if len(parts) > 2 else str(entry)
            row = QFrame()
            row.setObjectName("activityRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(9, 3, 9, 3)
            time_label = QLabel(stamp)
            time_label.setObjectName("activityTime")
            category_label = QLabel(category)
            category_label.setObjectName("activityCategory")
            message_label = QLabel(message)
            message_label.setObjectName("activityMessage")
            detail = QVBoxLayout()
            detail.setContentsMargins(0, 0, 0, 0)
            detail.setSpacing(0)
            detail.addWidget(category_label)
            detail.addWidget(message_label)
            row_layout.addWidget(time_label, 0, Qt.AlignTop)
            row_layout.addLayout(detail, 1)
            self.activity_rows.addWidget(row)

    def open_detail(self, key):
        data = getattr(self, "latest_data", {})
        system = getattr(self, "latest_system", {})
        titles = {
            "cpu": "CPU DETAILS", "gpu": "GPU DETAILS", "memory": "MEMORY DETAILS",
            "storage": "STORAGE ACTIVITY", "power": "BATTERY & POWER",
            "network": "NETWORK DETAILS", "security": "SECURITY REPORT",
            "disk": "DISK & SNAPSHOT DETAILS", "kernel": "KERNEL & DRIVER DETAILS",
            "readiness": "READINESS SCORE", "alerts": "ACTION CENTRE",
        }
        content = self.detail_content(key, data, system)
        self.parent_window.open_dashboard_drawer(titles.get(key, "SYSTEM DETAILS"), content)

    def detail_content(self, key, data, system):
        if key == "cpu":
            processes = "\n".join(system.get("top_processes", ["Unavailable"]))
            return (
                f"STATE\nUsage                 {data.get('cpu_usage', '--')}%\n"
                f"Temperature           {data.get('cpu_temp', '--')}°C\n"
                f"Frequency             {data.get('cpu_frequency', '--')}\n"
                f"Governor              {system.get('cpu_governor', 'unknown')}\n"
                f"System load           {system.get('load', '--')}\n\nTOP PROCESSES\n{processes}\n\n"
                "HISTORY\nThe dashboard graph contains the latest ten minutes of five-second samples."
            )
        if key == "gpu":
            query = run_text(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], 3)[0] if command_exists("nvidia-smi") else ""
            pmon = run_text(["nvidia-smi", "pmon", "-c", "1"], 3)[0] if command_exists("nvidia-smi") else ""
            processes = query or "No compute processes reported."
            graphics = "\n".join(line for line in pmon.splitlines() if line.strip() and not line.lstrip().startswith("#")) or "No graphics clients reported."
            devices = "\n".join(f"{gpu['type']}: {gpu['name']} ({gpu['slot']})" for gpu in data.get("gpu_devices", [])) or "No GPU devices reported."
            return (
                f"DEVICES\n{devices}\n\nSTATE\nPower state           {system.get('gpu_state', 'unknown')}\n"
                f"Power draw            {system.get('gpu_power', '--')}\nTemperature           {data.get('gpu_temp', '--')}°C\n"
                f"Utilization           {data.get('gpu_usage', '--')}%\nVRAM                  {data.get('gpu_vram', '--')}\n"
                f"Driver                {system.get('gpu_driver', 'unknown')}\n\nCOMPUTE PROCESSES\n{processes}\n\n"
                f"GRAPHICS CLIENTS\n{graphics}\n\nPOWER ANALYSIS\nFrequent NVIDIA polling can itself keep a hybrid GPU awake."
            )
        if key == "memory":
            free = run_text(["free", "-h"], 2)[0]
            return f"MEMORY\nUsage                 {data.get('ram_usage', '--')}%\n{data.get('ram_info', '--')}\nSwap {system.get('swap', '--')}\n\nSYSTEM DETAIL\n{free or 'Unavailable'}"
        if key in ("storage", "disk"):
            disks = run_text(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS"], 3)[0]
            return (
                f"ROOT FILESYSTEM\nUsage                 {data.get('storage_percent', '--')}%\n"
                f"Capacity              {data.get('storage_usage', '--')}\nFilesystem            {system.get('filesystem', 'Unknown')}\n"
                f"Health                {system.get('storage_health', 'Unknown')}\nSnapshots             {system.get('snapshot', 'Unavailable')}\n\n"
                f"DEVICES\n{disks or 'Unavailable'}"
            )
        if key == "power":
            battery = system.get("battery", {})
            return (
                f"BATTERY\nCharge                {data.get('battery_percent', '--')}%\nStatus                {battery.get('status', 'Unknown')}\n"
                f"Health                {battery.get('health', 'Unknown')}\nCurrent draw          {battery.get('power', '--')}\n\n"
                f"POWER\nProfile               {data.get('power_profile_label', 'Unknown')}\nCPU governor          {system.get('cpu_governor', 'unknown')}"
            )
        if key == "network":
            routes = run_text(["ip", "route"], 2)[0]
            return (
                f"CONNECTION\nState                 {system.get('connection', 'Unknown')}\nInterface             {data.get('network_iface', '--')}\n"
                f"Local IP              {system.get('local_ip', '--')}\nVPN                   {data.get('vpn_status', 'Unknown')}\n"
                f"Latency               {system.get('latency', '--')}\nDNS                   {system.get('dns', 'Unknown')}\n"
                f"Download              {data.get('network_down', '0 B/s')}\nUpload                {data.get('network_up', '0 B/s')}\n\nROUTES\n{routes or 'Unavailable'}"
            )
        if key == "security":
            security = system.get("security", {})
            return (
                f"SECURITY POSTURE\nFirewall              {system.get('firewall', 'Unknown')}\nSecure Boot           {security.get('secure_boot', 'Unknown')}\n"
                f"Root encryption       {security.get('encryption', 'Unknown')}\nSSH service           {security.get('ssh', 'Unknown')}\n"
                f"Listening ports       {security.get('ports', '--')}\nPending updates       {system.get('updates', 'unknown')}\n\n"
                "Important system changes are never applied automatically."
            )
        if key == "kernel":
            return (
                f"KERNEL\nCurrent               {system.get('kernel', '--')}\nBoot time             {system.get('boot_time', '--')}\n"
                f"Reboot                {system.get('reboot_required', 'unknown')}\n\nNVIDIA\nDriver                {system.get('gpu_driver', 'not detected')}\n"
                f"State                 {system.get('gpu_state', 'unknown')}\nPower                 {system.get('gpu_power', '--')}"
            )
        if key == "readiness":
            deductions = getattr(self, "readiness_deductions", [])
            return "SCORE CALCULATION\n\n" + ("\n\n".join(f"−{points}  {label}\nEvidence: {evidence}" for label, points, evidence in deductions) or "No active deductions.")
        if key == "alerts":
            issues = self.issue_list(data, system)
            return "ACTION CENTRE\n\n" + ("\n\n".join(f"{severity}\n{message}\nRecommended view: {action}" for severity, message, module, action in issues) or "No active recommendations.")
        return "No detail provider is available."

    def readiness_result(self, data, system):
        score = 100
        deductions = []
        failed = system.get("failed", 0)
        cpu_temp = float(data.get("cpu_temp") or 0)
        gpu_temp = float(data.get("gpu_temp") or 0)
        updates = system.get("updates") or 0
        network_ready = system.get("connection") not in (None, "Unknown", "Offline")
        security = system.get("security", {})
        storage_percent = float(data.get("storage_percent") or 0)
        def deduct(label, points, evidence):
            nonlocal score
            score -= points
            deductions.append((label, points, evidence))
        if failed: deduct("Failed services", min(20, 8 + failed * 3), f"{failed} failed")
        if max(cpu_temp, gpu_temp) >= 80: deduct("Critical temperature", 15, f"Peak {max(cpu_temp, gpu_temp):.0f}°C")
        elif max(cpu_temp, gpu_temp) >= 70: deduct("Elevated temperature", 6, f"Peak {max(cpu_temp, gpu_temp):.0f}°C")
        if system.get("firewall") != "Enabled": deduct("Firewall inactive", 6, system.get("firewall", "Unknown"))
        if security.get("secure_boot") == "Disabled": deduct("Secure Boot disabled", 4, "Firmware reports disabled")
        if security.get("encryption") == "Disabled": deduct("Root disk not encrypted", 5, "Root is not mapper-backed")
        if updates: deduct("Pending updates", min(5, updates), f"{updates} available")
        if not network_ready: deduct("Network offline", 10, system.get("connection", "Unknown"))
        if storage_percent >= 90: deduct("Storage critically full", 15, f"{storage_percent:.0f}%")
        elif storage_percent >= 80: deduct("Storage filling up", 7, f"{storage_percent:.0f}%")
        if system.get("snapshot") in ("Unavailable", "None found"): deduct("No verified snapshot", 5, system.get("snapshot", "Unknown"))
        score = max(0, score)
        lines = [
            f"{'MISSION READY' if score >= 80 else 'MISSION REVIEW'}                         {score}%",
            f"SYSTEM       {'READY' if data and failed == 0 else 'WARNING':<10} {failed} failed service(s)",
            f"THERMALS     {'READY' if max(cpu_temp, gpu_temp) < 70 else 'WARNING':<10} Peak {max(cpu_temp, gpu_temp):.0f}°C",
            f"SECURITY     {'READY' if system.get('firewall') == 'Enabled' and not updates else 'WARNING':<10} {updates} update(s)",
            f"NETWORK      {'READY' if network_ready else 'OFFLINE':<10} {system.get('latency', '--')}",
            f"STORAGE      {'READY' if storage_percent < 80 else 'WARNING':<10} Root {storage_percent:.0f}%",
            f"BACKUP       {'READY' if system.get('snapshot') not in ('Unavailable', 'None found') else 'WARNING':<10} {system.get('snapshot', 'Unknown')}",
            f"DRIVERS      {'READY' if system.get('gpu_driver') not in ('unknown', 'not detected') else 'CHECK':<10} NVIDIA {system.get('gpu_state', 'unknown')}",
        ]
        return score, deductions, lines

    def show_readiness_breakdown(self):
        data = getattr(self, "latest_data", {})
        system = getattr(self, "latest_system", {})
        security = system.get("security", {})
        updates = system.get("updates") or 0
        storage = float(data.get("storage_percent") or 0)
        battery = int(float(data.get("battery_percent") or 100))
        categories = [
            ("SECURITY", max(0, 100 - (25 if system.get("firewall") != "Enabled" else 0) - (10 if security.get("secure_boot") == "Disabled" else 0) - (15 if security.get("encryption") == "Disabled" else 0))),
            ("STORAGE", max(0, min(100, int(110 - storage)))),
            ("DRIVERS", 100 if system.get("gpu_driver") not in ("unknown", "not detected") else 55),
            ("UPDATES", max(0, 100 - updates * 3)),
            ("BATTERY", battery),
            ("BACKUPS", 20 if system.get("snapshot") in ("Unavailable", "None found") else 100),
            ("NETWORK", 100 if system.get("connection") not in ("Offline", "Unknown", None) else 20),
            ("INTELLIGENCE", 100),
        ]
        dialog = QDialog(self)
        dialog.setWindowTitle("Command Readiness Breakdown")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)
        title = QLabel("COMMAND READINESS")
        title.setObjectName("heroTitle")
        score = self.readiness_gauge.score
        summary = QLabel(f"{score}%   {'MISSION READY' if score >= 80 else 'MISSION REVIEW'}")
        summary.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(summary)
        for label, value in categories:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("panelTitle")
            name.setMinimumWidth(170)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(value)
            bar.setFormat(f"{value}%")
            row.addWidget(name)
            row.addWidget(bar, 1)
            layout.addLayout(row)
        evidence = QPlainTextEdit()
        evidence.setReadOnly(True)
        evidence.setObjectName("textPanel")
        deductions = getattr(self, "readiness_deductions", [])
        evidence.setPlainText("WHY THE SCORE ISN'T 100%\n\n" + ("\n\n".join(
            f"−{points}%  {label}\nEvidence: {detail}" for label, points, detail in deductions
        ) or "No active deductions."))
        layout.addWidget(evidence, 1)
        close = QPushButton("CLOSE READINESS BREAKDOWN")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.setWindowState(Qt.WindowMaximized)
        dialog.exec()

    def render_alerts(self, issues):
        while self.alerts_layout.count() > 1:
            item = self.alerts_layout.takeAt(1)
            if item.widget():
                if item.widget() is self.alerts_details:
                    item.widget().setParent(None)
                else:
                    item.widget().deleteLater()
        if not issues:
            label = QLabel("OK  No immediate recommendations.")
            label.setObjectName("muted")
            self.alerts_layout.addWidget(label)
            self.alerts_layout.addWidget(self.alerts_details)
            return
        for severity, message, module_id, action in issues[:5]:
            row = QFrame()
            row.setObjectName("alertRow")
            row.setProperty("severity", severity.lower())
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(7, 1, 7, 1)
            row_layout.setSpacing(6)
            icon = "▲" if severity in ("WARNING", "CRITICAL") else "ⓘ"
            label = QLabel(f"{icon}   {severity:<9}  {message}")
            label.setObjectName("alertText")
            label.setWordWrap(True)
            row_layout.addWidget(label, 1)
            button = QPushButton(action)
            button.setObjectName("alertAction")
            button.setFixedHeight(22)
            button.clicked.connect(lambda checked=False, target=module_id: self.parent_window.open_module(target))
            row_layout.addWidget(button)
            self.alerts_layout.addWidget(row)
        self.alerts_layout.addWidget(self.alerts_details)

    def open_system_information(self):
        if command_exists("kinfocenter"):
            subprocess.Popen(["kinfocenter"])
        else:
            QMessageBox.information(self, "System Information", "KDE Info Centre is not installed.")

    def show_telemetry_status(self):
        QMessageBox.information(self, "Telemetry Status", f"Source: {TELEMETRY_URL}\nFallback: {STATE_FILE}")

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
            issues.append(("WARNING", f"{system.get('failed')} failed service(s) detected.", "dashboard", "REVIEW"))
        if system.get("updates"):
            issues.append(("WARNING", f"{system.get('updates')} system update(s) available.", "software", "REVIEW UPDATES"))
        if float(data.get("cpu_temp") or 0) >= 80:
            issues.append(("CRITICAL", f"CPU temperature is high at {data.get('cpu_temp')}°C.", "dashboard", "REVIEW"))
        if float(data.get("gpu_temp") or 0) >= 80:
            issues.append(("CRITICAL", f"GPU temperature is high at {data.get('gpu_temp')}°C.", "dashboard", "REVIEW"))
        if float(data.get("storage_percent") or 0) >= 85:
            issues.append(("WARNING", f"Root storage is {data.get('storage_percent')}% full.", "software", "REVIEW STORAGE"))
        if system.get("firewall") != "Enabled":
            issues.append(("WARNING", "No active firewall service was detected.", "dashboard", "VIEW DETAILS"))
        if system.get("security", {}).get("secure_boot") == "Disabled":
            issues.append(("ADVISORY", "Secure Boot is disabled.", "dashboard", "VIEW DETAILS"))
        if system.get("gpu_state", "").startswith("awake") and float(data.get("gpu_usage") or 0) < 2:
            issues.append(("ADVISORY", f"NVIDIA GPU is awake while idle ({system.get('gpu_power', 'power unknown')}).", "dashboard", "VIEW DETAILS"))
        if not data:
            issues.append(("WARNING", "Telemetry is unavailable; dashboard readings may be stale.", "command_apps", "TELEMETRY"))
        order = {"CRITICAL": 0, "WARNING": 1, "ADVISORY": 2, "INFO": 3}
        return sorted(issues, key=lambda item: order[item[0]])


class ControlPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.power_buttons = {}
        self.profile_buttons = {}
        self.wifi_status = QLabel("--")
        self.bluetooth_status = QLabel("--")
        self.audio_combo = QComboBox()
        self.apply_queue = self.load_queue()
        self.feature_cards = []
        self.feature_state_labels = {}
        self.state_header = QLabel("Collecting system state…")
        self.state_header.setObjectName("healthHeader")
        self.state_header.setWordWrap(True)
        self.control_search = QLineEdit()
        self.control_search.setPlaceholderText("Search settings, devices, services and actions…")
        self.control_search.textChanged.connect(self.filter_controls)
        self.queue_status = QLabel()
        self.queue_status.setObjectName("panelTitle")
        self.service_summary = QLabel("Collecting service state…")
        self.service_summary.setObjectName("muted")
        self.service_filter = QLineEdit()
        self.service_filter.setPlaceholderText("Search services")
        self.service_filter.textChanged.connect(self.refresh_services)
        self.services = QListWidget()
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")
        self.result.setVisible(False)
        self.result.textChanged.connect(
            lambda: self.result.setVisible(bool(self.result.toPlainText().strip()))
        )
        for widget in (
            self.update_list, self.history_list, self.package_list, self.cachyos_list,
            self.orphan_list, self.foreign_list, self.installed_kernels,
        ):
            widget.setObjectName("softwareList")
        for widget in (self.cachyos_search, self.package_search):
            widget.setObjectName("softwareSearch")
        for widget in (self.cachyos_category, self.available_kernels):
            widget.setObjectName("softwareCombo")
        for widget in (
            self.status, self.tools_status, self.cachyos_pi_status, self.orphan_summary,
            self.foreign_summary, self.kernel_status, self.health_status, self.sources_status,
        ):
            widget.setObjectName("softwareStatusBlock")

        layout = QVBoxLayout(self)
        title = QLabel("SYSTEM CONTROL")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        layout.addWidget(self.state_header)
        layout.addWidget(self.control_search)
        layout.addWidget(self.quick_controls_panel())
        layout.addWidget(self.system_section())
        layout.addWidget(self.commandos_section())
        layout.addWidget(self.result)
        layout.addWidget(self.queue_bar())
        self.update_queue_bar()

    def load_queue(self):
        try:
            data = json.loads(CONTROL_QUEUE_FILE.read_text(encoding="utf-8"))
            return [item for item in data if isinstance(item, dict) and item.get("command")] if isinstance(data, list) else []
        except Exception:
            return []

    def save_queue(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONTROL_QUEUE_FILE.write_text(json.dumps(self.apply_queue, indent=2), encoding="utf-8")

    def queue_bar(self):
        frame = QFrame()
        frame.setObjectName("queueBar")
        row = QHBoxLayout(frame)
        row.addWidget(self.queue_status, 1)
        for label, action in [("REVIEW CHANGES", "show"), ("APPLY", "apply"), ("CLEAR", "clear")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, value=action: self.queue_action(value))
            row.addWidget(button)
        return frame

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def quick_controls_panel(self):
        frame, layout = self.panel("COMMANDOS PROFILE & QUICK CONTROLS")
        layout.addWidget(self.active_profile_panel())
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
            button.clicked.connect(lambda checked=False, p=profile, power=target_power: self.stage_profile(p, power))
            self.profile_buttons[profile] = button
            row.addWidget(button)
        layout.addLayout(row)
        note = QLabel("A CommandOS profile is a staged machine configuration. Power mode is one setting within the profile.  ·  REVERSIBLE")
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
        wifi_on = QPushButton("ENABLE")
        wifi_off = QPushButton("DISABLE")
        networks = QPushButton("NETWORKS")
        wifi_on.clicked.connect(lambda: self.set_wifi(True))
        wifi_off.clicked.connect(lambda: self.set_wifi(False))
        networks.clicked.connect(lambda: self.open_kcm("kcm_networkmanagement"))
        wifi_buttons = QHBoxLayout()
        wifi_buttons.addWidget(wifi_on)
        wifi_buttons.addWidget(wifi_off)
        wifi_buttons.addWidget(networks)
        wifi_layout.addLayout(wifi_buttons)

        bluetooth, bluetooth_layout = self.panel("Bluetooth")
        bluetooth_layout.addWidget(self.bluetooth_status)
        bt_on = QPushButton("ENABLE")
        bt_off = QPushButton("DISABLE")
        bt_devices = QPushButton("DEVICES")
        bt_on.clicked.connect(lambda: self.set_bluetooth(True))
        bt_off.clicked.connect(lambda: self.set_bluetooth(False))
        bt_buttons = QHBoxLayout()
        bt_buttons.addWidget(bt_on)
        bt_buttons.addWidget(bt_off)
        bt_devices.clicked.connect(lambda: self.open_kcm("kcm_bluetooth"))
        bt_buttons.addWidget(bt_devices)
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
        layout.addWidget(self.service_summary)
        self.services.itemSelectionChanged.connect(self.service_selection_changed)
        self.service_filter.setVisible(False)
        self.services.setVisible(False)
        layout.addWidget(self.service_filter)
        layout.addWidget(self.services)

        row = QHBoxLayout()
        manage = QPushButton("MANAGE SERVICES")
        manage.clicked.connect(self.toggle_service_manager)
        row.addWidget(manage)
        failed = QPushButton("FAILED ONLY")
        failed.clicked.connect(lambda: self.show_failed_services())
        row.addWidget(failed)
        for label, action in [("Start", "start"), ("Stop", "stop"), ("Restart", "restart"), ("Logs", "logs")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, a=action: self.service_action(a))
            row.addWidget(button)
        layout.addLayout(row)
        return frame

    def feature_card(self, title, body):
        frame, layout = self.panel(title)
        frame.setProperty("searchText", f"{title} {body}".lower())
        self.feature_cards.append(frame)
        state = QLabel("State will appear after refresh")
        state.setObjectName("controlState")
        state.setWordWrap(True)
        state.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.feature_state_labels[title] = state
        layout.addWidget(state)
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
            "Hardware & Drivers": [("System Information", "app", "kinfocenter"), ("PCI Devices", "terminal", "lspci -k"), ("Firmware", "terminal", "fwupdmgr get-devices")],
            "Diagnostics Centre": [("Quick Scan", "terminal", "systemctl --failed; echo; df -h /; echo; free -h"), ("Boot", "terminal", "systemd-analyze; systemd-analyze critical-chain"), ("Network", "terminal", "ip -brief address; echo; ip route")],
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
            self.stage_profile(target, power)
            self.parent_window.add_history(f"CommandOS profile staged: {label}")
        elif action == "stage":
            self.stage_change("Power profile", "current", target.rsplit(" ", 1)[-1], target, reversible=True)
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
        if action == "show":
            self.set_result(self.queue_review_text())
        elif action == "clear":
            if self.apply_queue and not confirm(self, "Clear Apply Queue", "Clear all staged changes?"):
                return
            self.apply_queue = []
            self.save_queue()
            self.update_queue_bar()
            self.set_result("Apply Queue cleared.")
        elif action == "apply":
            if not self.apply_queue:
                self.set_result("Apply Queue is empty.")
                return
            command = " && ".join(change["command"] for change in self.apply_queue)
            review = self.queue_review_text()
            if not confirm(self, "Apply Queue", f"Apply these staged changes?\n\n{review}"):
                return
            self.run_terminal_action(command)
            self.parent_window.add_history(f"Applied {len(self.apply_queue)} queued change(s)")
            self.apply_queue = []
            self.save_queue()
            self.update_queue_bar()

    def stage_change(self, label, current, proposed, command, root=False, reboot=False, reversible=False, interruption="none"):
        self.apply_queue = [change for change in self.apply_queue if change.get("label") != label]
        self.apply_queue.append({
            "label": label, "current": current, "proposed": proposed, "command": command,
            "root": root, "reboot": reboot, "reversible": reversible, "interruption": interruption,
        })
        self.save_queue()
        self.update_queue_bar()
        self.set_result(f"Staged: {label}\n{current} → {proposed}\n\n{self.queue_review_text()}")

    def stage_profile(self, profile, power_profile):
        label = profile.replace("-", " ").title()
        current = self.parent_window.power_state().get("active", "unknown")
        self.stage_change(f"CommandOS profile: {label}", current, power_profile,
                          f"powerprofilesctl set {shlex.quote(power_profile)}", reversible=True)

    def queue_review_text(self):
        if not self.apply_queue:
            return "Apply Queue is empty."
        lines = []
        for index, change in enumerate(self.apply_queue, 1):
            badges = ["ROOT" if change.get("root") else "USER"]
            if change.get("reboot"):
                badges.append("REBOOT")
            if change.get("reversible"):
                badges.append("REVERSIBLE")
            if change.get("interruption") != "none":
                badges.append(change["interruption"].upper())
            lines.append(f"{index}. {change['label']}  ·  {' · '.join(badges)}\n   {change['current']} → {change['proposed']}\n   {change['command']}")
        return "\n\n".join(lines)

    def update_queue_bar(self):
        roots = sum(bool(item.get("root")) for item in self.apply_queue)
        reboots = sum(bool(item.get("reboot")) for item in self.apply_queue)
        self.queue_status.setText(f"{len(self.apply_queue)} PENDING CHANGES  ·  {roots} ROOT  ·  {reboots} REBOOT")

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
            ("Hardware & Drivers", "Detected hardware, kernel drivers, GPU state, firmware, PCI/USB devices, battery, SMART/NVMe health, sensors, and conflicts."),
            ("Diagnostics Centre", "Quick, boot, graphics, network, audio, storage, and package-health scans with evidence and recommended actions."),
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

    def filter_controls(self, text):
        needle = text.strip().lower()
        for card in self.feature_cards:
            card.setVisible(not needle or needle in card.property("searchText"))

    def toggle_service_manager(self):
        visible = not self.services.isVisible()
        self.service_filter.setVisible(visible)
        self.services.setVisible(visible)
        if visible:
            self.refresh_services()

    def show_failed_services(self):
        self.toggle_service_manager() if not self.services.isVisible() else None
        self.service_filter.setText("failed")

    def refresh(self):
        power = self.parent_window.power_state()
        active = power.get("active", "unknown")
        telemetry = self.parent_window.telemetry
        system = self.parent_window.system
        updates = system.get("updates")
        reboot_required = Path("/run/reboot-required").exists()
        self.state_header.setText(
            f"PROFILE  {active.upper()}   ·   NETWORK  {system.get('connection', 'UNKNOWN').upper()}   ·   "
            f"FIREWALL  {system.get('firewall', 'UNKNOWN').upper()}   ·   FAILED SERVICES  {system.get('failed', 0)}   ·   "
            f"REBOOT  {'YES' if reboot_required else 'NO'}   ·   PENDING CHANGES  {len(self.apply_queue)}"
        )
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

        states = {
            "Performance & Power": f"{active.upper()}  ·  CPU {metric_value(telemetry, 'cpu_frequency', '--')}  ·  {metric_value(telemetry, 'cpu_temp', '--')}°C  ·  LIVE",
            "Graphics & Displays": f"{metric_value(telemetry, 'gpu_name', 'GPU unavailable')}  ·  {metric_value(telemetry, 'gpu_temp', '--')}°C  ·  Driver {metric_value(telemetry, 'gpu_driver', 'inspect for details')}",
            "Network": f"{system.get('connection', 'Unknown')}  ·  {metric_value(telemetry, 'network_iface', 'offline')}  ·  VPN {metric_value(telemetry, 'vpn_status', 'unknown')}  ·  Firewall {system.get('firewall', 'Unknown')}",
            "Startup & Boot": f"Kernel {system.get('kernel', '--')}  ·  Reboot {'required' if reboot_required else 'not required'}  ·  {system.get('failed', 0)} failed services",
            "Users & Permissions": f"User {os.environ.get('USER', '--')}  ·  Session {os.environ.get('XDG_SESSION_TYPE', 'unknown')}  ·  Host {system.get('host', '--')}",
            "Storage & Mounting": f"Root {metric_value(telemetry, 'storage_percent', '--')}% used  ·  {system.get('storage_health', 'UNKNOWN')}  ·  {metric_value(telemetry, 'storage_name', 'root')}",
            "Appearance & Desktop": f"KDE Plasma  ·  {os.environ.get('XDG_SESSION_TYPE', 'unknown').title()} session  ·  LIVE · REVERSIBLE",
            "Time, Locale & Input": f"{time.strftime('%Z · %Y-%m-%d %H:%M')}  ·  Locale {os.environ.get('LANG', 'unknown')}",
            "Hardware & Drivers": f"Kernel {system.get('kernel', '--')}  ·  {metric_value(telemetry, 'gpu_name', 'GPU unavailable')}  ·  Firmware {'available' if command_exists('fwupdmgr') else 'tool unavailable'}",
            "Diagnostics Centre": f"{system.get('failed', 0)} failed services  ·  {updates if updates is not None else 'Unknown'} updates  ·  Root {metric_value(telemetry, 'storage_percent', '--')}% used",
            "Profiles": f"Active power property: {active}  ·  Changes stage into the Apply Queue",
            "Security Controls": f"Firewall {system.get('firewall', 'Unknown')}  ·  Impact badges shown before execution",
            "Snapshots & Recovery": f"Backend {'available' if command_exists('snapper') else 'not detected'}  ·  ROOT · REVERSIBLE when snapshot exists",
            "Apply Queue": f"{len(self.apply_queue)} pending  ·  Persistent review and confirmation enabled",
            "Change History": f"{len(self.parent_window.change_history)} session events recorded",
        }
        for title, label in self.feature_state_labels.items():
            label.setText(states.get(title, "State unavailable"))

        current_sink, sinks = self.parent_window.audio_state()
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        for sink in sinks:
            self.audio_combo.addItem(sink, sink)
        index = self.audio_combo.findData(current_sink)
        if index >= 0:
            self.audio_combo.setCurrentIndex(index)
        self.audio_combo.blockSignals(False)

        if self.services.isVisible():
            self.refresh_services()
        service_data = self.parent_window.user_services()
        running = sum(service.get("active") == "active" for service in service_data)
        failed_count = sum(service.get("sub") == "failed" for service in service_data)
        self.service_summary.setText(f"{running} RUNNING  ·  {failed_count} FAILED  ·  {len(service_data)} DISCOVERED")
        self.update_queue_bar()

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
        try:
            service = validate_service(service)
        except ActionValidationError as error:
            self.set_result(f"Blocked invalid service name: {error}")
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
        self.software_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="software-state")
        self.software_future = None
        self.update_records = []
        self.software_history = self.load_history()
        self.health_header = QLabel("Collecting software state…")
        self.health_header.setObjectName("softwareAttention")
        self.health_header.setWordWrap(True)
        self.overview_status = QLabel("--")
        self.overview_status.setObjectName("controlState")
        self.overview_status.setWordWrap(True)
        self.impact_status = QLabel("--")
        self.impact_status.setObjectName("controlState")
        self.impact_status.setWordWrap(True)
        self.snapshot_status = QLabel("--")
        self.snapshot_status.setObjectName("muted")
        self.snapshot_status.setWordWrap(True)
        self.health_status = QLabel("--")
        self.health_status.setObjectName("muted")
        self.health_status.setWordWrap(True)
        self.sources_status = QLabel("--")
        self.sources_status.setObjectName("muted")
        self.sources_status.setWordWrap(True)
        self.history_list = QListWidget()
        self.update_list = QListWidget()
        self.status = QLabel("--")
        self.status.setObjectName("muted")
        self.tools_status = QLabel("--")
        self.tools_status.setObjectName("muted")
        self.cachyos_pi_status = QLabel("--")
        self.cachyos_pi_status.setObjectName("controlState")
        self.cachyos_pi_status.setWordWrap(True)
        self.cachyos_catalog = {}
        self.cachyos_checked = set()
        self.package_metadata = {}
        self.repository_packages = []
        self.cachyos_category = QComboBox()
        self.cachyos_search = QLineEdit()
        self.cachyos_search.setPlaceholderText("Filter CommandOS popular applications")
        self.cachyos_list = QListWidget()
        self.cachyos_list.setMinimumHeight(520)
        self.cachyos_category.currentTextChanged.connect(self.render_cachyos_catalog)
        self.cachyos_search.textChanged.connect(self.render_cachyos_catalog)
        self.cachyos_list.itemChanged.connect(self.cachyos_item_changed)
        self.package_search = QLineEdit()
        self.package_search.setPlaceholderText("Filter repository packages by name or description")
        self.package_search.returnPressed.connect(self.search_packages)
        self.package_list = QListWidget()
        self.package_list.itemDoubleClicked.connect(lambda _: self.install_selected_package())
        self.orphan_packages = []
        self.foreign_packages = []
        self.orphan_list = QListWidget()
        self.orphan_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.foreign_list = QListWidget()
        self.foreign_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.orphan_summary = QLabel("No orphan scan completed yet.")
        self.orphan_summary.setObjectName("muted")
        self.orphan_summary.setWordWrap(True)
        self.foreign_summary = QLabel("No foreign-package scan completed yet.")
        self.foreign_summary.setObjectName("muted")
        self.foreign_summary.setWordWrap(True)
        self.kernel_status = QLabel("--")
        self.kernel_status.setObjectName("muted")
        self.available_kernels = QComboBox()
        self.installed_kernels = QListWidget()
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        header = QFrame()
        header.setObjectName("softwareHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(5)
        title = QLabel("▣   SOFTWARE CENTRE")
        title.setObjectName("softwarePageTitle")
        header_copy.addWidget(title)
        subtitle = QLabel("PACKAGE HEALTH  •  UPDATES  •  RECOVERY")
        subtitle.setObjectName("softwareSubtitle")
        header_copy.addWidget(subtitle)
        header_copy.addWidget(self.health_header)
        header_copy.addSpacing(5)
        self.software_chip_row = QHBoxLayout()
        self.software_chip_row.setSpacing(6)
        self.software_chips = {}
        for key, text in [
            ("updates", "↻ UPDATES\n—"), ("aur", "◇ AUR\n—"), ("flatpak", "▣ FLATPAK\n—"),
            ("orphans", "⚠ ORPHANS\n—"), ("reboot", "⏻ REBOOT\n—"),
        ]:
            chip = QLabel(text)
            chip.setObjectName("softwareStatusChip")
            chip.setProperty("state", "info")
            self.software_chips[key] = chip
            self.software_chip_row.addWidget(chip)
        self.software_chip_row.addStretch()
        header_copy.addLayout(self.software_chip_row)
        header_layout.addLayout(header_copy, 1)
        header_layout.addWidget(RadarWidget())
        layout.addWidget(header)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("softwareTabs")
        self.tabs.addTab(self.overview_panel(), "Overview")
        self.tabs.addTab(self.updates_page(), "Updates")
        self.tabs.addTab(self.package_panel(), "Packages")
        self.tabs.addTab(self.package_cleanup_page(), "Orphans & Foreign")
        self.tabs.addTab(self.kernel_panel(), "Kernels")
        self.tabs.addTab(self.health_page(), "Health & Sources")
        self.tabs.addTab(self.history_page(), "History")
        layout.addWidget(self.tabs)
        self.result.setMaximumHeight(105)
        layout.addWidget(self.result)
        self.result.hide()
        self.software_poll = QTimer(self)
        self.software_poll.timeout.connect(self.finish_refresh)
        self.software_poll.start(100)

    def overview_panel(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 7, 4, 4)
        page_layout.setSpacing(10)

        self.software_metric_grid = QGridLayout()
        self.software_metric_grid.setSpacing(8)
        metric_specs = [
            ("updates", "↻", "UPDATES", "#F5B83D"), ("aur", "◇", "AUR", "#35D66B"),
            ("flatpak", "▣", "FLATPAK", "#16B9F3"), ("orphans", "⚠", "ORPHANS", "#F0A72B"),
            ("foreign", "◎", "FOREIGN", "#A65DFF"), ("reboot", "⏻", "REBOOT", "#35D66B"),
        ]
        self.software_metrics = {key: SoftwareMetricCard(icon, title, accent) for key, icon, title, accent in metric_specs}
        self.reflow_software_metrics(6)
        page_layout.addLayout(self.software_metric_grid)

        health_intelligence = QGridLayout()
        health_intelligence.setSpacing(10)
        health, health_layout = self.panel("◈   SOFTWARE HEALTH")
        health.setMaximumHeight(210)
        health_content = QHBoxLayout()
        health_content.setContentsMargins(4, 0, 4, 0)
        health_content.setSpacing(12)
        self.software_health_gauge = SoftwareHealthGauge()
        gauge_column = QVBoxLayout()
        gauge_column.setContentsMargins(0, 0, 0, 0)
        gauge_column.setSpacing(0)
        self.software_health_trend = QLabel("Establishing health trend…")
        self.software_health_trend.setObjectName("softwareTrend")
        self.software_health_trend.setAlignment(Qt.AlignCenter)
        gauge_column.addWidget(self.software_health_gauge, 0, Qt.AlignCenter)
        gauge_column.addWidget(self.software_health_trend)
        self.software_health_checklist = QLabel("Calculating software health…")
        self.software_health_checklist.setObjectName("softwareChecklist")
        self.software_health_checklist.setTextFormat(Qt.RichText)
        self.software_health_checklist.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        health_content.addLayout(gauge_column)
        health_content.addWidget(self.software_health_checklist, 1, Qt.AlignVCenter)
        health_layout.addLayout(health_content)
        health_details = QPushButton("VIEW HEALTH DETAILS")
        health_details.setObjectName("softwareFooterButton")
        health_details.clicked.connect(lambda: self.tabs.setCurrentIndex(5))
        health_layout.addWidget(health_details)
        health_intelligence.addWidget(health, 0, 0)

        intelligence, intelligence_layout = self.panel("✦   COMMAND INTELLIGENCE")
        intelligence.setMaximumHeight(210)
        intelligence_grid = QGridLayout()
        intelligence_grid.setSpacing(7)
        self.software_intelligence = {}
        intelligence_specs = [
            ("recommendation", "✦", "AI RECOMMENDATION", "REVIEW UPDATES", self.show_update_review),
            ("analysis", "☷", "UPDATE ANALYSIS", "VIEW IMPACT", lambda: self.tabs.setCurrentIndex(1)),
            ("action", "◎", "NEXT BEST ACTION", "TAKE ACTION", self.next_software_action),
        ]
        for column, (key, icon, title, action, handler) in enumerate(intelligence_specs):
            mini = QFrame(); mini.setObjectName("softwareMiniPanel")
            mini_layout = QVBoxLayout(mini); mini_layout.setContentsMargins(12, 10, 12, 10); mini_layout.setSpacing(7)
            heading = QLabel(f"{icon}  {title}"); heading.setObjectName("softwareMiniTitle")
            badge = QLabel("CHECKING"); badge.setObjectName("softwareIntelBadge"); badge.setProperty("state", "info")
            body = QLabel("Checking…"); body.setObjectName("softwareMiniBody"); body.setWordWrap(True)
            detail = QLabel(""); detail.setObjectName("softwareMiniDetail"); detail.setWordWrap(True)
            button = QPushButton(action); button.setObjectName("softwareActionButton"); button.clicked.connect(handler)
            title_row = QHBoxLayout(); title_row.addWidget(heading); title_row.addStretch(); title_row.addWidget(badge)
            mini_layout.addLayout(title_row); mini_layout.addWidget(body); mini_layout.addWidget(detail); mini_layout.addStretch(); mini_layout.addWidget(button)
            intelligence_grid.addWidget(mini, 0, column)
            self.software_intelligence[key] = (body, detail, badge, button)
        intelligence_layout.addLayout(intelligence_grid)
        health_intelligence.addWidget(intelligence, 0, 1)
        health_intelligence.setColumnStretch(0, 2)
        health_intelligence.setColumnStretch(1, 3)
        page_layout.addLayout(health_intelligence)

        impact_protection = QGridLayout(); impact_protection.setSpacing(10)
        impact, impact_layout = self.panel("▥   IMPACT ANALYSIS")
        impact.setMaximumHeight(175)
        impact_grid = QGridLayout(); impact_grid.setSpacing(7)
        self.impact_columns = {}
        for column, (key, title, color) in enumerate([("low", "LOW IMPACT", "#35D66B"), ("medium", "MEDIUM IMPACT", "#F5B83D"), ("high", "HIGH IMPACT", "#F05B5B")]):
            box = QFrame(); box.setObjectName("impactColumn"); box.setProperty("accent", color)
            box_layout = QVBoxLayout(box); box_layout.setContentsMargins(10, 8, 10, 8); box_layout.setSpacing(6)
            label = QLabel(title); label.setObjectName("softwareMetricTitle")
            bar = QProgressBar(); bar.setObjectName("impactBar"); bar.setProperty("impact", key); bar.setRange(0, 100); bar.setTextVisible(False)
            value = QLabel("—"); value.setObjectName("softwareImpactValue")
            status = QLabel("0% OF UPDATES"); status.setObjectName("impactStatus")
            value_row = QHBoxLayout(); value_row.setContentsMargins(0, 0, 0, 0)
            value_row.addWidget(value); value_row.addStretch(); value_row.addWidget(status, 0, Qt.AlignBottom)
            box_layout.addWidget(label); box_layout.addWidget(bar); box_layout.addLayout(value_row)
            impact_grid.addWidget(box, 0, column)
            self.impact_columns[key] = (value, bar, status)
        impact_layout.addLayout(impact_grid)
        impact_note = QLabel("ⓘ  High impact indicates core system, kernel, driver, boot, or filesystem packages. It is not a prediction of failure.")
        impact_note.setObjectName("softwareNote"); impact_note.setWordWrap(True); impact_layout.addWidget(impact_note)
        impact_protection.addWidget(impact, 0, 0)

        protection, protection_layout = self.panel("◈   PRE-UPDATE PROTECTION")
        protection.setMaximumHeight(175)
        protection_content = QHBoxLayout()
        protection_content.setSpacing(16)
        self.software_protection = QLabel("Reading snapshot status…")
        self.software_protection.setObjectName("softwareChecklist")
        self.software_protection.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        protection_action = QVBoxLayout()
        protection_action.setSpacing(5)
        protection_icon = QLabel("◈+"); protection_icon.setObjectName("protectionIcon"); protection_icon.setAlignment(Qt.AlignCenter)
        self.protection_explanation = QLabel("Checking rollback protection…")
        self.protection_explanation.setObjectName("protectionExplanation")
        self.protection_explanation.setWordWrap(True); self.protection_explanation.setAlignment(Qt.AlignCenter)
        self.snapshot_overview_button = QPushButton("CREATE SNAPSHOT")
        self.snapshot_overview_button.setObjectName("primaryButton")
        self.snapshot_overview_button.setMinimumHeight(30)
        self.snapshot_overview_button.clicked.connect(self.snapshot_overview_action)
        protection_action.addWidget(protection_icon); protection_action.addWidget(self.protection_explanation, 1); protection_action.addWidget(self.snapshot_overview_button)
        protection_divider = QFrame(); protection_divider.setObjectName("protectionDivider"); protection_divider.setFrameShape(QFrame.VLine)
        protection_content.addWidget(self.software_protection, 2); protection_content.addWidget(protection_divider); protection_content.addLayout(protection_action, 1)
        protection_layout.addLayout(protection_content)
        impact_protection.addWidget(protection, 0, 1)
        impact_protection.setColumnStretch(0, 1); impact_protection.setColumnStretch(1, 1)
        page_layout.addLayout(impact_protection)

        lower = QGridLayout(); lower.setSpacing(10)
        activity, activity_layout = self.panel("◷   RECENT SOFTWARE ACTIVITY")
        activity.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        activity.setMaximumHeight(310)
        activity_layout.setAlignment(Qt.AlignTop)
        self.software_activity_layout = QVBoxLayout(); self.software_activity_layout.setSpacing(5)
        self.software_activity_layout.setAlignment(Qt.AlignTop)
        activity_layout.addLayout(self.software_activity_layout)
        timeline = QPushButton("VIEW FULL TIMELINE"); timeline.setObjectName("softwareFooterButton"); timeline.clicked.connect(lambda: self.tabs.setCurrentIndex(6)); activity_layout.addWidget(timeline)
        lower.addWidget(activity, 0, 0)
        quick, quick_layout = self.panel("⚡   QUICK ACTIONS")
        quick.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        quick.setMaximumHeight(310)
        quick_layout.setAlignment(Qt.AlignTop)
        action_grid = QGridLayout(); action_grid.setHorizontalSpacing(8); action_grid.setVerticalSpacing(10)
        actions = [
            ("REVIEW UPDATES", QStyle.SP_BrowserReload, "update", self.show_update_review),
            ("UPDATE ALL", QStyle.SP_ArrowUp, "update", self.update_system),
            ("HEALTH CHECK", QStyle.SP_DialogApplyButton, "health", self.refresh),
            ("REMOVE ORPHANS", QStyle.SP_TrashIcon, "cleanup", self.remove_all_orphans),
            ("CLEAN CACHE", QStyle.SP_DriveHDIcon, "cleanup", lambda: self.run_maintenance("Clean Package Cache", "sudo paccache -r")),
            ("MANAGE KERNELS", QStyle.SP_ComputerIcon, "system", lambda: self.tabs.setCurrentIndex(4)),
        ]
        action_colors = {"update": "#2BC4FF", "health": "#35D66B", "cleanup": "#F0B230", "system": "#A55DFF"}
        for index, (label, icon, category, handler) in enumerate(actions):
            button = QToolButton(); button.setObjectName("softwareActionTile"); button.setText(label)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setFixedHeight(92)
            button.setProperty("category", category)
            button.setProperty("hierarchy", "primary" if label == "UPDATE ALL" else "danger" if label == "REMOVE ORPHANS" else "secondary")
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); button.setIcon(self.monochrome_icon(icon, action_colors[category])); button.setIconSize(QSize(32, 32))
            button.clicked.connect(handler); action_grid.addWidget(button, index // 3, index % 3)
        for column in range(3):
            action_grid.setColumnStretch(column, 1)
        quick_layout.addLayout(action_grid)
        lower.addWidget(quick, 0, 1)
        lower.setColumnStretch(0, 1); lower.setColumnStretch(1, 1)
        page_layout.addLayout(lower)
        page_layout.addStretch(1)
        return page

    def reflow_software_metrics(self, columns):
        if not hasattr(self, "software_metric_grid"):
            return
        self.software_metric_columns = columns
        while self.software_metric_grid.count():
            self.software_metric_grid.takeAt(0)
        for index, key in enumerate(("updates", "aur", "flatpak", "orphans", "foreign", "reboot")):
            self.software_metric_grid.addWidget(self.software_metrics[key], index // columns, index % columns)
        for column in range(columns):
            self.software_metric_grid.setColumnStretch(column, 1)

    def monochrome_icon(self, standard_icon, color="#C7E9F7"):
        pixmap = self.style().standardIcon(standard_icon).pixmap(32, 32)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return QIcon(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "software_metric_grid"):
            columns = 6 if self.width() >= 1160 else 3
            if columns != getattr(self, "software_metric_columns", 0):
                self.reflow_software_metrics(columns)

    def snapshot_overview_action(self):
        snapshot = getattr(self, "last_software_state", {}).get("snapshot", self.snapshot_state())
        if snapshot.get("configured"):
            self.create_snapshot()
        else:
            self.tabs.setCurrentIndex(5)
            self.result.setPlainText("Configure Snapper or Timeshift before relying on pre-update rollback protection.")

    def next_software_action(self):
        state = getattr(self, "last_software_state", {})
        if not state:
            self.refresh()
        elif not state.get("snapshot", {}).get("configured") or any(record["impact"] == "HIGH" for record in self.update_records):
            self.snapshot_overview_action()
        elif state.get("orphans") and not self.update_records:
            self.tabs.setCurrentIndex(3)
        elif self.update_records:
            self.tabs.setCurrentIndex(1)
        else:
            self.result.setPlainText("Software health is good. No immediate action is required.")

    def software_health_score(self, state, high_impact):
        score = 100
        total_updates = len(state["repo"]) + len(state["aur"])
        score -= min(10, total_updates // 3)
        score -= min(10, high_impact * 3)
        score -= min(8, len(state["orphans"]) // 2)
        if state["lock"] != "CLEAR":
            score -= 15
        if not state["snapshot"]["configured"]:
            score -= 8
        if state["reboot"]:
            score -= 5
        return max(0, score)

    def render_software_activity(self):
        while self.software_activity_layout.count():
            item = self.software_activity_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        records = self.software_history[:4]
        if not records:
            empty = QLabel("Monitoring software activity…")
            empty.setObjectName("softwareNote")
            self.software_activity_layout.addWidget(empty)
            return
        for record in records:
            row = QFrame(); row.setObjectName("softwareActivityRow")
            row_layout = QHBoxLayout(row); row_layout.setContentsMargins(10, 10, 10, 10); row_layout.setSpacing(10)
            timestamp = str(record.get("timestamp", "--"))
            stamp = QLabel(timestamp[11:16] if len(timestamp) >= 16 else timestamp)
            stamp.setObjectName("softwareActivityTime")
            action_text = str(record.get("action", "Software action"))
            category = "SNAPSHOT" if "snapshot" in action_text.lower() else "REMOVE" if "remove" in action_text.lower() else "INSTALL" if "install" in action_text.lower() else "UPDATE"
            category_label = QLabel(category); category_label.setObjectName("softwareActivityCategory"); category_label.setProperty("category", category.lower())
            description = QLabel(action_text); description.setObjectName("softwareActivityDescription")
            row_layout.addWidget(stamp); row_layout.addWidget(category_label); row_layout.addWidget(description, 1)
            self.software_activity_layout.addWidget(row)

    def updates_page(self):
        page = QWidget()
        page.setObjectName("softwareSubPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)
        layout.addWidget(self.software_section_header("SYSTEM UPDATES", "REVIEW  •  PROTECT  •  DEPLOY", "↻"))
        layout.addWidget(self.update_panel())
        heading = QLabel("▥   FULL SYSTEM UPGRADE REVIEW")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        layout.addWidget(self.update_list)
        warning = QLabel("CommandOS follows Arch's full-upgrade model. Repository updates are reviewed together and are not selectively applied.")
        warning.setObjectName("muted")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        return page

    def health_page(self):
        page = QWidget()
        page.setObjectName("softwareSubPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)
        layout.addWidget(self.software_section_header("HEALTH & SOURCES", "DATABASE  •  SOURCES  •  MAINTENANCE", "◈"))
        health, health_layout = self.panel("◈   SOFTWARE HEALTH")
        health.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        health_layout.addWidget(self.health_status)
        layout.addWidget(health)
        sources, sources_layout = self.panel("◎   PACKAGE SOURCES")
        sources.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sources_layout.addWidget(self.sources_status)
        layout.addWidget(sources)
        maintenance = self.maintenance_panel()
        maintenance.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(maintenance)
        layout.addStretch(1)
        return page

    def history_page(self):
        page = QWidget()
        page.setObjectName("softwareSubPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)
        layout.addWidget(self.software_section_header("SOFTWARE HISTORY", "TRANSACTIONS  •  SNAPSHOTS  •  AUDIT", "◷"))
        layout.addWidget(self.history_list)
        return page

    def load_history(self):
        try:
            data = json.loads(SOFTWARE_HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def record_transaction(self, action, command, status="STARTED", snapshot=""):
        self.software_history.insert(0, {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action,
                                         "command": command, "status": status, "snapshot": snapshot})
        self.software_history = self.software_history[:100]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SOFTWARE_HISTORY_FILE.write_text(json.dumps(self.software_history, indent=2), encoding="utf-8")
        self.render_history()
        if hasattr(self, "software_activity_layout"):
            self.render_software_activity()

    def render_history(self):
        self.history_list.clear()
        for record in self.software_history:
            snapshot = f" · Snapshot {record['snapshot']}" if record.get("snapshot") else ""
            self.history_list.addItem(f"{record.get('timestamp', '--')}  ·  {record.get('action', 'Software action')}  ·  {record.get('status', 'UNKNOWN')}{snapshot}\n{record.get('command', '')}")

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def software_section_header(self, title, subtitle, icon):
        frame = QFrame()
        frame.setObjectName("softwareSectionHeader")
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 10, 16, 10)
        mark = QLabel(icon)
        mark.setObjectName("softwareSectionIcon")
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(38, 38)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("softwareSectionTitle")
        detail = QLabel(subtitle)
        detail.setObjectName("softwareSectionSubtitle")
        copy.addWidget(heading)
        copy.addWidget(detail)
        row.addWidget(mark)
        row.addLayout(copy, 1)
        return frame

    def update_panel(self):
        frame, layout = self.panel("↻   UPDATE COMMANDS")
        body = QLabel("Update official repositories and AUR packages from a terminal session.")
        body.setWordWrap(True)
        body.setObjectName("muted")
        layout.addWidget(body)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        update = QPushButton("Update System")
        update.setObjectName("softwarePrimaryAction")
        update.clicked.connect(self.update_system)
        check = QPushButton("Check Updates")
        check.setObjectName("softwareSectionButton")
        check.clicked.connect(self.refresh)
        flatpak = QPushButton("Update Flatpaks")
        flatpak.setObjectName("softwareSectionButton")
        flatpak.clicked.connect(self.update_flatpaks)
        row.addWidget(update)
        row.addWidget(check)
        row.addWidget(flatpak)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def package_panel(self):
        frame, layout = self.panel("▣   PACKAGE CATALOGUE")
        frame.setObjectName("softwareSubPageCard")
        layout.setSpacing(10)
        layout.addWidget(self.software_section_header("PACKAGES", "CURATED APPS  •  REPOSITORIES  •  EXPORT", "▣"))
        layout.addWidget(self.tools_status)

        curated, curated_layout = self.panel("◇   COMMAND CURATED APPS")
        curated_body = QLabel(
            "Browse the CommandOS Popular Applications catalogue by category, including browsers, "
            "development, graphics, multimedia, office, gaming, and virtualization packages."
        )
        curated_body.setObjectName("muted")
        curated_body.setWordWrap(True)
        curated_layout.addWidget(curated_body)
        curated_layout.addWidget(self.cachyos_pi_status)
        filters = QHBoxLayout()
        filters.addWidget(self.cachyos_category)
        filters.addWidget(self.cachyos_search, 1)
        curated_layout.addLayout(filters)
        curated_layout.addWidget(self.cachyos_list)
        layout.addWidget(curated)
        self.load_package_metadata()
        self.load_cachyos_catalog()

        search_heading = QLabel("⌕   REPOSITORY PACKAGE SEARCH")
        search_heading.setObjectName("panelTitle")
        layout.addWidget(search_heading)
        layout.addWidget(self.package_search)
        layout.addWidget(self.package_list)
        self.show_repository_packages()

        row = QHBoxLayout()
        for label, handler in [
            ("Search", self.search_packages),
            ("Install Selected", self.install_selected_package),
            ("Remove Selected", self.remove_selected_package),
            ("Export Package List", self.export_package_list),
        ]:
            button = QPushButton(label)
            button.setObjectName("softwareSectionButton")
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def kernel_panel(self):
        page = QWidget()
        page.setObjectName("softwareSubPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 8, 4, 4)
        page_layout.setSpacing(10)
        page_layout.addWidget(self.software_section_header("KERNELS", "INSTALL  •  VERIFY  •  BOOT", "◉"))
        frame, layout = self.panel("◉   KERNEL MANAGER")
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
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
        self.installed_kernels.setMaximumHeight(170)
        layout.addLayout(grid)

        row = QHBoxLayout()
        for label, handler in [
            ("Refresh Kernels", self.refresh_kernels),
            ("Install Selected", self.install_selected_kernel),
            ("Remove Selected", self.remove_selected_kernel),
            ("Rebuild Initramfs", self.rebuild_initramfs),
            ("Update GRUB", self.update_grub),
        ]:
            button = QPushButton(label)
            button.setObjectName("softwareSectionButton")
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        page_layout.addWidget(frame, 0, Qt.AlignTop)
        page_layout.addStretch(1)
        return page

    def package_cleanup_page(self):
        page = QWidget()
        page.setObjectName("softwareSubPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 8, 4, 4)
        page_layout.setSpacing(10)
        page_layout.addWidget(self.software_section_header("ORPHANS & FOREIGN", "CLASSIFY  •  INSPECT  •  CLEAN", "△"))
        grid = QGridLayout()

        orphans, orphan_layout = self.panel("△   ORPHAN PACKAGES")
        orphan_help = QLabel("Dependencies that are no longer required by another installed package. Review them before removal; packages you still use can be marked as explicitly installed.")
        orphan_help.setObjectName("muted")
        orphan_help.setWordWrap(True)
        orphan_layout.addWidget(orphan_help)
        orphan_layout.addWidget(self.orphan_summary)
        orphan_layout.addWidget(self.orphan_list, 1)
        orphan_actions = QHBoxLayout()
        for label, handler in [
            ("Inspect", lambda: self.inspect_managed_packages(self.orphan_list)),
            ("Keep Selected", self.keep_selected_orphans),
            ("Remove Selected", self.remove_selected_orphans),
            ("Remove All", self.remove_all_orphans),
        ]:
            button = QPushButton(label); button.setObjectName("softwareSectionButton"); button.clicked.connect(handler); orphan_actions.addWidget(button)
        orphan_actions.addStretch(); orphan_layout.addLayout(orphan_actions)

        foreign, foreign_layout = self.panel("◎   FOREIGN PACKAGES")
        foreign_help = QLabel("Packages installed locally or from the AUR that are absent from configured repository databases. Foreign does not mean unsafe; inspect the source and decide whether to update, keep, or remove each package.")
        foreign_help.setObjectName("muted")
        foreign_help.setWordWrap(True)
        foreign_layout.addWidget(foreign_help)
        foreign_layout.addWidget(self.foreign_summary)
        foreign_layout.addWidget(self.foreign_list, 1)
        foreign_actions = QHBoxLayout()
        for label, handler in [
            ("Inspect", lambda: self.inspect_managed_packages(self.foreign_list)),
            ("Update / Rebuild", self.update_selected_foreign),
            ("Remove Selected", self.remove_selected_foreign),
        ]:
            button = QPushButton(label); button.setObjectName("softwareSectionButton"); button.clicked.connect(handler); foreign_actions.addWidget(button)
        foreign_actions.addStretch(); foreign_layout.addLayout(foreign_actions)

        grid.addWidget(orphans, 0, 0)
        grid.addWidget(foreign, 0, 1)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        page_layout.addLayout(grid, 1)
        refresh = QPushButton("Refresh Package Classification")
        refresh.setObjectName("softwareSectionButton")
        refresh.clicked.connect(self.refresh)
        page_layout.addWidget(refresh, 0, Qt.AlignLeft)
        return page

    def maintenance_panel(self):
        frame, layout = self.panel("⚙   MAINTENANCE")
        body = QLabel("Prepare repair and cleanup actions in a terminal so privilege prompts and package confirmations stay visible.")
        body.setWordWrap(True)
        body.setObjectName("muted")
        layout.addWidget(body)

        row = QHBoxLayout()
        for label, command in [
            ("Review Package Cache", "du -sh /var/cache/pacman/pkg; echo; paccache -dk3 2>/dev/null || true"),
            ("Check Dependencies", "pacman -Dk; echo; pacman -Qk 2>/dev/null | grep -v ' 0 missing files' | head -80 || true"),
            ("Inspect Keyring", "pacman-key --list-keys >/dev/null && echo 'Keyring is readable' || echo 'Keyring check failed'"),
            ("List Orphans", "pacman -Qtdq || true"),
        ]:
            button = QPushButton(label)
            button.setObjectName("softwareSectionButton")
            button.clicked.connect(lambda checked=False, l=label, c=command: self.run_maintenance(l, c))
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return frame

    def refresh(self):
        if self.software_future is None:
            self.health_header.setText("SOFTWARE STATE  ·  CHECKING…")
            for card in getattr(self, "software_metrics", {}).values():
                card.detail.setText("Checking packages…")
            if hasattr(self, "software_health_checklist"):
                self.software_health_checklist.setText("Calculating software health…")
            self.software_future = self.software_executor.submit(self.collect_software_state)

    def collect_software_state(self):
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
        flatpak_updates = self.live_lines(["flatpak", "remote-ls", "--updates", "--columns=application,version"], 12) if command_exists("flatpak") else []
        orphans = self.live_lines(["pacman", "-Qtdq"], 8) if command_exists("pacman") else []
        foreign = self.live_lines(["pacman", "-Qqm"], 8) if command_exists("pacman") else []
        cache_size = run_text(["du", "-sh", "/var/cache/pacman/pkg"], 4)[0].split("\t", 1)[0] or "unknown"
        lock_state = "PRESENT" if Path("/var/lib/pacman/db.lck").exists() else "CLEAR"
        snapshot = self.snapshot_state()
        return {"repo": repo_updates, "aur": aur_updates, "flatpak": flatpak_updates, "orphans": orphans,
                "foreign": foreign, "cache": cache_size, "lock": lock_state, "snapshot": snapshot,
                "reboot": Path("/run/reboot-required").exists(), "kernel": run_text(["uname", "-r"], 2)[0]}

    def live_lines(self, command, timeout):
        output, _, code = run_text(command, timeout)
        return [line for line in output.splitlines() if line.strip()] if code == 0 else []

    def snapshot_state(self):
        if command_exists("snapper"):
            configs = run_text(["snapper", "list-configs"], 4)[0]
            configured = len([line for line in configs.splitlines() if "|" in line and not line.lstrip().startswith("Config")]) > 0
            return {"backend": "Snapper", "configured": configured}
        if command_exists("timeshift"):
            return {"backend": "Timeshift", "configured": True}
        return {"backend": "None detected", "configured": False}

    def finish_refresh(self):
        if self.software_future is None or not self.software_future.done():
            return
        future = self.software_future
        self.software_future = None
        try:
            state = future.result()
        except Exception as error:
            self.health_header.setText(f"SOFTWARE STATE  ·  CHECK FAILED: {error}")
            self.health_header.setProperty("state", "critical")
            self.health_header.style().unpolish(self.health_header); self.health_header.style().polish(self.health_header)
            for card in getattr(self, "software_metrics", {}).values():
                card.set_state("—", "Unable to query package database", "critical")
            if hasattr(self, "software_health_checklist"):
                self.software_health_checklist.setText("✗  Health check failed\nℹ  Review package sources and retry")
            return
        self.render_software_state(state)

    def render_software_state(self, state):
        self.last_software_state = state
        self.update_records = self.parse_update_records(state["repo"], "OFFICIAL") + self.parse_update_records(state["aur"], "AUR")
        total = len(self.update_records)
        high = sum(record["impact"] == "HIGH" for record in self.update_records)
        medium = sum(record["impact"] == "MEDIUM" for record in self.update_records)
        low = total - high - medium
        critical = state["reboot"] or state["lock"] != "CLEAR" or high
        attention = total or state["orphans"] or not state["snapshot"]["configured"]
        if critical:
            headline = "ACTION REQUIRED"
            reason = "REBOOT OR HIGH-IMPACT SOFTWARE STATE REQUIRES REVIEW"
        elif state["orphans"]:
            headline = "SYSTEM ATTENTION"
            reason = f"{len(state['orphans'])} ORPHAN PACKAGE{'S' if len(state['orphans']) != 1 else ''} REQUIRE REVIEW"
        elif total:
            headline = "SYSTEM ATTENTION"
            reason = f"{total} SOFTWARE UPDATE{'S' if total != 1 else ''} AVAILABLE"
        elif not state["snapshot"]["configured"]:
            headline = "SYSTEM ATTENTION"
            reason = "SNAPSHOT PROTECTION IS NOT CONFIGURED"
        else:
            headline = "SYSTEM HEALTHY"
            reason = "PACKAGE STATE IS CURRENT AND PROTECTED"
        self.health_header.setText(f"●  {headline}   ·   {reason}")
        self.health_header.setProperty("state", "critical" if critical else "warning" if attention else "success")
        self.health_header.style().unpolish(self.health_header); self.health_header.style().polish(self.health_header)
        chip_values = {
            "updates": (total, "warning" if total else "success"),
            "aur": (len(state["aur"]), "warning" if state["aur"] else "success"),
            "flatpak": (len(state["flatpak"]), "warning" if state["flatpak"] else "success"),
            "orphans": (len(state["orphans"]), "warning" if state["orphans"] else "success"),
            "reboot": ("YES" if state["reboot"] else "NO", "critical" if state["reboot"] else "success"),
        }
        labels = {"updates": "↻ UPDATES", "aur": "◇ AUR", "flatpak": "▣ FLATPAK", "orphans": "⚠ ORPHANS", "reboot": "⏻ REBOOT"}
        for key, (value, status_state) in chip_values.items():
            chip = self.software_chips[key]
            chip.setText(f"{labels[key]}\n{value}")
            chip.setProperty("state", status_state)
            chip.style().unpolish(chip); chip.style().polish(chip)

        metric_values = {
            "updates": (total, "Available" if total else "System current", "warning" if total else "success"),
            "aur": (len(state["aur"]), "Updates available" if state["aur"] else "Up to date", "warning" if state["aur"] else "success"),
            "flatpak": (len(state["flatpak"]), "Updates available" if state["flatpak"] else "Up to date", "warning" if state["flatpak"] else "success"),
            "orphans": (len(state["orphans"]), "Orphaned packages", "warning" if state["orphans"] else "success"),
            "foreign": (len(state["foreign"]), "Installed", "info"),
            "reboot": ("YES" if state["reboot"] else "NO", "Restart pending" if state["reboot"] else "System stable", "critical" if state["reboot"] else "success"),
        }
        for key, values in metric_values.items():
            self.software_metrics[key].set_state(*values)

        score = self.software_health_score(state, high)
        previous_score = getattr(self, "previous_software_health_score", None)
        self.software_health_gauge.set_score(score)
        if previous_score is None:
            trend_text = f"● Live · checked {time.strftime('%H:%M')}"
        elif score > previous_score:
            trend_text = f"▲ Up {score - previous_score}% since last check"
        elif score < previous_score:
            trend_text = f"▼ Down {previous_score - score}% since last check"
        else:
            trend_text = "— Stable since last check"
        self.software_health_trend.setText(trend_text)
        self.software_health_trend.setProperty("direction", "up" if previous_score is not None and score > previous_score else "down" if previous_score is not None and score < previous_score else "stable")
        self.software_health_trend.style().unpolish(self.software_health_trend); self.software_health_trend.style().polish(self.software_health_trend)
        self.previous_software_health_score = score
        checklist = [
            ("Updates", "ATTENTION" if total else "GOOD", bool(total)),
            ("Orphan Packages", "WARNING" if state["orphans"] else "GOOD", bool(state["orphans"])),
            ("Configuration", "ATTENTION" if state["lock"] != "CLEAR" else "GOOD", state["lock"] != "CLEAR"),
            ("Snapshots", "NEEDS ATTENTION" if not state["snapshot"]["configured"] else "GOOD", not state["snapshot"]["configured"]),
            ("Kernel", "GOOD" if state["kernel"] else "ATTENTION", not bool(state["kernel"])),
            ("Security", "ATTENTION" if high else "GOOD", bool(high)),
        ]
        checklist_rows = []
        for name, value, problem in checklist:
            icon, icon_color = ("⚠", "#F5B83D") if problem else ("✓", "#35D66B")
            value_color = "#F5B83D" if problem else "#D8E3EA"
            checklist_rows.append(
                f"<tr><td style='color:{icon_color};padding-right:8px'>{icon}</td>"
                f"<td style='color:#D5E0E7;padding-right:24px'>{name}</td>"
                f"<td align='right' style='color:{value_color};font-weight:700'>{value}</td></tr>"
            )
        self.software_health_checklist.setText(
            "<table cellspacing='2' cellpadding='0'>" + "".join(checklist_rows) + "</table>"
        )

        estimate = max(2, round(total * 0.25)) if total else 0
        recommendation_body, recommendation_detail, recommendation_badge, recommendation_button = self.software_intelligence["recommendation"]
        recommendation_body.setText(f"{total} Update{'s' if total != 1 else ''} Available" if total else "System Is Up to Date")
        recommendation_detail.setText(
            f"Estimated time  ·  {estimate} minute{'s' if estimate != 1 else ''}\nReboot  ·  {'May be required' if high or state['reboot'] else 'Not required'}"
            if total else "No update action is required."
        )
        recommendation_badge.setText("RECOMMENDED" if total else "SAFE")
        recommendation_badge.setProperty("state", "warning" if total else "success")
        recommendation_button.setEnabled(bool(total))
        analysis_body, analysis_detail, analysis_badge, analysis_button = self.software_intelligence["analysis"]
        analysis_body.setText(f"Low {low}  ·  Medium {medium}  ·  High {high}")
        analysis_detail.setText("No risky updates detected." if not high else f"{high} high-impact update{'s' if high != 1 else ''} require review.")
        analysis_badge.setText("REVIEW" if high else "SAFE")
        analysis_badge.setProperty("state", "critical" if high else "success")
        analysis_button.setEnabled(bool(total))
        action_body, action_detail, action_badge, action_button = self.software_intelligence["action"]
        if not state["snapshot"]["configured"]:
            next_action, action_detail_text, action_label = "Configure snapshot protection", "Before the next system update.", "CONFIGURE SNAPSHOTS"
        elif high:
            next_action, action_detail_text, action_label = "Create a recovery snapshot", "Recommended before high-impact updates.", "CREATE SNAPSHOT"
        elif state["orphans"] and not total:
            next_action, action_detail_text, action_label = "Review orphan packages", "Remove packages that are no longer required.", "REVIEW ORPHANS"
        elif total:
            next_action, action_detail_text, action_label = "Review update impact", "Proceed when the package transaction is ready.", "REVIEW UPDATES"
        else:
            next_action, action_detail_text, action_label = "No action required", "Software health is good.", "SYSTEM HEALTHY"
        action_body.setText(next_action); action_detail.setText(action_detail_text)
        action_badge.setText("ACTION REQUIRED" if action_label not in ("SYSTEM HEALTHY", "REVIEW UPDATES") else "SAFE" if action_label == "SYSTEM HEALTHY" else "RECOMMENDED")
        action_badge.setProperty("state", "warning" if action_label != "SYSTEM HEALTHY" else "success")
        action_button.setText(action_label); action_button.setEnabled(bool(total or state["orphans"] or not state["snapshot"]["configured"]))
        for _, _, badge, _ in self.software_intelligence.values():
            badge.style().unpolish(badge); badge.style().polish(badge)

        impact_counts = {"low": low, "medium": medium, "high": high}
        for key, count in impact_counts.items():
            value, bar, status = self.impact_columns[key]
            percentage = round(count / max(1, total) * 100)
            value.setText(str(count)); bar.setValue(percentage); status.setText(f"{percentage}% OF UPDATES" if total else "NO UPDATES DETECTED")

        snapshot = state["snapshot"]
        configured = snapshot["configured"]
        self.software_protection.setText(
            f"{'✓' if snapshot['backend'] != 'None detected' else '✗'}  BACKEND              {snapshot['backend']}\n"
            f"{'✓' if configured else '⚠'}  CONFIGURATION        {'READY' if configured else 'NOT READY'}\n"
            f"{'✓' if configured else '⚠'}  ROLLBACK TEST        {'AVAILABLE' if configured else 'NOT CONFIRMED'}\n"
            f"ℹ  RECOMMENDED          {'CREATE SNAPSHOT BEFORE UPDATING' if total else 'OPTIONAL'}"
        )
        self.snapshot_overview_button.setText("CREATE SNAPSHOT" if configured else "CONFIGURE SNAPSHOTS")
        self.protection_explanation.setText(
            "Snapshot protection is ready.\nCreate a recovery point before major updates."
            if configured else "Snapshot protection is incomplete.\nConfigure Snapper before the next system update to enable reliable rollback."
        )
        self.render_software_activity()
        self.status.setText(f"{total} system updates ({len(state['repo'])} official, {len(state['aur'])} AUR) · {len(state['flatpak'])} Flatpak")
        self.overview_status.setText(f"UPDATES          {total}\nAUR              {len(state['aur'])}\nFLATPAK          {len(state['flatpak'])}\nORPHANS          {len(state['orphans'])}\nFOREIGN          {len(state['foreign'])}\nREBOOT REQUIRED  {'YES' if state['reboot'] else 'NO'}")
        self.impact_status.setText(f"LOW IMPACT  {low}  ·  MEDIUM IMPACT  {medium}  ·  HIGH IMPACT  {high}\nHigh impact indicates core system, kernel, driver, boot, or filesystem packages; it is not a prediction of failure.")
        snapshot = state["snapshot"]
        self.snapshot_status.setText(f"BACKEND  {snapshot['backend']}\nCONFIGURATION  {'READY' if snapshot['configured'] else 'NOT READY'}\nROLLBACK  {'POTENTIALLY AVAILABLE' if snapshot['configured'] else 'NOT CONFIRMED'}\nRECOMMENDATION  {'CREATE SNAPSHOT BEFORE HIGH-IMPACT UPDATE' if high else 'OPTIONAL'}")
        self.health_status.setText(f"PACKAGE DATABASE     {'LOCKED' if state['lock'] != 'CLEAR' else 'ACCESSIBLE'}\nPACMAN LOCK          {state['lock']}\nPACKAGE CACHE        {state['cache']}\nORPHANS              {len(state['orphans'])}\nFOREIGN PACKAGES     {len(state['foreign'])}\nRUNNING KERNEL       {state['kernel']}")
        commandos_repo = "ENABLED" if re.search(r"(?m)^\[commandos\]\s*$", safe_read_text("/etc/pacman.conf")) else "NOT CONFIGURED"
        self.sources_status.setText(f"PACMAN       {'AVAILABLE' if command_exists('pacman') else 'MISSING'}\nCOMMANDOS    {commandos_repo}\nAUR HELPER   {('YAY' if command_exists('yay') else 'PARU' if command_exists('paru') else 'NONE')}\nFLATPAK      {'AVAILABLE' if command_exists('flatpak') else 'MISSING'}\nSNAPSHOTS    {snapshot['backend']} · {'READY' if snapshot['configured'] else 'NOT CONFIGURED'}")
        self.orphan_packages = list(state["orphans"])
        self.foreign_packages = list(state["foreign"])
        self.orphan_list.clear()
        self.orphan_list.addItems(self.orphan_packages)
        self.foreign_list.clear()
        self.foreign_list.addItems(self.foreign_packages)
        self.orphan_summary.setText(
            f"{len(self.orphan_packages)} orphan package(s) detected."
            if self.orphan_packages else "No orphan packages detected."
        )
        aur_helper = "yay" if command_exists("yay") else "paru" if command_exists("paru") else "no AUR helper"
        self.foreign_summary.setText(
            f"{len(self.foreign_packages)} foreign package(s) detected · {aur_helper}."
            if self.foreign_packages else "No foreign packages detected."
        )
        self.update_list.clear()
        for record in sorted(self.update_records, key=lambda item: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[item["impact"]]):
            self.update_list.addItem(f"{record['name'].upper()}  ·  {record['impact']} IMPACT  ·  {record['source']}\n{record['current']} → {record['new']}\n{record['reason']}")
        for row in state["flatpak"]:
            self.update_list.addItem(f"FLATPAK  ·  LOW IMPACT\n{row}")
        self.render_cachyos_catalog()
        self.render_history()
        self.refresh_tools_status()

    def parse_update_records(self, rows, source):
        high_names = {"linux", "linux-commandos", "linux-commandos-lts", "nvidia", "nvidia-utils", "mesa", "systemd", "glibc", "grub", "mkinitcpio", "btrfs-progs", "pacman", "linux-firmware"}
        medium_prefixes = ("qt6-", "plasma-", "pipewire", "openssl", "python", "gcc")
        records = []
        for row in rows:
            parts = row.split()
            name = parts[0] if parts else row
            current = parts[1] if len(parts) > 1 else "installed"
            new = parts[3] if len(parts) > 3 and parts[2] in ("->", "→") else parts[2] if len(parts) > 2 else "available"
            if name in high_names or name.startswith(("linux-", "nvidia-")):
                impact, reason = "HIGH", "Core system, kernel, graphics, boot, or filesystem component. Reboot or snapshot may be appropriate."
            elif name.startswith(medium_prefixes):
                impact, reason = "MEDIUM", "Shared platform component with multiple consumers."
            else:
                impact, reason = "LOW", "Application or leaf-package update based on package-name classification."
            records.append({"name": name, "current": current, "new": new, "source": source, "impact": impact, "reason": reason})
        return records

    def selected_managed_packages(self, widget):
        packages = []
        for item in widget.selectedItems():
            try:
                packages.append(validate_package(item.text().strip()))
            except ActionValidationError:
                continue
        return packages

    def inspect_managed_packages(self, widget):
        packages = self.selected_managed_packages(widget)
        if not packages:
            self.result.setPlainText("Select one or more packages to inspect.")
            return
        sections = []
        for package in packages[:25]:
            output, error, code = run_text(["pacman", "-Qi", package], 6)
            sections.append(output.strip() if code == 0 else f"{package}\n{error or 'Package information unavailable.'}")
        self.result.setPlainText("\n\n".join(sections))

    def remove_managed_packages(self, packages, category):
        if not packages:
            self.result.setPlainText(f"Select one or more {category.lower()} packages first.")
            return
        quoted = " ".join(shlex.quote(package) for package in packages)
        command = f"sudo pacman -Rns {quoted}"
        review = "\n".join(f"• {package}" for package in packages)
        warning = "Pacman will calculate and show the complete removal transaction in the terminal before confirmation."
        if not confirm(self, f"Remove {category} Packages", f"Remove these packages?\n\n{review}\n\n{warning}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Remove {category} Packages", command):
            self.record_transaction(f"Remove {category.lower()} packages", command)
            self.parent_window.add_history(f"{category} package removal started: {len(packages)} package(s)", category="UPDATE")

    def remove_selected_orphans(self):
        self.remove_managed_packages(self.selected_managed_packages(self.orphan_list), "Orphan")

    def remove_all_orphans(self):
        packages = []
        for package in self.orphan_packages:
            try:
                packages.append(validate_package(package))
            except ActionValidationError:
                continue
        self.remove_managed_packages(packages, "All Orphan")

    def keep_selected_orphans(self):
        packages = self.selected_managed_packages(self.orphan_list)
        if not packages:
            self.result.setPlainText("Select orphan packages to keep as explicitly installed.")
            return
        quoted = " ".join(shlex.quote(package) for package in packages)
        command = f"sudo pacman -D --asexplicit {quoted}"
        review = "\n".join(f"• {package}" for package in packages)
        if not confirm(self, "Keep Orphan Packages", f"Mark these packages as explicitly installed so they are no longer classified as orphans?\n\n{review}\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Keep Orphan Packages", command):
            self.record_transaction("Mark orphan packages explicit", command)
            self.parent_window.add_history(f"Marked {len(packages)} orphan package(s) as explicit", category="UPDATE")

    def remove_selected_foreign(self):
        self.remove_managed_packages(self.selected_managed_packages(self.foreign_list), "Foreign")

    def update_selected_foreign(self):
        packages = self.selected_managed_packages(self.foreign_list)
        if not packages:
            self.result.setPlainText("Select foreign packages to update or rebuild.")
            return
        helper = "yay" if command_exists("yay") else "paru" if command_exists("paru") else ""
        if not helper:
            self.result.setPlainText("No AUR helper is available. Foreign packages can still be inspected or removed; locally built packages must be rebuilt from their original source.")
            return
        quoted = " ".join(shlex.quote(package) for package in packages)
        command = f"{helper} -S --needed {quoted}"
        review = "\n".join(f"• {package}" for package in packages)
        if not confirm(self, "Update Foreign Packages", f"Ask {helper} to update or rebuild these packages?\n\n{review}\n\nPackages unavailable from the AUR will be reported without being changed.\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Update Foreign Packages", command):
            self.record_transaction("Update selected foreign packages", command)
            self.parent_window.add_history(f"Foreign package update started: {len(packages)} package(s)", category="UPDATE")

    def show_update_review(self):
        self.tabs.setCurrentIndex(1)
        self.result.show()
        if not self.update_records:
            if self.software_future is not None:
                self.result.setPlainText("Checking package sources… The update review will populate when the current scan completes.")
            else:
                self.result.setPlainText("No system updates are currently available. The Updates workspace is open and ready for a new check.")
            return
        self.update_list.clear()
        for item in sorted(self.update_records, key=lambda record: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(record["impact"], 3)):
            self.update_list.addItem(
                f"{item['name'].upper()}  ·  {item['impact']} IMPACT  ·  {item['source']}\n"
                f"{item['current']} → {item['new']}\n{item['reason']}"
            )
        self.update_list.scrollToTop()
        high = sum(item["impact"] == "HIGH" for item in self.update_records)
        medium = sum(item["impact"] == "MEDIUM" for item in self.update_records)
        low = len(self.update_records) - high - medium
        self.result.setPlainText(
            f"UPDATE REVIEW READY  ·  {len(self.update_records)} package(s)\n"
            f"LOW {low}  ·  MEDIUM {medium}  ·  HIGH {high}\n"
            "Review package impact below before starting the full system upgrade."
        )

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
        if self.cachyos_catalog:
            package_count = sum(len(packages) for packages in self.cachyos_catalog.values())
            self.cachyos_pi_status.setText(
                f"READY  ·  {package_count} curated entries in {len(self.cachyos_catalog)} categories"
            )
        else:
            self.cachyos_pi_status.setText("CATALOGUE UNAVAILABLE  ·  CommandOS package catalogue data was not found")

    def load_cachyos_catalog(self):
        self.cachyos_catalog = {
            category: [entry.split(" + ") for entry in entries]
            for category, entries in COMMANDOS_CURATED_CATALOG.items()
        }
        self.cachyos_category.blockSignals(True)
        self.cachyos_category.clear()
        self.cachyos_category.addItem("All categories")
        self.cachyos_category.addItems(self.cachyos_catalog.keys())
        self.cachyos_category.blockSignals(False)
        self.render_cachyos_catalog()
        self.refresh_tools_status()

    def load_package_metadata(self):
        if not command_exists("expac"):
            return
        output, _, code = run_text(["expac", "-S", "%r\\t%n\\t%v\\t%d"], 12)
        if code != 0:
            return
        seen = set()
        for line in output.splitlines():
            parts = line.split("\t", 3)
            if len(parts) != 4:
                continue
            repository, name, version, description = parts
            if name in seen:
                continue
            seen.add(name)
            record = {"repository": repository, "name": name, "version": version, "description": description}
            self.repository_packages.append(record)
            self.package_metadata[name] = record
        self.repository_packages.sort(key=lambda record: record["name"].lower())

    def render_cachyos_catalog(self):
        if not hasattr(self, "cachyos_list"):
            return
        category_filter = self.cachyos_category.currentText()
        needle = self.cachyos_search.text().strip().lower()
        installed_output = run_text(["pacman", "-Qq"], 8)[0] if command_exists("pacman") else ""
        installed = set(installed_output.splitlines())
        self.cachyos_list.blockSignals(True)
        self.cachyos_list.clear()
        for category, entries in self.cachyos_catalog.items():
            if category_filter not in ("", "All categories", category):
                continue
            for packages in entries:
                bundle = " ".join(packages)
                if needle and needle not in category.lower() and needle not in bundle.lower():
                    continue
                state = "INSTALLED" if all(package in installed for package in packages) else "AVAILABLE"
                installed_count = sum(package in installed for package in packages)
                if installed_count and installed_count < len(packages):
                    state = f"PARTIAL · {installed_count}/{len(packages)}"
                descriptions = [self.package_metadata[package]["description"] for package in packages if package in self.package_metadata]
                description = descriptions[0] if descriptions else CURATED_CATEGORY_DESCRIPTIONS.get(category, "CommandOS curated application.")
                item = QListWidgetItem()
                item.setData(Qt.UserRole, packages)
                self.cachyos_list.addItem(item)
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 8, 10, 8)
                copy = QVBoxLayout()
                name = QLabel(packages[0])
                name.setObjectName("panelTitle")
                detail = QLabel(
                    f"{description}\n"
                    f"Packages: {bundle}\n"
                    f"Installation state: {state}"
                )
                detail.setObjectName("muted")
                detail.setWordWrap(True)
                copy.addWidget(name)
                copy.addWidget(detail)
                install = QPushButton("INSTALLED" if state == "INSTALLED" else "INSTALL")
                install.setEnabled(state != "INSTALLED")
                install.setObjectName("primaryButton" if state != "INSTALLED" else "")
                install.setMinimumWidth(110)
                install.clicked.connect(lambda checked=False, selected=list(packages): self.install_curated_bundle(selected))
                row_layout.addLayout(copy, 1)
                row_layout.addWidget(install)
                item.setSizeHint(row.sizeHint())
                self.cachyos_list.setItemWidget(item, row)
        self.cachyos_list.blockSignals(False)

    def install_curated_bundle(self, packages):
        try:
            packages = [validate_package(package) for package in packages]
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked invalid curated package: {error}")
            return
        missing = []
        installed_output = run_text(["pacman", "-Qq"], 8)[0] if command_exists("pacman") else ""
        installed = set(installed_output.splitlines())
        for package in packages:
            if package not in installed:
                missing.append(package)
        if not missing:
            self.result.setPlainText("Every package in this curated entry is already installed.")
            self.render_cachyos_catalog()
            return
        quoted = " ".join(shlex.quote(package) for package in missing)
        if command_exists("yay"):
            command = f"yay -S --needed {quoted}"
        elif command_exists("paru"):
            command = f"paru -S --needed {quoted}"
        else:
            command = f"sudo pacman -S --needed {quoted}"
        review = "\n".join(f"• {package}" for package in missing)
        if not confirm(self, "Install Curated Application", f"Install this CommandOS curated entry?\n\n{review}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Install {packages[0]}", command):
            self.record_transaction(f"Curated installation: {packages[0]}", command)
            self.parent_window.add_history(f"Curated install started: {' '.join(missing)}", category="UPDATE")

    def cachyos_item_changed(self, item):
        bundle = " ".join(item.data(Qt.UserRole) or [])
        if not bundle:
            return
        if item.checkState() == Qt.Checked:
            self.cachyos_checked.add(bundle)
        else:
            self.cachyos_checked.discard(bundle)

    def install_cachyos_packages(self):
        packages = []
        for bundle in sorted(self.cachyos_checked):
            for package in bundle.split():
                if package not in packages:
                    packages.append(package)
        if not packages:
            self.result.setPlainText("Check one or more CommandOS catalogue entries first.")
            return
        try:
            packages = [validate_package(package) for package in packages]
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked invalid curated package: {error}")
            return
        quoted = " ".join(shlex.quote(package) for package in packages)
        if command_exists("yay"):
            command = f"yay -S --needed {quoted}"
        elif command_exists("paru"):
            command = f"paru -S --needed {quoted}"
        else:
            command = f"sudo pacman -S --needed {quoted}"
        review = "\n".join(f"• {package}" for package in packages)
        if not confirm(self, "Install CommandOS Curated Packages", f"Install these packages?\n\n{review}\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Install CommandOS Curated Packages", command):
            self.record_transaction("CommandOS curated package installation", command)
            self.parent_window.add_history(f"CommandOS curated install started: {len(packages)} package(s)")

    def show_repository_packages(self, records=None):
        records = self.repository_packages[:150] if records is None else records[:150]
        self.package_list.clear()
        for record in records:
            item = QListWidgetItem(
                f"{record['name']}  {record['version']}  ·  {record['repository']}\n"
                f"{record['description']}"
            )
            item.setData(Qt.UserRole, record["name"])
            self.package_list.addItem(item)
        if not records and not self.repository_packages:
            self.result.setPlainText("Repository package metadata is unavailable. Use Search to query pacman directly.")

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
        try:
            package = validate_package(package)
        except ActionValidationError as error:
            self.result.setPlainText(str(error))
            return
        command = f"sudo chwd-kernel --install {shlex.quote(package)}"
        if not confirm(self, "Install Kernel", f"Install this kernel?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Install Kernel {package}", command):
            self.record_transaction(f"Kernel installation: {package}", command)
            self.parent_window.add_history(f"Kernel install started: {package}")

    def remove_selected_kernel(self):
        package = self.selected_installed_kernel()
        if not package:
            self.result.setPlainText("Select an installed kernel first.")
            return
        try:
            package = validate_package(package)
        except ActionValidationError as error:
            self.result.setPlainText(str(error))
            return
        if self.installed_kernels.count() <= 1:
            self.result.setPlainText("Refusing to remove the only detected installed kernel. Install and verify a fallback kernel first.")
            return
        running = run_text(["uname", "-r"], 2)[0]
        running_base = re.sub(r"-\d+(?:\.\d+)*.*$", "", running)
        if package == running_base or package in running:
            self.result.setPlainText("Refusing to remove the currently running kernel.")
            return
        command = f"sudo chwd-kernel --remove {shlex.quote(package)}"
        if not confirm(self, "Remove Kernel", f"Remove this installed kernel?\n\n{package}\n\nCommand:\n{command}"):
            return
        if self.terminal_command(f"Remove Kernel {package}", command):
            self.record_transaction(f"Kernel removal: {package}", command)
            self.parent_window.add_history(f"Kernel removal started: {package}")

    def rebuild_initramfs(self):
        command = "sudo mkinitcpio -P"
        if not confirm(self, "Rebuild Initramfs", f"Rebuild initramfs for all kernels?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Rebuild Initramfs", command):
            self.record_transaction("Rebuild initramfs", command)
            self.parent_window.add_history("Initramfs rebuild started")

    def update_grub(self):
        command = "sudo grub-mkconfig -o /boot/grub/grub.cfg"
        if not confirm(self, "Update GRUB", f"Regenerate GRUB configuration?\n\nCommand:\n{command}"):
            return
        if self.terminal_command("Update GRUB", command):
            self.record_transaction("Regenerate GRUB configuration", command)
            self.parent_window.add_history("GRUB update started")

    def update_command(self):
        if command_exists("yay"):
            return "yay -Syu"
        if command_exists("paru"):
            return "paru -Syu"
        return "sudo pacman -Syu"

    def update_system(self):
        command = self.update_command()
        snapshot = self.snapshot_state()
        message = (
            "Run a full system update in a terminal?\n\n"
            f"Command:\n{command}\n\n"
            f"Snapshot protection: {snapshot['backend']} · {'READY' if snapshot['configured'] else 'NOT CONFIRMED'}\n\n"
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
            self.record_transaction("Full system upgrade", command)
        else:
            self.result.setPlainText(terminal)

    def create_snapshot(self):
        snapshot = self.snapshot_state()
        if not snapshot["configured"]:
            self.result.setPlainText("No configured Snapper or Timeshift backend was confirmed. Configure snapshots in System Control before relying on rollback.")
            return
        stamp = time.strftime("command-centre-pre-update-%Y%m%d-%H%M")
        if snapshot["backend"] == "Snapper":
            command = f"sudo snapper create --description {shlex.quote(stamp)}"
        else:
            command = f"sudo timeshift --create --comments {shlex.quote(stamp)}"
        if not confirm(self, "Create Pre-update Snapshot", f"Create a pre-update snapshot?\n\nBackend: {snapshot['backend']}\nCommand:\n{command}"):
            return
        if self.terminal_command("Command Centre Pre-update Snapshot", command):
            self.record_transaction("Pre-update snapshot", command, snapshot=stamp)
            self.parent_window.add_history("Pre-update snapshot started")

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
            self.record_transaction("Flatpak update", command)
            self.parent_window.add_history("Flatpak update started")

    def search_packages(self):
        query = self.package_search.text().strip()
        if not query and self.repository_packages:
            self.show_repository_packages()
            return
        if len(query) < 2:
            self.result.setPlainText("Type at least two characters to search packages.")
            return
        if self.repository_packages:
            needle = query.lower()
            matches = [
                record for record in self.repository_packages
                if needle in record["name"].lower()
                or needle in record["description"].lower()
                or needle in record["repository"].lower()
            ]
            self.show_repository_packages(matches)
            self.result.setPlainText(
                f"Found {len(matches)} repository package(s) matching '{query}'. "
                "Showing the first 150 results. Double-click a package to install it."
            )
            return
        self.package_list.clear()
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
        package = validate_package(package)
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
            self.record_transaction(f"Software health: {label}", command)
            self.parent_window.add_history(f"Software maintenance started: {label}")

    def shutdown(self):
        self.software_executor.shutdown(wait=False, cancel_futures=True)


class ToolItemDelegate(QStyledItemDelegate):
    """Paint Tool Library entries as compact application cards."""

    def paint(self, painter, option, index):
        tool = index.data(Qt.UserRole) or {}
        if not isinstance(tool, dict):
            super().paint(painter, option, index)
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.State_Selected)
        painter.setPen(QPen(QColor("#2BC4FF" if selected else "#173B52"), 1))
        painter.setBrush(QColor("#102B3D" if selected else "#08141E"))
        painter.drawRoundedRect(rect, 8, 8)
        if selected:
            painter.setPen(Qt.NoPen); painter.setBrush(QColor("#2BC4FF"))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 4, rect.height()), 2, 2)

        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, int(rect.left() + 12), int(rect.top() + 15), 40, 40)
        left = rect.left() + 64
        width = rect.width() - 76
        title_font = painter.font(); title_font.setPixelSize(13); title_font.setWeight(QFont.Bold)
        painter.setFont(title_font); painter.setPen(QColor("#F3F8FB"))
        title = painter.fontMetrics().elidedText(str(tool.get("name", "Tool")), Qt.ElideRight, int(width))
        if tool.get("id") in tool.get("_favorites", []):
            title = "★  " + title
        painter.drawText(QRectF(left, rect.top() + 8, width, 20), Qt.AlignVCenter, title.upper())
        body_font = painter.font(); body_font.setPixelSize(11); body_font.setWeight(QFont.Normal)
        painter.setFont(body_font); painter.setPen(QColor("#9FB1BD"))
        description = painter.fontMetrics().elidedText(str(tool.get("description", "")), Qt.ElideRight, int(width))
        painter.drawText(QRectF(left, rect.top() + 29, width, 18), Qt.AlignVCenter, description)

        metadata = tool.get("metadata", {})
        badges = [
            ("INSTALLED" if tool.get("installed") else "AVAILABLE", "#35D66B" if tool.get("installed") else "#2BC4FF"),
            (str(metadata.get("type", tool.get("kind", "tool"))).upper(), "#8FA9BB"),
            (str(tool.get("group", "Tool")).upper(), "#A65DFF"),
        ]
        if metadata.get("recommended"):
            badges.append(("COMMANDOS", "#B478FF"))
        badge_x = left
        badge_font = painter.font(); badge_font.setPixelSize(9); badge_font.setWeight(QFont.DemiBold); painter.setFont(badge_font)
        for text_value, color in badges:
            badge_width = min(int(width), painter.fontMetrics().horizontalAdvance(text_value) + 14)
            if badge_x + badge_width > rect.right() - 8:
                break
            badge_rect = QRectF(badge_x, rect.top() + 52, badge_width, 20)
            fill = QColor(color); fill.setAlpha(28)
            painter.setBrush(fill); painter.setPen(QPen(QColor(color), 1)); painter.drawRoundedRect(badge_rect, 5, 5)
            painter.setPen(QColor(color)); painter.drawText(badge_rect, Qt.AlignCenter, text_value)
            badge_x += badge_width + 5
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(max(320, option.rect.width()), 82)


class ToolLibraryPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.tools = []
        self.filtered_tools = []
        self.metadata, self.collections = self.load_metadata()
        self.tools = [self.metadata_entry(tool_id, info) for tool_id, info in self.metadata.items()]
        self.tool_state = self.load_tool_state()
        self.inventory_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tool-inventory")
        self.inventory_future = None
        self.inventory_signature = None
        self.inventory_refresh_pending = False
        self.inventory_initialized = False
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tools, capabilities and tasks — e.g. inspect image metadata")
        self.search.textChanged.connect(self.render_tools)
        self.view_mode = QComboBox()
        self.view_mode.addItem("LIBRARY", "library")
        self.view_mode.addItem("COLLECTIONS", "collections")
        self.view_mode.addItem("INVENTORY", "inventory")
        self.view_mode.currentIndexChanged.connect(self.view_changed)
        self.categories = QListWidget()
        self.categories.setObjectName("toolCategories")
        self.categories.setMinimumWidth(210)
        self.categories.itemSelectionChanged.connect(self.render_tools)
        self.list = QListWidget()
        self.list.setObjectName("toolAppList")
        self.list.setItemDelegate(ToolItemDelegate(self.list))
        self.list.setIconSize(QSize(40, 40))
        self.list.setSpacing(2)
        self.list.itemSelectionChanged.connect(self.selection_changed)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("textPanel")
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")
        self.status = QLabel("--")
        self.status.setObjectName("muted")
        self.favorite_button = QPushButton("☆ FAVORITE")
        self.favorite_button.setObjectName("toolActionButton")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.filter_buttons = {}
        self.installing_tool_key = ""
        self.auto_refresh = QTimer(self)
        self.auto_refresh.timeout.connect(self.refresh_if_changed)
        self.auto_refresh.start(5000)
        self.inventory_watcher = QFileSystemWatcher(self)
        watch_paths = [
            CURATED_TOOLS_FILE,
            Path("/var/lib/pacman/local"),
            Path("/usr/share/applications"),
            Path.home() / ".local/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/var/lib/flatpak/app"),
            Path.home() / ".local/share/flatpak/app",
        ]
        watch_paths.extend(Path(path) for path in os.environ.get("PATH", "").split(os.pathsep) if path)
        self.inventory_watch_paths = list(dict.fromkeys(watch_paths))
        existing_watch_paths = [path for path in self.inventory_watch_paths if path.exists()]
        if existing_watch_paths:
            self.inventory_watcher.addPaths([str(path) for path in existing_watch_paths])
        self.inventory_watcher.fileChanged.connect(lambda _: self.refresh_if_changed())
        self.inventory_watcher.directoryChanged.connect(lambda _: self.refresh_if_changed())
        self.inventory_poll = QTimer(self)
        self.inventory_poll.timeout.connect(self.finish_inventory_refresh)
        self.inventory_poll.start(100)

        layout = QVBoxLayout(self)
        title = QLabel("TOOL LIBRARY")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        stats = QHBoxLayout(); stats.setSpacing(8)
        self.tool_stats = {}
        for key, label in (("installed", "INSTALLED"), ("available", "AVAILABLE"), ("recommended", "RECOMMENDED"), ("shown", "SHOWN")):
            card = QFrame(); card.setObjectName("toolStatCard")
            box = QVBoxLayout(card); box.setContentsMargins(10, 6, 10, 6); box.setSpacing(0)
            value = QLabel("—"); value.setObjectName("toolStatValue")
            caption = QLabel(label); caption.setObjectName("toolStatLabel")
            box.addWidget(value); box.addWidget(caption); stats.addWidget(card, 1)
            self.tool_stats[key] = value
        layout.addLayout(stats)
        layout.addWidget(self.status)

        controls = QHBoxLayout()
        controls.addWidget(self.view_mode)
        controls.addWidget(self.search, 1)
        refresh = QPushButton("Sync Now")
        refresh.setToolTip("Auto-sync is active; use this to force an immediate full inventory scan")
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        layout.addLayout(controls)

        filters = QHBoxLayout(); filters.setSpacing(6)
        filter_label = QLabel("QUICK FILTERS"); filter_label.setObjectName("toolFilterLabel"); filters.addWidget(filter_label)
        for key, label in (("installed", "Installed"), ("missing", "Available"), ("gui", "GUI"), ("cli", "CLI"), ("recommended", "Recommended")):
            chip = QPushButton(label); chip.setObjectName("toolFilterChip"); chip.setCheckable(True)
            chip.toggled.connect(self.render_tools); filters.addWidget(chip); self.filter_buttons[key] = chip
        filters.addStretch(); layout.addLayout(filters)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.categories)
        browser = QWidget(); browser_layout = QVBoxLayout(browser); browser_layout.setContentsMargins(0, 0, 0, 0); browser_layout.setSpacing(6)
        self.recommended_strip = QLabel("RECOMMENDED FOR YOU  ·  Calculating recommendations…")
        self.recommended_strip.setObjectName("toolRecommendedStrip")
        self.recommended_strip.setWordWrap(True)
        browser_layout.addWidget(self.recommended_strip); browser_layout.addWidget(self.list, 1)
        split.addWidget(browser)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.detail, 3)
        actions = QHBoxLayout()
        for label, handler in [
            ("▶  Launch", self.launch_selected_tool),
            (">_  Terminal", self.open_selected_terminal),
            ("↓  Install", self.install_selected_tool),
            ("▤  Guide", self.open_selected_guide),
        ]:
            button = QPushButton(label)
            button.setObjectName("toolActionButton")
            button.setMinimumWidth(92)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addWidget(self.favorite_button)
        actions.addStretch()
        right_layout.addLayout(actions)
        self.install_progress = QProgressBar(); self.install_progress.setObjectName("toolInstallProgress"); self.install_progress.setRange(0, 0); self.install_progress.hide()
        right_layout.addWidget(self.install_progress)
        right_layout.addWidget(self.result, 2)
        split.addWidget(right)
        split.setStretchFactor(0, 18); split.setStretchFactor(1, 42); split.setStretchFactor(2, 40)
        split.setSizes([216, 504, 480])
        layout.addWidget(split, 1)
        self.populate_categories()
        self.render_tools()
        self.refresh()

    def load_metadata(self):
        try:
            data = json.loads(CURATED_TOOLS_FILE.read_text(encoding="utf-8"))
            tools = {tool["id"]: tool for tool in data.get("tools", [])}
            return tools, data.get("collections", [])
        except Exception:
            return {}, []

    def metadata_entry(self, tool_id, info):
        command = info.get("command", "")
        return {
            "key": f"curated:{tool_id}", "id": tool_id, "name": info.get("name", tool_id),
            "package": info.get("package", tool_id), "command": command, "kind": "curated",
            "group": info.get("category", "Uncategorized"), "description": info.get("purpose", ""),
            "installed": bool(command and command_exists(command.split()[0])), "metadata": info,
        }

    def load_tool_state(self):
        try:
            data = json.loads(TOOL_STATE_FILE.read_text(encoding="utf-8"))
            return {"favorites": data.get("favorites", []), "recent": data.get("recent", [])}
        except Exception:
            return {"favorites": [], "recent": []}

    def save_tool_state(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOOL_STATE_FILE.write_text(json.dumps(self.tool_state, indent=2), encoding="utf-8")

    def refresh(self):
        if self.inventory_future is None:
            self.status.setText(f"{len(self.metadata)} curated tools ready · inventory scanning in background…")
            self.inventory_future = self.inventory_executor.submit(self.build_library)
        else:
            self.inventory_refresh_pending = True

    def finish_inventory_refresh(self):
        if self.inventory_future is None or not self.inventory_future.done():
            return
        future = self.inventory_future
        self.inventory_future = None
        previous_by_key = {tool.get("key"): tool for tool in self.tools}
        previous_keys = set(previous_by_key)
        try:
            self.tools = future.result()
        except Exception as error:
            self.result.setPlainText(f"Inventory refresh failed: {error}")
            return
        self.inventory_signature = self.inventory_change_signature()
        self.populate_categories()
        self.render_tools()
        added = [tool for tool in self.tools if tool.get("key") not in previous_keys]
        current_keys = {tool.get("key") for tool in self.tools}
        removed = [tool for key, tool in previous_by_key.items() if key not in current_keys]
        if self.inventory_initialized and previous_keys and added:
            names = ", ".join(tool.get("name", "Unknown") for tool in added[:5])
            suffix = f" and {len(added) - 5} more" if len(added) > 5 else ""
            message = f"Tool Library detected {len(added)} new item(s): {names}{suffix}"
            self.result.setPlainText(message)
            self.parent_window.add_history(message, category="SYSTEM")
        elif self.inventory_initialized and previous_keys and removed:
            names = ", ".join(tool.get("name", "Unknown") for tool in removed[:5])
            suffix = f" and {len(removed) - 5} more" if len(removed) > 5 else ""
            message = f"Tool Library removed {len(removed)} unavailable item(s): {names}{suffix}"
            self.result.setPlainText(message)
            self.parent_window.add_history(message, category="SYSTEM")
        else:
            self.result.setPlainText("Tool Library synchronized with the live system inventory. Automatic sync is active.")
        self.inventory_initialized = True
        # The lower-right panel is contextual tool information; restore it after
        # transient synchronization notices have been recorded.
        if self.selected_tool():
            self.selection_changed()
        if self.inventory_refresh_pending:
            self.inventory_refresh_pending = False
            if self.inventory_change_signature() != self.inventory_signature:
                self.refresh_if_changed()

    def refresh_if_changed(self):
        signature = self.inventory_change_signature()
        if self.inventory_signature is None or signature != self.inventory_signature:
            watched = set(self.inventory_watcher.files()) | set(self.inventory_watcher.directories())
            newly_available = [str(path) for path in self.inventory_watch_paths if path.exists() and str(path) not in watched]
            if newly_available:
                self.inventory_watcher.addPaths(newly_available)
            metadata, collections = self.load_metadata()
            self.metadata = metadata
            self.collections = collections
            self.refresh()

    def inventory_change_signature(self):
        signature = []
        for path in self.inventory_watch_paths:
            try:
                stat = path.stat()
                signature.append((str(path), stat.st_mtime_ns, stat.st_size))
            except OSError:
                signature.append((str(path), 0, 0))
        return tuple(signature)

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
        for info in self.metadata.values():
            descriptions[info.get("package", info["id"])] = info
            descriptions[info.get("command", info["id"])] = info
        for group, tools in TOOL_GROUPS:
            for name, command, description, package in tools:
                descriptions.setdefault(package, {
                    "id": command,
                    "name": name,
                    "command": command,
                    "description": description,
                    "package": package,
                    "group": group,
                })
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
        represented_ids = set()

        for package in explicit:
            info = curated.get(package, {})
            command = info.get("command") or (package if package in executables or command_exists(package) else "")
            kind = "aur" if package in aur else "package"
            tools.append(
                {
                    "key": f"{kind}:{package}",
                    "id": info.get("id", package),
                    "name": info.get("name") or package,
                    "package": package,
                    "command": command,
                    "kind": kind,
                    "group": info.get("category") or info.get("group") or ("AUR / Foreign" if kind == "aur" else "Installed Package"),
                    "description": info.get("purpose") or info.get("description") or f"Installed package from {'AUR/foreign source' if kind == 'aur' else 'pacman repositories'}.",
                    "installed": True,
                    "metadata": info,
                }
            )
            if info:
                represented_ids.add(info.get("id", package))
            seen.add(command or package)

        for row in flatpaks:
            parts = row.split("\t")
            app_id = parts[0]
            name = parts[1] if len(parts) > 1 and parts[1] else app_id
            version = parts[2] if len(parts) > 2 else ""
            tools.append(
                {
                    "key": f"flatpak:{app_id}",
                    "id": app_id,
                    "name": name,
                    "package": app_id,
                    "command": f"flatpak run {shlex.quote(app_id)}",
                    "kind": "flatpak",
                    "group": "Flatpak",
                    "description": f"Flatpak application{f' version {version}' if version else ''}.",
                    "installed": True,
                    "metadata": {},
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
                    "id": key_name,
                    "name": desktop.get("name") or key_name,
                    "package": executable or desktop.get("desktop_id") or key_name,
                    "desktop_id": desktop.get("desktop_id", ""),
                    "icon_name": desktop.get("icon_name", ""),
                    "command": command,
                    "kind": "desktop",
                    "group": "Desktop App",
                    "description": desktop.get("description") or "Installed desktop launcher discovered from application entries.",
                    "installed": True,
                    "metadata": {},
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
                    "id": info.get("id", command),
                    "name": info.get("name") or command,
                    "package": info.get("package") or command,
                    "command": command,
                    "kind": "curated" if info else "executable",
                    "group": info.get("category") or info.get("group") or "Executable Tool",
                    "description": info.get("purpose") or info.get("description") or "Executable command found in /usr/bin, /usr/local/bin, or ~/.local/bin.",
                    "installed": True,
                    "metadata": info,
                }
            )
            if info:
                represented_ids.add(info.get("id", command))

        for tool_id, info in self.metadata.items():
            if tool_id in represented_ids:
                continue
            command = info.get("command", "")
            installed = bool(command and command_exists(command.split()[0]))
            tools.append({
                "key": f"curated:{tool_id}", "id": tool_id, "name": info["name"],
                "package": info.get("package", tool_id), "command": command,
                "kind": "curated", "group": info.get("category", "Uncategorized"),
                "description": info.get("purpose", "Curated CommandOS tool."),
                "installed": installed, "metadata": info,
            })

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
        icon_name = ""
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
                elif line.startswith("Icon=") and not icon_name:
                    icon_name = line.split("=", 1)[1].strip()
                elif line.startswith("NoDisplay="):
                    no_display = line.split("=", 1)[1].strip().lower() == "true"
        except OSError:
            return None
        if not name or not exec_line or no_display:
            return None
        command = re.sub(r"\s+%[fFuUdDnNickvm]", "", exec_line).strip()
        return {"desktop_id": file_path.name, "name": name, "command": command, "description": comment, "icon_name": icon_name}

    def view_changed(self):
        self.populate_categories()
        self.render_tools()

    def populate_categories(self):
        selected = self.selected_category()
        self.categories.blockSignals(True)
        self.categories.clear()
        mode = self.view_mode.currentData() if hasattr(self, "view_mode") else "library"
        values = []
        if mode == "library":
            values = [("▦  ALL TOOLS\nBrowse the equipment locker", "all"), ("★  PINNED\nFavourite tools", "favorites"), ("◷  RECENT\nRecently launched", "recent"), ("✦  RECOMMENDED\nCommandOS selections", "recommended")]
            counts = {}
            installed_counts = {}
            for info in self.metadata.values():
                category = info.get("category", "Uncategorized")
                counts[category] = counts.get(category, 0) + 1
            for tool in self.tools:
                if tool.get("installed") and tool.get("id") in self.metadata:
                    installed_counts[tool.get("group", "Uncategorized")] = installed_counts.get(tool.get("group", "Uncategorized"), 0) + 1
            category_icons = {"3D Printing": "▣", "CAD & Creation": "✦", "Development": "⌘", "Networking": "◎", "Security": "◇", "Hardware": "⚙"}
            values.extend(
                (f"{category_icons.get(category, '◈')}  {category.upper()}\n{installed_counts.get(category, 0)} installed · {count} available", category)
                for category, count in sorted(counts.items())
            )
        elif mode == "collections":
            values = [("ALL COLLECTIONS", "all")]
        else:
            values = [("ALL INVENTORY", "all"), ("PACKAGES", "package"), ("AUR / FOREIGN", "aur"), ("FLATPAKS", "flatpak"), ("DESKTOP APPS", "desktop"), ("EXECUTABLES", "executable")]
        for label, value in values:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, value)
            item.setSizeHint(QSize(190, 54))
            self.categories.addItem(item)
            if value == selected:
                item.setSelected(True)
        if not self.categories.selectedItems() and self.categories.count():
            self.categories.item(0).setSelected(True)
        self.categories.blockSignals(False)

    def selected_category(self):
        if not hasattr(self, "categories"):
            return "all"
        selected = self.categories.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else "all"

    def render_tools(self):
        selected_key = self.selected_tool().get("key") if self.selected_tool() else ""
        needle = self.search.text().strip().lower()
        mode = self.view_mode.currentData() or "library"
        category = self.selected_category()
        self.list.clear()
        self.filtered_tools = []
        if mode == "collections":
            for collection in self.collections:
                haystack = f"{collection.get('name')} {collection.get('description')} {' '.join(collection.get('tools', []))}".lower()
                if needle and needle not in haystack:
                    continue
                members = [self.tool_by_id(tool_id) for tool_id in collection.get("tools", [])]
                installed = sum(bool(tool and tool.get("installed")) for tool in members)
                tool = {"key": f"collection:{collection['id']}", "id": collection["id"], "name": collection["name"],
                        "kind": "collection", "group": "Collection", "description": collection.get("description", ""),
                        "command": "", "package": "", "installed": installed == len(members), "collection": collection,
                        "metadata": {}}
                self.filtered_tools.append(tool)
                item = QListWidgetItem(f"{tool['name'].upper()}\n{installed} / {len(members)} INSTALLED  ·  {tool['description']}")
                item.setData(Qt.UserRole, tool)
                self.list.addItem(item)
            self.status.setText(f"{len(self.filtered_tools)} collections · reviewed installation plans required")
            if self.list.count():
                self.list.item(0).setSelected(True)
            self.selection_changed()
            return
        ordered_tools = sorted(
            self.tools,
            key=lambda tool: (tool.get("id") not in self.tool_state["favorites"], tool.get("group", ""), tool.get("name", "").lower()),
        )
        active_filters = {key for key, button in self.filter_buttons.items() if button.isChecked()}
        for tool in ordered_tools:
            metadata = tool.get("metadata", {})
            haystack = " ".join([tool["name"], tool["package"], tool["command"], tool["group"], tool["description"],
                                 " ".join(metadata.get("capabilities", [])), " ".join(metadata.get("tasks", [])),
                                 " ".join(metadata.get("integrations", []))]).lower()
            if needle and needle not in haystack:
                continue
            tool_type = str(metadata.get("type", tool.get("kind", ""))).lower()
            is_gui = tool_type in ("gui", "desktop", "graphical") or tool.get("kind") in ("desktop", "flatpak")
            if "installed" in active_filters and not tool.get("installed"):
                continue
            if "missing" in active_filters and tool.get("installed"):
                continue
            if "gui" in active_filters and not is_gui:
                continue
            if "cli" in active_filters and is_gui:
                continue
            if "recommended" in active_filters and not metadata.get("recommended"):
                continue
            if mode == "library":
                if tool.get("id") not in self.metadata:
                    continue
                if category == "favorites" and tool.get("id") not in self.tool_state["favorites"]:
                    continue
                if category == "recent" and tool.get("id") not in self.tool_state["recent"]:
                    continue
                if category == "recommended" and not metadata.get("recommended"):
                    continue
                if category not in ("all", "favorites", "recent", "recommended") and tool["group"] != category:
                    continue
            elif category != "all" and tool["kind"] != category:
                continue
            rendered_tool = dict(tool)
            rendered_tool["_favorites"] = list(self.tool_state["favorites"])
            self.filtered_tools.append(rendered_tool)
            item = QListWidgetItem()
            item.setIcon(self.tool_icon(rendered_tool))
            item.setSizeHint(QSize(360, 82))
            item.setData(Qt.UserRole, rendered_tool)
            self.list.addItem(item)
            if selected_key and tool["key"] == selected_key:
                item.setSelected(True)
        if not self.list.selectedItems() and self.list.count():
            self.list.item(0).setSelected(True)
        installed_curated = sum(tool.get("installed") and tool.get("id") in self.metadata for tool in self.tools)
        available_curated = max(0, len(self.metadata) - installed_curated)
        recommended = sum(bool(tool.get("metadata", {}).get("recommended")) for tool in self.tools if tool.get("id") in self.metadata)
        self.tool_stats["installed"].setText(str(installed_curated))
        self.tool_stats["available"].setText(str(available_curated))
        self.tool_stats["recommended"].setText(str(recommended))
        self.tool_stats["shown"].setText(str(len(self.filtered_tools)))
        recommended_names = [tool["name"] for tool in self.tools if tool.get("metadata", {}).get("recommended") and not tool.get("installed")][:3]
        if not recommended_names:
            recommended_names = [tool["name"] for tool in self.tools if tool.get("metadata", {}).get("recommended")][:3]
        self.recommended_strip.setText("✦  RECOMMENDED FOR YOU  ·  " + ("   •   ".join(recommended_names) if recommended_names else "Your equipment locker is ready"))
        self.status.setText(
            f"● AUTO-SYNC  ·  {len(self.metadata)} curated tools  ·  {installed_curated} installed  ·  "
            f"{len(self.filtered_tools)} shown  ·  {len(self.tools)} live inventory entries"
        )
        self.selection_changed()

    def tool_icon(self, tool):
        aliases = {
            "code": "visual-studio-code", "visual-studio-code-bin": "visual-studio-code",
            "docker": "docker", "git": "git", "blender": "blender", "freecad": "freecad",
            "wireshark": "wireshark", "ollama": "ollama", "kicad": "kicad", "prusaslicer": "prusa-slicer",
        }
        command = str(tool.get("command", "")).split()[0] if tool.get("command") else ""
        candidates = [tool.get("icon_name"), aliases.get(command), aliases.get(tool.get("package")), command,
                      tool.get("package"), str(tool.get("desktop_id", "")).removesuffix(".desktop")]
        for candidate in candidates:
            if not candidate:
                continue
            if str(candidate).startswith("/") and Path(candidate).is_file():
                icon = QIcon(str(candidate))
            else:
                icon = QIcon.fromTheme(str(candidate))
            if not icon.isNull():
                return icon
        metadata_type = str(tool.get("metadata", {}).get("type", "")).lower()
        fallback = QStyle.SP_ComputerIcon if metadata_type == "gui" or tool.get("kind") in ("desktop", "flatpak") else QStyle.SP_FileDialogDetailedView
        return self.style().standardIcon(fallback)

    def item_label(self, tool):
        metadata = tool.get("metadata", {})
        state = "● INSTALLED" if tool.get("installed") else "○ AVAILABLE"
        badges = [state, metadata.get("type", tool.get("kind", "tool")).upper(), tool["group"].upper()]
        if metadata.get("recommended"):
            badges.append("COMMANDOS RECOMMENDED")
        return f"{tool['name'].upper()}\n{tool['description']}\n{'  ·  '.join(badges)}"

    def tool_by_id(self, tool_id):
        return next((tool for tool in self.tools if tool.get("id") == tool_id), None)

    def selected_tool(self):
        selected = self.list.selectedItems()
        return selected[0].data(Qt.UserRole) if selected else None

    def selection_changed(self):
        tool = self.selected_tool()
        if not tool:
            self.detail.setPlainText("Select a tool.")
            self.result.setHtml("<h3>Tool Information</h3><p>Select an item to inspect its equipment status.</p>")
            self.favorite_button.setEnabled(False)
            return
        self.detail.setHtml(self.guide_html(tool))
        self.result.setHtml(self.tool_information_html(tool))
        self.favorite_button.setEnabled(tool.get("kind") != "collection" and tool.get("id") in self.metadata)
        favorite = tool.get("id") in self.tool_state["favorites"]
        self.favorite_button.setText("★  PINNED" if favorite else "☆  PIN TOOL")
        if tool.get("installed"):
            if self.installing_tool_key == tool.get("key"):
                self.installing_tool_key = ""
            self.install_progress.hide()
        else:
            self.install_progress.setVisible(self.installing_tool_key == tool.get("key"))

    def toggle_favorite(self):
        tool = self.selected_tool()
        if not tool or tool.get("id") not in self.metadata:
            return
        tool_id = tool["id"]
        if tool_id in self.tool_state["favorites"]:
            self.tool_state["favorites"].remove(tool_id)
        else:
            self.tool_state["favorites"].append(tool_id)
        self.save_tool_state()
        self.render_tools()

    def record_recent(self, tool):
        tool_id = tool.get("id")
        if tool_id not in self.metadata:
            return
        recent = [item for item in self.tool_state["recent"] if item != tool_id]
        self.tool_state["recent"] = [tool_id, *recent][:30]
        self.save_tool_state()

    def launch_selected_tool(self):
        tool = self.selected_tool()
        if not tool:
            return
        command = tool["command"]
        if not command:
            self.result.setPlainText(f"No launch command was detected for {tool['name']}.")
            return
        try:
            arguments = parse_program_command(command)
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked unsafe launch command: {error}")
            return
        if command_exists(arguments[0]):
            audited_launch(arguments, action=f"launch tool: {tool['name']}")
        else:
            self.result.setPlainText(f"{command} is not available.")
            return
        self.result.setPlainText(f"Launched {tool['name']}.\n{command}")
        self.record_recent(tool)
        self.parent_window.add_history(f"Tool launched: {tool['name']}")

    def open_selected_terminal(self):
        tool = self.selected_tool()
        if not tool:
            return
        command = tool["command"] or tool["package"]
        try:
            arguments = parse_program_command(command)
            command = shlex.join(arguments)
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked unsafe terminal command: {error}")
            return
        shell_command = (
            f"{command}; "
            "status=$?; echo; "
            "echo \"Tool finished with exit code $status.\"; "
            "read -n 1 -s -r -p \"Press any key to close this terminal...\""
        )
        ok, terminal = launch_terminal(f"Command Centre - {tool['name']}", shell_command)
        self.result.setPlainText(f"Started {tool['name']} in {terminal}." if ok else terminal)
        self.record_recent(tool)
        self.parent_window.add_history(f"Tool terminal opened: {tool['name']}")

    def install_selected_tool(self):
        tool = self.selected_tool()
        if not tool:
            return
        if tool.get("kind") == "collection":
            self.review_collection_install(tool)
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
        if ok:
            self.installing_tool_key = tool.get("key", "")
            self.install_progress.show()
            self.result.setHtml(f"<h3>Installing {html.escape(tool['name'])}…</h3><p>Package installation is running in {html.escape(terminal)}.</p><p>The Tool Library will mark it Installed automatically when the transaction completes.</p>")
        self.parent_window.add_history(f"Tool install started: {tool['name']}")

    def review_collection_install(self, tool):
        collection = tool["collection"]
        missing = [self.tool_by_id(tool_id) for tool_id in collection.get("tools", [])]
        missing = [member for member in missing if member and not member.get("installed")]
        if not missing:
            self.result.setPlainText(f"{collection['name']} is complete; every curated tool is installed.")
            return
        commands = [self.install_command(member) for member in missing]
        commands = [command for command in commands if command]
        review = "\n".join(f"• {member['name']} ({member['package']})" for member in missing)
        command = " && ".join(commands)
        if not command:
            self.result.setPlainText(f"Missing tools:\n{review}\n\nNo supported installer is available.")
            return
        if not confirm(self, "Install Collection Tools", f"Review missing tools for {collection['name']}:\n\n{review}\n\nCombined command:\n{command}"):
            return
        ok, terminal = launch_terminal(f"Install {collection['name']}", command)
        self.result.setPlainText(f"Started reviewed collection install in {terminal}." if ok else terminal)
        if ok:
            self.parent_window.add_history(f"Collection install started: {collection['name']}")

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
        guide.setHtml(self.guide_html(tool))
        layout.addWidget(guide)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def guide_html(self, tool):
        if tool.get("kind") == "collection":
            return f"<pre>{html.escape(self.guide_text(tool))}</pre>"
        metadata = tool.get("metadata", {})
        state = "INSTALLED · READY" if tool.get("installed") else "AVAILABLE · NOT INSTALLED"
        state_color = "#35D66B" if tool.get("installed") else "#2BC4FF"
        capabilities = metadata.get("capabilities", []) or ["General package or executable capability"]
        integrations = metadata.get("integrations", []) or ["Standard CommandOS launcher integration"]
        related = [self.metadata[item]["name"] for item in metadata.get("related_tools", []) if item in self.metadata]
        command = tool.get("command") or "No launch command detected"
        install = self.install_command(tool) or "No supported installer detected"
        rows = "".join(f"<li style='margin:5px 0'><span style='color:#35D66B'>✓</span> {html.escape(str(value))}</li>" for value in capabilities)
        integration_rows = "".join(f"<li style='margin:5px 0'><span style='color:#2BC4FF'>✓</span> {html.escape(str(value))}</li>" for value in integrations)
        return f"""
        <div style='color:#DCE7EE'>
          <h2 style='color:#FFFFFF;margin-bottom:3px'>{html.escape(tool.get('name', 'Tool').upper())}</h2>
          <div style='color:{state_color};font-weight:700;margin-bottom:14px'>● {state}</div>
          <hr style='color:#1A4058'>
          <h3 style='color:#8FDFFF'>Description</h3><p>{html.escape(tool.get('description', ''))}</p>
          <hr style='color:#1A4058'>
          <h3 style='color:#8FDFFF'>Installation</h3>
          <table cellspacing='5'><tr><td style='color:#8298A8'>Status</td><td style='color:{state_color}'>{state}</td></tr>
          <tr><td style='color:#8298A8'>Package</td><td>{html.escape(str(tool.get('package', '—')))}</td></tr>
          <tr><td style='color:#8298A8'>Type</td><td>{html.escape(str(metadata.get('type', tool.get('kind', 'tool'))).upper())}</td></tr></table>
          <hr style='color:#1A4058'><h3 style='color:#8FDFFF'>Capabilities</h3><ul style='list-style:none;margin-left:0'>{rows}</ul>
          <hr style='color:#1A4058'><h3 style='color:#8FDFFF'>CommandOS Integration</h3><ul style='list-style:none;margin-left:0'>{integration_rows}</ul>
          <hr style='color:#1A4058'><h3 style='color:#8FDFFF'>Commands</h3>
          <p><b>Launch</b><br><code>{html.escape(command)}</code></p><p><b>Install / repair</b><br><code>{html.escape(install)}</code></p>
          <hr style='color:#1A4058'><h3 style='color:#8FDFFF'>Related</h3><p>{html.escape(', '.join(related) if related else 'No related tools declared')}</p>
        </div>"""

    def tool_information_html(self, tool):
        metadata = tool.get("metadata", {})
        ready = "READY" if tool.get("installed") and tool.get("command") else "INSTALLED" if tool.get("installed") else "AVAILABLE"
        ready_color = "#35D66B" if tool.get("installed") else "#2BC4FF"
        return f"""
        <h3 style='color:#FFFFFF'>TOOL INFORMATION</h3>
        <table cellspacing='5'>
          <tr><td style='color:#8298A8'>Equipment status</td><td style='color:{ready_color};font-weight:700'>{ready}</td></tr>
          <tr><td style='color:#8298A8'>Source</td><td>{html.escape(str(tool.get('kind', 'tool')).upper())}</td></tr>
          <tr><td style='color:#8298A8'>Category</td><td>{html.escape(str(tool.get('group', '—')))}</td></tr>
          <tr><td style='color:#8298A8'>Package / App ID</td><td>{html.escape(str(tool.get('package', '—')))}</td></tr>
          <tr><td style='color:#8298A8'>Recommended</td><td>{'CommandOS recommended' if metadata.get('recommended') else 'Standard inventory item'}</td></tr>
          <tr><td style='color:#8298A8'>Launch command</td><td><code>{html.escape(str(tool.get('command') or 'Not detected'))}</code></td></tr>
        </table>"""

    def guide_text(self, tool):
        if tool.get("kind") == "collection":
            collection = tool["collection"]
            members = [self.tool_by_id(tool_id) for tool_id in collection.get("tools", [])]
            lines = []
            for member in members:
                if member:
                    lines.append(f"{'✓' if member.get('installed') else '○'}  {member['name']}  ·  {'INSTALLED' if member.get('installed') else 'AVAILABLE'}")
            installed = sum(bool(member and member.get("installed")) for member in members)
            return (f"{collection['name'].upper()}\n{'=' * len(collection['name'])}\n\n{collection.get('description', '')}\n\n"
                    f"COLLECTION HEALTH\n{installed} / {len(members)} tools installed\n\nTOOLS\n" + "\n".join(lines) +
                    "\n\nINSTALLATION\nSelect Install to review every missing package and the combined command before anything is started.")
        command = tool["command"] or tool["package"]
        metadata = tool.get("metadata", {})
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
        capabilities = "\n".join(f"• {value}" for value in metadata.get("capabilities", [])) or "• General package or executable entry"
        integrations = "\n".join(f"✓ {value}" for value in metadata.get("integrations", [])) or "No CommandOS integration declared."
        related = [self.metadata[item]["name"] for item in metadata.get("related_tools", []) if item in self.metadata]
        state = "INSTALLED · HEALTHY" if tool.get("installed") else "AVAILABLE · NOT INSTALLED"
        return (
            f"{tool['name'].upper()}\n"
            f"{'=' * len(tool['name'])}\n\n"
            f"{tool['description']}\n\n"
            f"{state}\n{metadata.get('type', tool['kind']).upper()} · {tool['group'].upper()}\n"
            f"Package/App ID: {tool['package']}\n"
            f"Launch command: {command or 'No command detected'}\n"
            f"Install command: {install}\n\n"
            f"CAPABILITIES\n{capabilities}\n\n"
            f"COMMANDOS INTEGRATION\n{integrations}\n\n"
            f"RELATED TOOLS\n{', '.join(related) if related else 'None declared'}\n\n"
            f"COMMAND LIBRARY\n"
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

    def shutdown(self):
        self.inventory_executor.shutdown(wait=False, cancel_futures=True)


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


class KnowledgeReadinessGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 0
        self.setFixedSize(142, 142)

    def set_score(self, score):
        self.score = max(0, min(100, int(score)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(11, 11, -11, -11)
        painter.setPen(QPen(QColor("#17364C"), 14)); painter.drawArc(rect, 0, 360 * 16)
        color = QColor("#42E978" if self.score >= 80 else "#2BC4FF" if self.score >= 50 else "#FFBF32")
        painter.setPen(QPen(color, 14, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self.score / 100))
        painter.setPen(QColor("#FFFFFF")); painter.setFont(QFont("Inter", 25, QFont.Bold))
        painter.drawText(QRectF(0, 33, self.width(), 36), Qt.AlignCenter, f"{self.score}%")
        painter.setPen(QColor("#DCE7EE")); painter.setFont(QFont("Inter", 8, QFont.Bold))
        painter.drawText(QRectF(0, 67, self.width(), 17), Qt.AlignCenter, "KNOWLEDGE READY")
        painter.setPen(color); painter.setFont(QFont("Inter", 7, QFont.Bold))
        label = "OFFLINE READY" if self.score >= 80 else "BUILDING SEARCH INDEX" if self.score else "SETUP NEEDED"
        painter.drawText(QRectF(0, 84, self.width(), 17), Qt.AlignCenter, label)


class OfflineKnowledgePage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.locations = []
        self.zim_files = []
        self.knowledge_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="knowledge-index")
        self.scan_future = None
        self.kiwix_process = None
        self.kiwix_port = None
        self.reader_url = None
        self.reader_title = "Offline Knowledge Reader"
        self.reader_started_at = 0
        self.library_button = QPushButton("Add Knowledge Library")
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
        self.zim_list.itemDoubleClicked.connect(lambda _: self.open_selected_library_item())
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Offline Knowledge…")
        self.search_input.returnPressed.connect(self.search_knowledge)
        self.search_results = QListWidget()
        self.search_results.itemDoubleClicked.connect(lambda _: self.open_search_result())
        self.bookmark_list = QListWidget()
        self.bookmark_list.itemDoubleClicked.connect(lambda _: self.open_bookmark())
        self.home_status = QLabel("Preparing local knowledge engine…")
        self.home_status.setObjectName("controlState")
        self.home_status.setWordWrap(True)
        self.storage_status = QLabel("--")
        self.storage_status.setObjectName("muted")
        self.storage_status.setWordWrap(True)
        self.reader_location = QLabel("No document open")
        self.reader_location.setObjectName("muted")
        self.reader_location.setWordWrap(True)
        self.current_document = None
        self.reader = QWebEngineView()
        self.reader.setMinimumHeight(420)
        self.reader.setHtml("<html><body style='background:#071019;color:#9fb3c3;font-family:sans-serif;padding:40px'><h2>Offline reader ready</h2><p>Open a local knowledge item or search your libraries.</p></body></html>")
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setObjectName("textPanel")
        self.result.setMaximumHeight(90)

        layout = QVBoxLayout(self)
        title = QLabel("OFFLINE KNOWLEDGE")
        title.setObjectName("healthHeader")
        layout.addWidget(title)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input, 1)
        search_button = QPushButton("SEARCH")
        search_button.clicked.connect(self.search_knowledge)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)
        knowledge_filters = QHBoxLayout(); knowledge_filters.setSpacing(6)
        filter_title = QLabel("FILTER"); filter_title.setObjectName("knowledgeFilterLabel"); knowledge_filters.addWidget(filter_title)
        self.knowledge_format_filters = {}
        for label, formats in (("PDF", ("PDF",)), ("Markdown", ("MARKDOWN",)), ("Books", ("EPUB",)), ("Wikipedia", ("ZIM",))):
            chip = QPushButton(label); chip.setObjectName("knowledgeFilterChip"); chip.setCheckable(True)
            chip.toggled.connect(lambda _: self.search_knowledge() if len(self.search_input.text().strip()) >= 2 else None)
            knowledge_filters.addWidget(chip); self.knowledge_format_filters[label.lower()] = (chip, formats)
        for label in ("Linux", "Programming"):
            chip = QPushButton(label); chip.setObjectName("knowledgeFilterChip")
            chip.clicked.connect(lambda checked=False, topic=label: self.quick_knowledge_search(topic)); knowledge_filters.addWidget(chip)
        knowledge_filters.addStretch(); layout.addLayout(knowledge_filters)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("offlineTabs")
        self.tabs.addTab(self.home_page(), "Home")
        self.tabs.addTab(self.libraries_page(), "Libraries")
        self.tabs.addTab(self.search_page(), "Search")
        self.tabs.addTab(self.reader_page(), "Reader")
        self.tabs.addTab(self.bookmarks_page(), "Bookmarks")
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.result)

        self.initialize_knowledge_db()
        self.scan_poll = QTimer(self)
        self.scan_poll.timeout.connect(self.finish_scan)
        self.scan_poll.start(100)
        self.reading_progress_timer = QTimer(self)
        self.reading_progress_timer.timeout.connect(self.capture_reading_progress)
        self.reading_progress_timer.start(5000)
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
        frame, layout = self.panel("Knowledge Libraries")
        row = QHBoxLayout()
        row.addWidget(self.library_button)
        row.addWidget(self.fullscreen_button)
        row.addWidget(self.browser_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.library_label)
        return frame

    def home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4); layout.setSpacing(10)

        stats = QHBoxLayout(); stats.setSpacing(8)
        self.knowledge_stats = {}
        for key, icon, label, context in (("libraries", "▤", "LIBRARIES", "Configured"), ("documents", "▥", "DOCUMENTS", "Available offline"),
                                          ("bookmarks", "★", "BOOKMARKS", "Saved"), ("storage", "▰", "STORAGE", "Knowledge used"),
                                          ("indexed", "⌕", "INDEXED", "Full-text searchable")):
            card = QFrame(); card.setObjectName("knowledgeStatCard")
            box = QVBoxLayout(card); box.setContentsMargins(12, 8, 12, 8); box.setSpacing(1)
            icon_label = QLabel(icon); icon_label.setObjectName("knowledgeStatIcon")
            value = QLabel("—"); value.setObjectName("knowledgeStatValue")
            caption = QLabel(label); caption.setObjectName("knowledgeStatLabel")
            subtitle = QLabel(context); subtitle.setObjectName("knowledgeStatContext")
            row = QHBoxLayout(); row.addWidget(icon_label); row.addStretch(); row.addWidget(value)
            box.addLayout(row); box.addWidget(caption); box.addWidget(subtitle); stats.addWidget(card, 1); self.knowledge_stats[key] = value
        top = QGridLayout(); top.setSpacing(10)
        readiness, readiness_layout = self.panel("◈   KNOWLEDGE READINESS")
        ready_row = QHBoxLayout(); ready_row.setSpacing(14)
        self.knowledge_gauge = KnowledgeReadinessGauge()
        ready_row.addWidget(self.knowledge_gauge, 0, Qt.AlignCenter); ready_row.addWidget(self.home_status, 1)
        readiness_layout.addLayout(ready_row)
        diagnostics = QPushButton("VIEW DIAGNOSTICS"); diagnostics.setObjectName("knowledgeSecondaryButton"); diagnostics.clicked.connect(lambda: self.result.setText(self.home_status.text()))
        readiness_layout.addWidget(diagnostics)
        top.addWidget(readiness, 0, 1)

        assistant, assistant_layout = self.panel("✦   COMMAND AI")
        assistant_note = QLabel("Ask your offline library. Answers are grounded in locally indexed documents.")
        assistant_note.setObjectName("knowledgeMuted"); assistant_note.setWordWrap(True); assistant_layout.addWidget(assistant_note)
        self.command_ai_input = QLineEdit(); self.command_ai_input.setPlaceholderText("How do I rebuild GRUB?")
        self.command_ai_input.returnPressed.connect(self.ask_offline_library); assistant_layout.addWidget(self.command_ai_input)
        ask = QPushButton("ASK OFFLINE LIBRARY"); ask.setObjectName("knowledgePrimaryButton"); ask.clicked.connect(self.ask_offline_library); assistant_layout.addWidget(ask)
        suggestion_title = QLabel("SUGGESTED QUESTIONS"); suggestion_title.setObjectName("knowledgeMiniTitle"); assistant_layout.addWidget(suggestion_title)
        suggestion_grid = QGridLayout(); suggestion_grid.setSpacing(5)
        for index, question in enumerate(("How do I rebuild GRUB?", "Explain Docker networking", "How do I recover Btrfs?",
                                          "Wireshark capture filters", "Python virtual environments")):
            suggestion = QPushButton(question); suggestion.setObjectName("knowledgeSuggestion")
            suggestion.clicked.connect(lambda checked=False, value=question: self.ask_suggested_question(value))
            suggestion_grid.addWidget(suggestion, index // 2, index % 2)
        assistant_layout.addLayout(suggestion_grid)
        self.recent_questions = QLabel("RECENT QUESTIONS\nNothing asked yet.")
        self.recent_questions.setObjectName("knowledgeRecentQuestions"); self.recent_questions.setWordWrap(True); assistant_layout.addWidget(self.recent_questions)
        top.addWidget(assistant, 0, 0); top.setColumnStretch(0, 1); top.setColumnStretch(1, 1)
        layout.addLayout(top)

        middle = QGridLayout(); middle.setSpacing(10)
        resume, resume_layout = self.panel("▶   CONTINUE READING")
        resume_row = QHBoxLayout(); resume_row.setSpacing(14)
        self.continue_cover = QLabel("📘"); self.continue_cover.setObjectName("knowledgeCover"); self.continue_cover.setAlignment(Qt.AlignCenter); self.continue_cover.setFixedSize(88, 112)
        resume_copy = QVBoxLayout(); resume_copy.setSpacing(4)
        self.continue_reading = QLabel("No reading history yet. Open a document to begin.")
        self.continue_reading.setObjectName("knowledgeFeatureText"); self.continue_reading.setWordWrap(True); resume_copy.addWidget(self.continue_reading)
        progress_title = QLabel("READING PROGRESS"); progress_title.setObjectName("knowledgeMiniTitle"); resume_copy.addWidget(progress_title)
        self.reading_progress = QProgressBar(); self.reading_progress.setObjectName("readingProgress"); self.reading_progress.setRange(0, 100); self.reading_progress.setValue(0); self.reading_progress.setFormat("%p%")
        resume_copy.addWidget(self.reading_progress)
        self.reading_remaining = QLabel("Progress tracking begins when you open a document."); self.reading_remaining.setObjectName("knowledgeMuted"); resume_copy.addWidget(self.reading_remaining)
        resume_row.addWidget(self.continue_cover); resume_row.addLayout(resume_copy, 1); resume_layout.addLayout(resume_row)
        resume_button = QPushButton("RESUME"); resume_button.setObjectName("knowledgePrimaryButton"); resume_button.clicked.connect(self.resume_reading); resume_layout.addWidget(resume_button)
        middle.addWidget(resume, 0, 0)
        recent, recent_layout = self.panel("◷   RECENTLY VIEWED")
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("knowledgeShelf")
        self.recent_list.setMaximumHeight(155)
        self.recent_list.itemDoubleClicked.connect(lambda _: self.open_recent())
        recent_layout.addWidget(self.recent_list)
        middle.addWidget(recent, 0, 1); middle.setColumnStretch(0, 1); middle.setColumnStretch(1, 1)
        layout.insertLayout(0, middle)
        layout.addLayout(stats)

        lower = QGridLayout(); lower.setSpacing(10)
        storage, storage_layout = self.panel("▰   KNOWLEDGE STORAGE")
        self.storage_bars = {}
        for key, label, role in (("knowledge", "KNOWLEDGE", "knowledge"), ("index", "SEARCH INDEX", "index"), ("free", "FREE SPACE", "free")):
            row = QHBoxLayout(); name = QLabel(label); name.setObjectName("knowledgeStorageLabel"); value = QLabel("—"); value.setObjectName("knowledgeStorageValue")
            row.addWidget(name); row.addStretch(); row.addWidget(value); storage_layout.addLayout(row)
            bar = QProgressBar(); bar.setObjectName("knowledgeStorageBar"); bar.setProperty("role", role); bar.setRange(0, 100); bar.setTextVisible(False); storage_layout.addWidget(bar)
            self.storage_bars[key] = (bar, value)
        self.storage_bar = self.storage_bars["knowledge"][0]
        storage_layout.addWidget(self.storage_status)
        lower.addWidget(storage, 0, 0)
        categories, categories_layout = self.panel("▦   LIBRARY CATEGORIES")
        self.knowledge_categories = QLabel("No indexed categories yet."); self.knowledge_categories.setObjectName("knowledgeCategories"); self.knowledge_categories.setWordWrap(True)
        categories_layout.addWidget(self.knowledge_categories)
        sources = QLabel("SOURCES  ·  Wikipedia  ·  PDFs  ·  Markdown  ·  Books  ·  Man Pages  ·  GitHub Docs")
        sources.setObjectName("knowledgeSources"); sources.setWordWrap(True); categories_layout.addWidget(sources)
        topics = QLabel("MOST USED TOPICS  ·  Linux  ·  Docker  ·  Networking  ·  Python  ·  Recovery")
        topics.setObjectName("knowledgeSources"); topics.setWordWrap(True); categories_layout.addWidget(topics)
        lower.addWidget(categories, 0, 1)
        lower.setColumnStretch(0, 1); lower.setColumnStretch(1, 1); layout.addLayout(lower)

        activity = QGridLayout(); activity.setSpacing(10)
        added, added_layout = self.panel("＋   RECENTLY ADDED")
        self.recently_added = QLabel("Monitoring knowledge libraries…"); self.recently_added.setObjectName("knowledgeFeatureText"); self.recently_added.setWordWrap(True); added_layout.addWidget(self.recently_added)
        activity.addWidget(added, 0, 0)
        quick, quick_layout = self.panel("⚡   QUICK ACTIONS")
        actions = QHBoxLayout()
        for icon, label, handler in (("＋", "ADD LIBRARY", self.select_library_location), ("▥", "IMPORT PDFS", self.select_library_location),
                                     ("◎", "WIKIPEDIA", self.select_library_location), ("⌕", "SEARCH", lambda: self.tabs.setCurrentIndex(2))):
            button = QToolButton(); button.setText(f"{icon}\n{label}"); button.setObjectName("knowledgeActionButton")
            button.setToolButtonStyle(Qt.ToolButtonTextOnly); button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); button.setFixedHeight(72)
            button.clicked.connect(handler); actions.addWidget(button)
        quick_layout.addLayout(actions); activity.addWidget(quick, 0, 1)
        activity.setColumnStretch(0, 1); activity.setColumnStretch(1, 1); layout.addLayout(activity)
        return page

    def ask_offline_library(self):
        query = self.command_ai_input.text().strip()
        if not query:
            self.result.setPlainText("Ask a question about your offline library.")
            return
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("INSERT INTO knowledge_questions(question,asked_at) VALUES(?,?)", (query, time.strftime("%Y-%m-%d %H:%M:%S")))
            db.execute("DELETE FROM knowledge_questions WHERE id NOT IN (SELECT id FROM knowledge_questions ORDER BY id DESC LIMIT 30)")
            db.commit()
        self.search_input.setText(query)
        self.search_knowledge()
        self.refresh_knowledge_summary()

    def ask_suggested_question(self, question):
        self.command_ai_input.setText(question)
        self.ask_offline_library()

    def quick_knowledge_search(self, topic):
        self.search_input.setText(topic)
        self.search_knowledge()

    def resume_reading(self):
        if self.recent_list.count():
            self.recent_list.item(0).setSelected(True)
            self.open_recent()
        else:
            self.tabs.setCurrentIndex(1)

    def capture_reading_progress(self):
        if not self.current_document:
            return
        path = self.current_document.get("path", "")
        script = """(() => { const d=document.documentElement; const max=Math.max(0,d.scrollHeight-window.innerHeight); return max ? Math.round(window.scrollY/max*100) : 0; })()"""
        self.reader.page().runJavaScript(script, lambda value, document_path=path: self.save_reading_progress(document_path, value))

    def save_reading_progress(self, document_path, value):
        try:
            progress = max(0, min(100, int(value or 0)))
        except (TypeError, ValueError):
            return
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("INSERT INTO reading_progress(document_path,progress,updated_at) VALUES(?,?,?) "
                       "ON CONFLICT(document_path) DO UPDATE SET progress=excluded.progress,updated_at=excluded.updated_at",
                       (document_path, progress, time.strftime("%Y-%m-%d %H:%M:%S")))
            db.commit()
        if self.current_document and self.current_document.get("path") == document_path:
            self.reading_progress.setValue(progress)
            self.reading_remaining.setText(f"Estimated remaining: {max(1, round((100 - progress) * .22))} minutes" if progress else "Progress tracking is active while you read.")

    def libraries_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.library_panel())
        layout.addWidget(self.zim_list)
        return page

    def search_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("Searches local titles, paths, and indexed text. ZIM content remains searchable inside its Kiwix reader until article-level indexing is available.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(self.search_results)
        return page

    def reader_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        for label, handler in [("BACK", self.reader.back), ("FORWARD", self.reader.forward), ("HOME", self.reader_home),
                               ("FIND", self.find_in_page), ("ZOOM -", lambda: self.adjust_zoom(-0.1)),
                               ("ZOOM +", lambda: self.adjust_zoom(0.1)), ("BOOKMARK", self.add_bookmark),
                               ("EXTERNAL", self.open_reader_browser), ("FULLSCREEN", self.open_fullscreen_reader)]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addWidget(self.reader_location)
        layout.addWidget(self.reader, 1)
        return page

    def bookmarks_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.bookmark_list)
        remove = QPushButton("REMOVE SELECTED BOOKMARK")
        remove.clicked.connect(self.remove_bookmark)
        layout.addWidget(remove)
        return page

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
            self.library_label.setText("\n".join(str(path) for path in self.locations))
        else:
            self.library_label.setText("No Knowledge Library configured.")

    def select_library_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Knowledge Library", str(Path.home()))
        if folder:
            path = Path(folder).expanduser()
            if path not in self.locations:
                self.locations.append(path)
            self.save_config()
            self.render_library_location()
            self.scan_locations()

    def scan_locations(self):
        if self.scan_future is None:
            self.home_status.setText("INDEXING  ·  Knowledge remains available while background discovery runs.")
            self.scan_future = self.knowledge_executor.submit(self.index_locations, list(self.locations))

    def initialize_knowledge_db(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS libraries (
                    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    available INTEGER NOT NULL DEFAULT 0, last_scan TEXT, total_size INTEGER NOT NULL DEFAULT 0,
                    document_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY, library_path TEXT NOT NULL, path TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL, format TEXT NOT NULL, size INTEGER NOT NULL, mtime REAL NOT NULL,
                    content TEXT NOT NULL DEFAULT '', available INTEGER NOT NULL DEFAULT 1, indexed_at TEXT
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS document_search USING fts5(title, path, content, content='documents', content_rowid='id');
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY, document_path TEXT NOT NULL, title TEXT NOT NULL, locator TEXT,
                    note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, UNIQUE(document_path, locator)
                );
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, document_path TEXT NOT NULL, title TEXT NOT NULL,
                    locator TEXT, viewed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reading_progress (
                    document_path TEXT PRIMARY KEY, progress INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_questions (
                    id INTEGER PRIMARY KEY, question TEXT NOT NULL, asked_at TEXT NOT NULL
                );
            """)

    def index_locations(self, locations):
        supported = {".zim": "ZIM", ".pdf": "PDF", ".epub": "EPUB", ".html": "HTML", ".htm": "HTML",
                     ".md": "MARKDOWN", ".markdown": "MARKDOWN", ".txt": "TEXT"}
        indexed = 0
        failures = []
        zim_files = []
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("UPDATE libraries SET available=0")
            db.execute("UPDATE documents SET available=0")
            for location in locations:
                root = Path(location).expanduser()
                if not root.exists():
                    continue
                candidates = [root] if root.is_file() else root.rglob("*")
                library_size = 0
                library_count = 0
                for candidate in candidates:
                    try:
                        if not candidate.is_file() or candidate.suffix.lower() not in supported:
                            continue
                        resolved = candidate.resolve()
                        stat = resolved.stat()
                        fmt = supported[resolved.suffix.lower()]
                        content = self.extract_index_text(resolved, fmt, stat.st_size)
                        title = resolved.stem.replace("_", " ").replace("-", " ").strip() or resolved.name
                        existing = db.execute("SELECT id,mtime,size FROM documents WHERE path=?", (str(resolved),)).fetchone()
                        if existing and existing[1] == stat.st_mtime and existing[2] == stat.st_size:
                            db.execute("UPDATE documents SET available=1 WHERE id=?", (existing[0],))
                        else:
                            if existing:
                                db.execute("DELETE FROM document_search WHERE rowid=?", (existing[0],))
                                db.execute("UPDATE documents SET library_path=?,title=?,format=?,size=?,mtime=?,content=?,available=1,indexed_at=? WHERE id=?",
                                           (str(root), title, fmt, stat.st_size, stat.st_mtime, content, time.strftime("%Y-%m-%d %H:%M:%S"), existing[0]))
                                doc_id = existing[0]
                            else:
                                cursor = db.execute("INSERT INTO documents(library_path,path,title,format,size,mtime,content,available,indexed_at) VALUES(?,?,?,?,?,?,?,1,?)",
                                                    (str(root), str(resolved), title, fmt, stat.st_size, stat.st_mtime, content, time.strftime("%Y-%m-%d %H:%M:%S")))
                                doc_id = cursor.lastrowid
                            db.execute("INSERT INTO document_search(rowid,title,path,content) VALUES(?,?,?,?)", (doc_id, title, str(resolved), content))
                        if fmt == "ZIM":
                            zim_files.append(str(resolved))
                        library_size += stat.st_size
                        library_count += 1
                        indexed += 1
                    except Exception as error:
                        failures.append(f"{candidate}: {error}")
                db.execute("INSERT INTO libraries(path,name,available,last_scan,total_size,document_count) VALUES(?,?,1,?,?,?) "
                           "ON CONFLICT(path) DO UPDATE SET name=excluded.name,available=1,last_scan=excluded.last_scan,total_size=excluded.total_size,document_count=excluded.document_count",
                           (str(root), root.name or str(root), time.strftime("%Y-%m-%d %H:%M:%S"), library_size, library_count))
            db.commit()
            stats = db.execute("SELECT COUNT(*),COALESCE(SUM(size),0),SUM(CASE WHEN available=1 THEN 1 ELSE 0 END) FROM documents").fetchone()
        return {"indexed": indexed, "failures": failures[:20], "zim_files": zim_files, "stats": stats}

    def extract_index_text(self, path, fmt, size):
        if fmt == "PDF" and size <= 50 * 1024 * 1024 and command_exists("pdftotext"):
            output, _, code = run_text(["pdftotext", "-f", "1", "-l", "200", str(path), "-"], 25)
            return output[:500000] if code == 0 else ""
        if fmt not in ("TEXT", "MARKDOWN", "HTML") or size > 2 * 1024 * 1024:
            return ""
        text = path.read_text(encoding="utf-8", errors="ignore")
        if fmt == "HTML":
            text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
        return text[:500000]

    def finish_scan(self):
        if self.scan_future is None or not self.scan_future.done():
            return
        future = self.scan_future
        self.scan_future = None
        try:
            scan = future.result()
        except Exception as error:
            self.home_status.setText(f"INDEX FAILED  ·  {error}")
            return
        self.zim_files = sorted((Path(path) for path in scan["zim_files"]), key=lambda item: item.name.lower())
        self.render_zim_files()
        self.refresh_knowledge_summary()
        self.result.setPlainText(f"Indexed {scan['indexed']} supported document(s)." + (f"\n\n{len(scan['failures'])} indexing warning(s):\n" + "\n".join(scan["failures"]) if scan["failures"] else ""))

    def render_zim_files(self):
        self.zim_list.clear()
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            rows = db.execute("SELECT path,title,format,size,indexed_at FROM documents WHERE available=1 ORDER BY title COLLATE NOCASE").fetchall()
        for path, title, fmt, size, indexed_at in rows:
            cover = {"PDF": "📕", "EPUB": "📗", "ZIM": "📘", "MARKDOWN": "📓", "HTML": "📙", "TEXT": "📄"}.get(fmt, "📚")
            item = QListWidgetItem(f"{cover}  {title.upper()}\n     {fmt}  ·  {self.format_size(size)}  ·  INDEXED  ·  AVAILABLE OFFLINE\n     {path}")
            item.setSizeHint(QSize(500, 68))
            item.setData(Qt.UserRole, {"path": path, "title": title, "format": fmt, "size": size, "indexed_at": indexed_at})
            self.zim_list.addItem(item)

    def format_size(self, size):
        value = float(size or 0)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if value < 1024 or unit == "TiB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TiB"

    def selected_zim(self):
        selected = self.zim_list.selectedItems()
        if not selected:
            return None
        data = selected[0].data(Qt.UserRole)
        return Path(data["path"]) if isinstance(data, dict) and data.get("format") == "ZIM" else None

    def open_selected_library_item(self):
        selected = self.zim_list.selectedItems()
        if not selected:
            return
        document = selected[0].data(Qt.UserRole)
        self.open_document(document)

    def refresh_knowledge_summary(self):
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            documents, total_size, available = db.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN available=1 THEN size ELSE 0 END),0),SUM(CASE WHEN available=1 THEN 1 ELSE 0 END) FROM documents").fetchone()
            libraries = db.execute("SELECT COUNT(*) FROM libraries WHERE available=1").fetchone()[0]
            indexed_text = db.execute("SELECT COUNT(*) FROM documents WHERE available=1 AND length(content)>0").fetchone()[0]
            recent = db.execute("SELECT document_path,title,locator,viewed_at FROM history ORDER BY id DESC LIMIT 12").fetchall()
            bookmarks = db.execute("SELECT id,document_path,title,locator,created_at FROM bookmarks ORDER BY id DESC").fetchall()
            formats = db.execute("SELECT format,COUNT(*) FROM documents WHERE available=1 GROUP BY format ORDER BY COUNT(*) DESC").fetchall()
            recently_added = db.execute("SELECT title,format,indexed_at FROM documents WHERE available=1 ORDER BY indexed_at DESC LIMIT 4").fetchall()
            questions = db.execute("SELECT question,asked_at FROM knowledge_questions ORDER BY id DESC LIMIT 3").fetchall()
            recent_progress = db.execute("SELECT progress FROM reading_progress WHERE document_path=?", (recent[0][0],)).fetchone() if recent else None
        disk = shutil.disk_usage(CONFIG_DIR)
        free = disk.free
        available = available or 0
        indexed_percent = round(indexed_text / max(1, available) * 100) if available else 0
        reader_ready = command_exists("kiwix-serve") or available > 0
        ai_ready = command_exists("ollama")
        score = min(100, (20 if libraries else 0) + (20 if available else 0) + round(indexed_percent * .3) + (15 if reader_ready else 0) + (15 if ai_ready else 0))
        self.knowledge_gauge.set_score(score)
        checklist = [
            ("Libraries", bool(libraries), f"{libraries} ready" if libraries else "Not configured"),
            ("Search Index", bool(indexed_text), f"{indexed_percent}% indexed" if available else "Waiting for documents"),
            ("AI Integration", ai_ready, "Enabled" if ai_ready else "Ollama offline"),
            ("Reader", reader_ready, "Ready" if reader_ready else "Backend needed"),
            ("Bookmarks", True, f"{len(bookmarks)} synced"),
        ]
        self.home_status.setText("<table cellspacing='4'>" + "".join(
            f"<tr><td style='color:{'#42E978' if ready else '#FFBF32'}'>{'✓' if ready else '⚠'}</td>"
            f"<td style='color:#DCE7EE;padding-right:18px'>{label}</td><td style='color:#9DB0BD'>{detail}</td></tr>"
            for label, ready, detail in checklist
        ) + "</table>")
        self.knowledge_stats["libraries"].setText(str(libraries))
        self.knowledge_stats["documents"].setText(f"{available:,}")
        self.knowledge_stats["bookmarks"].setText(str(len(bookmarks)))
        self.knowledge_stats["storage"].setText(self.format_size(total_size))
        self.knowledge_stats["indexed"].setText(f"{indexed_percent}%")
        index_size = OFFLINE_DB_FILE.stat().st_size if OFFLINE_DB_FILE.exists() else 0
        knowledge_percent = round(total_size / max(1, disk.total) * 100)
        index_percent = round(index_size / max(1, disk.total) * 100)
        free_percent = round(free / max(1, disk.total) * 100)
        for key, amount, percentage in (("knowledge", total_size, knowledge_percent), ("index", index_size, index_percent), ("free", free, free_percent)):
            bar, value = self.storage_bars[key]; bar.setValue(max(1, percentage) if amount else 0); value.setText(self.format_size(amount))
        self.storage_status.setText(f"KNOWLEDGE DATA  {self.format_size(total_size)}   ·   SEARCH INDEX  {self.format_size(index_size)}\nFREE SPACE  {self.format_size(free)}   ·   Libraries remain available without a network connection.")
        category_colors = ["#2BC4FF", "#A65DFF", "#42E978", "#FFBF32", "#F07C55"]
        self.knowledge_categories.setText("<br><br>".join(
            f"<span style='color:{category_colors[index % len(category_colors)]};font-size:18px'>▣</span>  <b style='color:#FFFFFF'>{html.escape(fmt.title())}</b>"
            f"<br><span style='color:#8298A8;margin-left:20px'>{count} document{'s' if count != 1 else ''} · Indexed offline</span>"
            for index, (fmt, count) in enumerate(formats)
        ) or "<b style='color:#FFFFFF'>📚 Wikipedia</b>  <span style='color:#8298A8'>0 articles</span><br><br>"
             "<b style='color:#FFFFFF'>📘 Manuals</b>  <span style='color:#8298A8'>0 documents</span><br><br>"
             "<b style='color:#FFFFFF'>📄 PDFs</b>  <span style='color:#8298A8'>0 documents</span><br><br>"
             "<b style='color:#FFFFFF'>▤ Markdown</b>  <span style='color:#8298A8'>0 notes</span>")
        self.recently_added.setText("<br>".join(
            f"<span style='color:#2BC4FF'>▥</span> <b>{html.escape(title)}</b>  <span style='color:#8298A8'>{fmt} · {indexed_at or 'Indexed'}</span>"
            for title, fmt, indexed_at in recently_added
        ) or "<b style='color:#FFFFFF'>Nothing here yet.</b><br><span style='color:#8298A8'>Import a PDF, Wikipedia ZIM, or documentation library to get started.</span>")
        self.recent_questions.setText("<b style='color:#8FDFFF'>RECENT QUESTIONS</b><br>" + ("<br>".join(
            f"• {html.escape(question)} <span style='color:#6F899B'>· {asked_at[11:16]}</span>" for question, asked_at in questions
        ) if questions else "<span style='color:#8298A8'>Nothing asked yet.</span>"))
        self.recent_list.clear()
        for index, (path, title, locator, viewed_at) in enumerate(recent[:4]):
            item = QListWidgetItem(f"{'📘' if index % 3 == 0 else '📗' if index % 3 == 1 else '📙'}  {title}\n     {viewed_at}  ·  Available offline")
            item.setSizeHint(QSize(300, 54))
            item.setData(Qt.UserRole, {"path": path, "title": title, "locator": locator})
            self.recent_list.addItem(item)
        if recent:
            path, title, locator, viewed_at = recent[0]
            fmt = Path(path).suffix.lstrip(".").upper() or "DOCUMENT"
            library_name = Path(path).parent.name or "Offline Library"
            progress = int(recent_progress[0]) if recent_progress else 0
            self.continue_cover.setText({"ZIM": "🌍", "PDF": "📕", "EPUB": "📗", "MD": "📓"}.get(fmt, "📘"))
            self.continue_reading.setText(f"<b style='color:#FFFFFF;font-size:16px'>{html.escape(title)}</b><br>"
                                          f"<span style='color:#2BC4FF'>{html.escape(library_name)} · {fmt}</span><br>"
                                          f"<span style='color:#8298A8'>Last opened: {viewed_at[:10]}</span>")
            self.reading_progress.setValue(progress)
            self.reading_remaining.setText(f"Estimated remaining: {max(1, round((100 - progress) * .22))} minutes" if progress else "Progress tracking is active while you read.")
        else:
            self.continue_reading.setText("No reading history yet.<br><span style='color:#8298A8'>Open a document to begin building your offline workspace.</span>")
            self.continue_cover.setText("📚"); self.reading_progress.setValue(0); self.reading_remaining.setText("Import a library to start reading offline.")
        self.bookmark_list.clear()
        for bookmark_id, path, title, locator, created_at in bookmarks:
            item = QListWidgetItem(f"★  {title}\n{created_at}  ·  {path}")
            item.setData(Qt.UserRole, {"id": bookmark_id, "path": path, "title": title, "locator": locator})
            self.bookmark_list.addItem(item)

    def search_knowledge(self):
        query = self.search_input.text().strip()
        if len(query) < 2:
            self.result.setPlainText("Enter at least two characters to search offline knowledge.")
            return
        tokens = [token for token in re.findall(r"[\w-]+", query) if token]
        fts_query = " AND ".join(f'"{token}"' for token in tokens)
        selected_formats = [fmt for button, formats in self.knowledge_format_filters.values() if button.isChecked() for fmt in formats]
        format_clause = f" AND d.format IN ({','.join('?' for _ in selected_formats)})" if selected_formats else ""
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            try:
                rows = db.execute("SELECT d.path,d.title,d.format,d.size,snippet(document_search,2,'[',']',' … ',18) "
                                  "FROM document_search JOIN documents d ON d.id=document_search.rowid "
                                  f"WHERE document_search MATCH ? AND d.available=1{format_clause} ORDER BY rank LIMIT 100", (fts_query, *selected_formats)).fetchall()
            except sqlite3.Error:
                pattern = f"%{query}%"
                fallback_format = f" AND format IN ({','.join('?' for _ in selected_formats)})" if selected_formats else ""
                rows = db.execute(f"SELECT path,title,format,size,substr(content,1,240) FROM documents WHERE available=1 AND (title LIKE ? OR path LIKE ? OR content LIKE ?){fallback_format} LIMIT 100",
                                  (pattern, pattern, pattern, *selected_formats)).fetchall()
        self.search_results.clear()
        for path, title, fmt, size, snippet in rows:
            item = QListWidgetItem(f"{title.upper()}  ·  {fmt}  ·  {self.format_size(size)}\n{(snippet or 'Metadata match').replace(chr(10), ' ')}\n{path}")
            item.setData(Qt.UserRole, {"path": path, "title": title, "format": fmt, "size": size})
            self.search_results.addItem(item)
        self.tabs.setCurrentWidget(self.search_results.parentWidget())
        self.result.setPlainText(f"Found {len(rows)} offline result(s) for: {query}")
        if rows:
            self.search_results.item(0).setSelected(True)

    def open_search_result(self):
        selected = self.search_results.selectedItems()
        if selected:
            self.open_document(selected[0].data(Qt.UserRole))

    def open_selected_zim(self):
        zim = self.selected_zim()
        if not zim:
            self.result.setPlainText("Select a ZIM file first.")
            return
        self.start_zim_reader(zim)

    def open_document(self, document):
        if not document:
            return
        path = Path(document.get("path", ""))
        if not path.exists():
            self.result.setPlainText(f"Knowledge source is currently unavailable:\n{path}")
            return
        fmt = document.get("format") or path.suffix.lstrip(".").upper()
        self.current_document = {"path": str(path), "title": document.get("title", path.stem), "format": fmt}
        self.reader_title = self.current_document["title"]
        self.reader_location.setText(f"{self.reader_title}  ·  {fmt}  ·  {path}")
        if fmt == "ZIM":
            self.start_zim_reader(path)
        elif fmt in ("TEXT", "MARKDOWN"):
            self.record_view(self.current_document)
            text = path.read_text(encoding="utf-8", errors="ignore")
            body = html.escape(text)
            self.reader.setHtml(f"<html><body style='background:#071019;color:#dcebf5;font-family:monospace;white-space:pre-wrap;padding:28px'>{body}</body></html>", QUrl.fromLocalFile(str(path.parent) + "/"))
            self.reader_url = QUrl.fromLocalFile(str(path))
        elif fmt in ("HTML", "PDF"):
            self.record_view(self.current_document)
            self.reader_url = QUrl.fromLocalFile(str(path))
            self.reader.load(self.reader_url)
        else:
            self.record_view(self.current_document)
            self.reader.setHtml("<html><body style='background:#071019;color:#dcebf5;padding:28px'><h2>External reader required</h2><p>This format is indexed by metadata and can be opened externally.</p></body></html>")
            self.reader_url = QUrl.fromLocalFile(str(path))
        self.tabs.setCurrentIndex(3)
        self.fullscreen_button.setEnabled(True)
        self.browser_button.setEnabled(True)

    def start_zim_reader(self, zim):
        self.current_document = {"path": str(zim), "title": zim.stem, "format": "ZIM"}
        self.reader_location.setText(f"{zim.stem}  ·  ZIM  ·  {zim}")
        self.record_view(self.current_document)

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

    def record_view(self, document):
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("INSERT INTO history(document_path,title,locator,viewed_at) VALUES(?,?,?,?)",
                       (document["path"], document["title"], self.reader.url().toString(), time.strftime("%Y-%m-%d %H:%M:%S")))
            db.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 200)")
            db.commit()
        self.refresh_knowledge_summary()

    def reader_home(self):
        if self.reader_url:
            self.reader.load(self.reader_url)

    def find_in_page(self):
        text, ok = QInputDialog.getText(self, "Find in Page", "Text:")
        if ok and text:
            self.reader.findText(text)

    def adjust_zoom(self, change):
        self.reader.setZoomFactor(max(0.4, min(3.0, self.reader.zoomFactor() + change)))

    def add_bookmark(self):
        if not self.current_document:
            self.result.setPlainText("Open a knowledge item before bookmarking it.")
            return
        locator = self.reader.url().toString() or self.current_document["path"]
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("INSERT OR REPLACE INTO bookmarks(document_path,title,locator,created_at) VALUES(?,?,?,?)",
                       (self.current_document["path"], self.current_document["title"], locator, time.strftime("%Y-%m-%d %H:%M:%S")))
            db.commit()
        self.refresh_knowledge_summary()
        self.result.setPlainText(f"Bookmarked: {self.current_document['title']}")

    def remove_bookmark(self):
        selected = self.bookmark_list.selectedItems()
        if not selected:
            return
        bookmark = selected[0].data(Qt.UserRole)
        with sqlite3.connect(OFFLINE_DB_FILE) as db:
            db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark["id"],))
            db.commit()
        self.refresh_knowledge_summary()

    def open_bookmark(self):
        selected = self.bookmark_list.selectedItems()
        if selected:
            data = selected[0].data(Qt.UserRole)
            self.open_document({"path": data["path"], "title": data["title"]})
            if data.get("locator", "").startswith("http"):
                self.reader.load(QUrl(data["locator"]))

    def open_recent(self):
        selected = self.recent_list.selectedItems()
        if selected:
            data = selected[0].data(Qt.UserRole)
            self.open_document({"path": data["path"], "title": data["title"]})

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
        dialog = ReaderFullscreenDialog(self.reader_url, self.reader_title, self)
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

    def shutdown(self):
        self.stop_kiwix_server()
        self.knowledge_executor.shutdown(wait=False, cancel_futures=True)


class CommandCodePage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.workspace = Path.home()
        self.open_files = {}
        self.codex_process = None
        self.external_agent_process = None
        self.fcc_server_process = None
        self.codex_last_message_path = None
        self.codex_log_buffer = ""
        self.codex_event_buffer = ""
        self.codex_answer_seen = False
        self.codex_current_answer = ""
        self.attached_files = []
        self.agent_config = self.load_agent_config()
        self.agent_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-provider")
        self.agent_future = None
        self.codex_usage = {"used": 0, "limit": 0, "last_run": 0}
        self.load_codex_usage()
        self.chat_session_path = None
        self.start_chat_session()
        self.agent_task = None
        self.agent_task_path = None
        self.agent_paused = False
        self.agent_phase = "idle"
        self.pending_execution_prompt = ""
        self.pending_execution_title = ""
        self.pending_execution_images = []

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
            ("Plan", "plan"),
            ("Edit", "edit"),
            ("Review", "review"),
            ("Debug", "debug"),
        ]:
            self.codex_mode.addItem(label, value)
        self.agent_provider = QComboBox()
        for label, value in [("Codex", "codex"), ("Claude", "claude"), ("FCC Claude", "fcc"), ("DeepSeek", "deepseek"), ("Ollama", "ollama"), ("Custom", "custom")]:
            self.agent_provider.addItem(label, value)
        configured_provider = self.agent_config.get("default_provider", "codex")
        self.agent_provider.setCurrentIndex(max(0, self.agent_provider.findData(configured_provider)))
        self.agent_provider.currentIndexChanged.connect(self.agent_provider_changed)
        self.permission_preset = QComboBox()
        self.permission_preset.addItem("Observe · read/search only", "observe")
        self.permission_preset.addItem("Safe · read/propose", "safe")
        self.permission_preset.addItem("Develop · edit + build/test", "develop")
        self.permission_preset.addItem("Elevated · confirmation required", "elevated")
        self.permission_preset.addItem("Autonomous · approved plan", "autonomous")
        self.permission_preset.setCurrentIndex(0)
        self.context_scope = QComboBox()
        self.context_scope.addItem("Context: current file", "file")
        self.context_scope.addItem("Context: file + Git diff", "git")
        self.context_scope.addItem("Context: file + Git + output", "full")
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
        self.agent_poll = QTimer(self)
        self.agent_poll.timeout.connect(self.finish_api_agent)
        self.agent_poll.start(100)

        layout = QVBoxLayout(self)
        self.command_bar = QLineEdit()
        self.command_bar.setPlaceholderText("Search files, commands and actions…")
        self.command_bar.returnPressed.connect(self.run_command_bar)
        command_row = QHBoxLayout(); command_row.addLayout(self.toolbar()); command_row.addWidget(self.command_bar, 1)
        layout.addLayout(command_row)

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
        self.append_chat("system", "Command Terminal Agent Hub ready. Choose a provider, mode, and permission preset.")
        self.load_latest_agent_task()

    def toolbar(self):
        row = QHBoxLayout()
        for label, handler in [
            ("Open Folder", self.choose_folder),
            ("Open File", self.choose_file),
            ("Save", self.save_current_file),
            ("Save All", self.save_all_files),
            ("New File", self.new_file),
            ("Preview HTML", self.preview_html),
            ("Terminal", self.open_terminal),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch()
        agents = QPushButton("Manage Agents")
        agents.clicked.connect(self.manage_agents)
        row.addWidget(agents)
        git_status = QPushButton("Git Status")
        git_status.clicked.connect(self.show_git_status)
        row.addWidget(git_status)
        checkpoint = QPushButton("Checkpoint")
        checkpoint.clicked.connect(self.create_checkpoint)
        row.addWidget(checkpoint)
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
        title = QLabel("AGENT HUB")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self.codex_chat_tab(), "Chat")
        tabs.addTab(self.agent_plan_tab(), "Plan")
        tabs.addTab(self.agent_changes_tab(), "Changes")
        tabs.addTab(self.chat_history_tab(), "History")
        tabs.addTab(self.codex_usage_tab(), "Usage")
        self.agent_hub_tabs = tabs
        layout.addWidget(tabs)
        self.update_codex_usage_display()
        return frame

    def codex_chat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        top = QGridLayout()
        top.addWidget(QLabel("Provider"), 0, 0)
        top.addWidget(self.agent_provider, 0, 1)
        mode_label = QLabel("Mode")
        mode_label.setObjectName("muted")
        top.addWidget(mode_label, 0, 2)
        top.addWidget(self.codex_mode, 0, 3)
        top.addWidget(self.permission_preset, 1, 0, 1, 2)
        profile_rules = QPushButton("Profile Rules")
        profile_rules.clicked.connect(self.show_permission_profile)
        top.addWidget(profile_rules, 2, 0, 1, 2)
        top.addWidget(self.context_scope, 1, 2, 1, 2)
        top.addWidget(self.codex_status, 2, 2, 1, 2)
        layout.addLayout(top)

        auth = QHBoxLayout()
        for label, handler in [
            ("Account Status", self.provider_status),
            ("Log In", self.login_selected_agent),
            ("Log Out", self.logout_selected_agent),
            ("Manage Provider", self.manage_agents),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            auth.addWidget(button)
        layout.addLayout(auth)

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

    def agent_plan_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.task_title = QLabel("TASK: No active task")
        self.task_title.setObjectName("healthHeader")
        self.task_status = QLabel("STATUS: IDLE")
        self.task_status.setObjectName("controlState")
        self.task_elapsed = QLabel("Elapsed: --")
        self.task_elapsed.setObjectName("muted")
        self.task_estimate = QLabel("ESTIMATED IMPACT\nNo plan has been generated.")
        self.task_estimate.setObjectName("controlState")
        self.task_estimate.setWordWrap(True)
        self.task_steps = QListWidget()
        self.task_commands = QListWidget()
        steps_label = QLabel("PLAN")
        steps_label.setObjectName("panelTitle")
        commands_label = QLabel("COMMANDS")
        commands_label.setObjectName("panelTitle")
        controls = QHBoxLayout()
        self.task_edit_plan = QPushButton("EDIT PLAN")
        self.task_edit_plan.clicked.connect(self.edit_agent_plan)
        self.task_approve = QPushButton("APPROVE & RUN")
        self.task_approve.setObjectName("primaryButton")
        self.task_approve.clicked.connect(self.approve_agent_plan)
        self.task_pause = QPushButton("PAUSE")
        self.task_pause.clicked.connect(self.toggle_agent_pause)
        stop = QPushButton("STOP")
        stop.clicked.connect(self.stop_codex)
        diff = QPushButton("VIEW DIFF")
        diff.clicked.connect(self.show_agent_diff)
        controls.addWidget(self.task_edit_plan)
        controls.addWidget(self.task_approve)
        controls.addWidget(self.task_pause)
        controls.addWidget(stop)
        controls.addWidget(diff)
        controls.addStretch()
        layout.addWidget(self.task_title)
        layout.addWidget(self.task_status)
        layout.addWidget(self.task_elapsed)
        layout.addWidget(self.task_estimate)
        layout.addWidget(steps_label)
        layout.addWidget(self.task_steps, 1)
        layout.addWidget(commands_label)
        layout.addWidget(self.task_commands, 1)
        layout.addLayout(controls)
        self.task_clock = QTimer(self)
        self.task_clock.timeout.connect(self.refresh_agent_task_ui)
        self.task_clock.start(1000)
        self.refresh_agent_task_ui()
        return tab

    def agent_changes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.agent_changes_summary = QLabel("No agent changes recorded.")
        self.agent_changes_summary.setObjectName("controlState")
        self.agent_files = QListWidget()
        self.agent_log = QPlainTextEdit()
        self.agent_log.setReadOnly(True)
        self.agent_log.setObjectName("textPanel")
        files_label = QLabel("FILES")
        files_label.setObjectName("panelTitle")
        log_label = QLabel("AUDITABLE AGENT LOG")
        log_label.setObjectName("panelTitle")
        review = QPushButton("REVIEW DIFF")
        review.clicked.connect(self.show_agent_diff)
        layout.addWidget(self.agent_changes_summary)
        layout.addWidget(files_label)
        layout.addWidget(self.agent_files, 1)
        layout.addWidget(log_label)
        layout.addWidget(self.agent_log, 1)
        layout.addWidget(review)
        return tab

    def chat_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        note = QLabel("Chat sessions are stored locally. Recent history is supplied to agents so conversations can continue across restarts.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.chat_log_list = QListWidget()
        self.chat_log_list.currentItemChanged.connect(self.show_selected_chat_log)
        layout.addWidget(self.chat_log_list, 1)

        self.chat_log_viewer = QPlainTextEdit()
        self.chat_log_viewer.setReadOnly(True)
        self.chat_log_viewer.setObjectName("textPanel")
        layout.addWidget(self.chat_log_viewer, 2)

        actions = QHBoxLayout()
        for label, handler in [
            ("New Chat", self.new_chat_session),
            ("Refresh", self.refresh_chat_logs),
            ("Delete Selected", self.delete_selected_chat_log),
            ("Delete All", self.delete_all_chat_logs),
            ("Open Log Folder", self.open_chat_log_folder),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.refresh_chat_logs()
        return tab

    def start_chat_session(self):
        CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        CHAT_LOG_DIR.chmod(0o700)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.chat_session_path = CHAT_LOG_DIR / f"chat-{stamp}-{os.getpid()}.jsonl"

    def log_chat_message(self, role, message):
        if not self.chat_session_path:
            self.start_chat_session()
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "role": role,
            "provider": self.agent_provider.currentText() if hasattr(self, "agent_provider") else "Command Terminal",
            "message": message,
        }
        try:
            with self.chat_session_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.chat_session_path.chmod(0o600)
        except OSError as error:
            self.status.setText(f"Unable to save chat log: {error}")

    def chat_log_files(self):
        CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(CHAT_LOG_DIR.glob("chat-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)

    def refresh_chat_logs(self):
        if not hasattr(self, "chat_log_list"):
            return
        selected = self.chat_log_list.currentItem().data(Qt.UserRole) if self.chat_log_list.currentItem() else ""
        self.chat_log_list.clear()
        for path in self.chat_log_files():
            item = QListWidgetItem(path.stem.replace("chat-", "Chat ", 1))
            item.setData(Qt.UserRole, str(path))
            if path == self.chat_session_path:
                item.setText(item.text() + " · current")
            self.chat_log_list.addItem(item)
            if str(path) == selected:
                self.chat_log_list.setCurrentItem(item)

    def formatted_chat_log(self, path):
        messages = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                messages.append(f"[{record.get('timestamp', '')}] {record.get('role', 'unknown').upper()} · {record.get('provider', '')}\n{record.get('message', '')}")
        except OSError as error:
            return f"Unable to read log: {error}"
        return "\n\n".join(messages)

    def chat_history_context(self, max_characters=24000):
        records = []
        for path in reversed(self.chat_log_files()[:10]):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("role") in ("user", "assistant"):
                    records.append(record)
        excerpts = []
        used = 0
        for record in reversed(records[-80:]):
            entry = f"{record.get('role', 'unknown').upper()}: {record.get('message', '')}"
            if used + len(entry) > max_characters:
                break
            excerpts.append(entry)
            used += len(entry)
        excerpts.reverse()
        if not excerpts:
            return ""
        return (
            f"Prior Command Terminal chat history is stored as JSONL files in {CHAT_LOG_DIR}. "
            "Use the following recent history when it is relevant to the current request:\n\n"
            + "\n\n".join(excerpts)
            + "\n\n--- End prior chat history ---\n\n"
        )

    def show_selected_chat_log(self, current, previous=None):
        if not current:
            self.chat_log_viewer.clear()
            return
        self.chat_log_viewer.setPlainText(self.formatted_chat_log(Path(current.data(Qt.UserRole))))

    def new_chat_session(self):
        self.start_chat_session()
        self.codex_output.clear()
        self.append_chat("system", "New chat session started. Prior sessions remain available in History.")
        self.refresh_chat_logs()

    def delete_selected_chat_log(self):
        item = self.chat_log_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        if not confirm(self, "Delete Chat Log", f"Permanently delete this local chat log?\n\n{path.name}"):
            return
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            QMessageBox.warning(self, "Delete Chat Log", str(error))
            return
        if path == self.chat_session_path:
            self.start_chat_session()
        self.chat_log_viewer.clear()
        self.refresh_chat_logs()

    def delete_all_chat_logs(self):
        files = self.chat_log_files()
        if not files or not confirm(self, "Delete All Chat Logs", f"Permanently delete all {len(files)} local chat logs?"):
            return
        errors = []
        for path in files:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                errors.append(f"{path.name}: {error}")
        self.start_chat_session()
        self.codex_output.clear()
        self.refresh_chat_logs()
        if errors:
            QMessageBox.warning(self, "Delete Chat Logs", "\n".join(errors))

    def open_chat_log_folder(self):
        CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(CHAT_LOG_DIR)))

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
        unlink = QPushButton("Unlink ChatGPT")
        unlink.clicked.connect(self.unlink_chatgpt_account)
        row.addWidget(save)
        row.addWidget(reset)
        row.addWidget(status)
        row.addWidget(unlink)
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

    def preview_html(self):
        editor = self.current_editor()
        path = None
        if editor:
            path_text = editor.property("path") or ""
            candidate = Path(path_text) if path_text else None
            if candidate and candidate.suffix.lower() in (".html", ".htm"):
                if editor.property("modified"):
                    self.save_editor(editor)
                    path_text = editor.property("path") or ""
                    candidate = Path(path_text) if path_text else None
                path = candidate

        if path is None:
            candidates = [self.workspace / "public/index.html", self.workspace / "index.html"]
            path = next((candidate for candidate in candidates if candidate.is_file()), None)

        if path is None or not path.is_file():
            QMessageBox.information(
                self,
                "Preview HTML",
                "Open an HTML file first, or add public/index.html or index.html to the workspace.",
            )
            return

        preview = QWebEngineView()
        preview.setUrl(QUrl.fromLocalFile(str(path.resolve())))
        self.tabs.addTab(preview, f"Preview: {path.name}")
        self.tabs.setCurrentWidget(preview)
        self.status.setText(f"Local preview: {path}")
        self.parent_window.add_history(f"Command Terminal previewed {path.name}")

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

    def load_agent_config(self):
        defaults = {"default_provider": "codex", "deepseek": {"endpoint": "https://api.deepseek.com/chat/completions", "model": "deepseek-chat"},
                    "custom": {"endpoint": "", "model": ""}, "ollama": {"model": ""}}
        try:
            data = validate_agent_config(json.loads(AGENT_CONFIG_FILE.read_text(encoding="utf-8")))
            for key, value in data.items(): defaults[key] = value
        except Exception:
            pass
        return defaults

    def save_agent_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        AGENT_CONFIG_FILE.write_text(json.dumps(self.agent_config, indent=2), encoding="utf-8")

    def secret_key(self, provider):
        if not command_exists("secret-tool"):
            return ""
        return run_text(["secret-tool", "lookup", "application", "command-centre", "provider", provider], 3)[0]

    def store_secret_key(self, provider, secret):
        if not command_exists("secret-tool"):
            QMessageBox.warning(self, "Secure storage unavailable", "Install libsecret/secret-tool before configuring API credentials. Keys will not be stored in plaintext.")
            return False
        try:
            result = subprocess.run(["secret-tool", "store", "--label", f"Command Centre {provider} API key", "application", "command-centre", "provider", provider], input=secret, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def clear_secret_key(self, provider):
        if not command_exists("secret-tool"):
            return False
        result = subprocess.run(
            ["secret-tool", "clear", "application", "command-centre", "provider", provider],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def provider_state(self, provider):
        if provider == "codex": return "CLI detected" if self.codex_command() else "CLI missing"
        if provider == "claude": return "CLI detected" if command_exists("claude") else "CLI missing"
        if provider == "fcc":
            installed = command_exists("fcc-claude") and command_exists("fcc-server")
            healthy = self.fcc_health_check() if installed else False
            return f"{'FCC installed' if installed else 'Not installed'} · {'local proxy healthy' if healthy else 'proxy stopped'} · reviewed integration pin {FCC_AUDITED_COMMIT[:8]}"
        if provider == "ollama": return "Local runtime detected" if command_exists("ollama") else "Local runtime missing"
        config = self.agent_config.get(provider, {})
        return f"Endpoint configured · {'credential stored' if self.secret_key(provider) else 'credential missing'}" if config.get("endpoint") else "Endpoint missing"

    def manage_agents(self):
        provider, ok = QInputDialog.getItem(self, "Manage Agents", "Provider:", ["Codex", "Claude", "FCC Claude", "DeepSeek", "Ollama", "Custom"], self.agent_provider.currentIndex(), False)
        if not ok: return
        key = provider.lower()
        if key == "codex":
            self.link_chatgpt_account(); return
        if key == "claude":
            if not command_exists("claude"):
                QMessageBox.information(self, "Claude", "Claude CLI was not detected. Install it using its official instructions before linking it here."); return
            ok, terminal = launch_terminal("Claude Authentication", "claude; echo; read -n 1 -s -r -p 'Press any key to close...' ")
            self.append_chat("system", f"Opened Claude CLI in {terminal}. Complete provider-owned authentication there." if ok else terminal); return
        if key == "fcc claude":
            self.manage_fcc(); return
        if key == "ollama":
            model, ok = QInputDialog.getText(self, "Ollama", "Default local model:", text=self.agent_config["ollama"].get("model", ""))
            if ok: self.agent_config["ollama"]["model"] = model.strip(); self.save_agent_config()
            return
        current = self.agent_config.get(key, {})
        endpoint, ok = QInputDialog.getText(self, f"{provider} endpoint", "OpenAI-compatible chat completions endpoint:", text=current.get("endpoint", ""))
        if not ok: return
        model, ok = QInputDialog.getText(self, f"{provider} model", "Model ID:", text=current.get("model", ""))
        if not ok: return
        secret, ok = QInputDialog.getText(self, f"{provider} credential", "API key (stored in system keyring):", QLineEdit.Password)
        if not ok or not secret.strip(): return
        if self.store_secret_key(key, secret.strip()):
            self.agent_config[key] = {"endpoint": endpoint.strip(), "model": model.strip()}; self.save_agent_config(); self.append_chat("system", f"{provider} configured. Credential stored by the system keyring.")

    def provider_status(self):
        provider = self.agent_provider.currentData() or "codex"
        if provider == "codex": self.codex_account_status(); return
        if provider == "claude" and command_exists("claude"):
            out, err, code = run_text(["claude", "auth", "status"], 10)
            self.append_chat("system", "Claude account status\n" + (out or err or f"Status exited with {code}")); return
        self.append_chat("system", f"{self.agent_provider.currentText()}\n{self.provider_state(provider)}")

    def login_selected_agent(self):
        provider = self.agent_provider.currentData() or "codex"
        label = self.agent_provider.currentText()
        if provider == "codex":
            self.link_chatgpt_account()
            return
        if provider == "claude":
            if not command_exists("claude"):
                QMessageBox.information(self, "Claude Login", "Claude CLI is not installed.")
                return
            if not confirm(self, "Claude Login", "Open the official Claude CLI login flow?"):
                return
            ok, terminal = launch_terminal("Claude Login", "claude auth login; status=$?; echo; echo 'Claude login exited with' $status; read -n 1 -s -r -p 'Press any key to close...'")
            self.append_chat("system", f"Started Claude login in {terminal}." if ok else terminal)
            return
        if provider == "fcc":
            QMessageBox.information(
                self,
                "FCC Claude Login",
                "FCC Claude uses the providers configured through its local proxy. Use Manage to start FCC and configure its provider credentials; use Claude Login if the selected backend is Claude.",
            )
            self.manage_fcc()
            return
        if provider == "ollama":
            if not command_exists("ollama"):
                QMessageBox.information(self, "Ollama Login", "Ollama is not installed.")
                return
            if not confirm(self, "Ollama Login", "Open the Ollama account sign-in flow?"):
                return
            ok, terminal = launch_terminal("Ollama Login", "ollama signin; status=$?; echo; echo 'Ollama sign-in exited with' $status; read -n 1 -s -r -p 'Press any key to close...'")
            self.append_chat("system", f"Started Ollama sign-in in {terminal}." if ok else terminal)
            return

        config = self.agent_config.get(provider, {})
        endpoint, ok = QInputDialog.getText(self, f"{label} Login", "API endpoint:", text=config.get("endpoint", ""))
        if not ok:
            return
        model, ok = QInputDialog.getText(self, f"{label} Login", "Model ID:", text=config.get("model", ""))
        if not ok:
            return
        secret, ok = QInputDialog.getText(self, f"{label} Login", "API key (stored in the system keyring):", QLineEdit.Password)
        if not ok or not secret.strip():
            return
        if self.store_secret_key(provider, secret.strip()):
            self.agent_config[provider] = {"endpoint": endpoint.strip(), "model": model.strip()}
            self.save_agent_config()
            self.append_chat("system", f"{label} login saved securely in the system keyring.")

    def logout_selected_agent(self):
        provider = self.agent_provider.currentData() or "codex"
        label = self.agent_provider.currentText()
        if provider == "codex":
            self.unlink_chatgpt_account()
            return
        if not confirm(self, f"Log Out of {label}", f"Remove the local authentication for {label} on this computer?"):
            return
        if provider == "claude":
            if not command_exists("claude"):
                QMessageBox.information(self, "Claude Logout", "Claude CLI is not installed.")
                return
            out, err, code = run_text(["claude", "auth", "logout"], 20)
        elif provider == "ollama":
            if not command_exists("ollama"):
                QMessageBox.information(self, "Ollama Logout", "Ollama is not installed.")
                return
            out, err, code = run_text(["ollama", "signout"], 20)
        elif provider == "fcc":
            if self.fcc_server_process and self.fcc_server_process.state() != QProcess.NotRunning:
                self.fcc_server_process.terminate()
            self.append_chat("system", "FCC local proxy stopped. Provider credentials managed by FCC were left intact; remove them through FCC Manage to avoid deleting unrelated provider access.")
            return
        else:
            removed = self.clear_secret_key(provider)
            self.append_chat("system", f"{label} API credential removed from the system keyring." if removed else f"No stored {label} credential was found.")
            return
        if code == 0:
            self.append_chat("system", f"Logged out of {label}.\n" + (out or "Local authentication removed."))
        else:
            QMessageBox.warning(self, f"{label} Logout", err or out or f"Logout exited with code {code}")

    def fcc_health_check(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8082/health", timeout=0.5) as response:
                return response.status == 200
        except Exception:
            return False

    def manage_fcc(self):
        installed = command_exists("fcc-server") and command_exists("fcc-claude")
        actions = ["Start local-only proxy", "Open local Admin UI", "Check health", "Repair config permissions"] if installed else ["Review and install pinned version"]
        action, ok = QInputDialog.getItem(self, "FCC Claude", "Action:", actions, 0, False)
        if not ok: return
        if action == "Review and install pinned version":
            self.install_fcc_reviewed(); return
        if action == "Start local-only proxy":
            self.start_fcc_server(); return
        if action == "Open local Admin UI":
            if not self.fcc_health_check():
                QMessageBox.information(self, "FCC Claude", "Start the local proxy first."); return
            QDesktopServices.openUrl(QUrl("http://127.0.0.1:8082/admin")); return
        if action == "Check health":
            QMessageBox.information(self, "FCC Claude", self.provider_state("fcc")); return
        self.repair_fcc_permissions()

    def install_fcc_reviewed(self):
        if not command_exists("uv"):
            QMessageBox.information(self, "FCC Claude", "The reviewed installer path requires uv, which is not installed. Install uv through a trusted package source, then retry. Command Centre will not execute a curl-to-shell bootstrap.")
            return
        if not command_exists("npm") and not command_exists("claude"):
            QMessageBox.information(self, "FCC Claude", "Claude Code CLI is also required. Install Node.js/npm or the official Claude Code CLI first.")
            return
        spec = f"free-claude-code @ git+{FCC_REPOSITORY}@{FCC_AUDITED_COMMIT}"
        command = f"uv tool install --force {shlex.quote(spec)}"
        message = ("Install the exact FCC revision reviewed by Command Centre?\n\n"
                   f"Repository: {FCC_REPOSITORY}\nCommit: {FCC_AUDITED_COMMIT}\nLicense: MIT\n\nCommand:\n{command}\n\n"
                   "FCC is a compatibility proxy, not free access to Anthropic models. Provider limits, terms, privacy policies, and charges still apply. Configuration keys are stored by FCC in ~/.fcc/.env.")
        if not confirm(self, "Install FCC Claude", message): return
        ok, terminal = launch_terminal("Install FCC Claude", f"{command}; status=$?; echo; echo 'FCC install exited with' $status; read -n 1 -s -r -p 'Press any key to close...'")
        self.append_chat("system", f"Started pinned FCC installation in {terminal}." if ok else terminal)

    def repair_fcc_permissions(self):
        folder = Path.home() / ".fcc"; env_file = folder / ".env"
        if folder.exists(): folder.chmod(0o700)
        if env_file.exists(): env_file.chmod(0o600)
        self.append_chat("system", f"Restricted FCC configuration permissions:\n{folder}: 0700\n{env_file}: {'0600' if env_file.exists() else 'not present'}")

    def start_fcc_server(self):
        if self.fcc_health_check():
            self.append_chat("system", "FCC proxy is already healthy on 127.0.0.1:8082."); return
        if self.fcc_server_process and self.fcc_server_process.state() != QProcess.NotRunning:
            self.append_chat("system", "FCC proxy is already starting."); return
        self.repair_fcc_permissions()
        self.fcc_server_process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("HOST", "127.0.0.1")
        environment.insert("FCC_OPEN_BROWSER", "false")
        self.fcc_server_process.setProcessEnvironment(environment)
        self.fcc_server_process.setProgram("fcc-server")
        self.fcc_server_process.readyReadStandardOutput.connect(self.read_fcc_output)
        self.fcc_server_process.readyReadStandardError.connect(self.read_fcc_output)
        self.fcc_server_process.finished.connect(lambda code, status: self.append_chat("system", f"FCC proxy stopped with exit code {code}."))
        self.fcc_server_process.start()
        self.append_chat("system", "Starting FCC on loopback only: 127.0.0.1:8082. Configure a non-default API token and provider in the local Admin UI.")

    def read_fcc_output(self):
        if not self.fcc_server_process: return
        output = bytes(self.fcc_server_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        error = bytes(self.fcc_server_process.readAllStandardError()).decode("utf-8", errors="replace")
        text = (output + error).strip()
        if text: self.output.appendPlainText("[FCC] " + text[-4000:])

    def agent_provider_changed(self):
        provider = self.agent_provider.currentData() or "codex"
        self.agent_config["default_provider"] = provider; self.save_agent_config()
        self.codex_status.setText(self.provider_state(provider))
        self.codex_prompt.setPlaceholderText(f"Message {self.agent_provider.currentText()}")

    def run_command_bar(self):
        query = self.command_bar.text().strip()
        if not query: return
        self.command_bar.clear()
        matches = [path for path in self.workspace.rglob("*") if path.is_file() and query.lower() in path.name.lower()][:30]
        if matches: self.open_file(matches[0]); self.status.setText(f"Opened command-bar match: {matches[0].name}")
        else: self.status.setText(f"No workspace file matched: {query}")

    def show_git_status(self):
        output, error, code = run_text(["git", "-C", str(self.workspace), "status", "--short", "--branch"], 5)
        self.output.setPlainText(output or error or ("Clean working tree" if code == 0 else "Not a Git workspace"))

    def create_checkpoint(self, silent=False):
        patch, error, code = run_text(["git", "-C", str(self.workspace), "diff", "--binary", "HEAD"], 8)
        if code != 0:
            if not silent: self.output.appendPlainText(error or "Unable to create Git patch checkpoint.")
            return ""
        checkpoint_root = CONFIG_DIR / "checkpoints"
        checkpoint_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = checkpoint_root / f"workspace-{time.strftime('%Y%m%d-%H%M%S')}"
        path.mkdir(mode=0o700)
        patch_path = path / "changes.patch"
        patch_path.write_text(patch, encoding="utf-8")
        patch_path.chmod(0o600)
        untracked_output = run_text(["git", "-C", str(self.workspace), "ls-files", "--others", "--exclude-standard", "-z"], 5)[0]
        copied, skipped = [], []
        for relative in filter(None, untracked_output.split("\0")):
            source = (self.workspace / relative).resolve()
            try:
                source.relative_to(self.workspace.resolve())
                if source.is_symlink() or not source.is_file() or source.stat().st_size > 50 * 1024 * 1024:
                    skipped.append(relative)
                    continue
                destination = path / "untracked" / relative
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(source, destination)
                destination.chmod(0o600)
                copied.append(relative)
            except OSError:
                skipped.append(relative)
        manifest_path = path / "manifest.json"
        manifest_path.write_text(json.dumps({
            "workspace": str(self.workspace), "tracked_patch": "changes.patch",
            "untracked_copied": copied, "untracked_skipped": skipped,
        }, indent=2), encoding="utf-8")
        manifest_path.chmod(0o600)
        if not silent:
            note = f"\nSkipped {len(skipped)} unsafe or oversized untracked file(s)." if skipped else ""
            self.output.appendPlainText(f"Complete workspace checkpoint saved without changing the working tree:\n{path}\nCopied {len(copied)} untracked file(s).{note}")
        return str(path)

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

    def unlink_chatgpt_account(self):
        command = self.codex_command()
        if not command:
            self.append_chat("system", "Codex CLI was not found.")
            return
        if not confirm(
            self,
            "Unlink ChatGPT Account",
            "Remove the locally stored Codex authentication credentials from this computer?\n\nYou will need to link ChatGPT again before using Codex.",
        ):
            return
        out, err, code = run_text([command, "logout"], 15)
        if code == 0:
            self.codex_status.setText("ChatGPT unlinked")
            self.append_chat("system", "ChatGPT/OpenAI was unlinked from Codex on this computer.\n" + (out or "Local authentication credentials removed."))
        else:
            self.codex_status.setText("Unlink failed")
            self.append_chat("system", "Unable to unlink ChatGPT.\n" + (err or out or f"codex logout exited with {code}"))

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

    def managed_context(self):
        context = self.current_file_context()
        scope = self.context_scope.currentData() or "file"
        if scope in ("git", "full"):
            diff = run_text(["git", "-C", str(self.workspace), "diff", "--", "."], 8)[0]
            if diff:
                context += f"\n\nCurrent Git diff (clipped):\n```diff\n{diff[:20000]}\n```"
        if scope == "full":
            output = self.output.toPlainText()[-12000:]
            if output:
                context += f"\n\nRecent Command Terminal output:\n```text\n{output}\n```"
        return context

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
                "inspect the workspace, make code edits when needed, run focused verification, and summarize the result. "
                "For local HTML, do not launch a GUI browser or local server; tell the user to use Command Terminal's Preview HTML button."
            ),
            "ask": (
                "You are in Ask mode inside Command Terminal. Answer and explain using workspace context, "
                "but do not edit files or run changing commands unless the user explicitly asks you to switch modes."
            ),
            "plan": (
                "You are in Plan mode. Inspect only the supplied context and produce a concrete implementation plan. Do not modify files or run commands."
            ),
            "edit": (
                "You are in Edit mode inside Command Terminal. Focus on implementing the requested change in the workspace. "
                "Keep edits scoped, preserve existing style, and run reasonable checks. For local HTML, do not launch a GUI browser "
                "or local server; tell the user to use Command Terminal's Preview HTML button."
            ),
            "review": (
                "You are in Review mode inside Command Terminal. Use a code-review stance: findings first, ordered by severity, "
                "with file references where possible. Do not rewrite code unless explicitly requested."
            ),
            "debug": (
                "You are in Debug mode. Diagnose the reported problem using supplied code and output. Propose focused checks and fixes; do not modify files unless explicitly approved."
            ),
        }
        permission = self.permission_preset.currentData() or "observe"
        permission_text = self.permission_profile_text(permission)
        return f"{instructions.get(mode, instructions['agent'])}\n\nCommand Terminal permission preset: {permission.upper()}\n{permission_text}\n\nUser request:\n{user_prompt}"

    def permission_profile_text(self, permission=None):
        permission = permission or self.permission_preset.currentData() or "observe"
        return {
            "observe": "FILES: read/search only. EDITS: prohibited. TERMINAL: inspection only. NETWORK: provider-owned request only. GIT: no writes.",
            "safe": "FILES: read/search and proposed changes only. EDITS: prohibited by the read-only sandbox. TERMINAL: inspection only. NETWORK: prohibited. GIT: no writes.",
            "develop": "FILES: workspace edits allowed. TERMINAL: project build/test/lint commands allowed. NETWORK: dependency access only when requested. SUDO and Git remote writes: prohibited.",
            "elevated": "FILES: workspace edits allowed. SYSTEM/PACKAGE actions require an explicit user confirmation outside the agent. SUDO is never silently authorized. Git remote writes require separate approval.",
            "autonomous": "Execute the approved task plan within this workspace. Build/test commands are allowed. Stop at boundary changes, privilege prompts, destructive actions, secrets, or Git remote writes.",
        }.get(permission, "Unknown permission profile.")

    def show_permission_profile(self):
        QMessageBox.information(
            self,
            f"Permission Profile · {self.permission_preset.currentText()}",
            self.permission_profile_text(),
        )

    def append_chat(self, role, message):
        role_labels = {
            "user": "You",
            "assistant": self.agent_provider.currentText() if hasattr(self, "agent_provider") else "Agent",
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
        self.log_chat_message(role, message)
        if hasattr(self, "chat_log_list"):
            self.refresh_chat_logs()

    def ask_codex(self):
        prompt = self.codex_prompt.toPlainText().strip()
        if not prompt:
            self.append_chat("system", "Type a prompt for the selected agent first.")
            return
        self.codex_prompt.clear()
        self.run_agent(self.mode_prompt(prompt) + self.managed_context() + self.attachment_context(), prompt)

    def explain_current_file(self):
        editor = self.current_editor()
        if not editor:
            self.append_chat("system", "Open a file first.")
            return
        self.set_codex_mode("ask")
        question = "Explain the current file."
        self.run_agent("Explain this file clearly and point out important functions, risks, and next improvements." + self.current_file_context(), question)

    def review_workspace(self):
        self.set_codex_mode("review")
        question = "Review this workspace."
        self.run_agent(self.mode_prompt("Review this workspace for likely bugs, missing tests, and risky implementation choices."), question)

    def run_agent(self, prompt, display_question=None):
        prompt = self.chat_history_context() + prompt
        provider = self.agent_provider.currentData() or "codex"
        if provider == "codex":
            self.run_codex(prompt, display_question); return
        if provider == "claude":
            if not command_exists("claude"): self.append_chat("system", "Claude CLI was not found."); return
            self.run_external_agent("claude", ["-p", prompt], display_question); return
        if provider == "fcc":
            if not command_exists("fcc-claude"):
                self.append_chat("system", "FCC Claude is not installed. Open Manage Agents to review the pinned installation."); return
            if not self.fcc_health_check():
                self.append_chat("system", "FCC local proxy is not running. Start it from Manage Agents first."); return
            self.repair_fcc_permissions()
            self.run_external_agent("fcc-claude", ["-p", prompt], display_question); return
        if provider == "ollama":
            if not command_exists("ollama"): self.append_chat("system", "Ollama was not found."); return
            model = self.agent_config.get("ollama", {}).get("model", "")
            if not model:
                rows = run_text(["ollama", "list"], 8)[0].splitlines()[1:]
                model = rows[0].split()[0] if rows else ""
            if not model: self.append_chat("system", "Configure or download an Ollama model first."); return
            self.run_external_agent("ollama", ["run", model, prompt], display_question); return
        if self.agent_future is not None:
            self.append_chat("system", "An API agent request is already running."); return
        config = self.agent_config.get(provider, {})
        secret = self.secret_key(provider)
        if not config.get("endpoint") or not config.get("model") or not secret:
            self.append_chat("system", f"Configure {self.agent_provider.currentText()} in Manage Agents first."); return
        self.append_chat("user", f"[{self.codex_mode.currentText()}] {display_question or 'Agent request'}")
        self.codex_status.setText(f"Running {self.agent_provider.currentText()}")
        self.agent_future = self.agent_executor.submit(self.call_api_agent, config, secret, prompt)

    def run_external_agent(self, program, arguments, display_question):
        if self.external_agent_process and self.external_agent_process.state() != QProcess.NotRunning:
            self.append_chat("system", "An external agent is already running."); return
        self.append_chat("user", f"[{self.codex_mode.currentText()}] {display_question or 'Agent request'}")
        self.codex_status.setText(f"Running {self.agent_provider.currentText()}")
        self.external_agent_process = QProcess(self); self.external_agent_process.setWorkingDirectory(str(self.workspace)); self.external_agent_process.setProgram(program); self.external_agent_process.setArguments(arguments)
        self.external_agent_process.finished.connect(self.external_agent_finished); self.external_agent_process.start()

    def external_agent_finished(self, code, status):
        output = bytes(self.external_agent_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        error = bytes(self.external_agent_process.readAllStandardError()).decode("utf-8", errors="replace")
        self.append_chat("assistant" if output else "system", output.strip() or error.strip() or f"Agent exited with code {code}")
        self.codex_status.setText("Ready")

    def call_api_agent(self, config, secret, prompt):
        payload = json.dumps({"model": config["model"], "messages": [{"role": "user", "content": prompt}], "stream": False}).encode("utf-8")
        request = urllib.request.Request(config["endpoint"], data=payload, method="POST", headers={"Content-Type":"application/json", "Authorization":f"Bearer {secret}"})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("choices", [{}])[0].get("message", {}).get("content", "Provider returned no message.")
        except Exception as error:
            return f"Provider request failed: {error}"

    def finish_api_agent(self):
        if self.agent_future is None or not self.agent_future.done(): return
        future = self.agent_future; self.agent_future = None
        try: message = future.result()
        except Exception as error: message = f"Provider request failed: {error}"
        self.append_chat("assistant", message); self.codex_status.setText("Ready")

    def start_agent_task(self, title):
        AGENT_TASK_DIR.mkdir(parents=True, exist_ok=True)
        task_id = f"task-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        self.agent_task_path = AGENT_TASK_DIR / f"{task_id}.json"
        self.agent_task = {
            "id": task_id,
            "title": title or "Agent request",
            "status": "PLANNING",
            "mode": self.selected_codex_mode(),
            "permission_profile": self.permission_preset.currentData() or "safe",
            "workspace": str(self.workspace),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "started_epoch": time.time(),
            "finished_at": "",
            "steps": [{"title": "Generate a read-only implementation plan", "status": "running"}],
            "commands": [], "files": [], "log": [], "usage": {},
        }
        self.agent_paused = False
        if hasattr(self, "task_pause"):
            self.task_pause.setText("PAUSE")
        self.log_agent_activity("TASK", "Agent task started", title)
        self.refresh_agent_files()
        self.save_agent_task()
        self.refresh_agent_task_ui()

    def save_agent_task(self):
        if not self.agent_task or not self.agent_task_path:
            return
        try:
            self.agent_task_path.write_text(json.dumps(self.agent_task, indent=2), encoding="utf-8")
            self.agent_task_path.chmod(0o600)
        except OSError as error:
            self.status.setText(f"Unable to save agent task: {error}")

    def load_latest_agent_task(self):
        AGENT_TASK_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(AGENT_TASK_DIR.glob("task-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not files:
            return
        try:
            task = json.loads(files[0].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if task.get("status") in ("EXECUTING", "PAUSED"):
            task["status"] = "INTERRUPTED"
            task["finished_epoch"] = time.time()
            task["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            task.setdefault("log", []).append({
                "timestamp": time.strftime("%H:%M:%S"), "kind": "TASK",
                "title": "Task interrupted by application restart", "detail": "", "status": "failed",
            })
        self.agent_task = task
        self.agent_task_path = files[0]
        if task.get("status") == "WAITING FOR APPROVAL":
            self.pending_execution_prompt = task.get("execution_prompt", "")
            self.pending_execution_title = task.get("execution_title", task.get("title", ""))
            self.pending_execution_images = [Path(path) for path in task.get("execution_images", []) if Path(path).is_file()]
        self.save_agent_task()
        self.refresh_agent_task_ui()

    def log_agent_activity(self, kind, title, detail="", status="info"):
        if not self.agent_task:
            return
        self.agent_task["log"].append({
            "timestamp": time.strftime("%H:%M:%S"), "kind": kind,
            "title": title, "detail": detail, "status": status,
        })
        self.agent_task["log"] = self.agent_task["log"][-500:]
        self.save_agent_task()
        self.refresh_agent_task_ui()

    def set_agent_step(self, index, status):
        if self.agent_task and 0 <= index < len(self.agent_task["steps"]):
            self.agent_task["steps"][index]["status"] = status
            self.save_agent_task()
            self.refresh_agent_task_ui()

    def refresh_agent_files(self):
        if not self.agent_task:
            return
        output = run_text(["git", "-C", str(self.workspace), "status", "--short"], 5)[0]
        files = []
        for line in output.splitlines():
            if len(line) >= 4:
                files.append({"status": line[:2].strip() or "M", "path": line[3:].strip()})
        self.agent_task["files"] = files
        self.save_agent_task()

    def refresh_agent_task_ui(self):
        if not hasattr(self, "task_title"):
            return
        task = self.agent_task
        if not task:
            self.task_title.setText("TASK: No active task")
            self.task_status.setText("STATUS: IDLE")
            self.task_elapsed.setText("Elapsed: --")
            self.task_steps.clear(); self.task_commands.clear()
            self.task_edit_plan.setVisible(False)
            self.task_approve.setVisible(False)
            self.task_pause.setVisible(False)
            return
        self.task_title.setText(f"TASK: {task['title']}")
        self.task_status.setText(f"STATUS: {task['status']}  ·  {task['mode'].upper()}  ·  {task['permission_profile'].upper()}")
        end = task.get("finished_epoch") or time.time()
        elapsed = max(0, int(end - task.get("started_epoch", end)))
        self.task_elapsed.setText(f"Elapsed: {elapsed // 60:02d}:{elapsed % 60:02d}")
        impact = task.get("estimated_impact", {})
        self.task_estimate.setText(
            "ESTIMATED IMPACT\n"
            f"Files to inspect        {len(impact.get('files_to_inspect', [])) if isinstance(impact.get('files_to_inspect', []), list) else impact.get('files_to_inspect', 'Unknown')}\n"
            f"Files likely modified   {len(impact.get('likely_modified_files', [])) if isinstance(impact.get('likely_modified_files', []), list) else impact.get('likely_modified_files', 'Unknown')}\n"
            f"Commands required       {len(impact.get('commands', [])) if isinstance(impact.get('commands', []), list) else impact.get('commands', 'Unknown')}\n"
            f"Privilege required      {'YES' if impact.get('privilege_required') else 'NO'}\n"
            f"Network required        {'YES' if impact.get('network_required') else 'NO'}\n"
            f"Risk                     {str(impact.get('risk_level', 'Unknown')).upper()}"
        )
        icons = {"completed": "✓", "running": "●", "pending": "○", "failed": "!", "stopped": "■"}
        self.task_steps.clear()
        for step in task["steps"]:
            self.task_steps.addItem(f"{icons.get(step['status'], '○')}  {step['title']}")
        self.task_commands.clear()
        for command in task["commands"][-30:]:
            self.task_commands.addItem(f"{icons.get(command['status'], '○')}  {command['command']}")
        waiting = task["status"] == "WAITING FOR APPROVAL"
        running = task["status"] in ("EXECUTING", "PAUSED", "PLANNING")
        self.task_edit_plan.setVisible(waiting)
        self.task_approve.setVisible(waiting)
        self.task_pause.setVisible(running and task["status"] != "PLANNING")
        if hasattr(self, "agent_files"):
            self.agent_files.clear()
            for file in task.get("files", []):
                self.agent_files.addItem(f"{file['status']:<2}  {file['path']}")
            self.agent_changes_summary.setText(f"{len(task.get('files', []))} workspace file(s) changed · Task {task['status'].lower()}")
            self.agent_log.setPlainText("\n\n".join(
                f"[{entry['timestamp']}] {entry['kind']} · {entry['title']}\n{entry['detail']}".strip()
                for entry in task.get("log", [])
            ))

    def parse_agent_plan(self, text):
        candidate = text.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.S)
        if fenced:
            candidate = fenced.group(1)
        else:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start >= 0 and end > start:
                candidate = candidate[start:end + 1]
        try:
            plan = json.loads(candidate)
        except (TypeError, ValueError):
            lines = [re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip() for line in text.splitlines()]
            steps = [line for line in lines if line and len(line) < 180][:12]
            plan = {"task": self.pending_execution_title, "steps": steps or ["Execute the requested task", "Run verification", "Review changes"]}
        raw_steps = plan.get("steps") or plan.get("plan") or []
        steps = []
        for entry in raw_steps:
            if isinstance(entry, dict):
                title = entry.get("title") or entry.get("text") or entry.get("step")
            else:
                title = str(entry)
            if title:
                steps.append({"title": str(title), "status": "pending"})
        return {
            "task": plan.get("task") or self.pending_execution_title,
            "steps": steps or [{"title": "Execute the requested task", "status": "pending"}],
            "files_to_inspect": plan.get("files_to_inspect", []),
            "likely_modified_files": plan.get("likely_modified_files", []),
            "commands": plan.get("commands", []),
            "privilege_required": bool(plan.get("privilege_required", False)),
            "network_required": bool(plan.get("network_required", False)),
            "risk_level": plan.get("risk_level", "unknown"),
        }

    def edit_agent_plan(self):
        if not self.agent_task or self.agent_task.get("status") != "WAITING FOR APPROVAL":
            return
        current = "\n".join(step["title"] for step in self.agent_task.get("steps", []))
        text, ok = QInputDialog.getMultiLineText(self, "Edit Agent Plan", "One approved step per line:", current)
        if not ok:
            return
        steps = [line.strip() for line in text.splitlines() if line.strip()]
        if not steps:
            QMessageBox.information(self, "Agent Plan", "The plan must contain at least one step.")
            return
        self.agent_task["steps"] = [{"title": step, "status": "pending"} for step in steps]
        self.agent_task["approval_status"] = "edited · approval required"
        self.log_agent_activity("PLAN", "Plan edited by user", f"{len(steps)} approved step(s)")

    def approve_agent_plan(self):
        if not self.agent_task or self.agent_task.get("status") != "WAITING FOR APPROVAL":
            return
        if not self.pending_execution_prompt:
            QMessageBox.warning(self, "Agent Plan", "The execution prompt is no longer available. Submit the task again to regenerate its plan.")
            return
        impact = self.agent_task.get("estimated_impact", {})
        if impact.get("privilege_required") and not confirm(
            self, "Approve Elevated Plan",
            "This plan predicts privileged operations. Approval allows the workspace execution pass, but every system or package action must still be confirmed separately.\n\nApprove this plan?",
        ):
            return
        checkpoint = self.create_checkpoint(silent=True)
        self.agent_task["checkpoint"] = checkpoint
        self.agent_task["approval_status"] = "approved"
        self.agent_task["approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.agent_task["status"] = "EXECUTING"
        if checkpoint:
            self.log_agent_activity("CHECKPOINT", "Pre-task checkpoint created", checkpoint, "completed")
        self.log_agent_activity("APPROVAL", "Plan approved by user", status="completed")
        approved_plan = "\n".join(f"{index}. {step['title']}" for index, step in enumerate(self.agent_task["steps"], 1))
        execution_prompt = self.pending_execution_prompt + f"\n\nAPPROVED TASK PLAN\n{approved_plan}\n\nExecute only within this approved plan. Stop and request approval if files, commands, network access, privileges, or scope materially exceed it."
        self.run_codex(execution_prompt, self.pending_execution_title, approved_run=True)

    def toggle_agent_pause(self):
        if not self.codex_process or self.codex_process.state() == QProcess.NotRunning:
            self.append_chat("system", "No running Codex task to pause.")
            return
        pid = int(self.codex_process.processId())
        try:
            if self.agent_paused:
                os.kill(pid, signal.SIGCONT); self.agent_paused = False
                self.agent_task["status"] = "EXECUTING"; self.task_pause.setText("PAUSE")
                self.log_agent_activity("CONTROL", "Agent resumed")
            else:
                os.kill(pid, signal.SIGSTOP); self.agent_paused = True
                self.agent_task["status"] = "PAUSED"; self.task_pause.setText("RESUME")
                self.log_agent_activity("CONTROL", "Agent paused")
        except (OSError, ProcessLookupError) as error:
            self.append_chat("system", f"Unable to change agent pause state: {error}")

    def show_agent_diff(self):
        diff, error, code = run_text(["git", "-C", str(self.workspace), "diff", "--stat"], 8)
        full = run_text(["git", "-C", str(self.workspace), "diff", "--", "."], 8)[0]
        self.output.setPlainText((diff + "\n\n" + full[:40000]).strip() or error or "No tracked changes to display.")

    def run_codex(self, prompt, display_question=None, approved_run=False):
        command = self.codex_command()
        if not command:
            self.append_chat("system", "Codex CLI was not found.")
            return
        if self.codex_process and self.codex_process.state() != QProcess.NotRunning:
            self.append_chat("system", "Codex is already running. Stop it first.")
            return

        mode_label = self.codex_mode.currentText()
        title = display_question or prompt.split(chr(10), 1)[0]
        profile = self.permission_preset.currentData() or "observe"
        needs_plan = not approved_run and self.selected_codex_mode() in ("agent", "edit") and profile in ("safe", "develop", "elevated", "autonomous")
        if needs_plan:
            self.start_agent_task(title)
            self.agent_phase = "planning"
            self.pending_execution_prompt = prompt
            self.pending_execution_title = title
            self.pending_execution_images = list(self.image_attachments())
            planning_request = (
                "Create a read-only implementation plan for the task below. Inspect the workspace as needed, but do not edit files or run changing commands. "
                "Return a single JSON object with exactly these fields: task (string), steps (array of concise strings), files_to_inspect (array of paths), "
                "likely_modified_files (array of paths), commands (array of anticipated commands), privilege_required (boolean), network_required (boolean), "
                "risk_level (low, medium, or high). Do not wrap the JSON in commentary.\n\n" + prompt
            )
            process_prompt = planning_request
            sandbox = "read-only"
            self.append_chat("user", f"[{mode_label}] {title}")
            self.append_chat("system", "Creating a read-only task plan for approval...")
            self.codex_status.setText("Planning · read-only")
        else:
            process_prompt = prompt
            sandbox = "read-only" if (profile in ("observe", "safe") or self.selected_codex_mode() in ("ask", "plan", "review", "debug")) else "workspace-write"
            if approved_run:
                self.agent_phase = "executing"
                self.agent_task["status"] = "EXECUTING"
                self.append_chat("system", "Approved plan is now executing.")
            else:
                self.start_agent_task(title)
                self.agent_phase = "executing"
                self.agent_task["status"] = "EXECUTING"
                self.agent_task["steps"] = [
                    {"title": "Process the request", "status": "running"},
                    {"title": "Review and report", "status": "pending"},
                ]
                self.append_chat("user", f"[{mode_label}] {title}")
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
            sandbox,
            "--color",
            "never",
            "--output-last-message",
            str(self.codex_last_message_path),
        ]
        images = self.pending_execution_images if approved_run else self.image_attachments()
        for image in images:
            args.extend(["--image", str(image)])
        args.append(process_prompt)
        self.codex_process.setArguments(args)
        self.codex_process.readyReadStandardOutput.connect(self.read_codex_stdout)
        self.codex_process.readyReadStandardError.connect(self.read_codex_stderr)
        self.codex_process.finished.connect(self.codex_finished)
        self.codex_process.start()
        self.codex_process.closeWriteChannel()
        if not needs_plan:
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
            self.log_agent_activity("AGENT", "Codex turn started")
            return
        if event_type == "turn.completed":
            usage = event.get("usage") or {}
            run_total = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
            self.codex_usage["last_run"] = run_total
            self.codex_usage["used"] = int(self.codex_usage.get("used", 0)) + run_total
            self.save_codex_usage()
            self.update_codex_usage_display()
            if self.agent_task:
                self.agent_task["usage"] = usage
                self.log_agent_activity("USAGE", "Token usage recorded", json.dumps(usage, sort_keys=True))
            return
        if item_type == "command_execution":
            command = item.get("command", "")
            if self.agent_phase == "planning":
                if event_type == "item.started":
                    self.agent_task["commands"].append({"command": command, "status": "running", "exit_code": None, "phase": "planning"})
                    self.log_agent_activity("PLAN INSPECTION", "Read-only command started", command, "running")
                elif event_type == "item.completed":
                    exit_code = item.get("exit_code")
                    for record in reversed(self.agent_task["commands"]):
                        if record["command"] == command and record["status"] == "running":
                            record["status"] = "completed" if exit_code == 0 else "failed"
                            record["exit_code"] = exit_code
                            break
                    self.log_agent_activity("PLAN INSPECTION", "Read-only command completed", f"{command}\nExit code: {exit_code}", "completed" if exit_code == 0 else "failed")
                return
            if event_type == "item.started":
                blocked = re.search(r"(^|[;&|]\s*)(sudo|pkexec|pacman|yay|paru|systemctl)\b|\brm\s+-[^\n]*r[^\n]*f\b|\bgit\s+(push|reset\s+--hard)\b", command, re.I)
                if blocked:
                    self.agent_task["status"] = "NEEDS APPROVAL"
                    self.log_agent_activity("PERMISSION", "Blocked privileged or destructive command", command, "failed")
                    self.append_chat("system", "Execution stopped: the agent attempted a privileged, destructive, or publishing command. Run that action separately with explicit confirmation.")
                    if self.codex_process and self.codex_process.state() != QProcess.NotRunning:
                        self.codex_process.kill()
                    return
                if self.agent_task:
                    verification = bool(re.search(r"\b(pytest|unittest|ruff|mypy|npm\s+test|pnpm\s+test|cargo\s+test|go\s+test|make\s+test)\b", command, re.I))
                    candidates = [
                        index for index, step in enumerate(self.agent_task["steps"])
                        if step["status"] == "pending" and (
                            not verification or re.search(r"test|verify|lint|check", step["title"], re.I)
                        )
                    ]
                    if candidates and not any(step["status"] == "running" for step in self.agent_task["steps"]):
                        self.set_agent_step(candidates[0], "running")
                    self.agent_task["commands"].append({"command": command, "status": "running", "exit_code": None})
                    self.log_agent_activity("COMMAND", "Command started", command, "running")
                self.append_chat("tool", f"Running command:\n{command}")
            elif event_type == "item.completed":
                output = (item.get("aggregated_output") or "").strip()
                exit_code = item.get("exit_code")
                if self.agent_task:
                    for record in reversed(self.agent_task["commands"]):
                        if record["command"] == command and record["status"] == "running":
                            record["status"] = "completed" if exit_code == 0 else "failed"
                            record["exit_code"] = exit_code
                            break
                    verification = bool(re.search(r"\b(pytest|unittest|ruff|mypy|npm\s+test|pnpm\s+test|cargo\s+test|go\s+test|make\s+test)\b", command, re.I))
                    running_steps = [index for index, step in enumerate(self.agent_task["steps"]) if step["status"] == "running"]
                    if running_steps:
                        self.set_agent_step(running_steps[0], "completed" if exit_code == 0 else "failed")
                    self.refresh_agent_files()
                    self.log_agent_activity("COMMAND", "Command completed", f"{command}\nExit code: {exit_code}", "completed" if exit_code == 0 else "failed")
                block = f"Executed command:\n{command}\nExit code: {exit_code}"
                if output:
                    block += f"\nOutput:\n{output}"
                self.append_chat("tool", block)
            return
        if item_type in ("file_change", "file_operation"):
            path = item.get("path") or item.get("file_path") or "workspace file"
            self.refresh_agent_files()
            self.log_agent_activity("FILE", "File operation", str(path))
            return
        if item_type in ("todo_list", "plan"):
            entries = item.get("items") or item.get("steps") or []
            if self.agent_task and entries:
                self.agent_task["steps"] = [
                    {"title": str(entry.get("text") or entry.get("title") or entry), "status": entry.get("status", "pending") if isinstance(entry, dict) else "pending"}
                    for entry in entries
                ]
                self.log_agent_activity("PLAN", "Agent plan updated", f"{len(entries)} step(s)")
            return
        if item_type == "agent_message":
            text = (item.get("text") or "").strip()
            if text:
                self.codex_answer_seen = True
                self.codex_current_answer = text
                if self.agent_phase == "planning":
                    self.log_agent_activity("PLAN", "Structured plan received", text[:1000])
                    return
                self.log_agent_activity("MESSAGE", "Agent response received", text[:1000])
                self.append_chat("assistant", text)

    def codex_finished(self, code, status):
        final = ""
        if self.codex_last_message_path and self.codex_last_message_path.exists():
            try:
                final = self.codex_last_message_path.read_text().strip()
            except Exception:
                final = ""
        if self.codex_last_message_path:
            try:
                self.codex_last_message_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.codex_last_message_path = None
        if self.agent_phase == "planning" and self.agent_task and self.agent_task.get("status") != "STOPPED":
            if code != 0:
                self.agent_task["status"] = "NEEDS ATTENTION"
                self.set_agent_step(0, "failed")
                self.log_agent_activity("PLAN", "Planning failed", f"Exit code: {code}", "failed")
                self.append_chat("system", "The read-only planning pass failed. Review the Plan log and submit the task again.")
            else:
                plan = self.parse_agent_plan(final or self.codex_current_answer)
                self.agent_task["title"] = plan["task"]
                self.agent_task["steps"] = plan["steps"]
                self.agent_task["estimated_impact"] = {
                    "files_to_inspect": plan["files_to_inspect"],
                    "likely_modified_files": plan["likely_modified_files"],
                    "commands": plan["commands"],
                    "privilege_required": plan["privilege_required"],
                    "network_required": plan["network_required"],
                    "risk_level": plan["risk_level"],
                }
                self.agent_task["status"] = "WAITING FOR APPROVAL"
                self.agent_task["approval_status"] = "pending"
                self.agent_task["execution_prompt"] = self.pending_execution_prompt
                self.agent_task["execution_title"] = self.pending_execution_title
                self.agent_task["execution_images"] = [str(path) for path in self.pending_execution_images]
                self.log_agent_activity("PLAN", "Plan ready for approval", f"{len(plan['steps'])} step(s)", "completed")
                self.append_chat("system", "The task plan is ready. Review it in the Plan tab, edit if needed, then choose APPROVE & RUN.")
                if hasattr(self, "agent_hub_tabs"):
                    self.agent_hub_tabs.setCurrentIndex(1)
            self.codex_status.setText("Waiting for approval" if code == 0 else "Planning failed")
            self.agent_phase = "waiting"
            self.save_agent_task()
            self.refresh_agent_task_ui()
            return
        if final and not self.codex_answer_seen:
            self.append_chat("assistant", final)
        elif self.codex_log_buffer.strip():
            if not self.codex_answer_seen:
                self.append_chat("system", "Codex finished, but no answer event was received.")
        else:
            self.append_chat("system", "Codex finished without output.")
        self.codex_status.setText("Ready")
        if self.agent_task:
            stopped = self.agent_task.get("status") == "STOPPED"
            self.agent_task["status"] = "STOPPED" if stopped else ("COMPLETE" if code == 0 else "NEEDS ATTENTION")
            self.agent_task["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            self.agent_task["finished_epoch"] = time.time()
            self.agent_paused = False
            self.task_pause.setText("PAUSE")
            if not stopped:
                for step in self.agent_task["steps"]:
                    if step["status"] == "running":
                        step["status"] = "completed" if code == 0 else "failed"
                self.agent_task["steps"][-1]["status"] = "completed" if code == 0 else "failed"
            self.refresh_agent_files()
            self.log_agent_activity("TASK", "Agent task finished", f"Exit code: {code}", "completed" if code == 0 else "failed")
        self.parent_window.add_history("Codex request completed in Command Terminal")

    def stop_codex(self):
        if self.codex_process and self.codex_process.state() != QProcess.NotRunning:
            if self.agent_task:
                self.agent_task["status"] = "STOPPED"
                for step in self.agent_task["steps"]:
                    if step["status"] == "running": step["status"] = "stopped"
                self.log_agent_activity("CONTROL", "Agent stopped by user", status="stopped")
            self.codex_process.kill()
            self.codex_status.setText("Stopped")
            self.append_chat("system", "Codex stopped.")
        if self.external_agent_process and self.external_agent_process.state() != QProcess.NotRunning:
            self.external_agent_process.kill(); self.codex_status.setText("Stopped"); self.append_chat("system", "External agent stopped.")

    def shutdown(self):
        self.stop_codex()
        if self.codex_last_message_path:
            try:
                self.codex_last_message_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.codex_last_message_path = None
        if self.fcc_server_process and self.fcc_server_process.state() != QProcess.NotRunning:
            self.fcc_server_process.terminate()
            if not self.fcc_server_process.waitForFinished(2000): self.fcc_server_process.kill()
        self.agent_executor.shutdown(wait=False, cancel_futures=True)

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
        self.deployment_state = self.load_deployment_state()
        self.overview_status = QLabel("--")
        self.overview_status.setObjectName("controlState")
        self.overview_status.setWordWrap(True)
        self.pipeline_status = QLabel("--")
        self.pipeline_status.setObjectName("controlState")
        self.pipeline_status.setWordWrap(True)
        self.build_list = QListWidget()
        self.validation_list = QListWidget()
        self.release_list = QListWidget()
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

        tabs = QTabWidget()
        tabs.addTab(self.overview_page(), "Overview")
        profiles_page = QWidget()
        profiles_layout = QVBoxLayout(profiles_page)
        profiles_layout.addWidget(self.status)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.tier_filter)
        reload_button = QPushButton("Reload Profiles")
        reload_button.clicked.connect(self.refresh)
        controls.addWidget(reload_button)
        new_button = QPushButton("New Workspace Profile")
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
        validate_button = QPushButton("Validate")
        validate_button.clicked.connect(self.validate_selected_profile)
        controls.addWidget(validate_button)
        compare_button = QPushButton("Compare")
        compare_button.clicked.connect(self.compare_selected_profile)
        controls.addWidget(compare_button)
        profiles_layout.addLayout(controls)

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
            ("Launch Workspace", self.launch_selected_deployment),
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
        profiles_layout.addWidget(split, 1)
        tabs.addTab(profiles_page, "Profiles")
        tabs.addTab(self.builds_page(), "Builds")
        tabs.addTab(self.validation_page(), "Validation")
        tabs.addTab(self.releases_page(), "Releases")
        layout.addWidget(tabs, 1)
        self.refresh()

    def default_deployment_state(self):
        return {
            "schema_version": 1,
            "system_profiles": [{
                "id": "commandos_workstation", "name": "CommandOS Workstation", "revision": 1,
                "type": "system_profile", "required_packages": ["base", "linux-commandos", "commandos-hooks", "commandos-settings"],
                "optional_packages": ["plasma-meta", "command-centre"], "services": [],
                "tool_collections": ["commandos-base"], "policies": {"release_channel": "development"},
            }],
            "build_targets": [{"id": "x86_64_iso", "name": "x86_64 ISO", "type": "iso"}],
            "build_jobs": [], "artifacts": [], "releases": [], "validation_reports": [],
        }

    def load_deployment_state(self):
        try:
            data = json.loads(DEPLOYMENT_STATE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and data.get("schema_version") == 1 else self.default_deployment_state()
        except Exception:
            return self.default_deployment_state()

    def save_deployment_state(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DEPLOYMENT_STATE_FILE.write_text(json.dumps(self.deployment_state, indent=2), encoding="utf-8")

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def overview_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        state, state_layout = self.panel("Deployment State")
        state_layout.addWidget(self.overview_status)
        layout.addWidget(state)
        pipeline, pipeline_layout = self.panel("Deployment Pipeline")
        pipeline_layout.addWidget(self.pipeline_status)
        layout.addWidget(pipeline)
        note = QLabel("Workspace Profiles configure the current session. System Profiles declare desired machine state. Build Targets produce immutable artifacts.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def builds_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.build_list)
        row = QHBoxLayout()
        create = QPushButton("NEW PLANNED BUILD")
        create.clicked.connect(self.create_planned_build)
        row.addWidget(create)
        row.addStretch()
        layout.addLayout(row)
        return page

    def validation_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        run = QPushButton("VALIDATE HOST & SELECTED PROFILE")
        run.clicked.connect(self.validate_selected_profile)
        layout.addWidget(run)
        layout.addWidget(self.validation_list)
        return page

    def releases_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.release_list)
        note = QLabel("A release can only reference a successful build with a verified artifact. Publishing remains disabled until a destination and signing policy are configured.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        return page

    def refresh(self):
        self.deployments = self.load_deployments()
        self.render_deployments()
        self.render_deployment_state()

    def load_json_file(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return validate_deployment_profiles(data, trusted_shell=path.resolve() == DEFAULT_DEPLOYMENTS_FILE.resolve())
        except (OSError, ValueError, ConfigValidationError):
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
            profile.setdefault("schema_version", 1)
            profile.setdefault("type", "workspace_profile")
            profile.setdefault("revision", 1)
            profile.setdefault("source", str(DEFAULT_DEPLOYMENTS_FILE))
        for profile in custom:
            profile["tier"] = "custom"
            profile.setdefault("schema_version", 1)
            profile.setdefault("type", "workspace_profile")
            profile.setdefault("revision", 1)
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
        profile.update({"schema_version": 1, "type": "workspace_profile", "revision": 1})
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
        updated.update({"schema_version": 1, "type": "workspace_profile"})
        if editing_default:
            updated["id"] = self.unique_profile_id(updated["name"], profiles)
            profiles.append(updated)
            message = f"Created editable custom copy: {updated['name']}"
        else:
            updated["id"] = profile.get("id")
            updated["revision"] = int(profile.get("revision", 1)) + 1
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
        duplicate["revision"] = 1
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
            item = QListWidgetItem(f"{profile.get('name', 'Workspace')}  ·  WORKSPACE PROFILE  ·  REV {profile.get('revision', 1)}\n{profile.get('summary', '')}")
            item.setData(Qt.UserRole, profile)
            self.list.addItem(item)
            shown += 1
            if selected_id and profile.get("id") == selected_id:
                item.setSelected(True)
        if not self.list.selectedItems() and self.list.count():
            self.list.item(0).setSelected(True)
        self.status.setText(f"{shown} shown / {len(self.deployments)} Workspace Profiles loaded · {len(self.deployment_state['system_profiles'])} System Profiles")
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

    def profile_hash(self, profile):
        canonical = {key: value for key, value in profile.items() if key not in ("source", "profile_hash")}
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def resolve_profile(self, profile):
        missing_required = []
        missing_optional = []
        available = 0
        for app in profile.get("apps", []):
            if self.component_status(app.get("command", "")) == "available":
                available += 1
            elif app.get("optional", False):
                missing_optional.append(f"{app.get('name', app.get('package', 'Unknown'))} · {app.get('package', 'no package declared')}")
            else:
                missing_required.append(f"{app.get('name', app.get('package', 'Unknown'))} · {app.get('package', 'no package declared')}")
        invalid_services = [service for service in profile.get("services", []) if not re.match(r"^[A-Za-z0-9_.@:-]+\.service$", service)]
        folders = [Path(os.path.expanduser(folder)) for folder in profile.get("folders", [])]
        return {"app_count": len(profile.get("apps", [])), "available_apps": available,
                "missing_required": missing_required, "missing_optional": missing_optional,
                "invalid_services": invalid_services, "folder_count": len(folders),
                "available_folders": sum(path.exists() for path in folders)}

    def validate_selected_profile(self):
        profile = self.selected_deployment()
        if not profile:
            self.result.setPlainText("Select a Workspace Profile first.")
            return
        resolution = self.resolve_profile(profile)
        checks = [
            self.validation_check("profile.schema", "Profile schema is supported", profile.get("schema_version") == 1, "FAIL"),
            self.validation_check("profile.identity", "Profile has a stable ID and name", bool(profile.get("id") and profile.get("name")), "FAIL"),
            self.validation_check("profile.commands", "Required applications are available", not resolution["missing_required"], "FAIL", resolution["missing_required"]),
            self.validation_check("profile.optional", "Optional applications are available", not resolution["missing_optional"], "WARN", resolution["missing_optional"]),
            self.validation_check("profile.services", "Service identifiers are valid", not resolution["invalid_services"], "FAIL", resolution["invalid_services"]),
            self.validation_check("host.disk", "Build host has at least 20 GiB free", shutil.disk_usage(APP_DIR).free >= 20 * 1024**3, "FAIL"),
            self.validation_check("host.packages", "Pacman package manager is available", command_exists("pacman"), "FAIL"),
            self.validation_check("host.build_tool", "Arch ISO build tooling is available", command_exists("mkarchiso"), "WARN"),
        ]
        report = {"id": f"validation-{int(time.time())}", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "profile_id": profile["id"], "profile_hash": self.profile_hash(profile), "checks": checks}
        self.deployment_state["validation_reports"].insert(0, report)
        self.deployment_state["validation_reports"] = self.deployment_state["validation_reports"][:50]
        self.save_deployment_state()
        self.render_deployment_state()
        failed = sum(check["status"] == "FAIL" for check in checks)
        warnings = sum(check["status"] == "WARN" for check in checks)
        self.result.setPlainText(f"Validation completed: {len(checks)-failed-warnings} passed · {warnings} warnings · {failed} failed\n\n" +
                                 "\n".join(f"{check['status']}  {check['message']}" + (f"\n  {', '.join(check['evidence'])}" if check.get("evidence") else "") for check in checks))

    def validation_check(self, check_id, message, passed, failure_status, evidence=None):
        return {"id": check_id, "message": message, "status": "PASS" if passed else failure_status,
                "evidence": evidence or [], "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def compare_selected_profile(self):
        profile = self.selected_deployment()
        if not profile:
            return
        resolution = self.resolve_profile(profile)
        services = profile.get("services", [])
        lines = [f"CURRENT SYSTEM → {profile.get('name', 'PROFILE').upper()}", "",
                 f"+ {len(resolution['missing_required'])} required applications missing",
                 f"+ {len(resolution['missing_optional'])} optional applications missing",
                 f"= {resolution['available_apps']} applications already available",
                 f"= {len(services)} services declared",
                 f"= {resolution['available_folders']} / {resolution['folder_count']} workspace paths present", "",
                 "No removals are inferred from absence. This Workspace Profile is additive and session-scoped."]
        self.result.setPlainText("\n".join(lines))

    def create_planned_build(self):
        profile = self.deployment_state["system_profiles"][0] if self.deployment_state["system_profiles"] else None
        target = self.deployment_state["build_targets"][0] if self.deployment_state["build_targets"] else None
        if not profile or not target:
            self.result.setPlainText("A System Profile and Build Target are required before creating a job.")
            return
        job_id = f"build-{len(self.deployment_state['build_jobs']) + 1:04d}"
        job = {"id": job_id, "schema_version": 1, "status": "PLANNED", "stage": "PROFILE",
               "created": time.strftime("%Y-%m-%d %H:%M:%S"), "profile_id": profile["id"],
               "profile_revision": profile.get("revision", 1), "profile_hash": self.profile_hash(profile),
               "target_id": target["id"], "logs": [], "artifacts": []}
        self.deployment_state["build_jobs"].insert(0, job)
        self.save_deployment_state()
        self.render_deployment_state()
        self.result.setPlainText(f"Created {job_id} as a PLANNED job.\n\nNo build command was executed. Resolve and validation stages must complete before build execution is enabled.")

    def render_deployment_state(self):
        jobs = self.deployment_state["build_jobs"]
        latest = jobs[0] if jobs else None
        reports = self.deployment_state["validation_reports"]
        latest_report = reports[0] if reports else None
        failed = sum(check["status"] == "FAIL" for check in latest_report.get("checks", [])) if latest_report else 0
        warnings = sum(check["status"] == "WARN" for check in latest_report.get("checks", [])) if latest_report else 0
        active_workspace = self.selected_deployment().get("name", "None") if self.selected_deployment() else "None"
        system_profile = self.deployment_state["system_profiles"][0]["name"] if self.deployment_state["system_profiles"] else "None"
        self.overview_status.setText(f"ACTIVE WORKSPACE  {active_workspace}\nSYSTEM PROFILE    {system_profile}\nLATEST BUILD      {latest['id'] + ' · ' + latest['status'] if latest else 'NOT BUILT'}\nVALIDATION        {failed} FAILURES · {warnings} WARNINGS\nRELEASES          {len(self.deployment_state['releases'])}")
        completed = latest.get("stage") if latest else "NONE"
        self.pipeline_status.setText(f"PROFILE  {'✓' if latest else '○'}  →  RESOLVE  ○  →  VALIDATE  {'⚠' if failed or warnings else '○'}  →  BUILD  ○\nTEST  ○  →  CHECKSUM  ○  →  ARCHIVE  ○  →  RELEASE  ○\nCurrent stage: {completed}")
        self.build_list.clear()
        for job in jobs:
            self.build_list.addItem(f"{job['id'].upper()}  ·  {job['status']}  ·  {job['stage']}\nProfile {job['profile_id']} revision {job['profile_revision']} · Target {job['target_id']}\nCreated {job['created']} · Hash {job['profile_hash'][:12]}")
        self.validation_list.clear()
        for report in reports:
            checks = report.get("checks", [])
            self.validation_list.addItem(f"{report['id']}  ·  {report['timestamp']}\n{sum(c['status']=='PASS' for c in checks)} PASS · {sum(c['status']=='WARN' for c in checks)} WARN · {sum(c['status']=='FAIL' for c in checks)} FAIL\nProfile {report['profile_id']} · {report['profile_hash'][:12]}")
        self.release_list.clear()
        for release in self.deployment_state["releases"]:
            self.release_list.addItem(f"{release.get('version', 'Unknown')} · {release.get('channel', 'development').upper()} · {release.get('status', 'DRAFT')}\nBuild {release.get('build_id', '--')}")

    def profile_detail(self, profile):
        lines = [
            profile.get("name", "Deployment"),
            "=" * len(profile.get("name", "Deployment")),
            "",
            profile.get("summary", ""),
            "",
            "Type: Workspace Profile",
            f"Schema: {profile.get('schema_version', 1)} · Revision: {profile.get('revision', 1)} · Hash: {self.profile_hash(profile)[:12]}",
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
        resolution = self.resolve_profile(profile)
        lines.extend(["", "Profile Resolution", "------------------",
                      f"Applications available: {resolution['available_apps']} / {resolution['app_count']}",
                      f"Required components missing: {len(resolution['missing_required'])}",
                      f"Optional components missing: {len(resolution['missing_optional'])}",
                      f"Invalid services: {len(resolution['invalid_services'])}",
                      f"Workspace paths available: {resolution['available_folders']} / {resolution['folder_count']}"])
        if resolution["missing_required"]:
            lines.extend(["", "Missing required:", *resolution["missing_required"]])
        if resolution["missing_optional"]:
            lines.extend(["", "Optional missing:", *resolution["missing_optional"]])
        return "\n".join(lines)

    def launch_selected_deployment(self):
        profile = self.selected_deployment()
        if not profile:
            return
        warning = profile.get("warning", "")
        message = f"Launch Workspace Profile?\n\n{profile.get('name')}\n\n{profile.get('summary', '')}"
        if warning:
            message += f"\n\nWARNING:\n{warning}"
        if not confirm(self, "Launch Deployment", message):
            return
        launched = []
        missing = []
        env = os.environ.copy()
        try:
            env.update(validate_environment(profile.get("environment", {})))
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked invalid deployment environment: {error}")
            return
        trusted_profile = Path(profile.get("source", "")).resolve() == DEFAULT_DEPLOYMENTS_FILE.resolve()

        for service in profile.get("services", []):
            try:
                service = validate_service(service)
            except ActionValidationError as error:
                missing.append(str(error))
                continue
            self.launch_terminal_command(f"Start {service}", f"systemctl --user start {shlex.quote(service)} || sudo systemctl start {shlex.quote(service)}")
            launched.append(f"service: {service}")

        for folder in profile.get("folders", []):
            self.open_path(folder)
            launched.append(f"folder: {folder}")

        for url in profile.get("urls", []):
            try:
                url = validate_url(url)
            except ActionValidationError as error:
                missing.append(str(error))
                continue
            if command_exists("xdg-open"):
                audited_launch(["xdg-open", url], action="open deployment URL", env=env)
                launched.append(f"url: {url}")

        for terminal in profile.get("terminals", []):
            try:
                cwd = validate_user_path(terminal.get("cwd", "~"))
                command = terminal.get("command", "exec bash")
                if not trusted_profile:
                    command = shlex.join(parse_program_command(command))
            except ActionValidationError as error:
                missing.append(str(error))
                continue
            launch_terminal(terminal.get("title", profile.get("name", "Deployment")), f"cd {shlex.quote(str(cwd))}; {command}")
            launched.append(f"terminal: {terminal.get('title', 'Terminal')}")

        for app in profile.get("apps", []):
            command = app.get("command", "")
            if not command:
                continue
            try:
                arguments = parse_program_command(command)
            except ActionValidationError as error:
                missing.append(f"{app.get('name', command)} ({error})")
                continue
            if self.component_status(arguments[0]) == "missing":
                missing.append(f"{app.get('name', command)} ({command})")
                continue
            audited_launch(arguments, action=f"launch deployment app: {app.get('name', arguments[0])}", env=env)
            launched.append(f"app: {app.get('name', command)}")

        self.result.setPlainText(
            "Launched:\n" + ("\n".join(launched) if launched else "Nothing launched.")
            + ("\n\nMissing components:\n" + "\n".join(missing) if missing else "")
        )
        self.parent_window.add_history(f"Deployment launched: {profile.get('name')}")

    def open_path(self, folder):
        try:
            path = validate_user_path(folder)
        except ActionValidationError as error:
            self.result.setPlainText(f"Blocked deployment folder: {error}")
            return
        path.mkdir(parents=True, exist_ok=True)
        if command_exists("xdg-open"):
            audited_launch(["xdg-open", str(path)], action="open deployment folder")

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
        trusted_profile = Path(profile.get("source", "")).resolve() == DEFAULT_DEPLOYMENTS_FILE.resolve()
        if not trusted_profile:
            try:
                command = shlex.join(parse_program_command(command))
            except ActionValidationError as error:
                self.result.setPlainText(f"Blocked custom quick action: {error}")
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
            "schema_version": 1,
            "type": "workspace_profile",
            "revision": 1,
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


class CommandAppsPage(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.widget_status = QLabel("Checking…")
        self.widget_status.setObjectName("muted")
        self.widget_install = QPushButton("Install")
        self.widget_install.setObjectName("primaryButton")
        self.widget_install.clicked.connect(self.install_command_widget)
        self.pdf_status = QLabel("Checking Command PDF…")
        self.pdf_status.setObjectName("muted")
        self.pdf_install = QPushButton("Install")
        self.pdf_install.setObjectName("primaryButton")
        self.pdf_install.clicked.connect(self.install_command_pdf)
        self.pdf_open = QPushButton("Open")
        self.pdf_open.clicked.connect(self.open_command_pdf)
        self.pdf_remove = QPushButton("Uninstall")
        self.pdf_remove.clicked.connect(self.uninstall_command_pdf)
        self.curated_apps_status = QLabel("Checking curated app collection…")
        self.curated_apps_status.setObjectName("muted")
        self.curated_apps_install = QPushButton("INSTALL ALL CURATED APPS")
        self.curated_apps_install.setObjectName("primaryButton")
        self.curated_apps_install.clicked.connect(self.install_curated_apps)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("textPanel")
        self.output.setMaximumHeight(150)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        title = QLabel("COMMAND APPS")
        title.setObjectName("heroTitle")
        subtitle = QLabel("OFFICIAL APPLICATIONS FOR COMMANDOS")
        subtitle.setObjectName("heroSubtitle")
        note = QLabel("Install and manage CommandOS applications from one trusted local catalogue. Every installation is previewed and confirmed first.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(note)

        cards = QGridLayout()
        cards.addWidget(self.command_widget_card(), 0, 0)
        cards.addWidget(self.command_pdf_card(), 0, 1)
        cards.addWidget(self.curated_apps_card(), 1, 0, 1, 2)
        cards.addWidget(self.command_centre_update_card(), 2, 0, 1, 2)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)

        result, result_layout = self.panel("Installation Output")
        result_layout.addWidget(self.output)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(hero)
        layout.addLayout(cards)
        layout.addWidget(result)
        layout.addStretch()
        self.refresh()

    def panel(self, title):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def command_widget_card(self):
        frame, layout = self.panel(f"CW   Command Widget · v{COMMAND_WIDGET_VERSION}")
        description = QLabel(
            "A KDE Plasma 6 system telemetry widget for CommandOS. It displays power mode, CPU, memory, GPU, storage, fans, network, VPN, and battery status."
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        features = QLabel("INCLUDES\n• Plasma desktop widget\n• Local telemetry collector\n• Local HTTP telemetry service\n• Automatic user-service startup")
        features.setObjectName("muted")
        features.setWordWrap(True)
        actions = QHBoxLayout()
        open_project = QPushButton("Open Installer Files")
        open_project.clicked.connect(self.open_widget_project)
        actions.addWidget(self.widget_install)
        actions.addWidget(open_project)
        actions.addStretch()
        layout.addWidget(description)
        layout.addWidget(features)
        layout.addStretch()
        layout.addWidget(self.widget_status)
        layout.addLayout(actions)
        return frame

    def command_pdf_card(self):
        frame, layout = self.panel("CP   Command PDF")
        description = QLabel(
            "Read, convert, edit, and visibly sign PDF documents with a private, local-first CommandOS application."
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        features = QLabel("INCLUDES\n• Native PDF viewer and trackpad gestures\n• Text boxes, page edits and visible signatures\n• PDF to DOCX, images and text\n• Drag-and-drop opening and PDF merging")
        features.setObjectName("muted")
        features.setWordWrap(True)
        actions = QHBoxLayout()
        actions.addWidget(self.pdf_install)
        actions.addWidget(self.pdf_open)
        actions.addWidget(self.pdf_remove)
        actions.addStretch()
        layout.addWidget(description)
        layout.addWidget(features)
        layout.addStretch()
        layout.addWidget(self.pdf_status)
        layout.addLayout(actions)
        return frame

    def curated_apps_card(self):
        frame, layout = self.panel("CA   Command Curated Apps")
        description = QLabel(
            "A portable collection of Command-selected applications for a fresh CachyOS installation. One click previews and installs everything in the collection that is not already present."
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        features = QLabel("INCLUDES\n• Official repository applications\n• Selected AUR applications\n• Selected Flatpak applications\n• Missing-app detection before installation")
        features.setObjectName("muted")
        features.setWordWrap(True)
        actions = QHBoxLayout()
        actions.addWidget(self.curated_apps_install)
        actions.addStretch()
        layout.addWidget(description)
        layout.addWidget(features)
        layout.addWidget(self.curated_apps_status)
        layout.addLayout(actions)
        return frame

    @staticmethod
    def valid_package_names(output):
        return sorted({name.strip() for name in output.splitlines() if re.fullmatch(r"[A-Za-z0-9@._+:-]+", name.strip())})

    def curated_apps_inventory(self):
        explicit_files = sorted(INVENTORY_DIR.glob("pacman-explicit-*.txt"), reverse=True)
        foreign_files = sorted(INVENTORY_DIR.glob("pacman-foreign-aur-*.txt"), reverse=True)
        flatpak_files = sorted(INVENTORY_DIR.glob("flatpak-apps-*.txt"), reverse=True)
        if not explicit_files:
            return {}
        explicit = set(self.valid_package_names(safe_read_text(explicit_files[0])))
        foreign = set(self.valid_package_names(safe_read_text(foreign_files[0]))) if foreign_files else set()
        flatpaks = []
        if flatpak_files:
            flatpaks = self.valid_package_names("\n".join(
                line.split("\t", 1)[0] for line in safe_read_text(flatpak_files[0]).splitlines()
            ))
        return {
            "repository_packages": sorted(explicit - foreign),
            "foreign_packages": sorted(explicit & foreign),
            "flatpak_apps": flatpaks,
        }

    def refresh_curated_apps_status(self):
        inventory = self.curated_apps_inventory()
        total = sum(len(inventory.get(key, [])) for key in ("repository_packages", "foreign_packages", "flatpak_apps"))
        if total:
            self.curated_apps_status.setText(
                f"● {total} CURATED APPS · {len(inventory.get('repository_packages', []))} repository · "
                f"{len(inventory.get('foreign_packages', []))} AUR/local · {len(inventory.get('flatpak_apps', []))} Flatpak"
            )
            self.curated_apps_install.setEnabled(True)
        else:
            self.curated_apps_status.setText("○ CURATED APP COLLECTION IS NOT INCLUDED")
            self.curated_apps_install.setEnabled(False)

    def install_curated_apps(self):
        inventory = self.curated_apps_inventory()
        if not inventory:
            QMessageBox.warning(self, "Command Curated Apps", "The curated app collection is not included in this installation.")
            return

        installed = set(self.valid_package_names(run_text(["pacman", "-Qq"], 20)[0])) if command_exists("pacman") else set()
        installed_flatpaks = set(self.valid_package_names(run_text(["flatpak", "list", "--app", "--columns=application"], 20)[0])) if command_exists("flatpak") else set()
        repository = [name for name in inventory.get("repository_packages", []) if name not in installed]
        foreign = [name for name in inventory.get("foreign_packages", []) if name not in installed]
        flatpaks = [name for name in inventory.get("flatpak_apps", []) if name not in installed_flatpaks]
        missing_count = len(repository) + len(foreign) + len(flatpaks)
        if not missing_count:
            self.output.setPlainText("Every app in the Command Curated Apps collection is already installed.")
            QMessageBox.information(self, "Command Curated Apps", "Every curated app is already installed.")
            return

        commands = []
        unavailable = []
        if repository:
            commands.append("sudo pacman -S --needed " + " ".join(shlex.quote(name) for name in repository))
        if foreign:
            helper = "yay" if command_exists("yay") else "paru" if command_exists("paru") else ""
            if helper:
                commands.append(f"{helper} -S --needed " + " ".join(shlex.quote(name) for name in foreign))
            else:
                unavailable.extend(foreign)
        if flatpaks:
            if command_exists("flatpak"):
                commands.append("flatpak install -y flathub " + " ".join(shlex.quote(name) for name in flatpaks))
            else:
                unavailable.extend(flatpaks)
        preview_names = repository + foreign + flatpaks
        preview = "\n".join(preview_names[:40])
        if len(preview_names) > 40:
            preview += f"\n… and {len(preview_names) - 40} more"
        warning = f"\n\n{len(unavailable)} item(s) need yay/paru or Flatpak and cannot be installed in this run." if unavailable else ""
        if not commands:
            QMessageBox.warning(self, "Command Curated Apps", f"No supported installer is available for the {missing_count} missing app(s).")
            return
        if not confirm(self, "Install Command Curated Apps", f"Install {missing_count - len(unavailable)} missing app(s) from the Command Curated Apps collection?\n\n{preview}{warning}\n\nThe package managers will show their own review and authorization prompts."):
            return
        command = " && ".join(commands)
        ok, terminal = launch_terminal("Install Command Curated Apps", command)
        self.output.setPlainText(f"Command Curated Apps installation started in {terminal}." if ok else terminal)
        if ok:
            self.parent_window.add_history(f"Command Curated Apps installation started: {missing_count - len(unavailable)} app(s)", category="APPLICATION")

    def command_centre_update_card(self):
        frame, layout = self.panel("CC   Command Centre Update")
        description = QLabel("Update from the public CommandOS package repository hosted on SourceForge. The updater configures pacman and retrieves the latest published release.")
        description.setWordWrap(True)
        description.setObjectName("muted")
        details = QLabel(f"CURRENT VERSION\n• v{APP_VERSION}\nSOURCE\n• SourceForge [commandos] repository\n• linux-commandos.sourceforge.io\n• HTTPS transport · system authorization required")
        details.setObjectName("muted")
        details.setWordWrap(True)
        actions = QHBoxLayout()
        self.command_centre_update = QPushButton("UPDATE COMMAND CENTRE")
        self.command_centre_update.setObjectName("primaryButton")
        self.command_centre_update.clicked.connect(self.update_command_centre)
        repository = QPushButton("Open Repository")
        repository.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://sourceforge.net/projects/linux-commandos/")))
        actions.addWidget(self.command_centre_update)
        actions.addWidget(repository)
        actions.addStretch()
        layout.addWidget(description)
        layout.addWidget(details)
        layout.addLayout(actions)
        return frame

    def update_command_centre(self):
        installer = RESOURCE_DIR / "install-command-centre-repo.sh"
        if not installer.is_file():
            QMessageBox.warning(self, "Command Centre Update", f"SourceForge repository updater is missing:\n{installer}")
            return
        if not confirm(
            self, "Update Command Centre",
            "Update Command Centre from the public SourceForge Arch repository?\n\n"
            "Pacman will request your system password and show the package transaction before updating.",
        ):
            return
        command = f"/bin/bash {shlex.quote(str(installer))} command-centre"
        ok, terminal = launch_terminal("Update Command Centre", command)
        self.output.setPlainText(
            f"SourceForge update started in {terminal}.\n\nRestart Command Centre after pacman finishes."
            if ok else terminal
        )
        if ok:
            self.parent_window.add_history("SourceForge Command Centre update started", category="UPDATE")

    def widget_installed(self):
        widget = Path.home() / ".local/share/plasma/plasmoids/telemetrywidget/metadata.json"
        daemon = Path.home() / ".local/bin/telemetry-daemon"
        http_daemon = Path.home() / ".local/bin/telemetry-http-daemon"
        return widget.exists() and daemon.exists() and http_daemon.exists()

    def command_pdf_user_installed(self):
        return (Path.home() / ".local/share/command-pdf/command_pdf.py").is_file() and (Path.home() / ".local/bin/command-pdf").exists()

    def command_pdf_installed(self):
        return self.command_pdf_user_installed() or command_exists("command-pdf")

    def refresh(self):
        installed = self.widget_installed()
        source_ready = (COMMAND_WIDGET_DIR / "install.sh").exists()
        if installed:
            self.widget_status.setText("● INSTALLED · Command Centre telemetry integration active")
            self.widget_install.setText("Reinstall / Update")
        elif source_ready:
            self.widget_status.setText("○ AVAILABLE · Installer included with Command Centre")
            self.widget_install.setText("Install")
        else:
            self.widget_status.setText("INSTALLER MISSING · Command Centre installation may be incomplete")
            self.widget_install.setText("Install unavailable")
        self.widget_install.setEnabled(source_ready)
        self.refresh_curated_apps_status()
        pdf_ready = (COMMAND_PDF_DIR / "install.sh").is_file()
        pdf_installed = self.command_pdf_installed()
        pdf_user_installed = self.command_pdf_user_installed()
        pdf_system_installed = command_exists("command-pdf") and not pdf_user_installed
        if pdf_system_installed:
            self.pdf_status.setText("● INSTALLED · Command PDF is managed by the system package manager")
            self.pdf_install.setText("Managed by pacman")
        elif pdf_user_installed:
            self.pdf_status.setText("● INSTALLED · User-local Command PDF application is ready")
            self.pdf_install.setText("Reinstall / Update")
        elif pdf_ready:
            self.pdf_status.setText("○ AVAILABLE · Installer included with Command Centre")
            self.pdf_install.setText("Install")
        else:
            self.pdf_status.setText("INSTALLER MISSING · Command Centre installation may be incomplete")
            self.pdf_install.setText("Install unavailable")
        self.pdf_install.setEnabled(pdf_ready and not pdf_system_installed)
        self.pdf_open.setEnabled(pdf_installed)
        self.pdf_remove.setEnabled(pdf_user_installed)

    def install_command_pdf(self):
        installer = RESOURCE_DIR / "install-command-centre-repo.sh"
        if not installer.is_file():
            QMessageBox.warning(self, "Command PDF", f"SourceForge package installer not found:\n{installer}")
            return
        action = "update" if self.command_pdf_installed() else "install"
        migration = "\n\nThe older user-local copy will be removed after the system package is installed." if self.command_pdf_user_installed() else ""
        if not confirm(self, f"{action.title()} Command PDF", f"Install Command PDF 1.1.0 from the SourceForge CommandOS repository?\n\nPacman will show the package transaction and request authorization.{migration}"):
            return
        command = f"/bin/bash {shlex.quote(str(installer))} command-pdf"
        if self.command_pdf_user_installed():
            command += f" && /bin/bash {shlex.quote(str(COMMAND_PDF_DIR / 'uninstall.sh'))}"
        ok, terminal = launch_terminal(f"{action.title()} Command PDF", command)
        self.output.setPlainText(f"Command PDF SourceForge {action} started in {terminal}." if ok else terminal)
        if ok:
            self.parent_window.add_history(f"Command PDF SourceForge {action} started", category="APPLICATION")

    def open_command_pdf(self):
        executable = Path.home() / ".local/bin/command-pdf"
        command = str(executable) if executable.exists() else shutil.which("command-pdf")
        if not command:
            QMessageBox.warning(self, "Command PDF", "Command PDF is not installed.")
            return
        log_path = CONFIG_DIR / "command-pdf-launch.log"
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen([command], stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True)
        log_handle.close()
        QTimer.singleShot(1200, lambda launched=process, log=log_path: self.finish_command_pdf_launch(launched, log))

    def finish_command_pdf_launch(self, process, log_path):
        exit_code = process.poll()
        if exit_code is None:
            self.output.setPlainText("Command PDF opened successfully.")
            self.parent_window.add_history("Command PDF opened", category="APPLICATION")
            return
        details = safe_read_text(log_path).strip() or f"Command PDF exited with code {exit_code}."
        self.output.setPlainText(details)
        QMessageBox.warning(self, "Command PDF", f"Command PDF could not start.\n\n{details[-1200:]}")

    def uninstall_command_pdf(self):
        uninstaller = COMMAND_PDF_DIR / "uninstall.sh"
        if not uninstaller.is_file() or not confirm(self, "Uninstall Command PDF", "Remove the user-local Command PDF installation?\n\nYour PDF documents will not be removed."):
            return
        result = subprocess.run(["/bin/bash", str(uninstaller)], cwd=str(COMMAND_PDF_DIR), check=False, capture_output=True, text=True, timeout=60)
        message = (result.stdout + "\n" + result.stderr).strip()
        self.output.setPlainText(message)
        if result.returncode == 0:
            self.parent_window.add_history("Command PDF uninstalled", category="APPLICATION")
        else:
            QMessageBox.warning(self, "Command PDF", message[-1400:])
        self.refresh()

    def install_command_widget(self):
        installer = RESOURCE_DIR / "install-command-centre-repo.sh"
        if not installer.exists():
            QMessageBox.warning(self, "Command Widget", f"SourceForge package installer not found:\n{installer}")
            self.refresh()
            return
        action = "update" if self.widget_installed() else "install"
        if not confirm(
            self,
            f"{action.title()} Command Widget",
            f"Install Command Widget 1.1.0 from SourceForge?\n\nPacman installs the published payload, then the user installer refreshes the Plasma widget and telemetry services.",
        ):
            return
        command = f"/bin/bash {shlex.quote(str(installer))} command-widget && command-widget-install"
        ok, terminal = launch_terminal(f"{action.title()} Command Widget", command)
        self.output.setPlainText(f"Command Widget SourceForge {action} started in {terminal}." if ok else terminal)
        if ok:
            self.parent_window.add_history(f"Command Widget SourceForge {action} started", category="APPLICATION")

    def open_widget_project(self):
        if COMMAND_WIDGET_DIR.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(COMMAND_WIDGET_DIR)))
        else:
            QMessageBox.information(self, "Command Widget", f"Bundled installer folder not found:\n{COMMAND_WIDGET_DIR}")


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


class SystemTimelineDialog(QDialog):
    def __init__(self, event_store, parent=None):
        super().__init__(parent)
        self.event_store = event_store
        self.setWindowTitle("Command Centre System Timeline")
        self.resize(920, 680)
        self.category = QComboBox()
        self.category.addItems(["ALL", "SYSTEM", "UPDATE", "POWER", "SECURITY", "NETWORK", "STORAGE", "SNAPSHOT", "DRIVER", "SERVICE", "COMMAND"])
        self.category.currentTextChanged.connect(self.refresh)
        self.events = QListWidget()
        self.events.setWordWrap(True)
        heading = QLabel("SYSTEM TIMELINE")
        heading.setObjectName("healthHeader")
        hint = QLabel("Persistent structured events from Command Centre. Newest events appear first.")
        hint.setObjectName("muted")
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(hint)
        layout.addWidget(self.category)
        layout.addWidget(self.events, 1)
        layout.addWidget(close)
        self.refresh()

    def refresh(self):
        self.events.clear()
        for row in self.event_store.recent(500, self.category.currentText()):
            stamp = row["created_utc"].replace("T", " ").replace("Z", " UTC")
            text = f"{stamp}   {row['severity']:<8}   {row['category']:<10}   {row['title']}"
            if row["detail"]:
                text += f"\n{row['detail']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, row["id"])
            self.events.addItem(item)


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


class SidebarNavButton(QAbstractButton):
    """Two-line navigation control with a smoothly animated cockpit accent."""

    def __init__(self, module_id, icon_name, title, subtitle, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        self.icon_name = icon_name
        self.title = title
        self.subtitle = subtitle
        self._hover_progress = 0.0
        self._collapsed = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(58)
        self.setToolTip("")
        self.animation = QPropertyAnimation(self, b"hoverProgress", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_hover_progress(self):
        return self._hover_progress

    def set_hover_progress(self, value):
        self._hover_progress = value
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event):
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        super().leaveEvent(event)

    def _animate_to(self, value):
        self.animation.stop()
        self.animation.setStartValue(self._hover_progress)
        self.animation.setEndValue(value)
        self.animation.start()

    def set_collapsed(self, collapsed):
        self._collapsed = collapsed
        self.setFixedHeight(48 if collapsed else 58)
        self.setToolTip(self.title if collapsed else "")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        active = self.isChecked()
        strength = 1.0 if active else self._hover_progress

        if strength > 0:
            base = QColor("#0b2536" if active else "#0a1d2a")
            base.setAlphaF(0.35 + strength * 0.55)
            painter.setBrush(base)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

            rail_height = rect.height() * (0.35 + strength * 0.65)
            rail = QRectF(rect.left(), rect.center().y() - rail_height / 2, 4, rail_height)
            rail_color = QColor("#2bd2ff")
            rail_color.setAlphaF(0.35 + strength * 0.65)
            painter.setBrush(rail_color)
            painter.drawRoundedRect(rail, 2, 2)

        icon_color = QColor("#eafaff" if active else "#8fa9bb")
        if not active:
            icon_color = self._mix(icon_color, QColor("#ffffff"), self._hover_progress)
        self._draw_icon(painter, QPointF(28 if not self._collapsed else self.width() / 2, self.height() / 2), icon_color)

        if not self._collapsed:
            title_color = QColor("#ffffff" if active else "#c4d2dc")
            title_color = self._mix(title_color, QColor("#ffffff"), self._hover_progress)
            painter.setPen(title_color)
            title_font = painter.font()
            title_font.setPixelSize(13)
            title_font.setWeight(QFont.DemiBold)
            painter.setFont(title_font)
            painter.drawText(QRectF(52, 9, self.width() - 62, 21), Qt.AlignLeft | Qt.AlignVCenter, self.title)

            painter.setPen(QColor("#88a0b0" if not active else "#a8c6d8"))
            subtitle_font = painter.font()
            subtitle_font.setPixelSize(11)
            subtitle_font.setWeight(QFont.Normal)
            painter.setFont(subtitle_font)
            painter.drawText(QRectF(52, 30, self.width() - 62, 18), Qt.AlignLeft | Qt.AlignVCenter, self.subtitle)

    @staticmethod
    def _mix(first, second, amount):
        amount = max(0.0, min(1.0, amount))
        return QColor(*(round(first.getRgb()[i] * (1 - amount) + second.getRgb()[i] * amount) for i in range(3)))

    def _draw_icon(self, painter, centre, color):
        """Draw a consistent set of 20 px monochrome line icons."""
        painter.save()
        painter.translate(centre)
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        if self.icon_name == "dashboard":
            painter.drawLine(-8, -1, 0, -8); painter.drawLine(0, -8, 8, -1)
            painter.drawRect(QRectF(-6, -1, 12, 9)); painter.drawLine(2, 8, 2, 3)
        elif self.icon_name == "package":
            painter.drawRect(QRectF(-8, -6, 16, 13)); painter.drawLine(-8, -6, 0, -1)
            painter.drawLine(8, -6, 0, -1); painter.drawLine(0, -1, 0, 7)
        elif self.icon_name == "tools":
            painter.drawRoundedRect(QRectF(-8, -5, 16, 12), 2, 2); painter.drawRect(QRectF(-3, -8, 6, 3))
            painter.drawLine(-8, 0, 8, 0)
        elif self.icon_name == "terminal":
            painter.drawRoundedRect(QRectF(-9, -7, 18, 14), 2, 2)
            painter.drawLine(-5, -3, -1, 0); painter.drawLine(-1, 0, -5, 3); painter.drawLine(1, 3, 5, 3)
        elif self.icon_name == "book":
            painter.drawRoundedRect(QRectF(-8, -7, 7, 14), 1, 1); painter.drawRoundedRect(QRectF(1, -7, 7, 14), 1, 1)
            painter.drawLine(0, -6, 0, 7)
        elif self.icon_name == "apps":
            for x, y in ((-6, -6), (2, -6), (-6, 2), (2, 2)):
                painter.drawRoundedRect(QRectF(x, y, 5, 5), 1, 1)
        else:  # intelligence / neural network
            painter.drawEllipse(QRectF(-7, -7, 14, 14)); painter.drawLine(-7, 0, 7, 0)
            painter.drawLine(0, -7, 0, 7); painter.drawEllipse(QRectF(-2, -2, 4, 4))
        painter.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Command Centre v{APP_VERSION}")
        if LOGO_FILE.exists():
            self.setWindowIcon(QIcon(str(LOGO_FILE)))
        self.resize(1280, 820)
        self.setMinimumSize(1120, 720)
        self.telemetry = {}
        self.system = {}
        self.pages = {}
        self.nav_buttons = {}
        self.nav_titles = {}
        self.sidebar_collapsed = False
        self.update_cache = None
        self.update_cache_time = 0
        self.change_history = []
        self.last_dashboard_state = {}
        self.event_store = SystemEventStore()
        self.probe_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="command-centre-probes")
        self.probe_future = None

        root = QWidget()
        root.setObjectName("appRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = QVBoxLayout()
        self.sidebar.setContentsMargins(8, 8, 8, 12)
        self.sidebar.setSpacing(0)
        self.stack = QStackedWidget()

        self.sidebar.addWidget(self.brand_widget())

        module_details = {module_id: (icon, title) for module_id, icon, title in MODULES}
        for section, module_ids in MODULE_SECTIONS:
            section_label = QLabel(section)
            section_label.setObjectName("sidebarSection")
            section_label.setFixedHeight(32)
            self.sidebar.addWidget(section_label)
            for module_id in module_ids:
                icon, title = module_details[module_id]
                button = SidebarNavButton(module_id, icon, title, MODULE_DESCRIPTIONS[module_id])
                button.clicked.connect(lambda checked=False, m=module_id: self.open_module(m))
                self.nav_buttons[module_id] = button
                self.nav_titles[module_id] = (icon, title)
                self.sidebar.addWidget(button)

        # Build pages independently from the visual sidebar grouping. Navigation
        # must remain stable when modules are moved between sidebar sections.
        for module_id, icon, title in MODULES:
            if module_id == "dashboard":
                page = DashboardPage(self)
            elif module_id == "control":
                page = ControlPage(self)
            elif module_id == "tools":
                page = ToolLibraryPage(self)
            elif module_id == "command_apps":
                page = CommandAppsPage(self)
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

        self.sidebar.addStretch(1)
        self.sidebar_status = self.status_widget()
        self.sidebar.addWidget(self.sidebar_status)
        self.sidebar_toggle = QPushButton("‹")
        self.sidebar_toggle.setObjectName("sidebarToggle")
        self.sidebar_toggle.setToolTip("Collapse sidebar (Ctrl+B)")
        self.sidebar_toggle.setFixedSize(32, 32)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        side = QWidget()
        side.setObjectName("sidebar")
        side.setLayout(self.sidebar)
        side.setFixedWidth(307)
        self.sidebar_widget = side
        shell.addWidget(side)
        shell.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.sidebar_toggle.setParent(root)
        self.sidebar_toggle.raise_()

        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_all)
        self.addAction(refresh_action)

        palette_action = QAction("Command Palette", self)
        palette_action.setShortcut("Ctrl+K")
        palette_action.triggered.connect(self.open_palette)
        self.addAction(palette_action)

        sidebar_action = QAction("Toggle Sidebar", self)
        sidebar_action.setShortcut("Ctrl+B")
        sidebar_action.triggered.connect(self.toggle_sidebar)
        self.addAction(sidebar_action)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(5000)

        self.probe_poll_timer = QTimer(self)
        self.probe_poll_timer.timeout.connect(self.finish_refresh)
        self.probe_poll_timer.start(100)

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

        self.brand_text = QLabel(
            "<span style='font-size:16px; font-weight:900;'>COMMAND CENTRE</span><br>"
            "<span style='font-size:11px; font-weight:600; color:#a9bac7;'>One system. One mission.</span><br>"
            f"<span style='font-size:10px; color:#6f899b;'>Version {APP_VERSION}</span>"
        )
        self.brand_text.setObjectName("brandText")
        layout.addWidget(logo)
        layout.addWidget(self.brand_text, 1)
        return frame

    def status_widget(self):
        frame = QFrame()
        frame.setObjectName("sidebarStatus")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(5)
        self.sidebar_health = QLabel("●  Checking")
        self.sidebar_health.setObjectName("sidebarHealth")
        self.sidebar_battery = QLabel("Battery    —")
        self.sidebar_vpn = QLabel("VPN        Checking")
        self.sidebar_updates = QLabel("Updates    —")
        for label in (self.sidebar_health, self.sidebar_battery, self.sidebar_vpn, self.sidebar_updates):
            layout.addWidget(label)
        return frame

    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        collapsed = self.sidebar_collapsed
        self.sidebar_widget.setFixedWidth(70 if collapsed else 307)
        self.brand_text.setVisible(not collapsed)
        self.sidebar_status.setVisible(not collapsed)
        for label in self.sidebar_widget.findChildren(QLabel, "sidebarSection"):
            label.setVisible(not collapsed)
        self.sidebar_toggle.setText("›" if collapsed else "‹")
        self.sidebar_toggle.setToolTip(("Expand" if collapsed else "Collapse") + " sidebar (Ctrl+B)")
        for button in self.nav_buttons.values():
            button.set_collapsed(collapsed)
        self.position_sidebar_toggle()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_sidebar_toggle()

    def position_sidebar_toggle(self):
        if hasattr(self, "sidebar_toggle"):
            x = self.sidebar_widget.width() - self.sidebar_toggle.width() // 2
            y = max(12, self.centralWidget().height() - 54)
            self.sidebar_toggle.move(x, y)
            self.sidebar_toggle.raise_()

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
        if module_id == "command_apps":
            self.pages["command_apps"].refresh()
        self.setGeometry(geometry)
        QTimer.singleShot(0, lambda saved=geometry: self.setGeometry(saved))

    def open_palette(self):
        dialog = PaletteDialog(self)
        dialog.exec()

    def open_dashboard_drawer(self, title, content):
        if not hasattr(self, "dashboard_drawer"):
            self.dashboard_drawer = QDockWidget("System Details", self)
            self.dashboard_drawer.setObjectName("dashboardDrawer")
            self.dashboard_drawer.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.dashboard_drawer.setMinimumWidth(430)
            host = QWidget()
            layout = QVBoxLayout(host)
            layout.setContentsMargins(12, 12, 12, 12)
            self.drawer_title = QLabel("SYSTEM DETAILS")
            self.drawer_title.setObjectName("healthHeader")
            self.drawer_content = QPlainTextEdit()
            self.drawer_content.setReadOnly(True)
            self.drawer_content.setObjectName("textPanel")
            refresh = QPushButton("REFRESH FROM DASHBOARD")
            refresh.clicked.connect(lambda: self.pages["dashboard"].open_detail(getattr(self, "drawer_key", "cpu")))
            layout.addWidget(self.drawer_title)
            layout.addWidget(self.drawer_content, 1)
            layout.addWidget(refresh)
            self.dashboard_drawer.setWidget(host)
            self.addDockWidget(Qt.RightDockWidgetArea, self.dashboard_drawer)
        title_to_key = {
            "CPU DETAILS": "cpu", "GPU DETAILS": "gpu", "MEMORY DETAILS": "memory",
            "STORAGE ACTIVITY": "storage", "BATTERY & POWER": "power", "NETWORK DETAILS": "network",
            "SECURITY REPORT": "security", "DISK & SNAPSHOT DETAILS": "disk",
            "KERNEL & DRIVER DETAILS": "kernel", "READINESS SCORE": "readiness", "ACTION CENTRE": "alerts",
        }
        self.drawer_key = title_to_key.get(title, "cpu")
        self.dashboard_drawer.setWindowTitle(title.title())
        self.drawer_title.setText(title)
        self.drawer_content.setPlainText(content)
        self.dashboard_drawer.show()
        self.dashboard_drawer.raise_()

    def add_history(self, message, category="COMMAND", severity="INFO", detail=""):
        stamp = time.strftime("%H:%M")
        self.change_history.insert(0, f"{stamp}  {message}")
        self.change_history = self.change_history[:20]
        self.event_store.add(
            category, message, severity=severity, detail=detail,
            dedupe_key=f"{category}:{message}", dedupe_seconds=300,
        )

    def show_system_timeline(self):
        SystemTimelineDialog(self.event_store, self).exec()

    def refresh_all(self):
        if self.probe_future is None:
            self.probe_future = self.probe_executor.submit(self.collect_dashboard_snapshot)

    def collect_dashboard_snapshot(self):
        telemetry = read_telemetry()
        telemetry["_telemetry_available"] = bool(telemetry)
        telemetry["gpu_devices"] = detected_gpu_devices()
        gpu_operating = self.gpu_operating_state()
        kernel = run_text(["uname", "-r"])[0] or os.uname().release
        uptime = run_text(["uptime", "-p"])[0] or "--"
        failed = run_text(["systemctl", "--failed", "--no-legend", "--no-pager"], 2)[0]
        system = {
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
            "filesystem": run_text(["findmnt", "-no", "FSTYPE", "/"], 2)[0] or "Unknown",
            "snapshot": self.snapshot_state(),
            "battery": self.battery_state(),
            "security": self.security_state(),
            "latency": self.network_latency(),
            "dns": self.dns_state(),
            "cpu_governor": self.cpu_governor(),
            "boot_time": self.boot_time(),
            "reboot_required": "required" if Path("/var/run/reboot-required").exists() else "not required",
            "gpu_driver": gpu_operating["driver"],
            "gpu_power": gpu_operating["power"],
            "gpu_state": gpu_operating["state"],
            "activity": self.recent_activity(),
        }
        system["thermal_lines"] = self.thermal_lines(telemetry)
        return telemetry, system

    def finish_refresh(self):
        if self.probe_future is None or not self.probe_future.done():
            return
        future = self.probe_future
        self.probe_future = None
        try:
            telemetry, system = future.result()
        except Exception as error:
            self.add_history(f"Dashboard probe failed: {error}")
            return
        self.record_dashboard_transitions(telemetry, system)
        system["activity"] = self.recent_activity(telemetry)
        self.telemetry = telemetry
        self.system = system
        self.update_sidebar_status()
        self.pages["dashboard"].refresh(self.telemetry, self.system)
        control_page = self.pages.get("control")
        if control_page and self.stack.currentWidget() is control_page:
            control_page.refresh()

    def update_sidebar_status(self):
        healthy = self.system.get("failed", 0) == 0
        self.sidebar_health.setText("●  Healthy" if healthy else "●  Attention required")
        self.sidebar_health.setProperty("state", "healthy" if healthy else "warning")
        self.sidebar_health.style().unpolish(self.sidebar_health)
        self.sidebar_health.style().polish(self.sidebar_health)
        battery = self.telemetry.get("battery_percent", "—")
        self.sidebar_battery.setText(f"Battery    {battery}%" if str(battery) not in ("—", "--", "") else "Battery    —")
        vpn = str(self.telemetry.get("vpn_status", "Unknown"))
        self.sidebar_vpn.setText(f"VPN        {vpn.title()}")
        updates = self.system.get("updates")
        self.sidebar_updates.setText(f"Updates    {updates if updates is not None else '—'}")

    def record_dashboard_transitions(self, telemetry, system):
        current = {
            "telemetry": telemetry.get("_telemetry_available", bool(telemetry)),
            "power": metric_value(telemetry, "power_profile_label", "Unknown"),
            "updates": system.get("updates"),
            "failed": system.get("failed", 0),
            "network": system.get("connection", "Unknown"),
            "vpn": telemetry.get("vpn_status", "Unknown"),
            "ssh": system.get("security", {}).get("ssh", "Unknown"),
            "gpu": system.get("gpu_state", "unknown"),
            "snapshot": system.get("snapshot", "Unknown"),
        }
        previous = self.last_dashboard_state
        if not previous:
            stored = self.event_store.observed_states()
            previous = self.event_store.decode_observed_states(stored)
        if previous:
            if current["telemetry"] != previous.get("telemetry"):
                title = "Telemetry restored" if current["telemetry"] else "Telemetry connection lost"
                self.add_history(title, category="SYSTEM", severity="INFO" if current["telemetry"] else "WARNING")
            if current["power"] != previous.get("power"):
                self.add_history(f"Profile changed: {previous.get('power', 'Unknown')} → {current['power']}", category="POWER")
            if current["updates"] != previous.get("updates") and current["updates"] is not None:
                title = "System packages are current" if current["updates"] == 0 else f"{current['updates']} updates detected"
                self.add_history(title, category="UPDATE", severity="WARNING" if current["updates"] else "INFO")
            if current["failed"] != previous.get("failed"):
                title = "Failed services cleared" if current["failed"] == 0 else f"{current['failed']} failed services detected"
                self.add_history(title, category="SERVICE", severity="WARNING" if current["failed"] else "INFO")
            if current["network"] != previous.get("network"):
                self.add_history(f"Connection changed: {previous.get('network', 'Unknown')} → {current['network']}", category="NETWORK")
            if current["vpn"] != previous.get("vpn"):
                vpn_on = str(current["vpn"]).upper() not in ("", "OFF", "VPN OFF", "DISCONNECTED", "UNKNOWN")
                self.add_history("VPN connection established" if vpn_on else "VPN connection disconnected", category="NETWORK", severity="INFO" if vpn_on else "WARNING")
            if current["ssh"] != previous.get("ssh"):
                active = current["ssh"] == "active"
                self.add_history("SSH service started" if active else "SSH service stopped", category="SECURITY", severity="WARNING" if active else "INFO")
            if current["gpu"] != previous.get("gpu"):
                match = re.search(r"\b(P\d+)\b", current["gpu"], re.I)
                title = f"NVIDIA GPU entered {match.group(1).upper()}" if match else f"NVIDIA GPU state changed to {current['gpu']}"
                self.add_history(title, category="POWER")
            if current["snapshot"] != previous.get("snapshot"):
                self.add_history(f"Snapshot state changed: {previous.get('snapshot', 'Unknown')} → {current['snapshot']}", category="SNAPSHOT")
        self.event_store.save_observed_states(current)
        self.last_dashboard_state = current

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

    def cpu_governor(self):
        path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        try:
            return path.read_text().strip()
        except OSError:
            return "unknown"

    def gpu_operating_state(self):
        if not command_exists("nvidia-smi"):
            return {"driver": "not detected", "power": "--", "state": "unavailable"}
        output = run_text([
            "nvidia-smi", "--query-gpu=driver_version,power.draw,pstate",
            "--format=csv,noheader,nounits",
        ], 3)[0]
        if not output:
            return {"driver": "unknown", "power": "--", "state": "suspended"}
        parts = [part.strip() for part in output.splitlines()[0].split(",")]
        driver = parts[0] if parts else "unknown"
        power = f"{parts[1]} W" if len(parts) > 1 and parts[1] not in ("", "[N/A]") else "power unknown"
        pstate = parts[2] if len(parts) > 2 else "unknown"
        return {"driver": driver, "power": power, "state": f"awake {pstate}"}

    def battery_state(self):
        batteries = sorted(Path("/sys/class/power_supply").glob("BAT*"))
        if not batteries:
            return {"status": "Not present", "health": "--", "power": "--"}
        battery = batteries[0]
        def read_number(name):
            try: return float((battery / name).read_text().strip())
            except (OSError, ValueError): return 0
        try: status = (battery / "status").read_text().strip()
        except OSError: status = "Unknown"
        full = read_number("energy_full") or read_number("charge_full")
        design = read_number("energy_full_design") or read_number("charge_full_design")
        health = f"{full / design * 100:.0f}%" if full and design else "Unknown"
        watts = read_number("power_now") / 1_000_000
        return {"status": status, "health": health, "power": f"{watts:.1f} W" if watts else "Unknown"}

    def security_state(self):
        boot = run_text(["bootctl", "status"], 3)[0] if command_exists("bootctl") else ""
        secure = "Enabled" if re.search(r"Secure Boot:\s+enabled", boot, re.I) else "Disabled" if re.search(r"Secure Boot:\s+disabled", boot, re.I) else "Unknown"
        source = run_text(["findmnt", "-no", "SOURCE", "/"], 2)[0]
        encryption = "Enabled" if "/dev/mapper/" in source else "Disabled"
        ssh = run_text(["systemctl", "is-active", "sshd.service"], 2)[0] or "inactive"
        ports = run_text(["ss", "-lntuH"], 2)[0] if command_exists("ss") else ""
        return {"secure_boot": secure, "encryption": encryption, "ssh": ssh, "ports": len([line for line in ports.splitlines() if line.strip()])}

    def network_latency(self):
        if not command_exists("ping"):
            return "Unavailable"
        route = run_text(["ip", "route", "show", "default"], 2)[0]
        match = re.search(r"\bvia\s+(\S+)", route)
        if not match:
            return "Unavailable"
        output = run_text(["ping", "-c", "1", "-W", "1", match.group(1)], 2)[0]
        latency = re.search(r"time[=<]([0-9.]+)\s*ms", output)
        return f"{latency.group(1)} ms" if latency else "No response"

    def dns_state(self):
        if command_exists("resolvectl"):
            output = run_text(["resolvectl", "status"], 3)[0]
            return "Ready" if "DNS Servers:" in output else "Unknown"
        return "Ready" if Path("/etc/resolv.conf").exists() else "Unavailable"

    def snapshot_state(self):
        if not command_exists("snapper"):
            return "Unavailable"
        output = run_text(["snapper", "list", "--csvout"], 5)[0]
        rows = [row for row in output.splitlines() if row.strip()]
        return f"{max(0, len(rows) - 1)} available" if rows else "None found"

    def boot_time(self):
        output = run_text(["systemd-analyze"], 4)[0]
        match = re.search(r"=\s+(.+?)\s*$", output)
        return match.group(1) if match else (output or "Unknown")

    def thermal_lines(self, telemetry):
        readings = []
        for label, key in (("CPU", "cpu_temp"), ("GPU", "gpu_temp")):
            value = float(telemetry.get(key) or 0)
            status = "CRITICAL" if value >= 80 else "ELEVATED" if value >= 70 else "NORMAL"
            readings.append(f"{label:<8} {value:.0f}°C · {status}")
        nvme_temps = []
        for path in Path("/sys/class/nvme").glob("nvme*/device/hwmon/hwmon*/temp1_input"):
            try: nvme_temps.append(float(path.read_text().strip()) / 1000)
            except (OSError, ValueError): pass
        if nvme_temps:
            value = max(nvme_temps)
            status = "CRITICAL" if value >= 80 else "ELEVATED" if value >= 70 else "NORMAL"
            readings.append(f"NVMe     {value:.0f}°C · {status}")
        return readings

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

    def recent_activity(self, data=None):
        rows = self.event_store.recent(7)
        if not rows:
            return ["No meaningful system events recorded yet."]
        return [
            f"{row['created_utc'][11:16]}  {row['category']:<9} {row['title']}"
            for row in rows
        ]

    def closeEvent(self, event):
        offline = self.pages.get("offline")
        if offline and hasattr(offline, "shutdown"):
            offline.shutdown()
        tools_page = self.pages.get("tools")
        if tools_page and hasattr(tools_page, "shutdown"):
            tools_page.shutdown()
        software_page = self.pages.get("software")
        if software_page and hasattr(software_page, "shutdown"):
            software_page.shutdown()
        command_page = self.pages.get("command_code")
        if command_page and hasattr(command_page, "shutdown"):
            command_page.shutdown()
        intel_page = self.pages.get("intel")
        if intel_page and hasattr(intel_page, "shutdown"):
            intel_page.shutdown()
        self.probe_executor.shutdown(wait=False, cancel_futures=True)
        self.event_store.close()
        super().closeEvent(event)


def main():
    os.umask(0o077)
    harden_private_storage()
    crash_dir = Path.home() / ".local/state/command-centre"
    crash_dir.mkdir(parents=True, exist_ok=True)

    def report_crash(error_type, error, error_traceback):
        report = "".join(traceback.format_exception(error_type, error, error_traceback))
        (crash_dir / "crash.log").write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n{report}", encoding="utf-8")
        sys.__excepthook__(error_type, error, error_traceback)

    sys.excepthook = report_crash
    ensure_codex_on_path()
    app = QApplication(sys.argv)
    app.setApplicationName("Command Centre")
    app.setApplicationDisplayName("Command Centre")
    desktop_entries = (
        Path.home() / ".local/share/applications/command-centre.desktop",
        Path("/usr/share/applications/command-centre.desktop"),
    )
    if any(path.is_file() for path in desktop_entries):
        app.setDesktopFileName("command-centre")
    if LOGO_FILE.exists():
        app.setWindowIcon(QIcon(str(LOGO_FILE)))
    splash = None
    if SPLASH_FILE.is_file():
        splash_pixmap = QPixmap(str(SPLASH_FILE))
        if not splash_pixmap.isNull():
            splash_pixmap = splash_pixmap.scaled(
                1200,
                800,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            splash = QSplashScreen(splash_pixmap)
            splash.show()
            app.processEvents()
    app.setStyleSheet(
        """
        QWidget {
            background: #030910;
            color: #e9f3fb;
            font-family: Segoe UI, Inter, sans-serif;
            font-size: 13px;
            selection-background-color: #1677b9;
            selection-color: #ffffff;
        }
        QLabel {
            background: transparent;
            border: 0;
        }
        #appRoot {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #02070c, stop:0.58 #06111a, stop:1 #010509);
        }
        #sidebar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #07131d, stop:0.52 #05101a, stop:1 #020a11);
            border-right: 1px solid #16415d;
        }
        #brand {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #091925, stop:0.55 #06111a, stop:1 #03101a);
            border: 1px solid #135077;
            border-radius: 9px;
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
        #sidebarSection {
            color: #5f8298;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: 2px;
            padding: 12px 10px 4px 10px;
        }
        #sidebarStatus {
            background: rgba(5, 17, 26, 190);
            border: 0;
            border-top: 1px solid #16415d;
            border-bottom: 1px solid #102f43;
            margin: 10px 8px 4px 8px;
        }
        #sidebarStatus QLabel {
            color: #91a8b8;
            font-size: 11px;
            font-weight: 650;
        }
        #sidebarHealth[state="healthy"] { color: #45dc79; font-weight: 800; }
        #sidebarHealth[state="warning"] { color: #f5b83d; font-weight: 800; }
        #sidebarToggle {
            background: #0d2637;
            border: 1px solid #2789ba;
            border-radius: 16px;
            color: #dff7ff;
            font-size: 22px;
            font-weight: 700;
            padding: 0;
        }
        #sidebarToggle:hover {
            background: #16415d;
            border-color: #35cfff;
            color: #ffffff;
        }
        #hero {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #071722, stop:0.55 #03101a, stop:1 #02090f);
            border: 1px solid #15577f;
            border-radius: 10px;
        }
        #heroLogo {
            background: #020406;
            border: 1px solid #1b8bd2;
            border-radius: 8px;
        }
        #heroEyebrow {
            color: #4abfff;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 3px;
        }
        #heroTitle {
            color: #f6f9fb;
            font-size: 42px;
            font-weight: 900;
            letter-spacing: 3px;
        }
        #heroSubtitle {
            color: #00AEEF;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 8px;
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
        #heroStatus {
            background: transparent;
            border: 0;
            border-top: 1px solid #123b56;
            padding: 8px 0 1px 0;
            color: #d4e5f2;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        #softwareHeader {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0B1520, stop:1 #071019);
            border: 1px solid #16415D;
            border-radius: 11px;
        }
        #softwarePageTitle {
            color: #F2F6FA;
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 2px;
        }
        #softwareSubtitle {
            color: #28C8FF;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 3px;
        }
        #softwareAttention {
            color: #B4C3CE;
            font-size: 12px;
            font-weight: 800;
            padding: 2px 0;
        }
        #softwareAttention[state="success"] { color: #35D66B; }
        #softwareAttention[state="warning"] { color: #FFD166; font-size: 13px; font-weight: 900; }
        #softwareAttention[state="critical"] { color: #F05B5B; }
        #softwareStatusChip {
            background: #09131D;
            border: 1px solid #153044;
            border-radius: 7px;
            min-width: 92px;
            padding: 4px 7px;
            color: #A3B1BD;
            font-size: 11px;
            font-weight: 800;
        }
        #softwareStatusChip[state="success"] { color: #35D66B; border-color: #205C3A; }
        #softwareStatusChip[state="warning"] { color: #F5B83D; border-color: #614B20; }
        #softwareStatusChip[state="critical"] { color: #F05B5B; border-color: #6B2929; }
        #softwareStatusChip[state="info"] { color: #28C8FF; border-color: #164B67; }
        #softwareTabs::pane { border: 1px solid #153044; border-radius: 9px; background: #071019; }
        #softwareTabs QTabBar::tab { min-height: 26px; padding: 7px 14px; background: #09131D; font-size: 12px; }
        #softwareTabs QTabBar::tab:selected { background: #0E1A26; color: #FFFFFF; border-color: #16B9F3; border-bottom: 2px solid #28C8FF; }
        #softwareTabs QTabBar::tab:hover { background: #122535; color: #FFFFFF; }
        #softwareSubPage { background: transparent; }
        #softwareSectionHeader {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0D1C28, stop:1 #08121B);
            border: 1px solid #1A4A67;
            border-radius: 10px;
        }
        #softwareSectionIcon {
            color: #2BC4FF;
            background: #0B2231;
            border: 1px solid #1C5877;
            border-radius: 8px;
            font-size: 22px;
            font-weight: 900;
        }
        #softwareSectionTitle { color: #F2F6FA; font-size: 18px; font-weight: 900; letter-spacing: 2px; }
        #softwareSectionSubtitle { color: #2BC4FF; font-size: 10px; font-weight: 800; letter-spacing: 3px; }
        #softwareSubPageCard {
            background: #08111A;
            border: 1px solid #183D56;
            border-radius: 12px;
        }
        #softwareStatusBlock {
            background: #091722;
            border: 1px solid #173C54;
            border-radius: 7px;
            padding: 9px 11px;
            color: #C8D5DE;
            font-size: 12px;
            font-weight: 650;
        }
        #softwareSearch, #softwareCombo {
            background: #071019;
            border: 1px solid #1A4A67;
            border-radius: 7px;
            padding: 9px 11px;
            color: #EAF3F8;
            font-size: 12px;
        }
        #softwareSearch:focus, #softwareCombo:hover { border-color: #2BC4FF; background: #0B1A26; }
        QListWidget#softwareList {
            background: #060C12;
            border: 1px solid #17384D;
            border-radius: 8px;
            color: #D8E4EC;
            font-size: 12px;
            outline: 0;
        }
        QListWidget#softwareList::item { padding: 11px 12px; border-bottom: 1px solid #152C3C; }
        QListWidget#softwareList::item:hover { background: #0D2130; border-left: 3px solid #2BC4FF; }
        QListWidget#softwareList::item:selected { background: #12334A; color: #FFFFFF; border-left: 3px solid #35CFFF; }
        #softwareSectionButton, #softwarePrimaryAction {
            min-height: 22px;
            padding: 7px 12px;
            border: 1px solid #28516C;
            border-radius: 7px;
            color: #E2EDF4;
            font-size: 11px;
            font-weight: 800;
        }
        #softwareSectionButton { background: #0C1B27; }
        #softwarePrimaryAction { background: #0D3B57; border-color: #2BC4FF; color: #FFFFFF; }
        #softwareSectionButton:hover, #softwarePrimaryAction:hover { background: #15354A; border-color: #35CFFF; }
        #softwareMetricCard {
            background: #0B1520;
            border: 1px solid #16415D;
            border-radius: 11px;
            min-height: 112px;
        }
        #softwareMetricCard[accent="#F5B83D"] { border-top: 2px solid #F5B83D; }
        #softwareMetricCard[accent="#35D66B"] { border-top: 2px solid #35D66B; }
        #softwareMetricCard[accent="#16B9F3"] { border-top: 2px solid #16B9F3; }
        #softwareMetricCard[accent="#F0A72B"] { border-top: 2px solid #F0A72B; }
        #softwareMetricCard[accent="#A65DFF"] { border-top: 2px solid #A65DFF; }
        #softwareMetricIcon {
            color: #28C8FF;
            background: #0D2130;
            border: 1px solid #16415D;
            border-radius: 7px;
            font-size: 25px;
            font-weight: 800;
        }
        #softwareMetricTitle { color: #B1C0CA; font-size: 12px; font-weight: 800; letter-spacing: 1px; }
        #softwareMetricValue { color: #F2F6FA; font-size: 34px; font-weight: 900; }
        #softwareMetricDetail { color: #91A4B1; font-size: 11px; font-weight: 650; }
        #softwareChecklist {
            color: #CAD5DD;
            font-family: JetBrains Mono, Cascadia Code, monospace;
            font-size: 12px;
            line-height: 120%;
        }
        #softwareMiniPanel, #impactColumn {
            background: #09131D;
            border: 1px solid #153044;
            border-radius: 8px;
        }
        #softwareMiniTitle { color: #28C8FF; font-size: 11px; font-weight: 850; letter-spacing: 1px; }
        #softwareMiniBody { color: #F1F6FA; font-size: 17px; font-weight: 900; }
        #softwareMiniDetail { color: #B8C6CF; font-size: 12px; font-weight: 650; }
        #softwareTrend { color: #FFFFFF; font-size: 10px; font-weight: 750; }
        #softwareTrend[direction="up"] { color: #42E978; }
        #softwareTrend[direction="down"] { color: #FFBF32; }
        #softwareIntelBadge {
            background: #102334;
            border: 1px solid #1C4D69;
            border-radius: 5px;
            padding: 2px 5px;
            color: #28C8FF;
            font-size: 9px;
            font-weight: 850;
        }
        #softwareIntelBadge[state="success"] { color: #35D66B; background: #10271B; border-color: #275D3B; }
        #softwareIntelBadge[state="warning"] { color: #F5B83D; background: #2B2312; border-color: #66501F; }
        #softwareIntelBadge[state="critical"] { color: #F05B5B; background: #2C171A; border-color: #652D34; }
        #softwareActionButton {
            background: #0D1A25;
            border: 1px solid #1A425C;
            border-radius: 7px;
            padding: 5px 8px;
            color: #DCE7EF;
            font-size: 11px;
            font-weight: 750;
            min-height: 18px;
        }
        #softwareActionButton:hover { background: #122535; border-color: #28C8FF; }
        #softwareFooterButton { min-height: 26px; max-height: 28px; font-size: 11px; }
        #softwareImpactValue { color: #F2F6FA; font-size: 26px; font-weight: 900; }
        #impactIndicator { color: #1B2B36; font-size: 20px; font-weight: 900; letter-spacing: 0px; }
        #impactIndicator[impact="low"][active="true"] { color: #35D66B; }
        #impactIndicator[impact="medium"][active="true"] { color: #F5B83D; }
        #impactIndicator[impact="high"][active="true"] { color: #F05B5B; }
        #impactStatus { color: #8396A3; font-size: 10px; font-weight: 750; letter-spacing: 1px; }
        QProgressBar#impactBar { background: #101A24; border: 0; border-radius: 4px; min-height: 9px; max-height: 9px; }
        QProgressBar#impactBar::chunk { background: #16B9F3; border-radius: 4px; }
        QProgressBar#impactBar[impact="low"]::chunk { background: #35D66B; }
        QProgressBar#impactBar[impact="medium"]::chunk { background: #F5B83D; }
        QProgressBar#impactBar[impact="high"]::chunk { background: #F05B5B; }
        #softwareNote { color: #91A4B1; font-size: 11px; }
        #protectionIcon { color: #28C8FF; font-size: 38px; font-weight: 800; }
        #protectionExplanation { color: #C2CDD5; font-size: 11px; font-weight: 650; }
        #protectionDivider { color: #1A4058; background: #1A4058; min-width: 1px; max-width: 1px; }
        #softwareActivityRow {
            background: #09131D;
            border: 1px solid #153044;
            border-left: 3px solid #16B9F3;
            border-radius: 6px;
        }
        #softwareActivityTime { color: #98AAB7; font-size: 12px; font-family: JetBrains Mono, monospace; min-width: 58px; max-width: 58px; }
        #softwareActivityCategory { color: #16B9F3; font-size: 11px; font-weight: 850; min-width: 82px; max-width: 82px; }
        #softwareActivityCategory[category="install"] { color: #35D66B; }
        #softwareActivityCategory[category="remove"] { color: #F0A72B; }
        #softwareActivityCategory[category="snapshot"] { color: #A65DFF; }
        #softwareActivityDescription { color: #E5EDF3; font-size: 12px; font-weight: 650; }
        #softwareActionTile {
            background: #0D1A25;
            border: 1px solid #1A425C;
            border-radius: 8px;
            min-height: 82px;
            padding: 9px 10px;
            color: #DCE7EF;
            font-size: 12px;
            font-weight: 750;
        }
        #softwareActionTile[category="update"] { background: #0C1822; border-color: #17445D; }
        #softwareActionTile[category="health"] { background: #0C1916; border-color: #20553A; }
        #softwareActionTile[category="cleanup"] { background: #19160F; border-color: #57441E; }
        #softwareActionTile[category="system"] { background: #121521; border-color: #443064; }
        #softwareActionTile[hierarchy="primary"] { background: #0D4665; border: 2px solid #2BC4FF; color: #FFFFFF; }
        #softwareActionTile[hierarchy="danger"] { background: #1B1710; border: 1px solid #D99A28; color: #FFD079; }
        #softwareActionTile:hover { background: #153044; border: 2px solid #35CFFF; color: #FFFFFF; }
        #softwareActionTile:pressed { background: #0D2E45; }
        #missionChip {
            background: rgba(7, 10, 14, 150);
            border: 1px solid #16344D;
            border-radius: 8px;
            min-width: 112px;
            padding: 5px 8px;
            color: #B5BDC6;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        #missionChip[state="success"] { color: #35D66B; border-color: #205C3A; }
        #missionChip[state="warning"] { color: #F4B942; border-color: #614B20; }
        #missionChip[state="critical"] { color: #FF4B4B; border-color: #6B2929; }
        #missionChip[state="info"] { color: #2BC4FF; border-color: #164B67; }
        #navButton {
            text-align: left;
            min-height: 38px;
            padding: 8px 11px;
            border: 1px solid transparent;
            border-radius: 8px;
            background: transparent;
            color: #b9c8d5;
            font-weight: 700;
        }
        #navButton:hover {
            background: #0a2030;
            border-color: #1b5579;
            color: #edf8ff;
        }
        #navButton:checked {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d3f63, stop:0.72 #08283d, stop:1 #061724);
            border-color: #13aef8;
            color: #ffffff;
        }
        #card, QFrame#card {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101822, stop:0.58 #0B141D, stop:1 #091018);
            border: 1px solid #183d56;
            border-radius: 14px;
        }
        #card:hover, QFrame#card:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #152131, stop:1 #0D1823);
            border-color: #2976A3;
        }
        QFrame#card[accent="#00AEEF"] { border-left: 2px solid #00AEEF; }
        QFrame#card[accent="#35D66B"] { border-left: 2px solid #35D66B; }
        QFrame#card[accent="#A55DFF"] { border-left: 2px solid #A55DFF; }
        QFrame#card[accent="#F0B230"] { border-left: 2px solid #F0B230; }
        #alertRow, QFrame#alertRow {
            background: #0B1017;
            border: 1px solid #30465a;
            border-radius: 8px;
            padding: 2px;
        }
        QFrame#alertRow[severity="warning"] { border-left: 6px solid #F4B942; }
        QFrame#alertRow[severity="critical"] { border-left: 6px solid #FF4B4B; }
        QFrame#alertRow[severity="advisory"] { border-left: 6px solid #00AEEF; }
        #alertText { color: #DCE6EE; font-size: 12px; font-weight: 650; }
        #alertAction {
            min-height: 20px;
            max-height: 22px;
            padding: 1px 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 800;
        }
        #queueBar, QFrame#queueBar {
            background: #102131;
            border: 1px solid #1e9be8;
            border-radius: 8px;
        }
        #controlState {
            color: #65d3ff;
            font-weight: 750;
            padding: 3px 0;
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
        #toolStatCard { background: #091722; border: 1px solid #173D55; border-radius: 8px; }
        #toolStatValue { color: #FFFFFF; font-size: 22px; font-weight: 900; }
        #toolStatLabel { color: #7F98A9; font-size: 9px; font-weight: 850; letter-spacing: 1px; }
        #toolFilterLabel { color: #6F899B; font-size: 10px; font-weight: 850; letter-spacing: 1px; }
        #toolFilterChip {
            min-height: 22px; max-height: 24px; padding: 1px 10px;
            background: #091722; border: 1px solid #1B455F; border-radius: 12px;
            color: #AFC0CB; font-size: 10px; font-weight: 750;
        }
        #toolFilterChip:checked { background: #104464; border-color: #2BC4FF; color: #FFFFFF; }
        #toolRecommendedStrip {
            background: #101B29; border: 1px solid #433063; border-left: 3px solid #A65DFF;
            border-radius: 7px; padding: 8px 10px; color: #DCC9FF; font-size: 11px; font-weight: 750;
        }
        QListWidget#toolCategories { background: #060D14; border: 1px solid #17384D; border-radius: 8px; outline: 0; }
        QListWidget#toolCategories::item { padding: 7px 10px; margin: 2px 3px; border: 1px solid transparent; border-radius: 7px; color: #AFC0CB; }
        QListWidget#toolCategories::item:hover { background: #0D2130; border-color: #1B4A66; color: #FFFFFF; }
        QListWidget#toolCategories::item:selected { background: #12334A; border-left: 3px solid #2BC4FF; color: #FFFFFF; }
        QListWidget#toolAppList { background: #050B11; border: 1px solid #17384D; border-radius: 8px; outline: 0; }
        #toolActionButton { min-height: 28px; padding: 5px 9px; font-size: 11px; font-weight: 800; }
        QProgressBar#toolInstallProgress { min-height: 8px; max-height: 8px; border: 0; border-radius: 4px; background: #101A24; }
        QProgressBar#toolInstallProgress::chunk { background: #2BC4FF; border-radius: 4px; }
        #offlineTabs::pane { border: 1px solid #17384D; border-radius: 9px; background: #071019; }
        #offlineTabs QTabBar::tab { min-height: 28px; padding: 7px 18px; background: #09131D; color: #91A5B3; font-weight: 750; }
        #offlineTabs QTabBar::tab:selected { background: #12334A; color: #FFFFFF; border-bottom: 3px solid #2BC4FF; }
        #offlineTabs QTabBar::tab:hover { background: #102535; color: #FFFFFF; }
        #knowledgeStatCard { background: #091722; border: 1px solid #173D55; border-radius: 9px; }
        #knowledgeStatIcon { color: #2BC4FF; font-size: 18px; font-weight: 850; }
        #knowledgeStatValue { color: #FFFFFF; font-size: 22px; font-weight: 900; }
        #knowledgeStatLabel { color: #8198A8; font-size: 9px; font-weight: 850; letter-spacing: 1px; }
        #knowledgeStatContext { color: #627D8F; font-size: 9px; font-weight: 650; }
        #knowledgeMuted { color: #8FA5B4; font-size: 11px; }
        #knowledgeFilterLabel { color: #6F899B; font-size: 10px; font-weight: 850; letter-spacing: 1px; }
        #knowledgeFilterChip { min-height: 22px; max-height: 24px; padding: 1px 10px; background: #091722; border: 1px solid #1B455F; border-radius: 12px; color: #AFC0CB; font-size: 10px; font-weight: 750; }
        #knowledgeFilterChip:checked { background: #17658F; border: 2px solid #35D5FF; color: #FFFFFF; font-weight: 850; }
        #knowledgeMiniTitle { color: #77CFF3; font-size: 9px; font-weight: 850; letter-spacing: 1px; }
        #knowledgeSuggestion { min-height: 24px; padding: 3px 7px; background: #0B1A26; border: 1px solid #1B455F; border-radius: 6px; color: #C3D3DD; text-align: left; font-size: 10px; }
        #knowledgeSuggestion:hover { background: #12334A; border-color: #2BC4FF; color: #FFFFFF; }
        #knowledgeRecentQuestions { color: #C7D6DF; font-size: 10px; padding-top: 4px; border-top: 1px solid #17384D; }
        #knowledgeFeatureText { color: #DCE7EE; font-size: 12px; padding: 5px; }
        #knowledgeCategories { color: #C8D5DE; font-size: 12px; padding: 6px; line-height: 140%; }
        #knowledgeSources { color: #7791A2; font-size: 9px; font-weight: 750; padding-top: 5px; border-top: 1px solid #17384D; }
        #knowledgePrimaryButton { background: #0D4665; border: 1px solid #2BC4FF; color: #FFFFFF; font-weight: 850; }
        #knowledgeSecondaryButton { background: #0B1822; border: 1px solid #28516C; color: #C9D7E0; }
        #knowledgeActionButton { min-height: 68px; padding: 6px 10px; background: #0B1822; border: 1px solid #24516D; border-radius: 8px; color: #D8E7EF; font-size: 11px; font-weight: 850; }
        #knowledgeActionButton:hover { background: #12334A; border-color: #2BC4FF; color: #FFFFFF; }
        #knowledgeCover { background: #0B2231; border: 1px solid #1C5877; border-radius: 9px; font-size: 38px; }
        QProgressBar#readingProgress { min-height: 16px; max-height: 16px; background: #101A24; border: 0; border-radius: 7px; color: #FFFFFF; font-size: 9px; font-weight: 800; text-align: center; }
        QProgressBar#readingProgress::chunk { background: #2BC4FF; border-radius: 7px; }
        QListWidget#knowledgeShelf { background: #060D14; border: 1px solid #17384D; border-radius: 7px; outline: 0; }
        QListWidget#knowledgeShelf::item { padding: 5px 8px; border-bottom: 1px solid #152C3C; color: #D8E4EC; }
        QListWidget#knowledgeShelf::item:hover, QListWidget#knowledgeShelf::item:selected { background: #102A3C; color: #FFFFFF; }
        QProgressBar#knowledgeStorageBar { min-height: 11px; max-height: 11px; border: 0; border-radius: 5px; background: #101A24; }
        QProgressBar#knowledgeStorageBar::chunk { background: #2BC4FF; border-radius: 5px; }
        QProgressBar#knowledgeStorageBar[role="index"]::chunk { background: #A65DFF; }
        QProgressBar#knowledgeStorageBar[role="free"]::chunk { background: #42E978; }
        #knowledgeStorageLabel { color: #8298A8; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
        #knowledgeStorageValue { color: #FFFFFF; font-size: 10px; font-weight: 800; }
        #metricValue {
            color: #ffffff;
            font-size: 34px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #muted {
            color: #a8bac8;
        }
        #panelTitle {
            color: #f2f6fa;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        #bar {
            background: #111b25;
            border: 1px solid #23384c;
            border-radius: 4px;
            min-height: 8px;
            max-height: 8px;
        }
        QProgressBar#metricBar {
            background: #101A24;
            border: 0;
            border-radius: 3px;
            min-height: 7px;
            max-height: 7px;
        }
        QProgressBar#metricBar::chunk { background: #00AEEF; border-radius: 3px; }
        QProgressBar#metricBar[accent="#35D66B"]::chunk { background: #35D66B; }
        QProgressBar#metricBar[accent="#A55DFF"]::chunk { background: #A55DFF; }
        QProgressBar#metricBar[accent="#F0B230"]::chunk { background: #F0B230; }
        #activityRow {
            background: #0B1017;
            border: 1px solid #16344D;
            border-left: 2px solid #00AEEF;
            border-radius: 7px;
        }
        #activityTime { color: #9AAAB7; font-family: JetBrains Mono, monospace; font-size: 12px; min-width: 48px; }
        #activityCategory { color: #2BC4FF; font-size: 11px; font-weight: 800; min-width: 64px; }
        #activityMessage { color: #DCE6EE; font-weight: 650; }
        #readinessDetail {
            color: #B9C5CE;
            font-family: JetBrains Mono, Cascadia Code, monospace;
            font-size: 12px;
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
        #quickActionButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101E2B, stop:1 #09131D);
            border: 1px solid #204661;
            border-radius: 10px;
            color: #DCEAF4;
            font-size: 13px;
            font-weight: 800;
            padding: 10px;
        }
        #quickActionButton:hover {
            background: #102C40;
            border-color: #2BC4FF;
            color: #FFFFFF;
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
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #102536, stop:1 #081520);
            border: 1px solid #28516c;
            border-radius: 7px;
            padding: 7px 10px;
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
    primary_screen = app.primaryScreen()
    if primary_screen:
        window.setGeometry(primary_screen.availableGeometry())
    window.showMaximized()
    if splash is not None:
        splash.finish(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
