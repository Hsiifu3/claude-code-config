#!/usr/bin/env python3
"""Clash Verge CLI - Control Clash Verge Rev via mihomo external controller API."""

import argparse
import json
import socket
import sys
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_SOCK = "/tmp/verge/verge-mihomo.sock"
DEFAULT_HTTP = "http://127.0.0.1:9090"


def _get_args():
    """Get connection args from environment or defaults."""
    import os
    sock = os.environ.get("CLASH_SOCK", DEFAULT_SOCK)
    http = os.environ.get("CLASH_API", DEFAULT_HTTP)
    secret = os.environ.get("CLASH_SECRET", "")
    return sock, http, secret


class UnixHTTPHandler(urllib.request.AbstractHTTPHandler):
    """HTTP handler for Unix domain sockets."""

    def __init__(self, sock_path):
        super().__init__()
        self.sock_path = sock_path

    def http_open(self, req):
        return self.do_open(self._make_connection, req)

    def _make_connection(self, host, **kwargs):
        conn = UnixHTTPConnection(self.sock_path)
        return conn


class UnixHTTPConnection:
    """Minimal HTTP/1.1 over Unix socket."""

    def __init__(self, sock_path):
        self.sock_path = sock_path
        self._sock = None
        self._response = None
        self.timeout = 10

    def request(self, method, url, body=None, headers=None):
        headers = headers or {}
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect(self.sock_path)
        path = url
        lines = [f"{method} {path} HTTP/1.1", "Host: localhost", "Connection: close"]
        if body:
            lines.append(f"Content-Length: {len(body)}")
        for k, v in headers.items():
            lines.append(f"{k}: {v}")
        lines.append("")
        lines.append("")
        raw = "\r\n".join(lines).encode()
        if body:
            raw = raw + (body.encode() if isinstance(body, str) else body)
        self._sock.sendall(raw)

    def getresponse(self):
        data = b""
        while True:
            chunk = self._sock.recv(65536)
            if not chunk:
                break
            data += chunk
        self._sock.close()
        return _RawResponse(data)


