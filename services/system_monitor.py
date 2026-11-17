"""
services/system_monitor.py
--------------------------
Real-time system resource monitoring using psutil.
Provides CPU, RAM, disk, battery, network, and process information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class SystemStats:
    """Snapshot of system resource usage."""
    cpu_percent: float = 0.0
    cpu_count: int = 0
    cpu_freq_mhz: float = 0.0
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_percent: float = 0.0
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0
    disk_partitions: list[dict[str, Any]] = field(default_factory=list)
    battery_percent: float | None = None
    battery_charging: bool | None = None
    battery_time_left_min: float | None = None
    network_bytes_sent_mb: float = 0.0
    network_bytes_recv_mb: float = 0.0


class SystemMonitor:
    """
    Wrapper around psutil for clean, typed system metrics.

    All get_* methods return plain dicts or dataclasses.
    ``get_full_report()`` aggregates everything into a SystemStats.
    ``format_report()`` turns that into a human-readable string.
    """

    def __init__(self, update_interval: float = 2.0) -> None:
        self.update_interval = update_interval
        logger.info("SystemMonitor initialised.")

    def start(self) -> None:
        """Start monitor (no-op for on-demand query mode)."""
        pass

    def stop(self) -> None:
        """Stop monitor."""
        pass

    def get_stats(self) -> SystemStats:
        """Alias for get_full_report with mapped property names."""
        report = self.get_full_report()
        # Add ram_percent alias if needed
        setattr(report, "ram_percent", report.memory_percent)
        return report

    def get_summary_text(self) -> str:
        """Return formatted summary string."""
        return self.format_report(self.get_full_report())


    # ── CPU ───────────────────────────────────────────────────────────────────

    def get_cpu(self) -> dict[str, Any]:
        """Return current CPU stats."""
        freq = psutil.cpu_freq()
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
            "freq_mhz": round(freq.current, 1) if freq else 0.0,
            "freq_max_mhz": round(freq.max, 1) if freq else 0.0,
        }

    # ── Memory ────────────────────────────────────────────────────────────────

    def get_memory(self) -> dict[str, Any]:
        """Return virtual and swap memory stats."""
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {
            "total_gb": round(vm.total / 1e9, 2),
            "used_gb": round(vm.used / 1e9, 2),
            "available_gb": round(vm.available / 1e9, 2),
            "percent": vm.percent,
            "swap_total_gb": round(sw.total / 1e9, 2),
            "swap_used_gb": round(sw.used / 1e9, 2),
            "swap_percent": sw.percent,
        }

    # ── Disk ──────────────────────────────────────────────────────────────────

    def get_disk_usage(self) -> list[dict[str, Any]]:
        """Return usage for all mounted, real (non-loop) partitions."""
        results: list[dict[str, Any]] = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                results.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / 1e9, 2),
                    "used_gb": round(usage.used / 1e9, 2),
                    "free_gb": round(usage.free / 1e9, 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue
        return results

    # ── Battery ───────────────────────────────────────────────────────────────

    def get_battery(self) -> dict[str, Any] | None:
        """Return battery stats, or None if no battery is detected."""
        bat = psutil.sensors_battery()
        if bat is None:
            return None
        time_left = bat.secsleft
        return {
            "percent": round(bat.percent, 1),
            "charging": bat.power_plugged,
            "time_left_min": round(time_left / 60, 1) if time_left > 0 else None,
        }

    # ── Network ───────────────────────────────────────────────────────────────

    def get_network(self) -> dict[str, Any]:
        """Return cumulative network I/O counters."""
        counters = psutil.net_io_counters()
        return {
            "bytes_sent_mb": round(counters.bytes_sent / 1e6, 2),
            "bytes_recv_mb": round(counters.bytes_recv / 1e6, 2),
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
        }

    # ── Processes ─────────────────────────────────────────────────────────────

    def get_top_processes(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the top *n* processes by CPU usage."""
        procs: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda p: p.get("cpu_percent") or 0, reverse=True)
        return procs[:n]

    # ── Full Report ───────────────────────────────────────────────────────────

    def get_full_report(self) -> SystemStats:
        """Aggregate all metrics into a SystemStats dataclass."""
        cpu = self.get_cpu()
        mem = self.get_memory()
        disks = self.get_disk_usage()
        bat = self.get_battery()
        net = self.get_network()

        return SystemStats(
            cpu_percent=cpu["percent"],
            cpu_count=cpu["count_logical"],
            cpu_freq_mhz=cpu["freq_mhz"],
            memory_total_gb=mem["total_gb"],
            memory_used_gb=mem["used_gb"],
            memory_percent=mem["percent"],
            swap_total_gb=mem["swap_total_gb"],
            swap_used_gb=mem["swap_used_gb"],
            disk_partitions=disks,
            battery_percent=bat["percent"] if bat else None,
            battery_charging=bat["charging"] if bat else None,
            battery_time_left_min=bat.get("time_left_min") if bat else None,
            network_bytes_sent_mb=net["bytes_sent_mb"],
            network_bytes_recv_mb=net["bytes_recv_mb"],
        )

    @staticmethod
    def format_report(stats: SystemStats) -> str:
        """Convert a SystemStats snapshot into a readable string."""
        lines = [
            "🖥️  **System Status**",
            f"  CPU: {stats.cpu_percent}% — {stats.cpu_count} cores @ {stats.cpu_freq_mhz} MHz",
            f"  RAM: {stats.memory_used_gb:.1f} / {stats.memory_total_gb:.1f} GB ({stats.memory_percent}%)",
        ]

        if stats.swap_total_gb > 0:
            lines.append(
                f"  Swap: {stats.swap_used_gb:.1f} / {stats.swap_total_gb:.1f} GB"
            )

        for disk in stats.disk_partitions:
            lines.append(
                f"  💾 {disk['device']}: {disk['used_gb']:.1f}/{disk['total_gb']:.1f} GB "
                f"({disk['percent']}% used)"
            )

        if stats.battery_percent is not None:
            status = "🔌 Charging" if stats.battery_charging else "🔋 On battery"
            time_str = ""
            if stats.battery_time_left_min:
                h, m = divmod(int(stats.battery_time_left_min), 60)
                time_str = f" — {h}h {m}m remaining"
            lines.append(f"  Battery: {stats.battery_percent:.0f}% {status}{time_str}")

        lines.append(
            f"  🌐 Network: ↑{stats.network_bytes_sent_mb} MB  ↓{stats.network_bytes_recv_mb} MB"
        )

        return "\n".join(lines)
