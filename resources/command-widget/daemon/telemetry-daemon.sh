#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/telemetry"
STATE_FILE="$STATE_DIR/telemetry.json"
PID_FILE="$STATE_DIR/telemetry-daemon.pid"
NET_SAMPLE_FILE="$STATE_DIR/network.sample"
STORAGE_SAMPLE_FILE="$STATE_DIR/storage.sample"
FAN_MAX_RPM="${FAN_MAX_RPM:-6000}"
NET_SCALE_BPS="${NET_SCALE_BPS:-125000000}"

mkdir -p "$STATE_DIR"

if [ -z "${INVOCATION_ID:-}" ]; then
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Telemetry daemon is already running."
    exit 0
  fi
fi

echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"; exit 0' EXIT INT TERM

percent_from_proc_stat() {
  local first second idle1 idle2 total1 total2 idle_diff total_diff

  first=$(awk '/^cpu / {print $5, $2+$3+$4+$5+$6+$7+$8+$9+$10}' /proc/stat)
  sleep 0.1
  second=$(awk '/^cpu / {print $5, $2+$3+$4+$5+$6+$7+$8+$9+$10}' /proc/stat)

  idle1=${first%% *}
  total1=${first##* }
  idle2=${second%% *}
  total2=${second##* }
  idle_diff=$((idle2 - idle1))
  total_diff=$((total2 - total1))

  awk -v idle="$idle_diff" -v total="$total_diff" \
    'BEGIN { if (total > 0) printf "%.1f", (1 - idle / total) * 100; else printf "0.0" }'
}

ram_percent() {
  awk '/MemTotal:/ {total=$2} /MemAvailable:/ {available=$2}
       END { if (total > 0) printf "%.1f", (total - available) / total * 100; else printf "0.0" }' /proc/meminfo
}

ram_display() {
  awk '/MemTotal:/ {total=$2} /MemAvailable:/ {available=$2}
       END { printf "%.1f/%.1f GB", (total - available) / 1048576, total / 1048576 }' /proc/meminfo
}

cpu_temp() {
  local temp

  temp=$(find /sys/class/hwmon -name 'temp*_input' -exec cat {} + 2>/dev/null \
    | awk '$1 > 0 && $1 < 120000 { if ($1 > max) max=$1 } END { if (max) print max }')

  if [ -z "$temp" ]; then
    temp=$(find /sys/class/thermal -name temp -exec cat {} + 2>/dev/null \
      | awk '$1 > 0 && $1 < 120000 { if ($1 > max) max=$1 } END { if (max) print max }')
  fi

  if [ -n "$temp" ]; then
    awk -v temp="$temp" 'BEGIN { printf "%.0f", temp / 1000 }'
  else
    printf "0"
  fi
}

cpu_frequency() {
  local freq

  freq=$(find /sys/devices/system/cpu -path '*/cpufreq/scaling_cur_freq' -exec cat {} + 2>/dev/null \
    | awk '$1 > 0 { total += $1; count++ } END { if (count > 0) printf "%.2f GHz", total / count / 1000000 }')

  if [ -n "$freq" ]; then
    printf "%s" "$freq"
    return
  fi

  awk -F': ' '/cpu MHz/ { total += $2; count++ }
       END { if (count > 0) printf "%.2f GHz", total / count / 1000; else printf "n/a" }' /proc/cpuinfo
}

gpu_name() {
  local name vendor

  if command -v nvidia-smi >/dev/null 2>&1; then
    name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || true)
    if [ -n "$name" ] && ! printf "%s" "$name" | grep -qi "failed"; then
      printf "%s" "$name"
      return
    fi
  fi

  vendor=$(find /sys/class/drm -maxdepth 2 -name vendor -print 2>/dev/null | head -1)
  if [ -n "$vendor" ]; then
    case "$(cat "$vendor" 2>/dev/null)" in
      0x1002) printf "AMD GPU" ;;
      0x8086) printf "Intel GPU" ;;
      0x10de) printf "NVIDIA GPU" ;;
      *) printf "GPU" ;;
    esac
  else
    printf "GPU"
  fi
}

gpu_vram() {
  local vram

  if command -v nvidia-smi >/dev/null 2>&1; then
    vram=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null \
      | head -1 \
      | awk -F', ' '{ if ($1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/) printf "%.1f/%.1f GB", $1 / 1024, $2 / 1024 }' || true)
    if [ -n "$vram" ]; then
      printf "%s" "$vram"
      return
    fi
  fi

  printf "n/a"
}

