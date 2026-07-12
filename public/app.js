const modules = [
  {
    id: "dashboard",
    icon: "SY",
    title: "System Dashboard",
    summary: "Live health, performance, updates, services, and hardware status.",
    cards: [],
  },
  {
    id: "control",
    icon: "SC",
    title: "System Control",
    summary: "Performance profiles, power, services, startup, display, audio, Wi-Fi, and Bluetooth.",
    cards: [
      ["Power Profiles", "Switch between performance, balanced, and power saver modes.", ["Performance mode", "Battery saver", "Service presets"]],
      ["Services", "Inspect and manage user-approved system services.", ["Failed services", "Startup services", "Repair previews"]],
      ["Devices", "Control everyday hardware entry points.", ["Displays", "Audio", "Bluetooth"]],
    ],
  },
  {
    id: "software",
    icon: "SW",
    title: "Software Centre",
    summary: "Package, AUR, Flatpak, AppImage, cache repair, and package list workflows.",
    cards: [
      ["Packages", "Track installed packages and planned repository actions.", ["Official repos", "AUR queue", "Package export"]],
      ["Maintenance", "Prepare safe repair commands before they run.", ["Clean cache", "Repair database", "Refresh mirrors"]],
      ["Libraries", "Organize local tools by purpose and install state.", ["Installed tools", "Offline repo", "Updates"]],
    ],
  },
  {
    id: "tools",
    icon: "TL",
    title: "CommandOS Tool Library",
    summary: "Launch and document toolsets for forensics, networking, radio, development, AI, and more.",
    cards: [
      ["Field Tools", "Curated application groups for fast launch.", ["Forensics", "Networking", "Radio/SDR"]],
      ["Build Tools", "Development, electronics, CAD, and 3D printing surfaces.", ["Development", "CAD", "3D printing"]],
      ["Knowledge", "Descriptions, docs, install state, and terminal commands.", ["Tool docs", "Command previews", "Update state"]],
    ],
  },
  {
    id: "network",
    icon: "NO",
    title: "Network Operations",
    summary: "Interfaces, routes, DNS, VPN, firewall, bandwidth, discovery, packet capture, and SSH.",
    cards: [
      ["Interfaces", "Watch active links and addressing.", ["IP state", "Traffic", "VPN status"]],
      ["Diagnostics", "Common troubleshooting commands with previews.", ["Routes", "DNS", "Connectivity"]],
      ["Remote Access", "SSH targets, Wake-on-LAN, and remote status.", ["SSH profiles", "Known hosts", "Remote checks"]],
    ],
  },
  {
    id: "hardware",
    icon: "HW",
    title: "Hardware Centre",
    summary: "Hardware inventory, disks, sensors, GPU, displays, serial, SDR, printers, and radios.",
    cards: [
      ["Inventory", "PCI, USB, disks, and connected devices.", ["PCI", "USB", "Serial"]],
      ["Sensors", "Temperatures, fans, battery, and NVIDIA data.", ["CPU temp", "GPU temp", "Fans"]],
      ["Peripherals", "Displays, SDR hardware, printers, and 3D printers.", ["Displays", "SDR", "Printers"]],
    ],
  },
  {
    id: "storage",
    icon: "DS",
    title: "Storage & Disk",
    summary: "Mounts, encrypted volumes, SMART tests, imaging, ISO tools, backups, and cloning.",
    cards: [
      ["Disk Health", "SMART and filesystem check previews.", ["SMART", "Filesystem", "Usage"]],
      ["Imaging", "Forensic and system imaging workflows.", ["Read-only mount", "Hashing", "Clone jobs"]],
      ["Removable Media", "USB formatting, ISO mounting, and boot media.", ["ISO mount", "USB write", "Backup jobs"]],
    ],
  },
  {
    id: "radio",
    icon: "RF",
    title: "Radio & SDR",
    summary: "SDR detection, radio tools, frequencies, presets, serial ports, APRS, satellites, and modes.",
    cards: [
      ["Devices", "Detect SDR hardware and radio interfaces.", ["RTL-SDR", "Serial ports", "Radio profiles"]],
      ["Presets", "Frequency plans, antenna notes, and launch profiles.", ["Frequencies", "Antennas", "Digital modes"]],
      ["Operations", "Future workspace for spectrum and satellite tools.", ["APRS", "Sat tracking", "Spectrum"]],
    ],
  },
  {
    id: "security",
    icon: "SF",
    title: "Security & Forensics",
    summary: "Cases, evidence drives, hashes, packet captures, metadata, reports, and isolated workspaces.",
    cards: [
      ["Cases", "Authorized target and case management placeholders.", ["Case profiles", "Evidence notes", "Reports"]],
      ["Evidence", "Read-only mount, hashing, imaging, and metadata workflow previews.", ["Hashing", "Disk image", "Metadata"]],
      ["Network Capture", "Packet capture launcher and analysis tools.", ["Capture", "PCAPs", "Reports"]],
    ],
  },
  {
    id: "ai",
    icon: "AI",
    title: "Local AI Centre",
    summary: "Local models, inference servers, RAG libraries, log analysis, and approved control hooks.",
    cards: [
      ["Models", "Track local models and GPU/VRAM availability.", ["Model list", "Downloads", "VRAM use"]],
      ["Servers", "Start and stop local inference services with previews.", ["Ollama", "Open WebUI", "API ports"]],
      ["Assistance", "Search docs, analyze logs, and troubleshoot hardware.", ["Docs search", "Log review", "Terminal help"]],
    ],
  },
  {
    id: "offline",
    icon: "OK",
    title: "Offline Knowledge",
    summary: "Wikipedia, Gutenberg, Linux docs, Arch Wiki mirrors, repair manuals, maps, PDFs, and references.",
    cards: [
      ["Indexes", "Track local knowledge libraries and search status.", ["Arch Wiki", "Manuals", "Maps"]],
      ["Libraries", "Group offline books, PDFs, and technical references.", ["Gutenberg", "PDFs", "Electronics"]],
      ["Search", "Future unified search across offline resources.", ["Metadata", "Tags", "Full text"]],
    ],
  },
  {
    id: "automation",
    icon: "AU",
    title: "Automation Centre",
    summary: "Composable workflows for radio, forensics, gaming, recovery, and field operations.",
    cards: [
      ["Workflows", "Build multi-step sequences with command previews.", ["Gaming mode", "Forensic drive", "SDR launch"]],
      ["Approvals", "Every changeable action stays confirm-first.", ["Preview", "Confirm", "Log"]],
      ["History", "Future audit log for completed automation runs.", ["Runs", "Results", "Rollback notes"]],
    ],
  },
  {
    id: "deployment",
    icon: "DP",
    title: "Deployment Centre",
    summary: "ISO configs, package manifests, offline repos, branding, checksums, USB writing, and builds.",
    cards: [
      ["ISO Profiles", "Manage Stable, Testing, and Development build presets.", ["Stable", "Testing", "Development"]],
      ["Manifests", "Track packages, presets, branding, and installer configuration.", ["Packages", "Branding", "Installer"]],
      ["Builds", "Validate, checksum, and write CommandOS images.", ["Build ISO", "Checksums", "Write USB"]],
    ],
  },
];

