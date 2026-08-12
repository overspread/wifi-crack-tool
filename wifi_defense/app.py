"""Tkinter interface for the offline WiFi security education tool."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .audit import AuditLogger
from .policy import OfflineAuthSimulator, SimulationResult
from .strength import assess_password


class WifiDefenseApp:
    """A local-only interface with no WiFi discovery or connection capabilities."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WiFi 防御与安全教育工具（完全离线）")
        self.root.minsize(860, 620)

        self.audit = AuditLogger(Path.cwd() / "audit_logs")
        self.max_failures = tk.IntVar(value=5)
        self.window_seconds = tk.IntVar(value=300)
        self.lockout_seconds = tk.IntVar(value=900)
        self.simulator = self._build_simulator()

        self.password_var = tk.StringVar()
        self.profile_var = tk.StringVar(value="家庭网络演示")
        self.strength_result = tk.StringVar(value="输入密码后执行本地评估。密码不会写入日志或文件。")
        self.simulation_result = tk.StringVar(value="仅可写入合成事件；本工具不扫描、不连接、不认证任何真实网络。")

        self._build_layout()
        self.refresh_audit()

    def _build_simulator(self) -> OfflineAuthSimulator:
        return OfflineAuthSimulator(
            audit_logger=self.audit,
            max_failures=self.max_failures.get(),
            window_seconds=self.window_seconds.get(),
            lockout_seconds=self.lockout_seconds.get(),
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="WiFi 防御与安全教育工具", font=("TkDefaultFont", 17, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "安全边界：本程序只处理本地输入与合成训练事件；不扫描 WiFi、不读取网卡、"
                "不发送认证请求、不抓包、不尝试密码。"
            ),
            foreground="#8a3b00",
            wraplength=810,
        ).pack(anchor="w", pady=(4, 12))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        strength_tab = ttk.Frame(notebook, padding=16)
        simulator_tab = ttk.Frame(notebook, padding=16)
        audit_tab = ttk.Frame(notebook, padding=16)
        notebook.add(strength_tab, text="密码强度评估")
        notebook.add(simulator_tab, text="认证策略模拟")
        notebook.add(audit_tab, text="本地审计日志")

        self._build_strength_tab(strength_tab)
        self._build_simulator_tab(simulator_tab)
        self._build_audit_tab(audit_tab)

    def _build_strength_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="评估自有 WiFi 密码", font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(parent, text="输入密码（仅在内存中用于本次评估，评估后立即清空）：").grid(row=1, column=0, sticky="w", pady=(18, 4))
        entry = ttk.Entry(parent, textvariable=self.password_var, show="•", width=42)
        entry.grid(row=2, column=0, sticky="we", padx=(0, 8))
        entry.focus_set()
        ttk.Button(parent, text="执行本地评估", command=self.evaluate_password).grid(row=2, column=1, sticky="e")
        ttk.Label(parent, textvariable=self.strength_result, justify="left", wraplength=700).grid(row=3, column=0, columnspan=2, sticky="nw", pady=(18, 0))
        parent.columnconfigure(0, weight=1)

    def _build_simulator_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="离线认证策略演示", font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(parent, text="演示配置名称：").grid(row=1, column=0, sticky="w", pady=(16, 4))
        ttk.Entry(parent, textvariable=self.profile_var, width=30).grid(row=1, column=1, columnspan=2, sticky="w", pady=(16, 4))

        ttk.Label(parent, text="失败阈值：").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Spinbox(parent, from_=1, to=20, textvariable=self.max_failures, width=8).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(parent, text="窗口（秒）：").grid(row=2, column=2, sticky="e", pady=6)
        ttk.Spinbox(parent, from_=30, to=3600, increment=30, textvariable=self.window_seconds, width=8).grid(row=2, column=3, sticky="w", pady=6)
        ttk.Label(parent, text="锁定（秒）：").grid(row=2, column=4, sticky="e", pady=6)
        ttk.Spinbox(parent, from_=30, to=86400, increment=30, textvariable=self.lockout_seconds, width=8).grid(row=2, column=5, sticky="w", pady=6)
        ttk.Button(parent, text="应用策略", command=self.apply_policy).grid(row=3, column=0, sticky="w", pady=(8, 16))

        button_row = ttk.Frame(parent)
        button_row.grid(row=4, column=0, columnspan=6, sticky="w")
        ttk.Button(button_row, text="记录合成失败事件", command=lambda: self.simulate("failure")).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="记录合成成功事件", command=lambda: self.simulate("success")).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="重置该演示配置", command=self.reset_profile).pack(side="left")
        ttk.Label(parent, textvariable=self.simulation_result, justify="left", wraplength=700).grid(row=5, column=0, columnspan=6, sticky="nw", pady=(18, 0))

    def _build_audit_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="本地审计记录", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(parent, text="日志仅保存合成事件元数据，不包含密码、网络标识或认证流量。", wraplength=740).pack(anchor="w", pady=(4, 10))
        self.audit_text = tk.Text(parent, height=20, wrap="word", state="disabled")
        self.audit_text.pack(fill="both", expand=True)
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="刷新日志", command=self.refresh_audit).pack(side="left")
        ttk.Button(controls, text="打开日志目录", command=self.show_log_path).pack(side="left", padx=8)

    def evaluate_password(self) -> None:
        password = self.password_var.get()
        if not password:
            self.strength_result.set("请先输入一个密码进行本地评估。")
            return
        assessment = assess_password(password)
        self.password_var.set("")
        feedback = "\n".join(f"• {item}" for item in assessment.feedback)
        self.strength_result.set(
            f"评级：{assessment.label}（{assessment.score}/4）\n"
            f"长度：{assessment.length}；估算搜索空间：10^{assessment.estimated_guesses_log10} 次猜测（启发式估计）。\n{feedback}"
        )
        self.audit.record("password_strength_assessed", "本地自评", {"score": assessment.score, "length": assessment.length})
        self.refresh_audit()

    def apply_policy(self) -> None:
        try:
            self.simulator = self._build_simulator()
        except ValueError as exc:
            messagebox.showerror("策略无效", str(exc))
            return
        self.audit.record(
            "synthetic_policy_updated",
            self.profile_var.get().strip() or "未命名演示配置",
            {
                "max_failures": self.max_failures.get(),
                "window_seconds": self.window_seconds.get(),
                "lockout_seconds": self.lockout_seconds.get(),
            },
        )
        self.simulation_result.set("策略已应用。此前的内存中合成计数已重置。")
        self.refresh_audit()

    def simulate(self, outcome: str) -> None:
        result = self.simulator.simulate(self.profile_var.get(), outcome)
        self._show_simulation_result(result)
        self.refresh_audit()

    def reset_profile(self) -> None:
        profile = self.profile_var.get()
        self.simulator.reset_profile(profile)
        self.simulation_result.set("已重置该演示配置的内存计数与模拟锁定状态。")
        self.refresh_audit()

    def _show_simulation_result(self, result: SimulationResult) -> None:
        lock_text = f" 锁定截止：{result.locked_until.isoformat()}。" if result.locked_until else ""
        self.simulation_result.set(f"状态：{result.status}。{result.message}{lock_text}")

    def refresh_audit(self) -> None:
        records = self.audit.read_recent()
        text = "\n".join(
            f"{record['timestamp']} | {record['event']} | {record['profile']} | {record['details']}"
            for record in records
        ) or "尚无本地审计记录。"
        self.audit_text.configure(state="normal")
        self.audit_text.delete("1.0", "end")
        self.audit_text.insert("1.0", text)
        self.audit_text.configure(state="disabled")

    def show_log_path(self) -> None:
        messagebox.showinfo("本地日志路径", str(self.audit.path.resolve()))


def run() -> None:
    """Start the local-only desktop application."""
    root = tk.Tk()
    WifiDefenseApp(root)
    root.mainloop()
