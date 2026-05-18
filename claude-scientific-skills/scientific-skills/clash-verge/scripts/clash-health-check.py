#!/usr/bin/env python3
"""
Clash Verge 自动健康检查
定期检查当前代理节点健康状态，如果失效则自动切换到最优节点
"""

import json
import subprocess
import sys
from pathlib import Path

# 配置
CLASH_SCRIPT = Path.home() / ".openclaw/workspace/skills/clash-verge/scripts/clash-verge.py"
PROXY_GROUP = "♻️自动选择"  # 要监控的代理组（注意包含emoji）
DELAY_THRESHOLD = 1000  # 延迟阈值（毫秒），超过此值视为不健康
TIMEOUT = 3000  # 延迟测试超时（毫秒）
PREFERRED_COUNTRIES = ["🇺🇸"]  # 优先选择的国家（按顺序）
NOTIFICATION_TARGET = os.environ.get("FEISHU_TARGET", "")  # 飞书通知目标
MONITOR_ONLY = True  # 仅监控模式：只检查和报告，不自动切换节点


def run_clash_cmd(cmd):
    """运行 clash-verge.py 命令"""
    result = subprocess.run(
        ["python3", str(CLASH_SCRIPT)] + cmd,
        capture_output=True,
        text=True,
        timeout=30
    )
    return result.stdout, result.stderr, result.returncode


def get_current_node():
    """获取当前选中的节点"""
    stdout, stderr, code = run_clash_cmd(["status"])
    if code != 0:
        print(f"❌ 获取状态失败: {stderr}", file=sys.stderr)
        return None

    # 解析输出找到当前节点（跳过 emoji 前缀）
    for line in stdout.split("\n"):
        if "自动选择" in line and ":" in line:
            parts = line.split(":")
            if len(parts) > 1:
                return parts[1].strip()
    return None


def get_all_nodes():
    """获取代理组中的所有节点及其延迟。以 group 视图为准，避免单节点测速误判。"""
    stdout, stderr, code = run_clash_cmd(["nodes", PROXY_GROUP])
    if code != 0:
        print(f"❌ 获取节点列表失败: {stderr}", file=sys.stderr)
        return []

    nodes = []
    current_node = None

    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("Current:"):
            current_node = line.split("Current:")[-1].strip()
        elif line and not line.startswith("Group:") and not line.startswith("Current:"):
            # 解析节点行：  🇺🇸11美国西集群-全网优化(hy2) ★  (199ms)
            is_current = " ★" in line
            line = line.replace(" ★", "")
            parts = line.rsplit("(", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                delay_str = parts[1].replace(")", "").replace("ms", "").strip()
                delay = None if delay_str == "N/A" else int(delay_str) if delay_str.isdigit() else None
                nodes.append({
                    "name": name,
                    "delay": delay,
                    "is_current": is_current
                })

    return nodes


def get_current_node_info(nodes, current_node_name=None):
    """从组视图中找到当前节点信息。"""
    for node in nodes:
        if node.get("is_current"):
            return node
    if current_node_name:
        for node in nodes:
            if node["name"] == current_node_name:
                return node
    return None


def find_best_node(nodes):
    """找到最优节点（优先国家 + 最低延迟）"""
    healthy_nodes = [n for n in nodes if n["delay"] is not None and n["delay"] < DELAY_THRESHOLD]

    if not healthy_nodes:
        return None

    def sort_key(node):
        for i, country in enumerate(PREFERRED_COUNTRIES):
            if node["name"].startswith(country):
                return (i, node["delay"])
        return (len(PREFERRED_COUNTRIES), node["delay"])

    healthy_nodes.sort(key=sort_key)
    return healthy_nodes[0]


def switch_node(node_name):
    """切换到指定节点"""
    stdout, stderr, code = run_clash_cmd(["select", PROXY_GROUP, node_name])
    return code == 0


def send_notification(message):
    """发送飞书通知（可选）"""
    try:
        # 使用 openclaw message 工具发送通知
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "feishu",
             "--target", NOTIFICATION_TARGET,
             "--message", message],
            capture_output=True,
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ 发送通知失败: {e}", file=sys.stderr)


def main():
    print("🔍 开始代理健康检查...")

    current_node = get_current_node()
    if not current_node:
        print("❌ 无法获取当前节点")
        sys.exit(1)

    print(f"📍 当前节点: {current_node}")

    print(f"\n🔎 读取 {PROXY_GROUP} 组节点延迟...")
    nodes = get_all_nodes()
    if not nodes:
        print("❌ 无法获取节点列表")
        sys.exit(1)

    print(f"📊 找到 {len(nodes)} 个节点")

    current_node_info = get_current_node_info(nodes, current_node)
    current_delay = current_node_info["delay"] if current_node_info else None

    if current_delay is None:
        print("⚠️ 当前节点在组视图中无可用延迟")
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

    best_node = find_best_node(nodes)

    if not best_node:
        print("❌ 没有找到健康的节点")
        message = f"⚠️ Clash 代理健康检查失败\n当前节点: {current_node}\n状态: 无可用健康节点"
        send_notification(message)
        sys.exit(1)

    if best_node["name"] == current_node:
        print(f"✅ 当前节点已是最优节点")
        return

    # 切换节点

    # 仅监控模式：只报告不切换
    if MONITOR_ONLY:
        print(f"\n📊 [仅监控模式] 建议切换节点: {current_node} → {best_node['name']} ({best_node['delay']}ms)")
        message = f"⚠️ Clash 代理健康告警（未自动切换）\n当前节点: {current_node} (延迟: {current_delay or 'N/A'}ms)\n建议节点: {best_node['name']} (延迟: {best_node['delay']}ms)\n\n💡 提示：当前为仅监控模式，不会自动切换"
        send_notification(message)
        return
    print(f"\n🔄 切换节点: {current_node} → {best_node['name']} ({best_node['delay']}ms)")

    if switch_node(best_node["name"]):
        print(f"✅ 节点切换成功")
        message = f"🔄 Clash 代理自动切换\n原节点: {current_node} (延迟: {current_delay or 'N/A'}ms)\n新节点: {best_node['name']} (延迟: {best_node['delay']}ms)"
        send_notification(message)
    else:
        print(f"❌ 节点切换失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
