#!/usr/bin/env node
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile } = require("child_process");

const PORT = Number(process.env.PORT || 4780);
const ROOT = __dirname;
const PUBLIC = path.join(ROOT, "public");
const STATE_FILE = path.join(os.homedir(), ".local/state/telemetry/telemetry.json");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml; charset=utf-8",
};

const commandPreviews = [
  {
    id: "gaming-mode",
    title: "Start Gaming Mode",
    area: "Profiles",
    command: "powerprofilesctl set performance && systemctl --user stop background-indexers.target",
    risk: "Medium",
    description: "Switches to performance mode and pauses background services configured for gaming.",
  },
  {
    id: "battery-saver",
    title: "Start Battery Saver",
    area: "Profiles",
    command: "powerprofilesctl set power-saver",
    risk: "Low",
    description: "Switches the system power profile to power saver.",
  },
  {
    id: "failed-services",
    title: "Check Failed Services",
    area: "Diagnostics",
    command: "systemctl --failed --no-pager",
    risk: "Read only",
    description: "Lists system services currently in a failed state.",
  },
  {
    id: "package-refresh",
    title: "Refresh Package Databases",
    area: "Software",
    command: "sudo pacman -Syy",
    risk: "Medium",
    description: "Refreshes package databases for Arch/CachyOS repositories.",
  },
  {
    id: "disk-health",
    title: "Check Disk Health",
    area: "Storage",
    command: "sudo smartctl -a /dev/nvme0",
    risk: "Read only",
    description: "Displays SMART health data for the primary NVMe disk.",
  },
  {
    id: "network-routes",
    title: "Inspect Routes",
    area: "Network",
    command: "ip route && resolvectl status",
    risk: "Read only",
    description: "Shows routing and DNS state for network troubleshooting.",
  },
  {
    id: "build-iso",
    title: "Build CommandOS ISO",
    area: "Deployment",
    command: "sudo mkarchiso -v ./profiles/commandos",
    risk: "High",
    description: "Placeholder for the future CommandOS ISO build workflow.",
  },
];

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 100000) req.destroy();
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        resolve({});
      }
    });
    req.on("error", () => resolve({}));
  });
}

function execText(cmd, args, timeout = 1500) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (error, stdout) => {
      if (error) {
        resolve("");
        return;
      }
      resolve(stdout.trim());
    });
  });
}

function execCapture(cmd, args, timeout = 5000) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        code: error?.code ?? 0,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
      });
    });
  });
}

async function hasCommand(cmd) {
  const result = await execCapture("which", [cmd], 1000);
  return result.ok;
}

async function getPowerState() {
  if (!(await hasCommand("powerprofilesctl"))) {
    return { available: false, active: "unavailable", profiles: [] };
  }

  const [active, list] = await Promise.all([
    execText("powerprofilesctl", ["get"], 1200),
    execText("powerprofilesctl", ["list"], 1200),
  ]);

  const profiles = Array.from(new Set((list.match(/\b(performance|balanced|power-saver)\b/g) || ["performance", "balanced", "power-saver"])));
  return { available: true, active: active || "unknown", profiles };
}

async function getWifiState() {
  if (!(await hasCommand("nmcli"))) {
    return { available: false, enabled: null, label: "nmcli unavailable" };
  }

  const radio = await execText("nmcli", ["radio", "wifi"], 1200);
  const devices = await execText("nmcli", ["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], 1500);
  const wifiDevices = devices
    .split("\n")
    .filter((line) => line.includes(":wifi:"))
    .map((line) => {
      const [device, , state, connection] = line.split(":");
      return { device, state, connection: connection || "" };
    });

  return { available: true, enabled: radio === "enabled", label: radio || "unknown", devices: wifiDevices };
}

async function getBluetoothState() {
  if (!(await hasCommand("bluetoothctl"))) {
    return { available: false, enabled: null, label: "bluetoothctl unavailable" };
  }

  const output = await execText("bluetoothctl", ["show"], 1500);
  const powered = /Powered:\s+yes/i.test(output);
  const controller = output.match(/Name:\s+(.+)/)?.[1] || "Bluetooth";
  return { available: Boolean(output), enabled: powered, label: output ? (powered ? "enabled" : "disabled") : "not detected", controller };
}

async function getAudioState() {
  if (!(await hasCommand("pactl"))) {
    return { available: false, defaultSink: "", sinks: [] };
  }

  const [defaultSink, sinkRows] = await Promise.all([
    execText("pactl", ["get-default-sink"], 1200),
    execText("pactl", ["list", "short", "sinks"], 1500),
  ]);
  const sinks = sinkRows
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const parts = line.split("\t");
      return { id: parts[0], name: parts[1], driver: parts[2] || "" };
    });

  return { available: true, defaultSink, sinks };
}