class _RawResponse:
    """Parse raw HTTP response."""

    def __init__(self, data):
        parts = data.split(b"\r\n\r\n", 1)
        header_block = parts[0].decode(errors="replace")
        self.body = parts[1] if len(parts) > 1 else b""
        first_line = header_block.split("\r\n")[0]
        self.status = int(first_line.split(" ", 2)[1])
        self.reason = first_line.split(" ", 2)[2] if len(first_line.split(" ", 2)) > 2 else ""
        self._headers = {}
        for line in header_block.split("\r\n")[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                self._headers[k.lower()] = v
        # Handle chunked transfer encoding
        if self._headers.get("transfer-encoding", "").lower() == "chunked":
            self.body = self._decode_chunked(self.body)

    def _decode_chunked(self, data):
        result = b""
        while data:
            line_end = data.find(b"\r\n")
            if line_end == -1:
                break
            size_str = data[:line_end].decode().strip()
            if not size_str:
                data = data[line_end + 2:]
                continue
            chunk_size = int(size_str, 16)
            if chunk_size == 0:
                break
            result += data[line_end + 2:line_end + 2 + chunk_size]
            data = data[line_end + 2 + chunk_size + 2:]
        return result

    def read(self):
        return self.body

    def getheader(self, name, default=None):
        return self._headers.get(name.lower(), default)


# ── API Client ───────────────────────────────────────────────────────


def api(method, path, body=None):
    """Call mihomo API. Prefers Unix socket, falls back to HTTP."""
    sock, http_url, secret = _get_args()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    if Path(sock).exists():
        conn = UnixHTTPConnection(sock)
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status >= 400:
            print(f"API error {resp.status}: {raw.decode(errors='replace')}", file=sys.stderr)
            sys.exit(1)
        return json.loads(raw) if raw.strip() else {}
    else:
        url = http_url.rstrip("/") + path
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            print(f"API error {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
            sys.exit(1)


# ── Commands ─────────────────────────────────────────────────────────


def cmd_status(args):
    """Show overall status."""
    ver = api("GET", "/version")
    cfg = api("GET", "/configs")
    conns = api("GET", "/connections")
    proxies_data = api("GET", "/proxies")

    nc = len(conns.get("connections", []))
    up = conns.get("uploadTotal", 0)
    down = conns.get("downloadTotal", 0)

    print(f"Mihomo {ver.get('version', '?')}")
    print(f"Mode: {cfg.get('mode', '?')}")
    print(f"Mixed port: {cfg.get('mixed-port', '?')}")
    tun = cfg.get("tun", {})
    print(f"TUN: {'enabled' if tun.get('enable') else 'disabled'} ({tun.get('stack', '?')})")
    print(f"Log level: {cfg.get('log-level', '?')}")
    print(f"Connections: {nc} active")
    print(f"Traffic: ↑ {_fmt_bytes(up)}  ↓ {_fmt_bytes(down)}")

    # Show current proxy selections
    proxies = proxies_data.get("proxies", {})
    group_types = ("Selector", "URLTest", "Fallback", "LoadBalance")
    groups = {k: v for k, v in proxies.items() if v.get("type") in group_types}
    if groups:
        print(f"\nProxy groups:")
        for name, g in sorted(groups.items()):
            now = g.get("now", "-")
            # Resolve chain: if 'now' is also a group, follow it
            chain = [now]
            seen = {name}
            cur = now
            while cur in proxies and proxies[cur].get("type") in group_types and cur not in seen:
                seen.add(cur)
                cur = proxies[cur].get("now", "")
                if cur:
                    chain.append(cur)
            chain_str = " → ".join(chain)
            print(f"  {name}: {chain_str}")


def cmd_mode(args):
    """Get or set proxy mode."""
    if args.value:
        api("PATCH", "/configs", {"mode": args.value})
        print(f"Mode set to: {args.value}")
    else:
        cfg = api("GET", "/configs")
        print(f"Mode: {cfg.get('mode', '?')}")


def cmd_groups(args):
    """List proxy groups."""
    data = api("GET", "/proxies")
    proxies = data.get("proxies", {})
    group_types = ("Selector", "URLTest", "Fallback", "LoadBalance")
    groups = {k: v for k, v in proxies.items() if v.get("type") in group_types}
    for name, g in sorted(groups.items()):
        now = g.get("now", "-")
        n = len(g.get("all", []))
        t = g.get("type", "?")
        print(f"  {name} ({t}): {now}  [{n} nodes]")


def cmd_nodes(args):
    """List nodes in a proxy group."""
    data = api("GET", f"/proxies/{_urlencode(args.group)}")
    if "all" not in data:
        print(f"'{args.group}' is not a group or not found.", file=sys.stderr)
        sys.exit(1)
    now = data.get("now", "")
    print(f"Group: {args.group} ({data.get('type', '?')})")
    print(f"Current: {now}\n")
    for node_name in data.get("all", []):
        marker = " ★" if node_name == now else ""
        # Get delay info from history
        node_data = api("GET", f"/proxies/{_urlencode(node_name)}")
        history = node_data.get("history", [])
        delay = history[-1].get("delay", 0) if history else 0
        delay_str = f"{delay}ms" if delay > 0 else "N/A"
        print(f"  {node_name}{marker}  ({delay_str})")


def cmd_select(args):
    """Select a node in a proxy group."""
    api("PUT", f"/proxies/{_urlencode(args.group)}", {"name": args.node})
    print(f"Switched '{args.group}' → {args.node}")


def cmd_delay(args):
    """Test delay for a node or group."""
    url = args.url or "http://www.gstatic.com/generate_204"
    timeout = args.timeout or 5000
    target = args.target
    result = api("GET", f"/proxies/{_urlencode(target)}/delay?timeout={timeout}&url={_urlencode(url)}")
    d = result.get("delay", 0)
    if d > 0:
        print(f"{target}: {d}ms")
    else:
        print(f"{target}: timeout / unreachable")


def cmd_delay_group(args):
    """Test delay for all nodes in a group."""
    url = args.url or "http://www.gstatic.com/generate_204"
    timeout = args.timeout or 5000
    data = api("GET", f"/proxies/{_urlencode(args.group)}")
    if "all" not in data:
        print(f"'{args.group}' is not a group.", file=sys.stderr)
        sys.exit(1)
    print(f"Testing {len(data['all'])} nodes in '{args.group}'...\n")
    results = []
    for node_name in data.get("all", []):
        try:
            r = api("GET", f"/proxies/{_urlencode(node_name)}/delay?timeout={timeout}&url={_urlencode(url)}")
            d = r.get("delay", 0)
        except SystemExit:
            d = 0
        results.append((node_name, d))
    # Sort by delay (0 = timeout, put at end)
    results.sort(key=lambda x: (x[1] == 0, x[1]))
    for name, d in results:
        marker = " ★" if name == data.get("now", "") else ""
        ds = f"{d}ms" if d > 0 else "timeout"
        print(f"  {name}{marker}: {ds}")


def cmd_conns(args):
    """List active connections."""
    data = api("GET", "/connections")
    conns = data.get("connections", [])
    if not conns:
        print("No active connections.")
        return
    up = data.get("uploadTotal", 0)
    down = data.get("downloadTotal", 0)
    print(f"Total: {len(conns)} connections  ↑ {_fmt_bytes(up)}  ↓ {_fmt_bytes(down)}\n")
    # Sort by download speed desc
    conns.sort(key=lambda c: c.get("download", 0), reverse=True)
    limit = args.limit or 20
    for c in conns[:limit]:
        meta = c.get("metadata", {})
        host = meta.get("host") or meta.get("destinationIP", "?")
        port = meta.get("destinationPort", "")
        chain = " → ".join(c.get("chains", []))
        rule = c.get("rule", "")
        dl = _fmt_bytes(c.get("download", 0))
        ul = _fmt_bytes(c.get("upload", 0))
        print(f"  {host}:{port}  ↑{ul} ↓{dl}  [{chain}]  ({rule})")


def cmd_conns_close(args):
    """Close connections."""
    if args.id:
        api("DELETE", f"/connections/{args.id}")
        print(f"Closed connection {args.id}")
    else:
        api("DELETE", "/connections")
        print("Closed all connections.")


def cmd_rules(args):
    """List rules."""
    data = api("GET", "/rules")
    rules = data.get("rules", [])
    limit = args.limit or 30
    print(f"Total: {len(rules)} rules (showing first {limit})\n")
    for r in rules[:limit]:
        print(f"  {r.get('type','?')}: {r.get('payload','')} → {r.get('proxy','')}")


def cmd_dns(args):
    """Query DNS resolution."""
    result = api("GET", f"/dns/query?name={_urlencode(args.domain)}&type={args.type}")
    answers = result.get("Answer", [])
    if not answers:
        print(f"No DNS records for {args.domain}")
        return
    for a in answers:
        print(f"  {a.get('Name','')}  {a.get('Type','')}  {a.get('data','')}")


def cmd_flush_dns(args):
    """Flush DNS cache."""
    api("POST", "/cache/flushdns")
    print("DNS cache flushed.")


def cmd_health_check(args):
    """Health check current node and report."""
    import subprocess
    PROXY_GROUP = args.group or "♻️自动选择"
    DELAY_THRESHOLD = args.threshold or 1000
    PREFERRED = (args.prefer or "🇺🇸").split(",")

    # Get current node from status
    cfg = api("GET", "/configs")
    proxies = api("GET", "/proxies")
    all_proxies = proxies.get("proxies", {})
    group_data = all_proxies.get(PROXY_GROUP, {})
    current_node = group_data.get("now", "")
    node_list = group_data.get("all", [])

    if not current_node:
        print("❌ 无法获取当前节点", file=sys.stderr)
        _notify("⚠️ Clash 代理健康检查失败\n无法获取当前节点")
        sys.exit(1)

    print(f"📍 当前节点: {current_node}")

    # Collect delays from group view (history)
    nodes = []
    for name in node_list:
        nd = all_proxies.get(name, {})
        hist = nd.get("history", [])
        delay = hist[-1].get("delay", 0) if hist else 0
        nodes.append({"name": name, "delay": delay if delay > 0 else None, "is_current": name == current_node})

    current_info = next((n for n in nodes if n["is_current"]), None)
    current_delay = current_info["delay"] if current_info else None

    if current_delay is None:
        print(f"⚠️ 当前节点在组视图中无可用延迟")
        need_switch = True
    elif current_delay > DELAY_THRESHOLD:
        print(f"⚠️ 当前节点延迟过高: {current_delay}ms (阈值: {DELAY_THRESHOLD}ms)")
        need_switch = True
    else:
        print(f"✅ 当前节点健康: {current_delay}ms")
        need_switch = False

    if not need_switch:
        print("✅ 无需切换节点")
        return

    # Find best node
    healthy = [n for n in nodes if n["delay"] is not None and n["delay"] < DELAY_THRESHOLD]
    if not healthy:
        msg = f"⚠️ Clash 代理健康检查失败\n当前节点: {current_node}\n状态: 无可用健康节点"
        _notify(msg)
        print("❌ 没有找到健康的节点", file=sys.stderr)
        sys.exit(1)

    def sort_key(n):
        for i, country in enumerate(PREFERRED):
            if n["name"].startswith(country):
                return (i, n["delay"])
        return (len(PREFERRED), n["delay"])

    healthy.sort(key=sort_key)
    best = healthy[0]

    if best["name"] == current_node:
        print("✅ 当前节点已是最优节点")
        return

    print(f"\n📊 [仅监控模式] 建议切换节点: {current_node} → {best['name']} ({best['delay']}ms)")
    msg = (f"⚠️ Clash 代理健康告警（未自动切换）\n"
           f"当前节点: {current_node} (延迟: {current_delay or 'N/A'}ms)\n"
           f"建议节点: {best['name']} (延迟: {best['delay']}ms)\n\n"
           f"💡 提示：当前为仅监控模式，不会自动切换")
    _notify(msg)


def _notify(message):
    """Send notification via openclaw message."""
    import subprocess
    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "feishu",
             "--target", os.environ.get("FEISHU_TARGET", ""),
             "--message", message],
            capture_output=True,
            timeout=10,
        )
    except Exception as e:
        print(f"⚠️ 发送通知失败: {e}", file=sys.stderr)


    """Restart mihomo core."""
    api("PUT", "/restart")
    print("Core restarting...")