const modes = [
  ["Daily Driver", "Balanced desktop", "blue"],
  ["Gaming", "Performance profile", "red"],
  ["Development", "Tools and services", "blue"],
  ["Field Ops", "Offline ready", "green"],
  ["Recovery", "Repair surface", "green"],
];

const state = {
  module: "dashboard",
  mode: "Daily Driver",
  system: null,
  control: null,
  commands: [],
};

const $ = (id) => document.getElementById(id);

function clamp(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}

function setWidth(id, value) {
  $(id).style.width = `${clamp(value)}%`;
}

function text(id, value) {
  $(id).textContent = value;
}

function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("'", "&#39;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderNav() {
  $("moduleNav").innerHTML = modules
    .map((module) => `
      <button class="nav-button ${module.id === state.module ? "active" : ""}" data-module="${module.id}">
        <span class="nav-icon">${module.icon}</span>
        <span>${module.title}</span>
      </button>
    `)
    .join("");

  document.querySelectorAll("[data-module]").forEach((button) => {
    button.addEventListener("click", () => setModule(button.dataset.module));
  });
}

function renderModes() {
  $("modeStrip").innerHTML = modes
    .map(([name, description, color]) => `
      <button class="mode-button ${state.mode === name ? "active" : ""}" data-mode="${name}" data-color="${color}">
        ${name}
        <span>${description}</span>
      </button>
    `)
    .join("");

  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      renderModes();
    });
  });
}

