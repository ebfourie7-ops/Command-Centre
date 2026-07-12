import base64
import hashlib
import html
import json
import shutil
import sqlite3
import subprocess
import time
import zipfile
from urllib.parse import urlparse
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGraphicsScene, QGraphicsView, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)


DATA_DIR = Path.home() / ".local/share/command-centre/intel"
DB_FILE = DATA_DIR / "intel.db"
EVIDENCE_DIR = DATA_DIR / "evidence"
ENCRYPTED_PREFIX = "enc:v1:"
VAULT_MAGIC = b"COMMAND-INTEL-VAULT-1\n"


class RequestBlocker(QWebEngineUrlRequestInterceptor):
    blocked = (
        "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adnxs.com",
        "amazon-adsystem.com", "advertising.com", "adsrvr.org", "adroll.com", "criteo.",
        "taboola.com", "outbrain.com", "pubmatic.com", "rubiconproject.com", "openx.net",
        "yieldmo.com", "scorecardresearch.com", "quantserve.com", "moatads.com", "mgid.com",
        "media.net", "hotjar.com", "fullstory.com", "mouseflow.com", "clarity.ms",
        "google-analytics.com", "googletagmanager.com", "segment.com", "mixpanel.com",
        "amplitude.com", "connect.facebook.net", "bat.bing.com", "appsflyer.com",
        "cookielaw.org", "onetrust.com", "trustarc.com",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.allowlist = set()
        self.extra_rules = set()

    def interceptRequest(self, info):
        host = info.requestUrl().host().lower()
        if self.enabled and host not in self.allowlist and any(value in host for value in self.blocked + tuple(self.extra_rules)):
            info.block(True)


class IntelStore:
    PROTECTED_FIELDS = {
        "cases": ("description", "authorization", "scope", "jurisdiction"),
        "evidence": ("title", "source", "local_path", "notes"),
        "entities": ("value", "source"),
        "relations": ("label",),
        "activity": ("action", "detail"),
        "targets": ("value", "purpose", "notes"),
        "plans": ("title", "objective"),
        "tasks": ("title", "resource", "input", "output"),
        "evidence_inbox": ("title", "source", "local_path", "notes"),
        "findings": ("title", "narrative", "limitations"),
        "custody_events": ("detail",),
    }

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        DATA_DIR.chmod(0o700)
        EVIDENCE_DIR.chmod(0o700)
        self.db = sqlite3.connect(DB_FILE)
        DB_FILE.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
                created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL, kind TEXT NOT NULL, source TEXT DEFAULT '', local_path TEXT DEFAULT '',
                sha256 TEXT DEFAULT '', notes TEXT DEFAULT '', created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                type TEXT NOT NULL, value TEXT NOT NULL, source TEXT DEFAULT '', confidence INTEGER DEFAULT 50,
                UNIQUE(case_id, type, value)
            );
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                source_entity INTEGER NOT NULL, target_entity INTEGER NOT NULL, label TEXT NOT NULL,
                evidence_id INTEGER, UNIQUE(case_id, source_entity, target_entity, label)
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY, case_id INTEGER, action TEXT NOT NULL, detail TEXT DEFAULT '',
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                type TEXT NOT NULL, value TEXT NOT NULL, purpose TEXT DEFAULT '', status TEXT DEFAULT 'active',
                scope_status TEXT DEFAULT 'review', entity_id INTEGER, notes TEXT DEFAULT '', created_utc TEXT NOT NULL,
                UNIQUE(case_id,type,value)
            );
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL, objective TEXT DEFAULT '', status TEXT DEFAULT 'active', created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                position INTEGER NOT NULL, title TEXT NOT NULL, status TEXT DEFAULT 'pending', resource TEXT DEFAULT '',
                input TEXT DEFAULT '', output TEXT DEFAULT '', started_utc TEXT DEFAULT '', completed_utc TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS evidence_inbox (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL, kind TEXT NOT NULL, source TEXT DEFAULT '', local_path TEXT DEFAULT '',
                sha256 TEXT DEFAULT '', notes TEXT DEFAULT '', status TEXT DEFAULT 'unreviewed', collected_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL, narrative TEXT DEFAULT '', status TEXT DEFAULT 'draft', confidence TEXT DEFAULT 'medium',
                limitations TEXT DEFAULT '', ai_assisted INTEGER DEFAULT 0, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS finding_evidence (
                finding_id INTEGER NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
                role TEXT DEFAULT 'supporting', PRIMARY KEY(finding_id,evidence_id,role)
            );
            CREATE TABLE IF NOT EXISTS custody_events (
                id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL, evidence_id INTEGER,
                action TEXT NOT NULL, detail TEXT DEFAULT '', previous_hash TEXT DEFAULT '', event_hash TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
        """)
        if not self.db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]:
            self.db.execute("INSERT INTO schema_version VALUES(3)")
        else:
            self.db.execute("UPDATE schema_version SET version=3")
        self.ensure_column("cases", "status", "TEXT DEFAULT 'active'")
        self.ensure_column("cases", "authorization", "TEXT DEFAULT ''")
        self.ensure_column("cases", "scope", "TEXT DEFAULT ''")
        self.ensure_column("cases", "jurisdiction", "TEXT DEFAULT ''")
        self.ensure_column("cases", "classification", "TEXT DEFAULT 'Private'")
        self.ensure_column("cases", "retention_until", "TEXT DEFAULT ''")
        self.ensure_column("cases", "password_salt", "TEXT DEFAULT ''")
        self.ensure_column("cases", "password_verifier", "TEXT DEFAULT ''")
        self.db.commit()
        self.case_keys = {}

    def ensure_column(self, table, name, declaration):
        columns = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
        if name not in columns:
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    @staticmethod
    def derive_key(password, salt):
        return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(password.encode("utf-8"))

    @staticmethod
    def encrypt_with_key(key, value):
        if value in (None, "") or str(value).startswith(ENCRYPTED_PREFIX): return value or ""
        nonce = __import__("os").urandom(12)
        payload = nonce + AESGCM(key).encrypt(nonce, str(value).encode("utf-8"), None)
        return ENCRYPTED_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii")

    @staticmethod
    def decrypt_with_key(key, value):
        if value in (None, "") or not str(value).startswith(ENCRYPTED_PREFIX): return value or ""
        payload = base64.urlsafe_b64decode(str(value)[len(ENCRYPTED_PREFIX):])
        return AESGCM(key).decrypt(payload[:12], payload[12:], None).decode("utf-8")

    def is_protected(self, case_id):
        row = self.db.execute("SELECT password_salt FROM cases WHERE id=?", (case_id,)).fetchone()
        return bool(row and row[0])

    def is_unlocked(self, case_id): return not self.is_protected(case_id) or case_id in self.case_keys

    def unlock_case(self, case_id, password):
        row = self.db.execute("SELECT password_salt,password_verifier FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row or not row["password_salt"]: return True
        try:
            key = self.derive_key(password, base64.b64decode(row["password_salt"]))
            valid = self.decrypt_with_key(key, row["password_verifier"]) == f"command-intel-case-{case_id}"
        except Exception: return False
        if valid: self.case_keys[case_id] = key
        return valid

    def lock_case(self, case_id): self.case_keys.pop(case_id, None)

    def protect_text(self, case_id, value):
        key = self.case_keys.get(case_id)
        if key: return self.encrypt_with_key(key, value)
        if case_id and self.is_protected(case_id): raise PermissionError("Case is locked")
        return value

    def reveal_text(self, case_id, value):
        if not str(value or "").startswith(ENCRYPTED_PREFIX): return value or ""
        key = self.case_keys.get(case_id)
        if not key: raise PermissionError("Case is locked")
        return self.decrypt_with_key(key, value)

    def protect_case(self, case_id, password):
        if self.is_protected(case_id): raise ValueError("Case is already password protected")
        salt = __import__("os").urandom(16); key = self.derive_key(password, salt); self.case_keys[case_id] = key
        verifier = self.encrypt_with_key(key, f"command-intel-case-{case_id}")
        self.db.execute("UPDATE cases SET password_salt=?,password_verifier=? WHERE id=?", (base64.b64encode(salt).decode("ascii"), verifier, case_id))
        for table in ("evidence", "evidence_inbox"):
            for row in self.db.execute(f"SELECT id,local_path FROM {table} WHERE case_id=?", (case_id,)).fetchall():
                if row["local_path"] and not str(row["local_path"]).startswith(ENCRYPTED_PREFIX):
                    encrypted_path = self.encrypt_evidence_file(case_id, row["local_path"])
                    if encrypted_path: self.db.execute(f"UPDATE {table} SET local_path=? WHERE id=?", (encrypted_path, row["id"]))
        for table, fields in self.PROTECTED_FIELDS.items():
            if table == "cases": rows = self.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchall(); id_column = "id"
            elif "case_id" in {column[1] for column in self.db.execute(f"PRAGMA table_info({table})")}: rows = self.db.execute(f"SELECT * FROM {table} WHERE case_id=?", (case_id,)).fetchall(); id_column = "id"
            else: continue
            for row in rows:
                updates = {field: self.encrypt_with_key(key, row[field]) for field in fields if field in row.keys() and row[field] not in (None, "")}
                if updates:
                    self.db.execute(f"UPDATE {table} SET " + ",".join(f"{field}=?" for field in updates) + f" WHERE {id_column}=?", (*updates.values(), row[id_column]))
        self.db.commit()

    def encrypt_evidence_file(self, case_id, path):
        key = self.case_keys.get(case_id); source = Path(path)
        if not key or not source.exists() or not source.is_file(): return str(path)
        if source.suffix == ".ccvault": return str(source)
        nonce = __import__("os").urandom(12)
        encrypted = AESGCM(key).encrypt(nonce, source.read_bytes(), f"case:{case_id}".encode())
        destination = source.with_name(source.name + ".ccvault")
        destination.write_bytes(VAULT_MAGIC + nonce + encrypted)
        source.unlink()
        return str(destination)

    def evidence_bytes(self, case_id, path):
        source = Path(path); payload = source.read_bytes()
        if not payload.startswith(VAULT_MAGIC): return payload
        key = self.case_keys.get(case_id)
        if not key: raise PermissionError("Case is locked")
        encrypted = payload[len(VAULT_MAGIC):]
        return AESGCM(key).decrypt(encrypted[:12], encrypted[12:], f"case:{case_id}".encode())

    def evidence_digest(self, case_id, path): return hashlib.sha256(self.evidence_bytes(case_id, path)).hexdigest()

    def decrypt_row(self, table, row):
        if not row: return row
        data = dict(row); case_id = data.get("case_id") or (data.get("id") if table == "cases" else None)
        for field in self.PROTECTED_FIELDS.get(table, ()):
            if field in data: data[field] = self.reveal_text(case_id, data[field])
        return data

    def case_record(self, case_id): return self.decrypt_row("cases", self.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone())

    @staticmethod
    def now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def cases(self, include_archived=True):
        where = "" if include_archived else "WHERE status != 'archived'"
        return self.db.execute(f"SELECT * FROM cases {where} ORDER BY updated_utc DESC").fetchall()

    def add_case(self, name, description=""):
        now = self.now()
        cursor = self.db.execute(
            "INSERT INTO cases(name, description, created_utc, updated_utc) VALUES(?,?,?,?)",
            (name, description, now, now),
        )
        self.db.commit()
        return cursor.lastrowid

    def update_case(self, case_id, **fields):
        allowed = {"name", "description", "status", "authorization", "scope", "jurisdiction", "classification", "retention_until"}
        values = {key: value for key, value in fields.items() if key in allowed}
        for key in self.PROTECTED_FIELDS["cases"]:
            if key in values: values[key] = self.protect_text(case_id, values[key])
        if not values: return
        values["updated_utc"] = self.now()
        assignments = ",".join(f"{key}=?" for key in values)
        self.db.execute(f"UPDATE cases SET {assignments} WHERE id=?", (*values.values(), case_id)); self.db.commit()

    def delete_case(self, case_id):
        self.db.execute("DELETE FROM cases WHERE id=?", (case_id,)); self.db.commit()

    def backup(self, destination):
        target = sqlite3.connect(destination)
        self.db.backup(target); target.close()

    def evidence(self, case_id):
        return [self.decrypt_row("evidence", row) for row in self.db.execute("SELECT * FROM evidence WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()]

    def add_evidence(self, case_id, title, kind, source="", local_path="", digest="", notes=""):
        cursor = self.db.execute(
            "INSERT INTO evidence(case_id,title,kind,source,local_path,sha256,notes,created_utc) VALUES(?,?,?,?,?,?,?,?)",
            (case_id, self.protect_text(case_id,title), kind, self.protect_text(case_id,source), self.protect_text(case_id,local_path), digest, self.protect_text(case_id,notes), self.now()),
        )
        evidence_id = cursor.lastrowid
        self.log(case_id, "Evidence added", title)
        self.add_custody_event(case_id, evidence_id, "accepted", f"{kind}: {title}; original SHA-256 {digest or 'not applicable'}")
        self.db.commit()
        return evidence_id

    def add_custody_event(self, case_id, evidence_id, action, detail=""):
        previous = self.db.execute("SELECT event_hash FROM custody_events WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        previous_hash = previous[0] if previous else ""
        created = self.now()
        payload = f"{case_id}|{evidence_id or ''}|{action}|{detail}|{created}|{previous_hash}"
        event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO custody_events(case_id,evidence_id,action,detail,previous_hash,event_hash,created_utc) VALUES(?,?,?,?,?,?,?)",
                        (case_id, evidence_id, action, self.protect_text(case_id,detail), previous_hash, event_hash, created))

    def add_inbox(self, case_id, title, kind, source="", local_path="", digest="", notes=""):
        cursor = self.db.execute("INSERT INTO evidence_inbox(case_id,title,kind,source,local_path,sha256,notes,collected_utc) VALUES(?,?,?,?,?,?,?,?)",
                                 (case_id,self.protect_text(case_id,title),kind,self.protect_text(case_id,source),self.protect_text(case_id,local_path),digest,self.protect_text(case_id,notes),self.now()))
        self.log(case_id, "Collected to inbox", title); self.db.commit(); return cursor.lastrowid

    def inbox(self, case_id, status="unreviewed"):
        return [self.decrypt_row("evidence_inbox", row) for row in self.db.execute("SELECT * FROM evidence_inbox WHERE case_id=? AND status=? ORDER BY id DESC", (case_id,status)).fetchall()]

    def accept_inbox(self, inbox_id):
        row = self.db.execute("SELECT * FROM evidence_inbox WHERE id=?", (inbox_id,)).fetchone()
        if not row: return None
        row = self.decrypt_row("evidence_inbox", row)
        evidence_id = self.add_evidence(row["case_id"],row["title"],row["kind"],row["source"],row["local_path"],row["sha256"],row["notes"])
        self.db.execute("UPDATE evidence_inbox SET status='accepted' WHERE id=?", (inbox_id,)); self.db.commit(); return evidence_id

    def add_target(self, case_id, target_type, value, purpose=""):
        cursor = self.db.execute("INSERT OR IGNORE INTO targets(case_id,type,value,purpose,created_utc) VALUES(?,?,?,?,?)", (case_id,target_type,self.protect_text(case_id,value),self.protect_text(case_id,purpose),self.now()))
        self.log(case_id,"Target added",f"{target_type}: {value}"); self.db.commit(); return cursor.lastrowid

    def targets(self, case_id): return [self.decrypt_row("targets", row) for row in self.db.execute("SELECT * FROM targets WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
    def findings(self, case_id): return [self.decrypt_row("findings", row) for row in self.db.execute("SELECT * FROM findings WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()]
    def add_finding(self, case_id, title, narrative, confidence="medium"):
        now=self.now(); cursor=self.db.execute("INSERT INTO findings(case_id,title,narrative,confidence,created_utc,updated_utc) VALUES(?,?,?,?,?,?)",(case_id,self.protect_text(case_id,title),self.protect_text(case_id,narrative),confidence,now,now)); self.log(case_id,"Draft finding created",title); self.db.commit(); return cursor.lastrowid
    def activity(self, case_id, limit=12): return [self.decrypt_row("activity", row) for row in self.db.execute("SELECT * FROM activity WHERE case_id=? ORDER BY id DESC LIMIT ?",(case_id,limit)).fetchall()]

    def add_entity(self, case_id, entity_type, value, source="", confidence=50):
        self.db.execute(
            "INSERT OR IGNORE INTO entities(case_id,type,value,source,confidence) VALUES(?,?,?,?,?)",
            (case_id, entity_type, self.protect_text(case_id,value), self.protect_text(case_id,source), confidence),
        )
        self.db.commit()

    def entities(self, case_id):
        return [self.decrypt_row("entities", row) for row in self.db.execute("SELECT * FROM entities WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]

    def add_relation(self, case_id, source_id, target_id, label, evidence_id=None):
        self.db.execute(
            "INSERT OR IGNORE INTO relations(case_id,source_entity,target_entity,label,evidence_id) VALUES(?,?,?,?,?)",
            (case_id, source_id, target_id, self.protect_text(case_id,label), evidence_id),
        )
        self.db.commit()

    def relations(self, case_id):
        return [self.decrypt_row("relations", row) for row in self.db.execute("SELECT * FROM relations WHERE case_id=?", (case_id,)).fetchall()]

    def log(self, case_id, action, detail=""):
        self.db.execute(
            "INSERT INTO activity(case_id,action,detail,created_utc) VALUES(?,?,?,?)",
            (case_id, self.protect_text(case_id,action), self.protect_text(case_id,detail), self.now()),
        )
        if case_id:
            self.db.execute("UPDATE cases SET updated_utc=? WHERE id=?", (self.now(), case_id))
        self.db.commit()


class AdvancedCommandIntelPage(QWidget):
    def __init__(self, parent_window, categories, providers):
        super().__init__()
        self.parent_window = parent_window
        self.categories = categories
        self.providers = providers
        self.store = IntelStore()
        self.case_id = None
        self.suppress_case_auto_open = False
        self.blocker = RequestBlocker(self)
        self.browser_profiles = {}
        self.ollama_process = None
        self.tabs = QTabWidget()
        self.browser_tabs = QTabWidget()
        self.browser_tabs.setTabsClosable(True)
        self.browser_tabs.tabCloseRequested.connect(self.close_browser_tab)
        self.case_combo = QComboBox()
        self.case_combo.currentIndexChanged.connect(self.select_case)
        self.investigation_status = QLabel("NO ACTIVE CASE")
        self.investigation_status.setObjectName("healthHeader")
        self.investigation_status.setWordWrap(True)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.build_overview()
        self.build_dashboard()
        self.build_browser()
        self.build_cases()
        self.build_evidence()
        self.build_graph()
        self.build_tools()
        self.build_ai()
        self.build_findings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        investigation_bar = QHBoxLayout()
        investigation_bar.addWidget(QLabel("CASE:")); investigation_bar.addWidget(self.case_combo)
        investigation_bar.addWidget(self.investigation_status, 1)
        add_target = QPushButton("ADD TARGET"); capture = QPushButton("CAPTURE")
        add_target.clicked.connect(self.add_target); capture.clicked.connect(self.capture_page)
        investigation_bar.addWidget(add_target); investigation_bar.addWidget(capture)
        layout.addLayout(investigation_bar)
        layout.addWidget(self.tabs)
        layout.addWidget(self.status)
        self.refresh_cases()

    def frame(self, title):
        frame = QFrame(); frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title); heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return frame, layout

    def build_dashboard(self):
        page = QWidget(); layout = QVBoxLayout(page)
        hero, hero_layout = self.frame("TARGET WORKBENCH  ·  PUBLIC-SOURCE INVESTIGATION")
        row = QHBoxLayout()
        self.resource_filter = QLineEdit(); self.resource_filter.setPlaceholderText("Filter resources…")
        row.addWidget(self.resource_filter, 1)
        hero_layout.addLayout(row)
        layout.addWidget(hero)
        query, query_layout = self.frame("QUERY ONCE")
        controls = QHBoxLayout()
        self.target_type = QComboBox(); self.target_type.addItems(self.providers.keys())
        self.query = QLineEdit(); self.query.setPlaceholderText("Enter an authorized public target")
        run = QPushButton("Search selected sources")
        controls.addWidget(self.target_type); controls.addWidget(self.query, 1); controls.addWidget(run)
        self.provider_list = QListWidget(); self.provider_list.setSelectionMode(QListWidget.MultiSelection)
        query_layout.addLayout(controls); query_layout.addWidget(self.provider_list)
        layout.addWidget(query)
        self.cards_host = QWidget(); self.cards_grid = QGridLayout(self.cards_host)
        layout.addWidget(self.cards_host); layout.addStretch()
        self.target_type.currentTextChanged.connect(self.refresh_providers)
        self.resource_filter.textChanged.connect(self.render_resources)
        run.clicked.connect(self.run_search)
        self.query.returnPressed.connect(self.run_search)
        self.refresh_providers(); self.render_resources()
        self.tabs.addTab(page, "Investigate")

    def build_overview(self):
        page = QWidget(); layout = QVBoxLayout(page)
        summary, summary_layout = self.frame("INVESTIGATION OVERVIEW")
        self.overview_summary = QLabel("Select or create a case to begin."); self.overview_summary.setObjectName("controlState"); self.overview_summary.setWordWrap(True)
        summary_layout.addWidget(self.overview_summary); layout.addWidget(summary)
        split = QSplitter()
        targets, targets_layout = self.frame("TARGETS"); self.target_list = QListWidget(); targets_layout.addWidget(self.target_list)
        progress, progress_layout = self.frame("INVESTIGATION PROGRESS & ATTENTION"); self.progress_summary = QLabel("--"); self.progress_summary.setObjectName("muted"); self.progress_summary.setWordWrap(True); progress_layout.addWidget(self.progress_summary)
        split.addWidget(targets); split.addWidget(progress); layout.addWidget(split)
        recent, recent_layout = self.frame("RECENT ACTIVITY"); self.activity_list = QListWidget(); recent_layout.addWidget(self.activity_list); layout.addWidget(recent)
        self.tabs.addTab(page,"Overview")

    def render_resources(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        needle = self.resource_filter.text().lower().strip()
        groups = []
        for title, icon, tools in self.categories:
            matches = [(name, url) for name, url in tools if not needle or needle in title.lower() or needle in name.lower()]
            if matches: groups.append((title, icon, matches))
        for index, (title, icon, tools) in enumerate(groups):
            card = QFrame(); card.setObjectName("intelCard"); card_layout = QVBoxLayout(card)
            heading = QLabel(f"{icon}   {title}"); heading.setObjectName("intelCardTitle"); card_layout.addWidget(heading)
            for name, url in tools:
                button = QPushButton(name); button.setObjectName("intelLink"); button.setToolTip(url)
                button.clicked.connect(lambda checked=False, u=url: self.open_url(u))
                card_layout.addWidget(button)
            card_layout.addStretch(); self.cards_grid.addWidget(card, index // 3, index % 3)

    def refresh_providers(self):
        self.provider_list.clear()
        for name, url in self.providers[self.target_type.currentText()]:
            item = QListWidgetItem(name); item.setData(Qt.UserRole, url); item.setSelected(True); self.provider_list.addItem(item)

    def run_search(self):
        value = self.query.text().strip()
        if not value: return
        selected = self.provider_list.selectedItems()
        if len(selected) > 5 and QMessageBox.question(self, "Launch searches", f"Open {len(selected)} research tabs?") != QMessageBox.Yes: return
        from urllib.parse import quote
        for item in selected: self.open_url(item.data(Qt.UserRole).format(q=quote(value, safe="")))
        if self.case_id:
            self.store.add_target(self.case_id, self.target_type.currentText(), value, "Target Workbench collection")
            self.store.add_entity(self.case_id, self.target_type.currentText(), value, "Manual query", 80)
            self.store.log(self.case_id, "OSINT search", f"{self.target_type.currentText()}: {value}")
            self.refresh_overview()

    def build_browser(self):
        page = QWidget(); layout = QVBoxLayout(page)
        self.browser_page = page
        bar = QHBoxLayout()
        new = QPushButton("+"); back = QPushButton("←"); forward = QPushButton("→"); reload_button = QPushButton("↻")
        self.address = QLineEdit(); self.address.setPlaceholderText("URL")
        self.privacy = QComboBox(); self.privacy.addItems(["Standard", "Strict (no JavaScript)", "External browser"])
        capture = QPushButton("Capture evidence"); allow_site = QPushButton("Allow site ads"); external = QPushButton("External")
        for widget in (new, back, forward, reload_button): bar.addWidget(widget)
        bar.addWidget(QLabel("● AD BLOCK ON")); bar.addWidget(self.address, 1); bar.addWidget(self.privacy); bar.addWidget(capture); bar.addWidget(allow_site); bar.addWidget(external)
        layout.addLayout(bar); layout.addWidget(self.browser_tabs, 1)
        new.clicked.connect(lambda: self.new_browser_tab("https://duckduckgo.com"))
        back.clicked.connect(lambda: self.current_browser() and self.current_browser().back())
        forward.clicked.connect(lambda: self.current_browser() and self.current_browser().forward())
        reload_button.clicked.connect(lambda: self.current_browser() and self.current_browser().reload())
        self.address.returnPressed.connect(lambda: self.open_url(self.address.text()))
        capture.clicked.connect(self.capture_page)
        allow_site.clicked.connect(self.allow_current_site)
        external.clicked.connect(lambda: self.current_browser() and QDesktopServices.openUrl(self.current_browser().url()))
        self.privacy.currentTextChanged.connect(self.apply_privacy)
        self.tabs.addTab(page, "Browser")

    def current_browser(self):
        return self.browser_tabs.currentWidget()

    def new_browser_tab(self, url):
        view = QWebEngineView()
        profile_key = str(self.case_id or "temporary")
        if profile_key not in self.browser_profiles:
            if self.case_id:
                profile = QWebEngineProfile(f"command-intel-case-{profile_key}", self)
                profile.setPersistentStoragePath(str(DATA_DIR / "browser" / profile_key))
                profile.setCachePath(str(DATA_DIR / "browser" / profile_key / "cache"))
                profile.setDownloadPath(str(DATA_DIR / "downloads" / profile_key))
            else:
                profile = QWebEngineProfile(self)
            profile.setUrlRequestInterceptor(self.blocker)
            self.browser_profiles[profile_key] = profile
        view.setPage(QWebEnginePage(self.browser_profiles[profile_key], view))
        view.urlChanged.connect(lambda value, browser=view: self.browser_url_changed(browser, value))
        view.titleChanged.connect(lambda title, browser=view: self.browser_title_changed(browser, title))
        index = self.browser_tabs.addTab(view, "New tab"); self.browser_tabs.setCurrentIndex(index)
        self.apply_privacy(); view.setUrl(QUrl(url)); return view

    def allow_current_site(self):
        browser = self.current_browser()
        if not browser: return
        host = browser.url().host().lower()
        if host:
            self.blocker.allowlist.add(host); browser.reload(); self.status.setText(f"Ad-block allowlist: {host}")

    def open_url(self, url):
        if not url.startswith(("http://", "https://")): url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            QMessageBox.warning(self, "Blocked URL", "Command Intel only opens valid HTTP and HTTPS addresses.")
            return
        if self.privacy.currentText() == "External browser": QDesktopServices.openUrl(QUrl(url)); return
        self.new_browser_tab(url); self.tabs.setCurrentWidget(self.browser_page)

    def close_browser_tab(self, index):
        widget = self.browser_tabs.widget(index); self.browser_tabs.removeTab(index); widget.deleteLater()

    def browser_url_changed(self, browser, url):
        if browser is self.current_browser(): self.address.setText(url.toString())

    def browser_title_changed(self, browser, title):
        index = self.browser_tabs.indexOf(browser)
        if index >= 0: self.browser_tabs.setTabText(index, (title or "Page")[:28])

    def apply_privacy(self):
        strict = self.privacy.currentText().startswith("Strict")
        for i in range(self.browser_tabs.count()):
            self.browser_tabs.widget(i).settings().setAttribute(QWebEngineSettings.JavascriptEnabled, not strict)

    def build_cases(self):
        page = QWidget(); layout = QVBoxLayout(page)
        cases, cases_layout = self.frame("CASES")
        cases.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.case_list = QListWidget(); self.case_list.setMinimumHeight(100); self.case_list.setMaximumHeight(360)
        new = QPushButton("New case"); edit = QPushButton("Authorization & scope"); protect = QPushButton("Set case password"); lock = QPushButton("Lock case"); archive = QPushButton("Archive"); delete = QPushButton("Delete"); backup = QPushButton("Backup database"); bundle = QPushButton("Export case bundle"); report = QPushButton("Export HTML"); pdf = QPushButton("Export PDF"); print_case = QPushButton("Print case")
        cases_layout.addWidget(self.case_list)
        actions=QGridLayout()
        for index,button in enumerate((new,edit,protect,lock,archive,delete,backup,bundle,report,pdf,print_case)): actions.addWidget(button,index//3,index%3)
        actions.setColumnStretch(0,1); actions.setColumnStretch(1,1); actions.setColumnStretch(2,1)
        cases_layout.addLayout(actions)
        layout.addWidget(cases,0,Qt.AlignTop); layout.addStretch(1)
        new.clicked.connect(self.new_case); edit.clicked.connect(self.edit_case); protect.clicked.connect(self.set_case_password); lock.clicked.connect(self.lock_case); archive.clicked.connect(self.archive_case); delete.clicked.connect(self.delete_case); backup.clicked.connect(self.backup_database); bundle.clicked.connect(self.export_case_bundle); report.clicked.connect(self.export_report); pdf.clicked.connect(self.export_pdf); print_case.clicked.connect(self.print_case); self.case_list.currentItemChanged.connect(self.case_list_changed)
        self.tabs.addTab(page, "Cases")

    def build_evidence(self):
        page = QWidget(); layout = QVBoxLayout(page)
        inbox, inbox_layout = self.frame("EVIDENCE INBOX · REVIEW REQUIRED")
        inbox_buttons = QHBoxLayout(); accept = QPushButton("Accept as evidence"); discard = QPushButton("Discard with record")
        inbox_buttons.addWidget(accept); inbox_buttons.addWidget(discard); inbox_buttons.addStretch()
        self.inbox_list = QListWidget(); inbox_layout.addLayout(inbox_buttons); inbox_layout.addWidget(self.inbox_list)
        layout.addWidget(inbox)
        evidence, evidence_layout = self.frame("ACCEPTED EVIDENCE · SHA-256 INTEGRITY")
        buttons = QHBoxLayout(); add_file = QPushButton("Import file"); add_note = QPushButton("Add note"); verify = QPushButton("Verify hashes")
        buttons.addWidget(add_file); buttons.addWidget(add_note); buttons.addWidget(verify)
        self.evidence_table = QTableWidget(0, 5); self.evidence_table.setHorizontalHeaderLabels(["UTC", "Type", "Title", "SHA-256", "Source"])
        evidence_layout.addLayout(buttons); evidence_layout.addWidget(self.evidence_table)
        layout.addWidget(evidence)
        add_file.clicked.connect(self.import_file); add_note.clicked.connect(self.add_note_evidence); verify.clicked.connect(self.verify_hashes)
        accept.clicked.connect(self.accept_inbox_item); discard.clicked.connect(self.discard_inbox_item)
        self.tabs.addTab(page, "Evidence")

    def refresh_cases(self):
        active = self.case_id
        self.case_list.clear(); self.case_combo.blockSignals(True); self.case_combo.clear()
        for row in self.store.cases():
            protection = "🔒 PROTECTED" if row["password_salt"] else "UNPROTECTED"
            item = QListWidgetItem(f"{row['name']}  ·  {protection}\n{row['updated_utc']}"); item.setData(Qt.UserRole, row["id"]); self.case_list.addItem(item)
            self.case_combo.addItem(("🔒 " if row["password_salt"] else "") + row["name"], row["id"])
        visible_rows=max(1,min(self.case_list.count(),5)); row_height=max(54,self.case_list.sizeHintForRow(0) if self.case_list.count() else 54)
        self.case_list.setFixedHeight(max(100,min(360,visible_rows*row_height+12)))
        self.case_combo.blockSignals(False)
        if active:
            index = self.case_combo.findData(active)
            if index >= 0: self.case_combo.setCurrentIndex(index); self.select_case(index)
        elif self.case_combo.count() and not self.suppress_case_auto_open: self.select_case(0)
        else: self.refresh_overview()
        self.suppress_case_auto_open = False

    def new_case(self):
        name, ok = QInputDialog.getText(self, "New investigation", "Case name:")
        if not ok or not name.strip(): return
        self.case_id = self.store.add_case(name.strip())
        password, protected = QInputDialog.getText(self, "Protect case", "Optional password (leave blank for no encryption):", QLineEdit.Password)
        if protected and password:
            if len(password)<10: QMessageBox.warning(self,"Case password","Use at least 10 characters. The case was created without encryption."); self.refresh_cases(); return
            confirmation, confirmed = QInputDialog.getText(self, "Confirm password", "Repeat case password:", QLineEdit.Password)
            if not confirmed or confirmation != password:
                QMessageBox.warning(self, "Case password", "Passwords did not match. The case was created without encryption.")
            else: self.store.protect_case(self.case_id, password)
        self.refresh_cases(); self.refresh_evidence()

    def set_case_password(self):
        if not self.require_case(): return
        if self.store.is_protected(self.case_id): QMessageBox.information(self,"Case protection","This case is already password protected."); return
        password, ok = QInputDialog.getText(self,"Set case password","New password (minimum 10 characters):",QLineEdit.Password)
        if not ok:return
        if len(password)<10: QMessageBox.warning(self,"Case protection","Use at least 10 characters."); return
        confirmation,ok=QInputDialog.getText(self,"Confirm password","Repeat password:",QLineEdit.Password)
        if not ok or confirmation!=password: QMessageBox.warning(self,"Case protection","Passwords did not match."); return
        self.store.protect_case(self.case_id,password); self.status.setText("Case data and copied evidence encrypted; key held in memory for this session."); self.refresh_cases()

    def lock_case(self):
        if not self.case_id:return
        case_id=self.case_id; self.store.lock_case(case_id); self.case_id=None; self.suppress_case_auto_open=True; self.refresh_cases(); self.status.setText("Case locked and encryption key removed from memory.")

    def edit_case(self):
        if not self.require_case(): return
        row = self.store.case_record(self.case_id)
        authorization, ok = QInputDialog.getMultiLineText(self, "Authorization", "Authority and purpose:", row["authorization"] or "")
        if not ok: return
        scope, ok = QInputDialog.getMultiLineText(self, "Scope", "Authorized targets and limits:", row["scope"] or "")
        if not ok: return
        jurisdiction, ok = QInputDialog.getText(self, "Jurisdiction", "Jurisdiction:", text=row["jurisdiction"] or "")
        if ok: self.store.update_case(self.case_id, authorization=authorization, scope=scope, jurisdiction=jurisdiction); self.refresh_cases()

    def archive_case(self):
        if self.require_case() and QMessageBox.question(self, "Archive case", "Archive this case?") == QMessageBox.Yes:
            self.store.update_case(self.case_id, status="archived"); self.refresh_cases()

    def delete_case(self):
        if not self.require_case(): return
        if QMessageBox.warning(self, "Delete case", "Permanently delete the case database records? Copied evidence files are retained for recovery.", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.store.delete_case(self.case_id); self.case_id = None; self.refresh_cases()

    def backup_database(self):
        target, _ = QFileDialog.getSaveFileName(self, "Backup Command Intel", f"command-intel-{time.strftime('%Y%m%d')}.db", "SQLite (*.db)")
        if target: self.store.backup(target); self.status.setText(f"Database backup saved to {target}")

    def export_case_bundle(self):
        if not self.require_case(): return
        if self.store.is_protected(self.case_id) and QMessageBox.question(self,"Export protected case","This export contains decrypted case data and evidence. Continue?")!=QMessageBox.Yes:return
        target, _ = QFileDialog.getSaveFileName(self, "Export case bundle", f"command-intel-case-{self.case_id}.zip", "ZIP (*.zip)")
        if not target: return
        manifest = {"case_id": self.case_id, "exported_utc": self.store.now(),
                    "targets": [dict(row) for row in self.store.targets(self.case_id)],
                    "evidence": [dict(row) for row in self.store.evidence(self.case_id)],
                    "entities": [dict(row) for row in self.store.entities(self.case_id)],
                    "relations": [dict(row) for row in self.store.relations(self.case_id)],
                    "findings": [dict(row) for row in self.store.findings(self.case_id)],
                    "custody_events": [self.store.decrypt_row("custody_events",row) for row in self.store.db.execute("SELECT * FROM custody_events WHERE case_id=? ORDER BY id",(self.case_id,)).fetchall()]}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for row in self.store.evidence(self.case_id):
                path = Path(row["local_path"]) if row["local_path"] else None
                if path and path.exists() and path.is_file():
                    original_name = Path(row["source"]).name if row["source"] and not row["source"].startswith(("http://","https://")) else path.name.removesuffix(".ccvault")
                    safe_name = re.sub(r"[^A-Za-z0-9._-]+","_",original_name) or "evidence.bin"
                    archive.writestr(f"evidence/E-{row['id']:04d}-{safe_name}",self.store.evidence_bytes(self.case_id,path))
        self.status.setText(f"Case bundle exported to {target}")

    def select_case(self, index):
        case_id = self.case_combo.itemData(index) if index >= 0 else None
        if case_id and self.store.is_protected(case_id) and not self.store.is_unlocked(case_id):
            password, ok = QInputDialog.getText(self,"Unlock protected case","Case password:",QLineEdit.Password)
            if not ok or not self.store.unlock_case(case_id,password):
                if ok: QMessageBox.warning(self,"Protected case","Incorrect password.")
                self.case_id=None; self.refresh_overview(); return
        self.case_id = case_id
        for i in range(self.case_list.count()):
            if self.case_list.item(i).data(Qt.UserRole) == self.case_id: self.case_list.setCurrentRow(i); break
        self.refresh_evidence(); self.refresh_inbox(); self.refresh_graph(); self.refresh_overview(); self.refresh_findings()

    def case_list_changed(self, current, previous):
        if current:
            index = self.case_combo.findData(current.data(Qt.UserRole))
            if index >= 0: self.case_combo.setCurrentIndex(index)

    def require_case(self):
        if not self.case_id: QMessageBox.information(self, "Command Intel", "Create or select a case first."); return False
        return True

    @staticmethod
    def hash_file(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
        return digest.hexdigest()

    def import_file(self):
        if not self.require_case(): return
        source, _ = QFileDialog.getOpenFileName(self, "Import evidence")
        if not source: return
        source_path = Path(source); case_dir = EVIDENCE_DIR / str(self.case_id); case_dir.mkdir(parents=True, exist_ok=True)
        destination = case_dir / f"{int(time.time())}-{source_path.name}"; shutil.copy2(source_path, destination)
        digest = self.hash_file(destination)
        if self.store.is_protected(self.case_id): destination = Path(self.store.encrypt_evidence_file(self.case_id,destination))
        self.store.add_inbox(self.case_id, source_path.name, "file", str(source_path), str(destination), digest)
        self.refresh_inbox(); self.refresh_overview()

    def add_note_evidence(self):
        if not self.require_case(): return
        text, ok = QInputDialog.getMultiLineText(self, "Evidence note", "Observation:")
        if ok and text.strip(): self.store.add_evidence(self.case_id, text.strip().splitlines()[0][:80], "note", notes=text); self.refresh_evidence()

    def capture_page(self):
        if not self.require_case() or not self.current_browser(): return
        browser = self.current_browser(); capture_case_id=self.case_id; case_dir = EVIDENCE_DIR / str(capture_case_id); case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / f"web-{int(time.time())}.png"
        if browser.grab().save(str(path), "PNG"):
            digest = self.hash_file(path)
            if self.store.is_protected(capture_case_id): path=Path(self.store.encrypt_evidence_file(capture_case_id,path))
            self.store.add_inbox(capture_case_id, browser.title() or "Web capture", "screenshot", browser.url().toString(), str(path), digest)
            browser.page().toHtml(lambda markup, b=browser, folder=case_dir, cid=capture_case_id: self.save_page_html(markup, b, folder, cid))
            self.refresh_inbox(); self.refresh_overview(); self.status.setText(f"Collected {path.name} to Evidence Inbox")

    def save_page_html(self, markup, browser, case_dir, case_id):
        path = case_dir / f"web-{int(time.time())}.html"
        path.write_text(markup, encoding="utf-8")
        digest=self.hash_file(path)
        if self.store.is_protected(case_id): path=Path(self.store.encrypt_evidence_file(case_id,path))
        self.store.add_inbox(case_id, f"{browser.title() or 'Web page'} (HTML)", "web-page", browser.url().toString(), str(path), digest, "Captured rendered page source")
        if self.case_id==case_id: self.refresh_inbox(); self.refresh_overview()

    def refresh_evidence(self):
        rows = self.store.evidence(self.case_id) if self.case_id else []
        self.evidence_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["created_utc"], row["kind"], row["title"], row["sha256"], row["source"]]
            for c, value in enumerate(values): self.evidence_table.setItem(r, c, QTableWidgetItem(value or ""))

    def refresh_inbox(self):
        if not hasattr(self,"inbox_list"): return
        self.inbox_list.clear()
        for row in self.store.inbox(self.case_id) if self.case_id else []:
            item=QListWidgetItem(f"I-{row['id']:04d}  ·  {row['kind'].upper()}  ·  UNREVIEWED\n{row['title']}\n{row['collected_utc']}  ·  SHA-256 {row['sha256'] or 'not applicable'}")
            item.setData(Qt.UserRole,row["id"]); self.inbox_list.addItem(item)

    def accept_inbox_item(self):
        selected=self.inbox_list.selectedItems()
        if not selected:return
        evidence_id=self.store.accept_inbox(selected[0].data(Qt.UserRole))
        self.refresh_inbox(); self.refresh_evidence(); self.refresh_overview(); self.status.setText(f"Accepted as E-{evidence_id:04d}")

    def discard_inbox_item(self):
        selected=self.inbox_list.selectedItems()
        if not selected:return
        inbox_id=selected[0].data(Qt.UserRole)
        if QMessageBox.question(self,"Discard collected item","Mark this inbox item discarded? The review decision remains recorded.")!=QMessageBox.Yes:return
        self.store.db.execute("UPDATE evidence_inbox SET status='discarded' WHERE id=?",(inbox_id,)); self.store.log(self.case_id,"Inbox item discarded",f"I-{inbox_id:04d}"); self.store.db.commit(); self.refresh_inbox(); self.refresh_overview()

    def add_target(self):
        if not self.require_case():return
        target_type,ok=QInputDialog.getItem(self,"Add target","Type:",list(self.providers.keys()),0,False)
        if not ok:return
        value,ok=QInputDialog.getText(self,"Add target",f"{target_type} value:")
        if not ok or not value.strip():return
        purpose,ok=QInputDialog.getText(self,"Target purpose","Authorized investigative purpose:")
        if not ok:return
        self.store.add_target(self.case_id,target_type,value.strip(),purpose.strip()); self.store.add_entity(self.case_id,target_type,value.strip(),"Case target",90); self.refresh_overview(); self.refresh_graph()

    def refresh_overview(self):
        if not hasattr(self,"overview_summary"):return
        self.target_list.clear(); self.activity_list.clear()
        if not self.case_id:
            self.investigation_status.setText("NO ACTIVE CASE  ·  COLLECTION WILL NOT BE RETAINED"); self.overview_summary.setText("Create or select a case to begin."); return
        case=self.store.case_record(self.case_id)
        targets=self.store.targets(self.case_id); evidence=self.store.evidence(self.case_id); entities=self.store.entities(self.case_id); findings=self.store.findings(self.case_id); inbox=self.store.inbox(self.case_id)
        scope="DEFINED" if (case["scope"] or "").strip() else "MISSING"; authorization="RECORDED" if (case["authorization"] or "").strip() else "MISSING"
        self.investigation_status.setText(f"SCOPE  {scope}  ·  AUTHORIZATION  {authorization}  ·  TARGETS {len(targets)}  ·  EVIDENCE {len(evidence)}  ·  ENTITIES {len(entities)}  ·  FINDINGS {len(findings)}")
        self.overview_summary.setText(f"ACTIVE CASE  {case['name']}\nSTATUS       {case['status'].upper()}\nAUTHORIZATION {authorization}\nSCOPE         {scope}\nEVIDENCE      {len(evidence)} ACCEPTED · {len(inbox)} UNREVIEWED\nENTITIES      {len(entities)}\nFINDINGS      {len(findings)}")
        for row in targets:self.target_list.addItem(f"{row['type'].upper()}  ·  {row['value']}  ·  {row['status'].upper()}\n{row['purpose'] or 'No purpose recorded'}")
        self.progress_summary.setText(f"CASE CREATED       ✓\nSCOPE DEFINED      {'✓' if scope=='DEFINED' else '⚠'}\nAUTHORIZATION      {'✓' if authorization=='RECORDED' else '⚠'}\nTARGETS DEFINED    {'✓' if targets else '○'}\nCOLLECTION         {'●' if inbox else '○'}\nANALYST REVIEW     {'⚠ '+str(len(inbox))+' INBOX ITEMS' if inbox else '○'}\nFINDINGS           {len(findings)} DRAFT/REVIEWED")
        for row in self.store.activity(self.case_id):self.activity_list.addItem(f"{row['created_utc']}  ·  {row['action']}\n{row['detail']}")

    def verify_hashes(self):
        if not self.require_case(): return
        good = bad = missing = unverifiable = 0
        for row in self.store.evidence(self.case_id):
            if not row["local_path"] or not row["sha256"]: unverifiable += 1; continue
            if not Path(row["local_path"]).exists(): missing += 1; continue
            try: digest=self.store.evidence_digest(self.case_id,row["local_path"])
            except Exception: bad += 1; continue
            if digest == row["sha256"]: good += 1
            else: bad += 1
        QMessageBox.information(self, "Integrity verification", f"Verified: {good}\nChanged or invalid: {bad}\nMissing files: {missing}\nNo stored digest: {unverifiable}")

    def export_report(self):
        if not self.require_case(): return
        if not self.confirm_decrypted_output("Export HTML"): return
        target, _ = QFileDialog.getSaveFileName(self, "Export report", "command-intel-report.html", "HTML (*.html)")
        if not target: return
        Path(target).write_text(self.case_report_html(), encoding="utf-8")
        self.status.setText(f"Report exported to {target}")

    def case_report_html(self):
        case = self.store.case_record(self.case_id)
        rows = self.store.evidence(self.case_id); entities = self.store.entities(self.case_id); findings=self.store.findings(self.case_id)
        body = [f"<h1>{html.escape(case['name'])}</h1><p>Created {case['created_utc']}</p>",
                f"<h2>Scope &amp; Authorization</h2><p><b>Authorization:</b> {html.escape(case['authorization'] or 'Not recorded')}</p><p><b>Scope:</b> {html.escape(case['scope'] or 'Not recorded')}</p>",
                "<h2>Approved Findings</h2><ol>" + "".join(f"<li><b>{html.escape(r['title'])}</b> · confidence {html.escape(r['confidence'])}<p>{html.escape(r['narrative'])}</p></li>" for r in findings if r["status"]=="approved") + "</ol>",
                "<h2>Evidence</h2><table><tr><th>UTC</th><th>Type</th><th>Title</th><th>SHA-256</th><th>Source</th></tr>"]
        for row in rows: body.append("<tr>" + "".join(f"<td>{html.escape(str(row[key] or ''))}</td>" for key in ("created_utc","kind","title","sha256","source")) + "</tr>")
        body.append("</table><h2>Entities</h2><ul>" + "".join(f"<li>{html.escape(r['type'])}: {html.escape(r['value'])} ({r['confidence']}%)</li>" for r in entities) + "</ul>")
        return "<!doctype html><meta charset='utf-8'><style>body{font-family:sans-serif;color:#111}table{border-collapse:collapse;width:100%}td,th{border:1px solid #555;padding:7px}h1,h2{color:#123b59}</style>" + "".join(body)

    def confirm_decrypted_output(self, action):
        return not self.store.is_protected(self.case_id) or QMessageBox.question(self,action,"This output contains decrypted protected-case data. Continue?")==QMessageBox.Yes

    def export_pdf(self):
        if not self.require_case(): return
        if not self.confirm_decrypted_output("Export PDF"): return
        target,_=QFileDialog.getSaveFileName(self,"Export case PDF",f"command-intel-case-{self.case_id}.pdf","PDF (*.pdf)")
        if not target:return
        printer=QPrinter(QPrinter.PrinterMode.HighResolution); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(target)
        document=QTextDocument(); document.setHtml(self.case_report_html()); document.print_(printer); self.status.setText(f"PDF exported to {target}")

    def print_case(self):
        if not self.require_case(): return
        if not self.confirm_decrypted_output("Print case"): return
        printer=QPrinter(QPrinter.PrinterMode.HighResolution); dialog=QPrintDialog(printer,self)
        if dialog.exec()!=QDialog.Accepted:return
        document=QTextDocument(); document.setHtml(self.case_report_html()); document.print_(printer); self.status.setText("Case sent to printer")

    def build_graph(self):
        page = QWidget(); layout = QVBoxLayout(page); controls = QHBoxLayout()
        add = QPushButton("Add entity"); relate = QPushButton("Connect selected entities"); refresh = QPushButton("Refresh")
        controls.addWidget(add); controls.addWidget(relate); controls.addWidget(refresh); controls.addStretch()
        self.entity_list = QListWidget(); self.entity_list.setSelectionMode(QListWidget.MultiSelection)
        self.graph_scene = QGraphicsScene(); self.graph_view = QGraphicsView(self.graph_scene)
        split = QSplitter(); split.addWidget(self.entity_list); split.addWidget(self.graph_view); split.setStretchFactor(1, 1)
        layout.addLayout(controls); layout.addWidget(split)
        add.clicked.connect(self.add_entity); relate.clicked.connect(self.connect_entities); refresh.clicked.connect(self.refresh_graph)
        self.tabs.addTab(page, "Graph")

    def add_entity(self):
        if not self.require_case(): return
        value, ok = QInputDialog.getText(self, "Entity", "Value:")
        if not ok or not value.strip(): return
        kind, ok = QInputDialog.getItem(self, "Entity type", "Type:", ["Person","Username","Email","Phone","Domain","IP Address","Company","Location","Document","Other"], 0, False)
        if ok: self.store.add_entity(self.case_id, kind, value.strip(), "Manual", 70); self.refresh_graph()

    def connect_entities(self):
        selected = self.entity_list.selectedItems()
        if len(selected) != 2: QMessageBox.information(self, "Graph", "Select exactly two entities."); return
        label, ok = QInputDialog.getText(self, "Relationship", "Connection label:")
        if ok and label.strip(): self.store.add_relation(self.case_id, selected[0].data(Qt.UserRole), selected[1].data(Qt.UserRole), label.strip()); self.refresh_graph()

    def refresh_graph(self):
        self.entity_list.clear(); self.graph_scene.clear()
        if not self.case_id: return
        entities = self.store.entities(self.case_id); positions = {}
        columns = 4
        for index, row in enumerate(entities):
            item = QListWidgetItem(f"{row['type']} · {row['value']} · {row['confidence']}%"); item.setData(Qt.UserRole, row["id"]); self.entity_list.addItem(item)
            x, y = (index % columns) * 210, (index // columns) * 120; positions[row["id"]] = (x, y)
            rect = self.graph_scene.addRect(x, y, 175, 62); rect.setToolTip(f"Source: {row['source']}")
            text = self.graph_scene.addText(f"{row['type']}\n{row['value'][:24]}"); text.setDefaultTextColor(Qt.white); text.setPos(x + 8, y + 6)
        for rel in self.store.relations(self.case_id):
            if rel["source_entity"] in positions and rel["target_entity"] in positions:
                a, b = positions[rel["source_entity"]], positions[rel["target_entity"]]
                self.graph_scene.addLine(a[0] + 87, a[1] + 62, b[0] + 87, b[1]); label = self.graph_scene.addText(rel["label"]); label.setDefaultTextColor(Qt.cyan); label.setPos((a[0]+b[0])/2, (a[1]+b[1])/2)

    def build_tools(self):
        page = QWidget(); layout = QVBoxLayout(page)
        self.tool_list = QListWidget()
        tools = [("ExifTool", "exiftool", "Inspect file metadata"), ("Nmap", "nmap", "Authorized network discovery"), ("Sherlock", "sherlock", "Username enumeration"), ("Maigret", "maigret", "Username enumeration"), ("Amass", "amass", "Domain mapping"), ("theHarvester", "theHarvester", "Public-source domain research"), ("SpiderFoot", "spiderfoot", "OSINT automation"), ("yt-dlp", "yt-dlp", "Media metadata")]
        for title, command, description in tools:
            state = "INSTALLED" if shutil.which(command) else "NOT INSTALLED"
            item = QListWidgetItem(f"{title:<18} {state:<15} {description}"); item.setData(Qt.UserRole, command); self.tool_list.addItem(item)
        controls = QHBoxLayout(); run = QPushButton("Run selected in terminal"); import_results = QPushButton("Import structured JSON"); workflow = QPushButton("Run domain workflow"); controls.addWidget(run); controls.addWidget(import_results); controls.addWidget(workflow); controls.addStretch()
        self.workflow_output = QPlainTextEdit(); self.workflow_output.setReadOnly(True)
        layout.addWidget(self.tool_list); layout.addLayout(controls); layout.addWidget(self.workflow_output)
        run.clicked.connect(self.run_tool); import_results.clicked.connect(self.import_structured_results); workflow.clicked.connect(self.domain_workflow)
        self.tabs.addTab(page, "Workflows")

    def run_tool(self):
        item = self.tool_list.currentItem()
        if not item: return
        command = item.data(Qt.UserRole)
        if not shutil.which(command): QMessageBox.information(self, "Tool unavailable", f"{command} is not installed."); return
        argument, ok = QInputDialog.getText(self, "Tool argument", f"Authorized input for {command}:")
        if not ok: return
        terminals = [["konsole", "-e"], ["gnome-terminal", "--"], ["xterm", "-e"]]
        for terminal in terminals:
            if shutil.which(terminal[0]): subprocess.Popen(terminal + [command, argument]); self.store.log(self.case_id, "Tool launched", f"{command} {argument}"); return

    def import_structured_results(self):
        if not self.require_case(): return
        source, _ = QFileDialog.getOpenFileName(self, "Import structured tool results", "", "JSON (*.json)")
        if not source: return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Import failed", str(error)); return
        rows = payload if isinstance(payload, list) else payload.get("entities", []) if isinstance(payload, dict) else []
        imported = 0
        for row in rows:
            if not isinstance(row, dict): continue
            value = str(row.get("value") or row.get("host") or row.get("username") or "").strip()
            if value:
                kind = str(row.get("type") or ("IP Address" if row.get("host") else "Other"))
                self.store.add_entity(self.case_id, kind, value, f"Imported: {Path(source).name}", int(row.get("confidence", 60))); imported += 1
        digest = self.hash_file(source)
        self.store.add_evidence(self.case_id, Path(source).name, "tool-results", source, source, digest, f"Imported {imported} structured entities")
        self.refresh_evidence(); self.refresh_graph(); self.status.setText(f"Imported {imported} entities")

    def domain_workflow(self):
        domain, ok = QInputDialog.getText(self, "Domain workflow", "Authorized domain:")
        if not ok or not domain.strip(): return
        domain = domain.strip(); self.workflow_output.setPlainText("Workflow started:\n• Certificate history\n• Web archive\n• VirusTotal\n• SecurityTrails\n• WHOIS")
        for url in (f"https://crt.sh/?q={domain}", f"https://web.archive.org/web/*/{domain}", f"https://www.virustotal.com/gui/domain/{domain}", f"https://securitytrails.com/domain/{domain}/history/a", f"https://who.is/whois/{domain}"): self.open_url(url)
        if self.case_id: self.store.add_entity(self.case_id, "Domain", domain, "Domain workflow", 90); self.store.log(self.case_id, "Workflow", f"Domain investigation: {domain}")

    def build_ai(self):
        page = QWidget(); layout = QVBoxLayout(page)
        notice = QLabel("Evidence-grounded assistant. Local Ollama is used when installed; generated text is analysis, not evidence."); notice.setObjectName("muted")
        self.ai_prompt = QPlainTextEdit(); self.ai_prompt.setPlaceholderText("Ask about the active case…")
        buttons = QHBoxLayout(); summarize = QPushButton("Summarize case"); ask = QPushButton("Ask local AI"); buttons.addWidget(summarize); buttons.addWidget(ask); buttons.addStretch()
        self.ai_output = QPlainTextEdit(); self.ai_output.setReadOnly(True)
        layout.addWidget(notice); layout.addWidget(self.ai_prompt); layout.addLayout(buttons); layout.addWidget(self.ai_output, 1)
        summarize.clicked.connect(self.summarize_case); ask.clicked.connect(self.ask_ai)
        self.tabs.addTab(page, "Analysis")

    def build_findings(self):
        page=QWidget(); layout=QVBoxLayout(page)
        notice=QLabel("Findings are human-reviewed investigative conclusions. AI may assist drafting but cannot approve a finding."); notice.setObjectName("muted"); notice.setWordWrap(True); layout.addWidget(notice)
        controls=QHBoxLayout(); add=QPushButton("NEW DRAFT FINDING"); approve=QPushButton("APPROVE SELECTED"); link=QPushButton("LINK EVIDENCE")
        controls.addWidget(add); controls.addWidget(approve); controls.addWidget(link); controls.addStretch(); layout.addLayout(controls)
        self.finding_list=QListWidget(); layout.addWidget(self.finding_list)
        add.clicked.connect(self.add_finding); approve.clicked.connect(self.approve_finding); link.clicked.connect(self.link_finding_evidence)
        self.tabs.addTab(page,"Findings")

    def refresh_findings(self):
        if not hasattr(self,"finding_list"):return
        self.finding_list.clear()
        for row in self.store.findings(self.case_id) if self.case_id else []:
            linked=self.store.db.execute("SELECT COUNT(*) FROM finding_evidence WHERE finding_id=?",(row["id"],)).fetchone()[0]
            item=QListWidgetItem(f"F-{row['id']:04d}  ·  {row['status'].upper()}  ·  CONFIDENCE {row['confidence'].upper()}\n{row['title']}\n{row['narrative']}\n{linked} linked evidence item(s)"); item.setData(Qt.UserRole,row["id"]); self.finding_list.addItem(item)

    def add_finding(self):
        if not self.require_case():return
        title,ok=QInputDialog.getText(self,"Draft finding","Title:")
        if not ok or not title.strip():return
        narrative,ok=QInputDialog.getMultiLineText(self,"Draft finding","Analyst narrative:")
        if not ok:return
        confidence,ok=QInputDialog.getItem(self,"Finding confidence","Confidence:",["low","medium","high"],1,False)
        if ok:self.store.add_finding(self.case_id,title.strip(),narrative.strip(),confidence); self.refresh_findings(); self.refresh_overview()

    def approve_finding(self):
        selected=self.finding_list.selectedItems()
        if not selected:return
        finding_id=selected[0].data(Qt.UserRole)
        linked=self.store.db.execute("SELECT COUNT(*) FROM finding_evidence WHERE finding_id=?",(finding_id,)).fetchone()[0]
        if not linked:
            QMessageBox.information(self,"Finding review","Link at least one accepted evidence item before approval.");return
        if QMessageBox.question(self,"Approve finding","Approve this human-reviewed finding for reporting?")!=QMessageBox.Yes:return
        self.store.db.execute("UPDATE findings SET status='approved',updated_utc=? WHERE id=?",(self.store.now(),finding_id)); self.store.log(self.case_id,"Finding approved",f"F-{finding_id:04d}"); self.store.db.commit(); self.refresh_findings(); self.refresh_overview()

    def link_finding_evidence(self):
        selected=self.finding_list.selectedItems()
        if not selected or not self.require_case():return
        evidence=self.store.evidence(self.case_id)
        if not evidence:QMessageBox.information(self,"Findings","No accepted evidence is available.");return
        labels=[f"E-{row['id']:04d} · {row['title']}" for row in evidence]
        label,ok=QInputDialog.getItem(self,"Link supporting evidence","Evidence:",labels,0,False)
        if not ok:return
        evidence_id=evidence[labels.index(label)]["id"]; finding_id=selected[0].data(Qt.UserRole)
        self.store.db.execute("INSERT OR IGNORE INTO finding_evidence(finding_id,evidence_id,role) VALUES(?,?,'supporting')",(finding_id,evidence_id)); self.store.log(self.case_id,"Evidence linked to finding",f"E-{evidence_id:04d} → F-{finding_id:04d}"); self.store.db.commit(); self.refresh_findings()

    def case_context(self):
        if not self.case_id: return "No active case."
        evidence = self.store.evidence(self.case_id); entities = self.store.entities(self.case_id)
        return "ENTITIES\n" + "\n".join(f"[{r['id']}] {r['type']}: {r['value']} (source: {r['source']})" for r in entities) + "\nEVIDENCE\n" + "\n".join(f"[{r['id']}] {r['title']} | {r['source']} | {r['notes']}" for r in evidence)

    def summarize_case(self):
        if not self.require_case(): return
        entities = self.store.entities(self.case_id); evidence = self.store.evidence(self.case_id)
        kinds = {}
        for row in entities: kinds[row["type"]] = kinds.get(row["type"], 0) + 1
        self.ai_output.setPlainText(f"Case summary (deterministic)\n\n{len(entities)} entities · {len(evidence)} evidence items\n" + "\n".join(f"• {key}: {value}" for key, value in kinds.items()) + "\n\nReview every source before drawing conclusions.")

    def ask_ai(self):
        if not self.require_case(): return
        if not shutil.which("ollama"): QMessageBox.information(self, "Local AI unavailable", "Install Ollama and a local model to enable generative case analysis. Deterministic summaries remain available."); return
        models = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10).stdout.splitlines()[1:]
        if not models: QMessageBox.information(self, "No local model", "Download an Ollama model first."); return
        if self.ollama_process and self.ollama_process.state()!=QProcess.ProcessState.NotRunning: QMessageBox.information(self,"Local AI","An analysis is already running."); return
        model = models[0].split()[0]; prompt = "Use only the supplied case evidence. Cite item IDs in brackets. State when evidence is insufficient.\n\n" + self.case_context() + "\n\nQUESTION\n" + self.ai_prompt.toPlainText()
        self.ai_output.setPlainText("Analyzing locally… The interface remains available.")
        self.ollama_process=QProcess(self); self.ollama_process.setProgram("ollama"); self.ollama_process.setArguments(["run",model,prompt])
        self.ollama_process.finished.connect(self.ollama_finished); self.ollama_process.start()

    def ollama_finished(self, code, status):
        output=bytes(self.ollama_process.readAllStandardOutput()).decode("utf-8",errors="replace")
        error=bytes(self.ollama_process.readAllStandardError()).decode("utf-8",errors="replace")
        self.ai_output.setPlainText(output or error or f"Local AI exited with code {code}")

    def shutdown(self):
        if self.ollama_process and self.ollama_process.state()!=QProcess.ProcessState.NotRunning:
            self.ollama_process.kill(); self.ollama_process.waitForFinished(2000)
        self.store.case_keys.clear()
        self.store.db.close()
