#!/bin/sh
set -eu

ROOT_DIR="${HOMENET_ROOT:-/home/pi/network}"
OUT_DIR="${HOMENET_INCIDENT_DIR:-$ROOT_DIR/runtime/incidents}"
ROUTER="${OPENWRT_HOST:-192.168.10.1}"
PI_IP="${HOMENET_SERVER_IP:-192.168.10.5}"
ROOM_AP="${ROOM_AP_IP:-192.168.10.2}"
UPSTREAM_IP="${HOMENET_UPSTREAM_IP:-223.5.5.5}"
DNS_TEST_NAME="${HOMENET_DNS_TEST_NAME:-www.baidu.com}"
MIHOMO_URL="${MIHOMO_URL:-http://127.0.0.1:9090/version}"
WAN_RECOVERY="${HOMENET_WAN_RECOVERY:-1}"
WAN_RECOVERY_THRESHOLD="${HOMENET_WAN_RECOVERY_THRESHOLD:-5}"
WAN_RECOVERY_COOLDOWN="${HOMENET_WAN_RECOVERY_COOLDOWN:-1800}"
WAN_INTERFACE="${OPENWRT_WAN_INTERFACE:-wan}"

mkdir -p "$OUT_DIR"

ts="$(date -Is)"
log="$OUT_DIR/network-samples.log"
latest="$OUT_DIR/latest-network-sample.env"
state_file="$OUT_DIR/wan-recovery.state"
recovery_log="$OUT_DIR/wan-recovery.log"
lock_dir="$OUT_DIR/network-incident-recorder.lock"

mkdir "$lock_dir" 2>/dev/null || exit 0
trap 'rmdir "$lock_dir" 2>/dev/null' EXIT

probe_ping() {
  host="$1"
  if timeout 3 ping -c 1 -W 1 "$host" >/tmp/homenet-ping.$$ 2>&1; then
    rtt="$(sed -n 's/.*time=\([0-9.]*\).*/\1/p' /tmp/homenet-ping.$$ | tail -n 1)"
    rm -f /tmp/homenet-ping.$$
    printf 'ok:%sms' "${rtt:-unknown}"
  else
    rm -f /tmp/homenet-ping.$$
    printf 'fail'
  fi
}

probe_dns() {
  server="$1"
  if timeout 4 nslookup "$DNS_TEST_NAME" "$server" >/tmp/homenet-dns.$$ 2>&1; then
    rm -f /tmp/homenet-dns.$$
    printf 'ok'
  else
    detail="$(tail -n 1 /tmp/homenet-dns.$$ | tr ' ' '_' | tr -cd 'A-Za-z0-9._:-')"
    rm -f /tmp/homenet-dns.$$
    printf 'fail:%s' "${detail:-unknown}"
  fi
}

probe_http() {
  url="$1"
  code="$(timeout 4 curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
  case "$code" in
    2*|3*|401|403)
      printf 'ok:http_%s' "$code"
      ;;
    000|"")
      printf 'fail'
      ;;
    *)
      printf 'warn:http_%s' "$code"
      ;;
  esac
}

router_read() {
  command="$1"
  timeout 7 ssh -F none \
    -o BatchMode=yes \
    -o ConnectTimeout=4 \
    -o StrictHostKeyChecking=accept-new \
    "root@$ROUTER" "$command" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//'
}

router_exec() {
  command="$1"
  timeout 20 ssh -F none \
    -o BatchMode=yes \
    -o ConnectTimeout=4 \
    -o StrictHostKeyChecking=accept-new \
    "root@$ROUTER" "$command" >/dev/null 2>&1
}

wan_is_up_with_addr() {
  set -- $router_wan
  [ "${1:-}" = "true" ] && [ -n "${3:-}" ]
}

should_recover_wan() {
  [ "$WAN_RECOVERY" = "1" ] || return 1
  [ "$gateway_ping" != "fail" ] || return 1
  wan_is_up_with_addr || return 1
  [ "$internet_ping" = "fail" ] || return 1
  case "$public_dns" in
    fail*) ;;
    *) return 1 ;;
  esac
  return 0
}

recover_wan_if_needed() {
  now="$(date +%s)"
  fail_count=0
  last_action=0
  if [ -f "$state_file" ]; then
    # shellcheck disable=SC1090
    . "$state_file" 2>/dev/null || true
  fi

  if should_recover_wan; then
    fail_count=$((fail_count + 1))
  else
    fail_count=0
  fi

  action="none"
  cooldown_left=0
  if [ "$fail_count" -ge "$WAN_RECOVERY_THRESHOLD" ]; then
    cooldown_left=$((last_action + WAN_RECOVERY_COOLDOWN - now))
    if [ "$cooldown_left" -le 0 ]; then
      if router_exec "logger -t homenet-wan-recovery 'wan blackhole detected; redial $WAN_INTERFACE'; ifdown $WAN_INTERFACE; sleep 3; ifup $WAN_INTERFACE"; then
        action="redial:$WAN_INTERFACE"
        last_action="$now"
        fail_count=0
      else
        action="redial-failed:$WAN_INTERFACE"
      fi
      printf 'ts=%s action=%s gateway=%s internet=%s public_dns=%s router_wan="%s"\n' \
        "$ts" "$action" "$gateway_ping" "$internet_ping" "$public_dns" "$router_wan" >> "$recovery_log"
    fi
  fi

  {
    printf 'fail_count=%s\n' "$fail_count"
    printf 'threshold=%s\n' "$WAN_RECOVERY_THRESHOLD"
    printf 'cooldown=%s\n' "$WAN_RECOVERY_COOLDOWN"
    printf 'last_action=%s\n' "$last_action"
    printf 'last_status=%s\n' "$action"
    printf 'last_seen=%s\n' "$now"
  } > "$state_file"
  printf '%s' "$action"
}

gateway_ping="$(probe_ping "$ROUTER")"
pi_ping="$(probe_ping "$PI_IP")"
room_ping="$(probe_ping "$ROOM_AP")"
internet_ping="$(probe_ping "$UPSTREAM_IP")"
adguard_dns="$(probe_dns "$PI_IP")"
public_dns="$(probe_dns "$UPSTREAM_IP")"
mihomo_api="$(probe_http "$MIHOMO_URL")"

router_wan="$(router_read "ifstatus wan 2>/dev/null | jsonfilter -e '@.up' -e '@.uptime' -e '@[\"ipv4-address\"][0].address' 2>/dev/null || true")"
router_mem="$(router_read "grep -E 'MemAvailable|Slab|SUnreclaim' /proc/meminfo || true")"
router_recent="$(router_read "logread | tail -n 80 | grep -Ei 'oom|out of memory|pppoe|wan|dnsmasq|radio|wlan|nlbwmon' | tail -n 5 || true")"
wan_recovery="$(recover_wan_if_needed)"

line="ts=$ts gateway=$gateway_ping pi=$pi_ping room_ap=$room_ping internet=$internet_ping adguard_dns=$adguard_dns public_dns=$public_dns mihomo=$mihomo_api wan_recovery=$wan_recovery router_wan=\"$(printf '%s' "$router_wan")\" router_mem=\"$(printf '%s' "$router_mem")\" router_recent=\"$(printf '%s' "$router_recent")\""
printf '%s\n' "$line" >> "$log"
printf '%s\n' "$line" > "$latest"

tail -n 2880 "$log" > "$log.tmp"
mv "$log.tmp" "$log"