function renderCommands(commands = state.commands) {
  $("commandList").innerHTML = commands.slice(0, 5).map(commandTemplate).join("");
}

function commandTemplate(command) {
  return `
    <article class="command-item">
      <div class="command-title">
        <span>${command.title}</span>
        <span>${command.risk}</span>
      </div>
      <p>${command.description}</p>
      <code>${command.command}</code>
    </article>
  `;
}

function controlButton(label, action, payload = {}, extraClass = "") {
  return `<button class="control-button ${extraClass}" data-action="${action}" data-payload='${escapeAttr(JSON.stringify(payload))}'>${label}</button>`;
}

function serviceRow(service) {
  const running = service.active === "active";
  return `
    <article class="service-row">
      <div>
        <strong>${service.name}</strong>
        <span>${service.active}/${service.sub} ${service.description ? `- ${service.description}` : ""}</span>
      </div>
      <div class="row-actions">
        ${controlButton("Start", "service", { service: service.name, serviceAction: "start" }, running ? "muted" : "")}
        ${controlButton("Stop", "service", { service: service.name, serviceAction: "stop" }, running ? "" : "muted")}
        ${controlButton("Restart", "service", { service: service.name, serviceAction: "restart" })}
      </div>
    </article>
  `;
}

function renderControl() {
  const control = state.control || {};
  const power = control.power || { profiles: [] };
  const wifi = control.wifi || {};
  const bluetooth = control.bluetooth || {};
  const audio = control.audio || { sinks: [] };
  const services = (control.services || []).filter((service) => service.name);

  $("moduleContent").innerHTML = `
    <section class="control-grid">
      <article class="control-panel wide">
        <div class="panel-head">
          <h3>Power Profile</h3>
          <span class="pill">${power.active || "unknown"}</span>
        </div>
        <div class="segmented">
          ${["performance", "balanced", "power-saver"].map((profile) => `
            <button class="${power.active === profile ? "active" : ""}" data-action="setPowerProfile" data-payload='${escapeAttr(JSON.stringify({ profile }))}' ${power.available ? "" : "disabled"}>
              ${profile === "power-saver" ? "Power Saver" : profile[0].toUpperCase() + profile.slice(1)}
            </button>
          `).join("")}
        </div>
        <p class="control-note">Uses powerprofilesctl and updates the same power mode shown in your widget.</p>
      </article>

      <article class="control-panel">
        <div class="panel-head">
          <h3>Wi-Fi</h3>
          <span class="pill neutral">${wifi.label || "unknown"}</span>
        </div>
        <div class="toggle-row">
          ${controlButton("Turn On", "setWifi", { enabled: true }, wifi.enabled ? "muted" : "")}
          ${controlButton("Turn Off", "setWifi", { enabled: false }, wifi.enabled ? "" : "muted")}
        </div>
        <div class="mini-list">
          ${(wifi.devices || []).map((device) => `<span>${device.device}: ${device.state}${device.connection ? ` / ${device.connection}` : ""}</span>`).join("") || "<span>No Wi-Fi devices reported.</span>"}
        </div>
      </article>

      <article class="control-panel">
        <div class="panel-head">
          <h3>Bluetooth</h3>
          <span class="pill neutral">${bluetooth.label || "unknown"}</span>
        </div>
        <div class="toggle-row">
          ${controlButton("Turn On", "setBluetooth", { enabled: true }, bluetooth.enabled ? "muted" : "")}
          ${controlButton("Turn Off", "setBluetooth", { enabled: false }, bluetooth.enabled ? "" : "muted")}
        </div>
        <p class="control-note">${bluetooth.controller || "Bluetooth controller status depends on bluetoothctl."}</p>
      </article>

      <article class="control-panel wide">
        <div class="panel-head">
          <h3>Audio Output</h3>
          <span class="pill neutral">${audio.defaultSink || "unavailable"}</span>
        </div>
        <div class="sink-list">
          ${(audio.sinks || []).map((sink) => `
            <button class="sink-button ${audio.defaultSink === sink.name ? "active" : ""}" data-action="setDefaultSink" data-payload='${escapeAttr(JSON.stringify({ sink: sink.name }))}' ${audio.available ? "" : "disabled"}>
              <strong>${sink.name}</strong>
              <span>${sink.driver || "audio sink"}</span>
            </button>
          `).join("") || "<p class='control-note'>No PulseAudio/PipeWire sinks reported by pactl.</p>"}
        </div>
      </article>

      <article class="control-panel services">
        <div class="panel-head">
          <h3>User Services</h3>
          <span class="pill neutral">${services.length} loaded</span>
        </div>
        <div class="service-list">
          ${services.slice(0, 18).map(serviceRow).join("") || "<p class='control-note'>No user services reported.</p>"}
        </div>
      </article>

      <article class="control-panel wide">
        <div class="panel-head">
          <h3>Action Result</h3>
          <span class="pill neutral">Local only</span>
        </div>
        <pre id="controlResult" class="result-box">Ready.</pre>
      </article>
    </section>
  `;

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => runControlAction(button));
  });
}