def cmd_restart(args):
    """Restart mihomo core."""
    api("PUT", "/restart")
    print("Core restarting...")


def cmd_upgrade_geo(args):

    """Update GeoIP/GeoSite databases."""
    api("POST", "/configs/geo")
    print("GeoIP/GeoSite update triggered.")


# ── Helpers ──────────────────────────────────────────────────────────


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _urlencode(s):
    import urllib.parse
    return urllib.parse.quote(s, safe="")


# ── Main ─────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Clash Verge CLI - control mihomo via API")
    p.add_argument("--sock", help=f"Unix socket path (default: {DEFAULT_SOCK})")
    p.add_argument("--api", help=f"HTTP API URL (default: {DEFAULT_HTTP})")
    p.add_argument("--secret", help="API secret")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Show overall status")

    s = sub.add_parser("mode", help="Get/set proxy mode")
    s.add_argument("value", nargs="?", choices=["rule", "global", "direct"])

    sub.add_parser("groups", help="List proxy groups")

    s = sub.add_parser("nodes", help="List nodes in a group")
    s.add_argument("group", help="Group name")

    s = sub.add_parser("select", help="Select node in a group")
    s.add_argument("group", help="Group name")
    s.add_argument("node", help="Node name")

    s = sub.add_parser("delay", help="Test node delay")
    s.add_argument("target", help="Node or group name")
    s.add_argument("--url", help="Test URL")
    s.add_argument("--timeout", type=int, help="Timeout in ms (default: 5000)")

    s = sub.add_parser("health-check", help="Check proxy health and notify if needed")
    s.add_argument("--group", default="♻️自动选择", help="Proxy group to monitor")
    s.add_argument("--threshold", type=int, default=1000, help="Delay threshold in ms")
    s.add_argument("--prefer", default="🇺🇸", help="Preferred country prefixes (comma-separated)")

    s = sub.add_parser("delay-group", help="Test all nodes in a group")
    s.add_argument("group", help="Group name")
    s.add_argument("--url", help="Test URL")
    s.add_argument("--timeout", type=int, help="Timeout in ms (default: 5000)")

    s = sub.add_parser("conns", help="List active connections")
    s.add_argument("--limit", type=int, help="Max connections to show (default: 20)")

    s = sub.add_parser("conns-close", help="Close connections")
    s.add_argument("--id", help="Connection ID (omit to close all)")

    s = sub.add_parser("rules", help="List rules")
    s.add_argument("--limit", type=int, help="Max rules to show (default: 30)")

    s = sub.add_parser("dns", help="Query DNS")
    s.add_argument("domain", help="Domain to query")
    s.add_argument("--type", default="A", help="Record type (default: A)")

    sub.add_parser("flush-dns", help="Flush DNS cache")
    sub.add_parser("restart", help="Restart mihomo core")
    sub.add_parser("upgrade-geo", help="Update GeoIP/GeoSite databases")

    args = p.parse_args()

    # Override env from CLI args
    import os
    if args.sock:
        os.environ["CLASH_SOCK"] = args.sock
    if args.api:
        os.environ["CLASH_API"] = args.api
    if args.secret:
        os.environ["CLASH_SECRET"] = args.secret

    dispatch = {
        "status": cmd_status, "mode": cmd_mode, "groups": cmd_groups,
        "nodes": cmd_nodes, "select": cmd_select, "delay": cmd_delay,
        "delay-group": cmd_delay_group, "conns": cmd_conns,
        "conns-close": cmd_conns_close, "rules": cmd_rules,
        "dns": cmd_dns, "flush-dns": cmd_flush_dns,
        "restart": cmd_restart, "upgrade-geo": cmd_upgrade_geo,
        "health-check": cmd_health_check,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