gpu_percent() {
  local usage

  if command -v nvidia-smi >/dev/null 2>&1; then
    usage=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | awk '{printf "%.0f", $1}' || true)
    if [ -n "$usage" ] && printf "%s" "$usage" | grep -Eq '^[0-9]+$'; then
      printf "%s" "$usage"
      return
    fi
  fi

  printf "0"
}

gpu_temp() {
  local temp

  if command -v nvidia-smi >/dev/null 2>&1; then
    temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | awk '{printf "%.0f", $1}' || true)
    if [ -n "$temp" ] && printf "%s" "$temp" | grep -Eq '^[0-9]+$'; then
      printf "%s" "$temp"
      return
    fi
  fi

  temp=$(find /sys/class/drm -path '*/hwmon/hwmon*/temp1_input' -print 2>/dev/null \
    | head -1 \
    | xargs -r cat 2>/dev/null || true)

  if [ -n "$temp" ]; then
    awk -v temp="$temp" 'BEGIN { printf "%.0f", temp / 1000 }'
  else
    printf "0"
  fi
}

storage_percent() {
  df / | awk 'NR == 2 { gsub("%", "", $5); printf "%.1f", $5 }'
}

storage_display() {
  df / | awk 'NR == 2 { printf "%.1f/%.1f GB", $3 / 1048576, $2 / 1048576 }'
}

storage_name() {
  local label source target

  label=$(findmnt -no LABEL / 2>/dev/null | head -1 || true)
  if [ -n "$label" ]; then
    printf "%s" "$label"
    return
  fi

  target=$(findmnt -no TARGET / 2>/dev/null | head -1 || true)
  if [ "$target" = "/" ]; then
    printf "ROOT"
    return
  fi

  source=$(findmnt -no SOURCE / 2>/dev/null | head -1 || true)
  if [ -n "$source" ]; then
    basename "$source" | tr '[:lower:]' '[:upper:]'
  else
    printf "ROOT"
  fi
}

storage_device() {
  local source device

  source=$(findmnt -no SOURCE / 2>/dev/null | head -1 || true)
  source=${source%%\[*}
  device=$(basename "$source" 2>/dev/null || true)

  if [ -n "$device" ]; then
    printf "%s" "$device"
  fi
}

storage_sectors() {
  local device="$1"

  awk -v device="$device" '$3 == device { print $6, $10 }' /proc/diskstats
}

format_rate() {
  local bytes="$1"

  awk -v bytes="$bytes" \
    'BEGIN {
      if (bytes >= 1048576) printf "%.1f MB/s", bytes / 1048576;
      else if (bytes >= 1024) printf "%.0f KB/s", bytes / 1024;
      else printf "%.0f B/s", bytes;
    }'
}