async function loadControl() {
  try {
    const response = await fetch("/api/control", { cache: "no-store" });
    state.control = await response.json();
    if (state.module === "control") renderControl();
  } catch {
    state.control = {};
    if (state.module === "control") renderControl();
  }
}

async function runControlAction(button) {
  const action = button.dataset.action;
  const payload = JSON.parse(button.dataset.payload || "{}");
  const label = button.textContent.trim();
  const confirmed = window.confirm(`Run this System Control action?\n\n${label}`);
  if (!confirmed) return;

  button.disabled = true;
  const resultBox = $("controlResult");
  if (resultBox) resultBox.textContent = "Running...";

  try {
    const response = await fetch("/api/control/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    const result = await response.json();
    if (resultBox) {
      resultBox.textContent = `${result.ok ? "OK" : "FAILED"}: ${result.message || ""}\n${result.stdout || result.stderr || ""}`.trim();
    }
  } catch (error) {
    if (resultBox) resultBox.textContent = `FAILED: ${error.message}`;
  } finally {
    button.disabled = false;
    await Promise.all([loadControl(), loadSystem()]);
  }
}

function renderSystem() {
  const payload = state.system || {};
  const telemetry = payload.telemetry || {};

  text("hostLabel", payload.hostname || "CommandOS");
  text("cpuValue", `${Number(clamp(telemetry.cpu_usage)).toFixed(1)}%`);
  text("cpuMeta", `${telemetry.cpu_frequency || "n/a"} / ${telemetry.cpu_temp || "n/a"}C`);
  setWidth("cpuBar", telemetry.cpu_usage);

  text("gpuValue", `${Number(clamp(telemetry.gpu_usage)).toFixed(0)}%`);
  text("gpuMeta", `${telemetry.gpu_vram || "VRAM n/a"} / ${telemetry.gpu_temp || "n/a"}C`);
  setWidth("gpuBar", telemetry.gpu_usage);

  text("ramValue", telemetry.ram_info || `${payload.memory?.freeGb || "--"} GB free`);
  text("ramMeta", `${Number(clamp(telemetry.ram_usage)).toFixed(1)}% used`);
  setWidth("ramBar", telemetry.ram_usage);

  text("netValue", telemetry.network_iface || "offline");
  text("netMeta", `Down ${telemetry.network_down || "0 B/s"} / Up ${telemetry.network_up || "0 B/s"} / ${telemetry.vpn_status || "VPN OFF"}`);
  setWidth("netBar", telemetry.network_percent);

  text("kernelValue", payload.kernel || "--");
  text("uptimeValue", payload.uptime || "--");
  text("storageValue", `${telemetry.storage_name || "ROOT"} ${telemetry.storage_usage || "--"} (${telemetry.storage_percent || "--"}%)`);
  text("batteryValue", `${telemetry.battery_status || "n/a"} ${telemetry.battery_percent || "--"}% / ${telemetry.battery_watts || "--"}W`);
  text("failedValue", String(payload.failedServices ?? "--"));
  text("updatesValue", payload.updates === null ? "checkupdates unavailable" : String(payload.updates ?? "--"));
  text("modePill", telemetry.power_profile_label || "Unknown");
}

function setModule(id) {
  state.module = id;
  renderNav();

  const module = modules.find((item) => item.id === id) || modules[0];
  text("activeTitle", module.title);

  $("dashboardView").classList.toggle("active", id === "dashboard");
  $("moduleView").classList.toggle("active", id !== "dashboard");

  if (id === "control") {
    renderControl();
    loadControl();
  } else if (id !== "dashboard") {
    $("moduleContent").innerHTML = module.cards
      .map(([title, description, items]) => `
        <article class="module-card">
          <h3>${title}</h3>
          <p>${description}</p>
          <ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>
        </article>
      `)
      .join("");
  }
}

async function loadSystem() {
  try {
    const response = await fetch("/api/system", { cache: "no-store" });
    state.system = await response.json();
    renderSystem();
  } catch {
    state.system = { telemetry: {} };
    renderSystem();
  }
}

async function loadCommands() {
  const response = await fetch("/api/commands", { cache: "no-store" });
  state.commands = await response.json();
  renderCommands();
  renderPaletteResults("");
}

function openPalette() {
  $("palette").showModal();
  $("paletteInput").value = "";
  renderPaletteResults("");
  requestAnimationFrame(() => $("paletteInput").focus());
}

function renderPaletteResults(query) {
  const search = query.trim().toLowerCase();
  const moduleResults = modules
    .filter((module) => module.title.toLowerCase().includes(search) || module.summary.toLowerCase().includes(search))
    .map((module) => ({
      title: module.title,
      risk: "Open",
      description: module.summary,
      command: `open module:${module.id}`,
      module: module.id,
    }));

  const commandResults = state.commands.filter((command) => {
    const haystack = `${command.title} ${command.area} ${command.description} ${command.command}`.toLowerCase();
    return haystack.includes(search);
  });

  const results = [...moduleResults, ...commandResults].slice(0, 10);
  $("paletteResults").innerHTML = results.map(commandTemplate).join("") || `<div class="command-item"><p>No matches</p></div>`;

  document.querySelectorAll("#paletteResults .command-item").forEach((item, index) => {
    const result = results[index];
    if (result?.module) {
      item.addEventListener("click", () => {
        $("palette").close();
        setModule(result.module);
      });
    }
  });
}

function bindEvents() {
  $("refreshButton").addEventListener("click", loadSystem);
  $("refreshButton").addEventListener("click", loadControl);
  $("paletteButton").addEventListener("click", openPalette);
  $("paletteInput").addEventListener("input", (event) => renderPaletteResults(event.target.value));

  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openPalette();
    }
  });
}

renderNav();
renderModes();
bindEvents();
setModule("dashboard");
loadCommands();
loadSystem();
loadControl();
setInterval(loadSystem, 5000);
setInterval(loadControl, 10000);
