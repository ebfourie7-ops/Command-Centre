#!/usr/bin/env python3
"""Collect per-GPU and per-disk telemetry for Command Widget."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except (OSError, ValueError):
        return default


def number(path, scale=1):
    try:
        return float(read(path)) / scale
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


def temperature(device):
    candidates = sorted(device.glob("hwmon/hwmon*/temp1_input"))
    return round(number(candidates[0], 1000)) if candidates else 0


def gpu_devices():
    devices = []
    nvidia_slots = set()
    try:
        query = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,pci.bus_id,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        ).stdout
        for line in query.splitlines():
            fields = [part.strip() for part in line.split(",")]
            if len(fields) != 7:
                continue
            index, slot, name, usage, used, total, temp = fields
            slot = slot.lower().replace("00000000:", "0000:")
            nvidia_slots.add(slot)
            stable_id = f"pci-{slot}" if slot else f"nvidia-{index}"
            devices.append({
                "id": stable_id, "legacy_id": f"nvidia-{index}", "name": name, "kind": "Dedicated GPU",
                "usage": float(usage or 0), "vram": f"{float(used) / 1024:.1f}/{float(total) / 1024:.1f} GB",
                "temp": float(temp or 0),
            })
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        pass

    vendors = {"0x1002": ("AMD", "Integrated GPU"), "0x8086": ("Intel", "Integrated GPU"), "0x10de": ("NVIDIA", "Dedicated GPU")}
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        if not card.name[4:].isdigit():
            continue
        device = card / "device"
        vendor = read(device / "vendor")
        if vendor not in vendors:
            continue
        slot = device.resolve().name.lower()
        if vendor == "0x10de" and slot in nvidia_slots:
            continue
        vendor_name, kind = vendors[vendor]
        usage = number(device / "gpu_busy_percent")
        used = number(device / "mem_info_vram_used", 1024 ** 3)
        total = number(device / "mem_info_vram_total", 1024 ** 3)
        vram = f"{used:.1f}/{total:.1f} GB" if total else "shared"
        devices.append({
            "id": f"pci-{slot}", "legacy_id": card.name, "name": f"{vendor_name} {kind}", "kind": kind,
            "usage": usage, "vram": vram, "temp": temperature(device),
        })
    return devices


def cpu_cores():
    def snapshot():
        result = {}
        for line in read("/proc/stat").splitlines():
            fields = line.split()
            if not fields or not fields[0].startswith("cpu") or fields[0] == "cpu":
                continue
            values = [int(value) for value in fields[1:]]
            idle = sum(values[3:5])
            result[fields[0]] = (idle, sum(values))
        return result

    first = snapshot()
    time.sleep(0.1)
    second = snapshot()
    cores = []
    for key in sorted(second, key=lambda item: int(item[3:])):
        idle_delta = second[key][0] - first.get(key, second[key])[0]
        total_delta = second[key][1] - first.get(key, second[key])[1]
        usage = max(min((1 - idle_delta / total_delta) * 100, 100), 0) if total_delta else 0
        cores.append({"id": key, "name": key.upper(), "usage": round(usage, 1)})
    return cores


def diskstats():
    stats = {}
    for line in read("/proc/diskstats").splitlines():
        fields = line.split()
        if len(fields) >= 14:
            stats[fields[2]] = [int(fields[5]) * 512, int(fields[9]) * 512]
    return stats


def rate_text(value):
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB/s"
    if value >= 1024:
        return f"{value / 1024:.0f} KB/s"
    return f"{value:.0f} B/s"


def disk_health(device_name, cache):
    cached = cache.get(device_name, {})
    if time.time() - cached.get("checked", 0) < 300 and cached.get("health") != "Warning":
        return cached
    result = {"checked": time.time(), "health": "Unknown", "temperature": 0}
    try:
        output = subprocess.run(
            ["smartctl", "-H", "-A", f"/dev/{device_name}"], capture_output=True,
            text=True, timeout=3, check=False,
        ).stdout
        upper = output.upper()
        if "PASSED" in upper or "OK" in upper:
            result["health"] = "Good"
        elif "SMART OVERALL-HEALTH" in upper and "FAILED" in upper:
            result["health"] = "Warning"
        for line in output.splitlines():
            if "Temperature:" in line or "Temperature_Celsius" in line:
                values = [token for token in line.replace("Celsius", "").split() if token.isdigit()]
                if values:
                    result["temperature"] = int(values[-1])
                    break
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    cache[device_name] = result
    return result


def storage_devices(sample_path):
    try:
        payload = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,KNAME,TYPE,LABEL,MOUNTPOINTS,SIZE,FSUSED,FSUSE%,MODEL"],
            capture_output=True, text=True, timeout=2, check=False,
        ).stdout
        blockdevices = json.loads(payload).get("blockdevices", [])
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
        blockdevices = []

    now = time.time()
    current = diskstats()
    try:
        previous_payload = json.loads(Path(sample_path).read_text())
    except (OSError, json.JSONDecodeError):
        previous_payload = {"time": now, "stats": {}}
    elapsed = max(now - float(previous_payload.get("time", now)), 0.001)
    previous = previous_payload.get("stats", {})
    try:
        Path(sample_path).write_text(json.dumps({"time": now, "stats": current}))
    except OSError:
        pass

    health_path = Path(sample_path).with_suffix(".health.json")
    try:
        health_cache = json.loads(health_path.read_text())
    except (OSError, json.JSONDecodeError):
        health_cache = {}
    devices = []
    for disk in blockdevices:
        if disk.get("type") != "disk" or disk.get("name", "").startswith(("loop", "zram", "ram")):
            continue
        children = disk.get("children") or []
        mounted = [item for item in children if any(item.get("mountpoints") or [])]
        filesystem = next((item for item in mounted if "/" in (item.get("mountpoints") or [])), mounted[0] if mounted else disk)
        size = float(filesystem.get("size") or disk.get("size") or 0)
        used = float(filesystem.get("fsused") or 0)
        percent_text = str(filesystem.get("fsuse%") or "0").replace("%", "")
        try:
            percent = float(percent_text)
        except ValueError:
            percent = 0
        child_labels = [str(item.get("label") or "").strip() for item in children]
        if any("/" in (item.get("mountpoints") or []) for item in children):
            name = "ROOT"
        elif "OS" in child_labels or "Windows" in child_labels:
            name = "DRIVE C"
        else:
            label = str(filesystem.get("label") or disk.get("label") or "").strip()
            name = label.upper()[:12] if label else disk.get("name", "SSD").upper()
        key = disk.get("kname") or disk.get("name")
        before = previous.get(key, current.get(key, [0, 0]))
        after = current.get(key, [0, 0])
        read_rate = max((after[0] - before[0]) / elapsed, 0)
        write_rate = max((after[1] - before[1]) / elapsed, 0)
        usage = f"{used / 1024 ** 3:.1f}/{size / 1024 ** 3:.1f} GB" if used else f"{size / 1024 ** 3:.1f} GB total"
        health = disk_health(key, health_cache)
        hwmon_temps = sorted((Path("/sys/class/block") / key / "device").glob("hwmon*/temp1_input"))
        if hwmon_temps:
            health["temperature"] = round(number(hwmon_temps[0], 1000))
        devices.append({
            "id": key, "name": str(name).strip(), "model": str(disk.get("model") or "").strip(),
            "usage": usage, "percent": percent, "read": rate_text(read_rate), "write": rate_text(write_rate),
            "health": health.get("health", "Unknown"), "temp": health.get("temperature", 0),
        })
    try:
        health_path.write_text(json.dumps(health_cache))
    except OSError:
        pass
    return devices


def network_interfaces(sample_path):
    now = time.time()
    current = {}
    for iface in sorted(Path("/sys/class/net").iterdir()):
        if iface.name == "lo" or iface.name.startswith(("veth", "docker", "br-", "virbr")):
            continue
        rx = number(iface / "statistics/rx_bytes")
        tx = number(iface / "statistics/tx_bytes")
        current[iface.name] = [rx, tx]
    net_path = Path(sample_path).with_suffix(".network.json")
    try:
        old = json.loads(net_path.read_text())
    except (OSError, json.JSONDecodeError):
        old = {"time": now, "stats": {}}
    elapsed = max(now - float(old.get("time", now)), 0.001)
    try:
        net_path.write_text(json.dumps({"time": now, "stats": current}))
    except OSError:
        pass
    result = []
    for name, values in current.items():
        before = old.get("stats", {}).get(name, values)
        down = max((values[0] - before[0]) / elapsed, 0)
        up = max((values[1] - before[1]) / elapsed, 0)
        state = read(Path("/sys/class/net") / name / "operstate", "unknown")
        kind = "VPN" if name.startswith(("tun", "tap", "wg", "tailscale", "ppp")) else ("Wi-Fi" if (Path("/sys/class/net") / name / "wireless").exists() else "Ethernet")
        result.append({"id": name, "name": name, "kind": kind, "state": state,
                       "down": rate_text(down), "up": rate_text(up),
                       "percent": min(round((down + up) / 125000000 * 100, 1), 100)})
    result.sort(key=lambda item: (item["state"] != "up", item["kind"] == "VPN", item["name"]))
    active = [item for item in result if item["state"] == "up"]
    if result:
        def rate_value(text):
            value, unit = text.split()[:2]
            factor = {"B/s": 1, "KB/s": 1024, "MB/s": 1024 ** 2}.get(unit, 1)
            return float(value) * factor
        combined_down = sum(rate_value(item["down"]) for item in active)
        combined_up = sum(rate_value(item["up"]) for item in active)
        combined = {"id": "combined", "name": "ALL", "kind": "Combined", "state": "up" if active else "down",
                    "down": rate_text(combined_down), "up": rate_text(combined_up),
                    "percent": min(round((combined_down + combined_up) / 125000000 * 100, 1), 100)}
        result.insert(0, combined)
    return result


def main():
    sample_path = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".local/state/telemetry/storage-devices.sample")
    print(json.dumps({
        "gpu_devices": gpu_devices(), "storage_devices": storage_devices(sample_path),
        "cpu_cores": cpu_cores(), "network_interfaces": network_interfaces(sample_path),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