async function getUserServices() {
  const output = await execText("systemctl", ["--user", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"], 2200);
  return output
    .split("\n")
    .filter(Boolean)
    .slice(0, 80)
    .map((line) => {
      const parts = line.trim().split(/\s+/);
      return {
        name: parts[0],
        load: parts[1] || "",
        active: parts[2] || "",
        sub: parts[3] || "",
        description: parts.slice(4).join(" "),
      };
    });
}

async function getControlState() {
  const [power, wifi, bluetooth, audio, services] = await Promise.all([
    getPowerState(),
    getWifiState(),
    getBluetoothState(),
    getAudioState(),
    getUserServices(),
  ]);

  return { power, wifi, bluetooth, audio, services };
}

function validServiceName(name) {
  return typeof name === "string" && /^[A-Za-z0-9_.@:\\-]+\.service$/.test(name);
}

async function runControlAction(body) {
  const action = body.action;

  if (action === "setPowerProfile") {
    const profile = body.profile;
    if (!["performance", "balanced", "power-saver"].includes(profile)) {
      return { ok: false, message: "Invalid power profile." };
    }
    const result = await execCapture("powerprofilesctl", ["set", profile], 5000);
    return { ...result, message: result.ok ? `Power profile set to ${profile}.` : result.stderr || "Power profile change failed." };
  }

  if (action === "setWifi") {
    const enabled = Boolean(body.enabled);
    const result = await execCapture("nmcli", ["radio", "wifi", enabled ? "on" : "off"], 5000);
    return { ...result, message: result.ok ? `Wi-Fi turned ${enabled ? "on" : "off"}.` : result.stderr || "Wi-Fi change failed." };
  }

  if (action === "setBluetooth") {
    const enabled = Boolean(body.enabled);
    const result = await execCapture("bluetoothctl", ["power", enabled ? "on" : "off"], 5000);
    return { ...result, message: result.ok ? `Bluetooth turned ${enabled ? "on" : "off"}.` : result.stderr || "Bluetooth change failed." };
  }

  if (action === "setDefaultSink") {
    const sink = String(body.sink || "");
    if (!/^[A-Za-z0-9_.:-]+$/.test(sink)) {
      return { ok: false, message: "Invalid audio sink." };
    }
    const result = await execCapture("pactl", ["set-default-sink", sink], 5000);
    return { ...result, message: result.ok ? "Default audio output changed." : result.stderr || "Audio output change failed." };
  }

  if (action === "service") {
    const serviceAction = body.serviceAction;
    const service = body.service;
    if (!["start", "stop", "restart"].includes(serviceAction) || !validServiceName(service)) {
      return { ok: false, message: "Invalid service action." };
    }
    const result = await execCapture("systemctl", ["--user", serviceAction, service], 8000);
    return { ...result, message: result.ok ? `${serviceAction} sent to ${service}.` : result.stderr || "Service action failed." };
  }

  return { ok: false, message: "Unknown control action." };
}

function readTelemetryFile() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return null;
  }
}

function requestTelemetryHttp() {
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:9090/telemetry", { timeout: 900 }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch {
          resolve(null);
        }
      });
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(null);
    });
    req.on("error", () => resolve(null));
  });
}

async function getSystemPayload() {
  const telemetry = (await requestTelemetryHttp()) || readTelemetryFile() || {};
  const [kernel, uptimeRaw, failedServices, updatesRaw] = await Promise.all([
    execText("uname", ["-r"]),
    execText("uptime", ["-p"]),
    execText("systemctl", ["--failed", "--no-legend", "--no-pager"], 1800),
    execText("checkupdates", [], 2500),
  ]);

  return {
    hostname: os.hostname(),
    platform: "CommandOS base",
    kernel: kernel || os.release(),
    uptime: uptimeRaw || `${Math.floor(os.uptime() / 3600)}h`,
    failedServices: failedServices ? failedServices.split("\n").filter(Boolean).length : 0,
    updates: updatesRaw ? updatesRaw.split("\n").filter(Boolean).length : null,
    telemetry,
    memory: {
      totalGb: Number((os.totalmem() / 1073741824).toFixed(1)),
      freeGb: Number((os.freemem() / 1073741824).toFixed(1)),
    },
  };
}

function serveStatic(req, res) {
  const requestPath = decodeURIComponent(new URL(req.url, `http://127.0.0.1:${PORT}`).pathname);
  const relative = requestPath === "/" ? "index.html" : requestPath.slice(1);
  const filePath = path.normalize(path.join(PUBLIC, relative));

  if (!filePath.startsWith(PUBLIC)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    res.writeHead(200, { "Content-Type": contentTypes[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/api/system") {
    sendJson(res, 200, await getSystemPayload());
    return;
  }

  if (url.pathname === "/api/commands") {
    sendJson(res, 200, commandPreviews);
    return;
  }

  if (url.pathname === "/api/control" && req.method === "GET") {
    sendJson(res, 200, await getControlState());
    return;
  }

  if (url.pathname === "/api/control/action" && req.method === "POST") {
    const body = await readBody(req);
    sendJson(res, 200, await runControlAction(body));
    return;
  }

  serveStatic(req, res);
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Command Centre running at http://127.0.0.1:${PORT}`);
});
