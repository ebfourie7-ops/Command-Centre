import hashlib
import html
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGraphicsScene, QGraphicsView, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)


DATA_DIR = Path.home() / ".local/share/command-centre/intel"
DB_FILE = DATA_DIR / "intel.db"
EVIDENCE_DIR = DATA_DIR / "evidence"


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

    def interceptRequest(self, info):
        if any(value in info.requestUrl().host().lower() for value in self.blocked):
            info.block(True)


class IntelStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(DB_FILE)
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
        """)
        self.db.commit()

    @staticmethod
    def now():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def cases(self):
        return self.db.execute("SELECT * FROM cases ORDER BY updated_utc DESC").fetchall()

    def add_case(self, name, description=""):
        now = self.now()
        cursor = self.db.execute(
            "INSERT INTO cases(name, description, created_utc, updated_utc) VALUES(?,?,?,?)",
            (name, description, now, now),
        )
        self.db.commit()
        return cursor.lastrowid

    def evidence(self, case_id):
        return self.db.execute("SELECT * FROM evidence WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()

    def add_evidence(self, case_id, title, kind, source="", local_path="", digest="", notes=""):
        cursor = self.db.execute(
            "INSERT INTO evidence(case_id,title,kind,source,local_path,sha256,notes,created_utc) VALUES(?,?,?,?,?,?,?,?)",
            (case_id, title, kind, source, local_path, digest, notes, self.now()),
        )
        self.log(case_id, "Evidence added", title)
        self.db.commit()
        return cursor.lastrowid

    def add_entity(self, case_id, entity_type, value, source="", confidence=50):
        self.db.execute(
            "INSERT OR IGNORE INTO entities(case_id,type,value,source,confidence) VALUES(?,?,?,?,?)",
            (case_id, entity_type, value, source, confidence),
        )
        self.db.commit()

    def entities(self, case_id):
        return self.db.execute("SELECT * FROM entities WHERE case_id=? ORDER BY id", (case_id,)).fetchall()

    def add_relation(self, case_id, source_id, target_id, label, evidence_id=None):
        self.db.execute(
            "INSERT OR IGNORE INTO relations(case_id,source_entity,target_entity,label,evidence_id) VALUES(?,?,?,?,?)",
            (case_id, source_id, target_id, label, evidence_id),
        )
        self.db.commit()

    def relations(self, case_id):
        return self.db.execute("SELECT * FROM relations WHERE case_id=?", (case_id,)).fetchall()

    def log(self, case_id, action, detail=""):
        self.db.execute(
            "INSERT INTO activity(case_id,action,detail,created_utc) VALUES(?,?,?,?)",
            (case_id, action, detail, self.now()),
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
        self.blocker = RequestBlocker(self)
        self.tabs = QTabWidget()
        self.browser_tabs = QTabWidget()
        self.browser_tabs.setTabsClosable(True)
        self.browser_tabs.tabCloseRequested.connect(self.close_browser_tab)
        self.case_combo = QComboBox()
        self.case_combo.currentIndexChanged.connect(self.select_case)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.build_dashboard()
        self.build_browser()
        self.build_cases()
        self.build_graph()
        self.build_tools()
        self.build_ai()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
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
        hero, hero_layout = self.frame("COMMAND INTEL  ·  OSINT RESOURCE CENTRE")
        row = QHBoxLayout()
        self.resource_filter = QLineEdit(); self.resource_filter.setPlaceholderText("Filter resources…")
        row.addWidget(QLabel("Active case:")); row.addWidget(self.case_combo); row.addWidget(self.resource_filter, 1)
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
        self.tabs.addTab(page, "Resources")

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
            self.store.add_entity(self.case_id, self.target_type.currentText(), value, "Manual query", 80)
            self.store.log(self.case_id, "OSINT search", f"{self.target_type.currentText()}: {value}")

    def build_browser(self):
        page = QWidget(); layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        new = QPushButton("+"); back = QPushButton("←"); forward = QPushButton("→"); reload_button = QPushButton("↻")
        self.address = QLineEdit(); self.address.setPlaceholderText("URL")
        self.privacy = QComboBox(); self.privacy.addItems(["Standard", "Strict (no JavaScript)", "External browser"])
        capture = QPushButton("Capture evidence"); external = QPushButton("External")
        for widget in (new, back, forward, reload_button): bar.addWidget(widget)
        bar.addWidget(QLabel("● AD BLOCK ON")); bar.addWidget(self.address, 1); bar.addWidget(self.privacy); bar.addWidget(capture); bar.addWidget(external)
        layout.addLayout(bar); layout.addWidget(self.browser_tabs, 1)
        new.clicked.connect(lambda: self.new_browser_tab("https://duckduckgo.com"))
        back.clicked.connect(lambda: self.current_browser() and self.current_browser().back())
        forward.clicked.connect(lambda: self.current_browser() and self.current_browser().forward())
        reload_button.clicked.connect(lambda: self.current_browser() and self.current_browser().reload())
        self.address.returnPressed.connect(lambda: self.open_url(self.address.text()))
        capture.clicked.connect(self.capture_page)
        external.clicked.connect(lambda: self.current_browser() and QDesktopServices.openUrl(self.current_browser().url()))
        self.privacy.currentTextChanged.connect(self.apply_privacy)
        self.tabs.addTab(page, "Research Browser")

    def current_browser(self):
        return self.browser_tabs.currentWidget()

    def new_browser_tab(self, url):
        view = QWebEngineView(); view.page().profile().setUrlRequestInterceptor(self.blocker)
        view.urlChanged.connect(lambda value, browser=view: self.browser_url_changed(browser, value))
        view.titleChanged.connect(lambda title, browser=view: self.browser_title_changed(browser, title))
        index = self.browser_tabs.addTab(view, "New tab"); self.browser_tabs.setCurrentIndex(index)
        self.apply_privacy(); view.setUrl(QUrl(url)); return view

    def open_url(self, url):
        if not url.startswith(("http://", "https://")): url = "https://" + url
        if self.privacy.currentText() == "External browser": QDesktopServices.openUrl(QUrl(url)); return
        self.new_browser_tab(url); self.tabs.setCurrentIndex(1)

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
        page = QWidget(); layout = QGridLayout(page)
        cases, cases_layout = self.frame("CASES")
        self.case_list = QListWidget(); new = QPushButton("New case"); report = QPushButton("Export HTML report")
        cases_layout.addWidget(self.case_list); cases_layout.addWidget(new); cases_layout.addWidget(report)
        evidence, evidence_layout = self.frame("EVIDENCE · SHA-256 INTEGRITY")
        buttons = QHBoxLayout(); add_file = QPushButton("Import file"); add_note = QPushButton("Add note"); verify = QPushButton("Verify hashes")
        buttons.addWidget(add_file); buttons.addWidget(add_note); buttons.addWidget(verify)
        self.evidence_table = QTableWidget(0, 5); self.evidence_table.setHorizontalHeaderLabels(["UTC", "Type", "Title", "SHA-256", "Source"])
        evidence_layout.addLayout(buttons); evidence_layout.addWidget(self.evidence_table)
        layout.addWidget(cases, 0, 0); layout.addWidget(evidence, 0, 1); layout.setColumnStretch(1, 2)
        new.clicked.connect(self.new_case); report.clicked.connect(self.export_report); add_file.clicked.connect(self.import_file)
        add_note.clicked.connect(self.add_note_evidence); verify.clicked.connect(self.verify_hashes); self.case_list.currentItemChanged.connect(self.case_list_changed)
        self.tabs.addTab(page, "Cases & Evidence")

    def refresh_cases(self):
        active = self.case_id
        self.case_list.clear(); self.case_combo.blockSignals(True); self.case_combo.clear()
        for row in self.store.cases():
            item = QListWidgetItem(f"{row['name']}\n{row['updated_utc']}"); item.setData(Qt.UserRole, row["id"]); self.case_list.addItem(item)
            self.case_combo.addItem(row["name"], row["id"])
        self.case_combo.blockSignals(False)
        if active:
            index = self.case_combo.findData(active)
            if index >= 0: self.case_combo.setCurrentIndex(index)
        elif self.case_combo.count(): self.select_case(0)

    def new_case(self):
        name, ok = QInputDialog.getText(self, "New investigation", "Case name:")
        if ok and name.strip(): self.case_id = self.store.add_case(name.strip()); self.refresh_cases(); self.refresh_evidence()

    def select_case(self, index):
        self.case_id = self.case_combo.itemData(index) if index >= 0 else None
        for i in range(self.case_list.count()):
            if self.case_list.item(i).data(Qt.UserRole) == self.case_id: self.case_list.setCurrentRow(i); break
        self.refresh_evidence(); self.refresh_graph()

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
        self.store.add_evidence(self.case_id, source_path.name, "file", str(source_path), str(destination), digest)
        self.refresh_evidence()

    def add_note_evidence(self):
        if not self.require_case(): return
        text, ok = QInputDialog.getMultiLineText(self, "Evidence note", "Observation:")
        if ok and text.strip(): self.store.add_evidence(self.case_id, text.strip().splitlines()[0][:80], "note", notes=text); self.refresh_evidence()

    def capture_page(self):
        if not self.require_case() or not self.current_browser(): return
        browser = self.current_browser(); case_dir = EVIDENCE_DIR / str(self.case_id); case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / f"web-{int(time.time())}.png"
        if browser.grab().save(str(path), "PNG"):
            digest = self.hash_file(path); self.store.add_evidence(self.case_id, browser.title() or "Web capture", "screenshot", browser.url().toString(), str(path), digest)
            self.refresh_evidence(); self.status.setText(f"Captured {path.name}")

    def refresh_evidence(self):
        rows = self.store.evidence(self.case_id) if self.case_id else []
        self.evidence_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["created_utc"], row["kind"], row["title"], row["sha256"], row["source"]]
            for c, value in enumerate(values): self.evidence_table.setItem(r, c, QTableWidgetItem(value or ""))

    def verify_hashes(self):
        if not self.require_case(): return
        good = bad = 0
        for row in self.store.evidence(self.case_id):
            if row["local_path"] and row["sha256"] and Path(row["local_path"]).exists():
                if self.hash_file(row["local_path"]) == row["sha256"]: good += 1
                else: bad += 1
        QMessageBox.information(self, "Integrity verification", f"Verified: {good}\nChanged or invalid: {bad}")

    def export_report(self):
        if not self.require_case(): return
        target, _ = QFileDialog.getSaveFileName(self, "Export report", "command-intel-report.html", "HTML (*.html)")
        if not target: return
        case = self.store.db.execute("SELECT * FROM cases WHERE id=?", (self.case_id,)).fetchone()
        rows = self.store.evidence(self.case_id); entities = self.store.entities(self.case_id)
        body = [f"<h1>{html.escape(case['name'])}</h1><p>Created {case['created_utc']}</p>", "<h2>Evidence</h2><table><tr><th>UTC</th><th>Type</th><th>Title</th><th>SHA-256</th><th>Source</th></tr>"]
        for row in rows: body.append("<tr>" + "".join(f"<td>{html.escape(str(row[key] or ''))}</td>" for key in ("created_utc","kind","title","sha256","source")) + "</tr>")
        body.append("</table><h2>Entities</h2><ul>" + "".join(f"<li>{html.escape(r['type'])}: {html.escape(r['value'])} ({r['confidence']}%)</li>" for r in entities) + "</ul>")
        Path(target).write_text("<!doctype html><meta charset='utf-8'><style>body{font-family:sans-serif;max-width:1100px;margin:auto;background:#111;color:#eee}table{border-collapse:collapse;width:100%}td,th{border:1px solid #555;padding:7px}</style>" + "".join(body), encoding="utf-8")
        self.status.setText(f"Report exported to {target}")

    def build_graph(self):
        page = QWidget(); layout = QVBoxLayout(page); controls = QHBoxLayout()
        add = QPushButton("Add entity"); relate = QPushButton("Connect selected entities"); refresh = QPushButton("Refresh")
        controls.addWidget(add); controls.addWidget(relate); controls.addWidget(refresh); controls.addStretch()
        self.entity_list = QListWidget(); self.entity_list.setSelectionMode(QListWidget.MultiSelection)
        self.graph_scene = QGraphicsScene(); self.graph_view = QGraphicsView(self.graph_scene)
        split = QSplitter(); split.addWidget(self.entity_list); split.addWidget(self.graph_view); split.setStretchFactor(1, 1)
        layout.addLayout(controls); layout.addWidget(split)
        add.clicked.connect(self.add_entity); relate.clicked.connect(self.connect_entities); refresh.clicked.connect(self.refresh_graph)
        self.tabs.addTab(page, "Investigation Graph")

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
        controls = QHBoxLayout(); run = QPushButton("Run selected in terminal"); workflow = QPushButton("Run domain workflow"); controls.addWidget(run); controls.addWidget(workflow); controls.addStretch()
        self.workflow_output = QPlainTextEdit(); self.workflow_output.setReadOnly(True)
        layout.addWidget(self.tool_list); layout.addLayout(controls); layout.addWidget(self.workflow_output)
        run.clicked.connect(self.run_tool); workflow.clicked.connect(self.domain_workflow)
        self.tabs.addTab(page, "Tools & Workflows")

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
        self.tabs.addTab(page, "Command AI")

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
        model = models[0].split()[0]; prompt = "Use only the supplied case evidence. Cite item IDs in brackets. State when evidence is insufficient.\n\n" + self.case_context() + "\n\nQUESTION\n" + self.ai_prompt.toPlainText()
        self.ai_output.setPlainText("Analyzing locally…"); result = subprocess.run(["ollama", "run", model, prompt], capture_output=True, text=True, timeout=180)
        self.ai_output.setPlainText(result.stdout or result.stderr)