storage_rates() {
  local now device sectors read_sectors write_sectors prev_now prev_device prev_read prev_write elapsed read_bps write_bps

  now=$(date +%s)
  device=$(storage_device)
  if [ -z "$device" ]; then
    printf '0 B/s|0 B/s'
    return
  fi

  sectors=$(storage_sectors "$device")
  read_sectors=${sectors%% *}
  write_sectors=${sectors##* }
  if [ -z "$read_sectors" ] || [ -z "$write_sectors" ]; then
    printf '0 B/s|0 B/s'
    return
  fi

  if [ -f "$STORAGE_SAMPLE_FILE" ]; then
    read -r prev_now prev_device prev_read prev_write < "$STORAGE_SAMPLE_FILE" || true
  fi
  printf '%s %s %s %s\n' "$now" "$device" "$read_sectors" "$write_sectors" > "$STORAGE_SAMPLE_FILE"

  if [ "${prev_device:-}" != "$device" ] || [ -z "${prev_now:-}" ] || [ "$now" -le "${prev_now:-0}" ]; then
    printf '0 B/s|0 B/s'
    return
  fi

  elapsed=$((now - prev_now))
  read_bps=$(( (read_sectors - prev_read) * 512 / elapsed ))
  write_bps=$(( (write_sectors - prev_write) * 512 / elapsed ))
  if [ "$read_bps" -lt 0 ]; then read_bps=0; fi
  if [ "$write_bps" -lt 0 ]; then write_bps=0; fi

  printf '%s|%s' "$(format_rate "$read_bps")" "$(format_rate "$write_bps")"
}

fan_rpm() {
  for file in /sys/class/hwmon/hwmon*/fan*_input; do
    [ -r "$file" ] && cat "$file"
  done \
    | awk '$1 > 0 { total += $1; count++ } END { if (count > 0) printf "%.0f", total / count; else printf "0" }'
}

fan_percent() {
  local rpm="$1"

  awk -v rpm="$rpm" -v max="$FAN_MAX_RPM" \
    'BEGIN { if (max > 0 && rpm > 0) { pct = rpm / max * 100; if (pct > 100) pct = 100; printf "%.0f", pct } else printf "0" }'
}

network_interface() {
  local iface

  iface=$(ip route get 1.1.1.1 2>/dev/null | awk '{ for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit } }')
  if [ -n "$iface" ]; then
    printf "%s" "$iface"
    return
  fi

  ip -o link show up 2>/dev/null \
    | awk -F': ' '$2 != "lo" && $2 !~ /^(docker|tailscale|veth|br-|virbr)/ { print $2; exit }'
}

network_bytes() {
  local iface="$1"

  awk -v iface="$iface" -F'[: ]+' '$2 == iface { print $3, $11 }' /proc/net/dev
}

network_rates() {
  local now iface bytes rx tx prev_now prev_iface prev_rx prev_tx elapsed down up total percent

  now=$(date +%s)
  iface=$(network_interface)
  if [ -z "$iface" ]; then
    printf 'NET|0|0|0|n/a|n/a|0'
    return
  fi

  bytes=$(network_bytes "$iface")
  rx=${bytes%% *}
  tx=${bytes##* }
  if [ -z "$rx" ] || [ -z "$tx" ]; then
    printf '%s|0|0|0|n/a|n/a|0' "$iface"
    return
  fi

  if [ -f "$NET_SAMPLE_FILE" ]; then
    read -r prev_now prev_iface prev_rx prev_tx < "$NET_SAMPLE_FILE" || true
  fi
  printf '%s %s %s %s\n' "$now" "$iface" "$rx" "$tx" > "$NET_SAMPLE_FILE"

  if [ "${prev_iface:-}" != "$iface" ] || [ -z "${prev_now:-}" ] || [ "$now" -le "${prev_now:-0}" ]; then
    printf '%s|0|0|0|0 B/s|0 B/s|0' "$iface"
    return
  fi

  elapsed=$((now - prev_now))
  down=$(( (rx - prev_rx) / elapsed ))
  up=$(( (tx - prev_tx) / elapsed ))
  if [ "$down" -lt 0 ]; then down=0; fi
  if [ "$up" -lt 0 ]; then up=0; fi

  total=$((down + up))
  percent=$(awk -v total="$total" -v scale="$NET_SCALE_BPS" \
    'BEGIN { if (scale > 0) { pct = total / scale * 100; if (pct > 100) pct = 100; printf "%.1f", pct } else printf "0.0" }')

  printf '%s|%s|%s|%s|%s|%s|%s' "$iface" "$down" "$up" "$total" "$(format_rate "$down")" "$(format_rate "$up")" "$percent"
}

vpn_status() {
  if command -v nmcli >/dev/null 2>&1; then
    if nmcli -t -f TYPE,STATE connection show --active 2>/dev/null | grep -Eq '^vpn:activated$'; then
      printf "VPN ON"
      return
    fi
  fi

  if ip -o link show up 2>/dev/null | awk -F': ' '$2 ~ /^(tun|tap|wg|tailscale|ppp|proton|nord|mullvad)/ { found=1 } END { exit found ? 0 : 1 }'; then
    printf "VPN ON"
  else
    printf "VPN OFF"
  fi
}

battery_dir() {
  for dir in /sys/class/power_supply/*; do
    if [ -r "$dir/type" ] && [ "$(cat "$dir/type" 2>/dev/null)" = "Battery" ]; then
      printf "%s" "$dir"
      return
    fi
  done
}

battery_percent() {
  local dir

  dir=$(battery_dir)
  if [ -n "$dir" ] && [ -r "$dir/capacity" ]; then
    cat "$dir/capacity"
  else
    printf "0"
  fi
}

battery_status() {
  local dir

  dir=$(battery_dir)
  if [ -n "$dir" ] && [ -r "$dir/status" ]; then
    cat "$dir/status"
  else
    printf "n/a"
  fi
}

battery_watts() {
  local dir power current voltage

  dir=$(battery_dir)
  if [ -z "$dir" ]; then
    printf "0.0"
    return
  fi

  if [ -r "$dir/power_now" ]; then
    power=$(cat "$dir/power_now" 2>/dev/null || true)
    awk -v power="$power" 'BEGIN { printf "%.1f", power / 1000000 }'
    return
  fi

  if [ -r "$dir/current_now" ] && [ -r "$dir/voltage_now" ]; then
    current=$(cat "$dir/current_now" 2>/dev/null || true)
    voltage=$(cat "$dir/voltage_now" 2>/dev/null || true)
    awk -v current="$current" -v voltage="$voltage" 'BEGIN { printf "%.1f", current * voltage / 1000000000000 }'
  else
    printf "0.0"
  fi
}

power_profile() {
  if command -v powerprofilesctl >/dev/null 2>&1; then
    powerprofilesctl get 2>/dev/null || printf "unknown"
  else
    printf "unknown"
  fi
}

power_profile_label() {
  case "$1" in
    performance) printf "Performance" ;;
    balanced) printf "Balanced" ;;
    power-saver) printf "Power Saver" ;;
    *) printf "Unknown" ;;
  esac
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip())[1:-1])'
}

while true; do
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  profile=$(power_profile)
  profile_label=$(power_profile_label "$profile" | json_escape)
  profile=$(printf "%s" "$profile" | json_escape)
  cpu_usage=$(percent_from_proc_stat)
  cpu_temperature=$(cpu_temp)
  cpu_speed=$(cpu_frequency | json_escape)
  ram_usage=$(ram_percent)
  ram_info=$(ram_display)
  active_gpu=$(gpu_name | json_escape)
  gpu_memory=$(gpu_vram | json_escape)
  gpu_usage=$(gpu_percent)
  gpu_temperature=$(gpu_temp)
  disk_name=$(storage_name | json_escape)
  disk_usage=$(storage_percent)
  disk_info=$(storage_display)
  disk_rates=$(storage_rates)
  disk_read=$(printf "%s" "$disk_rates" | awk -F'|' '{print $1}' | json_escape)
  disk_write=$(printf "%s" "$disk_rates" | awk -F'|' '{print $2}' | json_escape)
  fan_speed=$(fan_rpm)
  fan_usage=$(fan_percent "$fan_speed")
  network_data=$(network_rates)
  network_iface=$(printf "%s" "$network_data" | awk -F'|' '{print $1}' | json_escape)
  network_down=$(printf "%s" "$network_data" | awk -F'|' '{print $5}' | json_escape)
  network_up=$(printf "%s" "$network_data" | awk -F'|' '{print $6}' | json_escape)
  network_usage=$(printf "%s" "$network_data" | awk -F'|' '{print $7}')
  vpn_state=$(vpn_status | json_escape)
  battery_usage=$(battery_percent)
  battery_state=$(battery_status | json_escape)
  battery_power=$(battery_watts)

  printf '{"timestamp":"%s","power_profile":"%s","power_profile_label":"%s","cpu_usage":"%s","cpu_temp":"%s","cpu_frequency":"%s","ram_usage":"%s","ram_info":"%s","gpu_name":"%s","gpu_vram":"%s","gpu_usage":"%s","gpu_temp":"%s","storage_name":"%s","storage_percent":"%s","storage_usage":"%s","storage_read":"%s","storage_write":"%s","fan_percent":"%s","fan_rpm":"%s","network_iface":"%s","network_down":"%s","network_up":"%s","network_percent":"%s","vpn_status":"%s","battery_percent":"%s","battery_status":"%s","battery_watts":"%s"}\n' \
    "$timestamp" "$profile" "$profile_label" "$cpu_usage" "$cpu_temperature" "$cpu_speed" "$ram_usage" "$ram_info" "$active_gpu" "$gpu_memory" "$gpu_usage" "$gpu_temperature" "$disk_name" "$disk_usage" "$disk_info" "$disk_read" "$disk_write" "$fan_usage" "$fan_speed" "$network_iface" "$network_down" "$network_up" "$network_usage" "$vpn_state" "$battery_usage" "$battery_state" "$battery_power" > "$STATE_FILE"

  sleep 5
done
