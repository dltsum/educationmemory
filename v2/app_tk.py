# -*- coding: utf-8 -*-
"""
三层记忆辅导台 · 桌面客户端 (tkinter, 不依赖浏览器)
复用 server.call_llm / memory_core / testcases 用例集
运行: python app_tk.py
"""
import os, sys, json, threading, queue
import tkinter as tk
from tkinter import ttk, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_core as mc
import server  # 复用 CFG/call_llm/load_demos (__main__ 保护, 不会起 http 服务)

# ---- 与网页版一致的 26 模型与推理变体 ----
MODELS = [
    ("Grok 4.6", "grok-4.6", "openai"),
    ("GLM-5.3-Flash", "glm-5.3-flash", "g"), ("GLM-5.3", "glm-5.3", "g"), ("GLM-5.2", "glm-5.2", "g"), ("GLM-5.1", "glm-5.1", "g"),
    ("GPT 5.6 Luna", "gpt-5.6-luna", "openai"),
    ("Kimi K3", "kimi-k3", "g"), ("Kimi K2.7 Code", "kimi-k2.7-code", "g"), ("Kimi K2.6", "kimi-k2.6", "g"),
    ("LongCat-2.0", "longcat-2.0", "g"),
    ("MiMo-V2.5", "mimo-v2.5", "g"), ("MiMo-V2.5-Pro", "mimo-v2.5-pro", "g"),
    ("MiniMax M3", "minimax-m3", "g"), ("MiniMax M2.7", "minimax-m2.7", "g"),
    ("Muse Spark 1.3 Contributor", "muse-spark-1.3-contributor", "g"), ("Muse Spark 1.2 Contributor", "muse-spark-1.2-contributor", "g"),
    ("Qwen3.8 Max", "qwen3.8-max", "google"), ("Qwen3.8 Flash", "qwen3.8-flash", "google"),
    ("Qwen3.7 Max", "qwen3.7-max", "google"), ("Qwen3.7 Plus", "qwen3.7-plus", "google"), ("Qwen3.6 Plus", "qwen3.6-plus", "google"),
    ("DeepSeek V4 Pro", "deepseek-v4-pro", "g"), ("DeepSeek V4 Flash", "deepseek-v4-flash", "g"), ("DeepSeek V4 Flash Vision Exp", "deepseek-v4-flash-vision-exp", "g"),
    ("Hy4 preview", "hy4-preview", "anthropic"), ("Hy3", "hy3", "anthropic"),
]
VARIANTS = {"anthropic": ["high", "max"], "openai": ["none", "minimal", "low", "medium", "high", "xhigh"],
            "google": ["low", "high"], "g": ["none", "minimal", "low", "medium", "high", "xhigh", "max"]}
PRESETS = {"默认 (记忆块+最近4轮)": 8, "纯记忆 (只记忆+问题)": 0, "长历史 (记忆块+最近16轮)": 32}
SYSTEM = "你是一位耐心的中小学辅导老师, 讲解适合学生水平, 善用生活化例子。"
BG, CARD, TX, DIM, ACC = "#0b0f1a", "#161d2e", "#e5e9f0", "#8b93a7", "#6ea8fe"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("三层记忆辅导台 (桌面版)  保存 → 整理 → 压缩")
        self.geometry("1280x780"); self.configure(bg=BG)
        self.store = mc.MemoryStore()
        self.history = []
        self.turn_no = 0
        self.q = queue.Queue()
        self.preset = tk.StringVar(value=list(PRESETS)[0])
        self.demos = server.DEMOS
        self._build()
        self.after(100, self._poll)

    # ---------- UI ----------
    def _build(self):
        style = ttk.Style(self); style.theme_use("clam")
        style.configure("TNotebook", background=CARD, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 6), background="#1c2540", foreground=DIM)
        style.map("TNotebook.Tab", background=[("selected", "#2b4a7f")], foreground=[("selected", TX)])
        style.configure("TCombobox", fieldbackground="#1c2540", background="#1c2540", foreground=TX)

        top = tk.Frame(self, bg=BG); top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="● 三层记忆辅导台", bg=BG, fg=TX, font=("微软雅黑", 14, "bold")).pack(side="left")
        self.lbl_model = tk.Label(top, text=f"模型: {server.CFG['model']} (key已预填)", bg=BG, fg=DIM, font=("微软雅黑", 9))
        self.lbl_model.pack(side="left", padx=14)
        tk.Button(top, text="⚙ 配置", command=self._config, bg="#2b4a7f", fg="white", relief="flat", padx=12).pack(side="right")
        tk.Button(top, text="↺ 重置", command=self._reset, bg="#333c55", fg="white", relief="flat", padx=12).pack(side="right", padx=6)

        main = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=5); main.pack(fill="both", expand=True, padx=12, pady=8)

        # 左: 对话
        left = tk.Frame(main, bg=CARD); main.add(left, minsize=560)
        self.chat = scrolledtext.ScrolledText(left, bg=CARD, fg=TX, font=("微软雅黑", 10),
                                              insertbackground=TX, relief="flat", wrap="word", spacing3=6, state="disabled")
        self.chat.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat.tag_config("u", foreground="#9ec1ff"); self.chat.tag_config("a", foreground=TX)
        self.chat.tag_config("sys", foreground=DIM, font=("微软雅黑", 9, "italic"))

        bar = tk.Frame(left, bg=CARD); bar.pack(fill="x", padx=10, pady=(0, 6))
        self.inp = tk.Text(bar, height=3, bg="#1c2540", fg=TX, insertbackground=TX, relief="flat", font=("微软雅黑", 10), wrap="word")
        self.inp.pack(side="left", fill="x", expand=True)
        self.inp.bind("<Control-Return>", lambda e: self._send())
        self.btn_send = tk.Button(bar, text="发送\n(Ctrl+Enter)", command=self._send, bg=ACC, fg="white", relief="flat", width=10)
        self.btn_send.pack(side="left", padx=8)

        dbar = tk.Frame(left, bg=CARD); dbar.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(dbar, text="演示方案:", bg=CARD, fg=DIM, font=("微软雅黑", 9)).pack(side="left")
        self.sel_demo = ttk.Combobox(dbar, state="readonly", width=34, font=("微软雅黑", 9),
                                     values=[c["label"] for c in self.demos])
        self.sel_demo.pack(side="left", padx=6)
        self.sel_demo.bind("<<ComboboxSelected>>", self._load_demo)
        tk.Button(dbar, text="填入档案", command=self._fill_dossier, bg="#333c55", fg="white", relief="flat").pack(side="left")

        self.chips = tk.Frame(left, bg=CARD); self.chips.pack(fill="x", padx=10, pady=(0, 8))

        # 右: 记忆
        right = tk.Frame(main, bg=CARD); main.add(right, minsize=430)
        tk.Label(right, text="🧠 记忆储存", bg=CARD, fg=TX, font=("微软雅黑", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        stats = tk.Frame(right, bg=CARD); stats.pack(fill="x", padx=12)
        self.stat_lbls = {}
        for i, (k, name) in enumerate([("n_items", "保存条目"), ("raw_chars", "原始字符"), ("organized_chars", "整理字符"), ("compressed_chars", "压缩字符")]):
            f = tk.Frame(stats, bg="#1c2540"); f.grid(row=0, column=i, sticky="ew", padx=3); stats.columnconfigure(i, weight=1)
            v = tk.Label(f, text="0", bg="#1c2540", fg=ACC, font=("微软雅黑", 14, "bold")); v.pack()
            tk.Label(f, text=name, bg="#1c2540", fg=DIM, font=("微软雅黑", 8)).pack()
            self.stat_lbls[k] = v

        self.nb = ttk.Notebook(right); self.nb.pack(fill="both", expand=True, padx=12, pady=8)
        self.mem_views = {}
        for key, name in [("raw", "原始保存"), ("organized", "整理版"), ("compressed", "压缩版")]:
            t = scrolledtext.ScrolledText(self.nb, bg="#10182b", fg=TX, font=("Consolas", 9), relief="flat", wrap="word")
            self.nb.add(t, text=name); self.mem_views[key] = t

        acts = tk.Frame(right, bg=CARD); acts.pack(fill="x", padx=12, pady=(0, 10))
        self.btn_org = tk.Button(acts, text="🗂 记忆整理", command=lambda: self._op("organize"), bg="#3b3a75", fg="white", relief="flat", pady=8)
        self.btn_org.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_cmp = tk.Button(acts, text="🗜 记忆压缩", command=lambda: self._op("compress"), bg="#3b3a75", fg="white", relief="flat", pady=8)
        self.btn_cmp.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_delta = tk.Label(right, text="", bg=CARD, fg="#34d399", font=("微软雅黑", 9)); self.lbl_delta.pack(pady=(0, 8))

    # ---------- 演示方案 ----------
    def _load_demo(self, *_):
        case = self.demos[self.sel_demo.current()]
        self._fill_dossier()
        for w in self.chips.winfo_children(): w.destroy()
        tk.Label(self.chips, text="示例问题:", bg=CARD, fg=DIM, font=("微软雅黑", 8)).pack(side="left")
        for q in case["questions"][:5]:
            b = tk.Button(self.chips, text=q[:14] + ("…" if len(q) > 14 else ""), bg="#1c2540", fg=DIM,
                          relief="flat", font=("微软雅黑", 8),
                          command=lambda t=q: (self.inp.delete("1.0", "end"), self.inp.insert("1.0", t)))
            b.pack(side="left", padx=3)

    def _fill_dossier(self):
        if self.sel_demo.current() < 0: return
        self.inp.delete("1.0", "end")
        self.inp.insert("1.0", self.demos[self.sel_demo.current()]["dossier"])

    # ---------- 配置 ----------
    def _config(self):
        d = tk.Toplevel(self); d.title("⚙ 配置"); d.geometry("520x380"); d.configure(bg=CARD); d.grab_set()
        rows = tk.Frame(d, bg=CARD); rows.pack(fill="both", expand=True, padx=16, pady=14)

        def row(label, r):
            tk.Label(rows, text=label, bg=CARD, fg=DIM, font=("微软雅黑", 9)).grid(row=r, column=0, sticky="w", pady=5)
        row("API Key", 0)
        e_key = tk.Entry(rows, width=44, show="*", bg="#1c2540", fg=TX, insertbackground=TX, relief="flat")
        e_key.insert(0, server.CFG["api_key"]); e_key.grid(row=0, column=1, pady=5)
        row("模型", 1)
        cb_model = ttk.Combobox(rows, state="readonly", width=41, values=[f"{lbl}  ({mid})" for lbl, mid, _ in MODELS])
        cur = next((i for i, (_, mid, _) in enumerate(MODELS) if mid == server.CFG["model"]), 10)
        cb_model.current(cur); cb_model.grid(row=1, column=1, pady=5)
        row("推理变体", 2)
        cb_var = ttk.Combobox(rows, state="readonly", width=41)
        def refresh_var(*_):
            prov = MODELS[cb_model.current()][2]
            cb_var["values"] = ["默认(提供商默认)"] + VARIANTS[prov]
            if not cb_var.get(): cb_var.current(0)
        cb_model.bind("<<ComboboxSelected>>", refresh_var); refresh_var()
        if server.CFG.get("variant"): cb_var.set(server.CFG["variant"])
        cb_var.grid(row=2, column=1, pady=5)
        row("max_tokens", 3)
        e_tok = tk.Entry(rows, width=12, bg="#1c2540", fg=TX, insertbackground=TX, relief="flat")
        e_tok.insert(0, server.CFG.get("max_tokens", "4000")); e_tok.grid(row=3, column=1, sticky="w", pady=5)
        row("temperature (空=默认)", 4)
        e_temp = tk.Entry(rows, width=12, bg="#1c2540", fg=TX, insertbackground=TX, relief="flat")
        e_temp.insert(0, server.CFG.get("temperature", "")); e_temp.grid(row=4, column=1, sticky="w", pady=5)
        row("上下文方案", 5)
        cb_pre = ttk.Combobox(rows, state="readonly", width=41, values=list(PRESETS))
        cb_pre.set(self.preset.get()); cb_pre.grid(row=5, column=1, pady=5)

        def save():
            server.CFG["api_key"] = e_key.get().strip() or server.CFG["api_key"]
            server.CFG["model"] = MODELS[cb_model.current()][1]
            v = cb_var.get(); server.CFG["variant"] = "" if v.startswith("默认") else v
            server.CFG["max_tokens"] = e_tok.get().strip() or "4000"
            server.CFG["temperature"] = e_temp.get().strip()
            self.preset.set(cb_pre.get())
            self.lbl_model.config(text=f"模型: {server.CFG['model']} (key已预填)")
            d.destroy()
        tk.Button(d, text="保存", command=save, bg=ACC, fg="white", relief="flat", padx=24, pady=6).pack(pady=10)

    # ---------- 对话 ----------
    def _msgs(self, question):
        mem = mc.default_memory_block(self.store)
        n = PRESETS[self.preset.get()]
        return ([{"role": "system", "content": SYSTEM + ("\n\n" + mem if mem else "")}]
                + self.history[-n:] + [{"role": "user", "content": question}])

    def _send(self):
        q = self.inp.get("1.0", "end").strip()
        if not q: return
        self.inp.delete("1.0", "end")
        self.turn_no += 1
        self._append(f"🧑 学生: {q}\n", "u")
        self.btn_send.config(state="disabled", text="思考中…")
        threading.Thread(target=self._chat_worker, args=(q, self.turn_no), daemon=True).start()

    def _chat_worker(self, q, turn):
        try:
            reply = server.call_llm(self._msgs(q)) or "(空回复)"
            self.store.save(q, turn, "学生"); self.store.save(reply, turn, "老师")
            self.history += [{"role": "user", "content": q}, {"role": "assistant", "content": reply}]
            self.q.put(("chat", reply))
        except Exception as e:
            self.q.put(("err", str(e)))

    def _op(self, kind):
        btn = self.btn_org if kind == "organize" else self.btn_cmp
        btn.config(state="disabled", text="⏳ 处理中…")
        before = len(self.store.raw_text()) if kind == "organize" else len(self.store.organized)
        def w():
            try:
                fn = mc.organize if kind == "organize" else mc.compress
                _, changed = fn(self.store, lambda p: server.call_llm([{"role": "user", "content": p}]))
                after = len(self.store.organized) if kind == "organize" else len(self.store.compressed)
                self.q.put(("op", (kind, changed, before, after)))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=w, daemon=True).start()

    def _reset(self):
        self.store = mc.MemoryStore(); self.history = []; self.turn_no = 0
        self._append("—— 已重置 ——\n", "sys"); self._refresh_mem()

    # ---------- 渲染 ----------
    def _append(self, text, tag):
        self.chat.config(state="normal"); self.chat.insert("end", text + "\n", tag)
        self.chat.see("end"); self.chat.config(state="disabled")

    def _refresh_mem(self):
        st = self.store.stats
        vals = {"n_items": len(self.store.items), "raw_chars": len(self.store.raw_text()),
                "organized_chars": len(self.store.organized), "compressed_chars": len(self.store.compressed)}
        for k, v in vals.items(): self.stat_lbls[k].config(text=str(v))
        for key, txt in [("raw", self.store.raw_text()), ("organized", self.store.organized), ("compressed", self.store.compressed)]:
            t = self.mem_views[key]; t.config(state="normal"); t.delete("1.0", "end")
            t.insert("1.0", txt or "(暂无内容)"); t.config(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "chat":
                    self._append(f"🤖 老师: {payload}\n", "a")
                    self.btn_send.config(state="normal", text="发送\n(Ctrl+Enter)")
                    self._refresh_mem()
                elif kind == "op":
                    op, changed, before, after = payload
                    btn, name = (self.btn_org, "🗂 记忆整理") if op == "organize" else (self.btn_cmp, "🗜 记忆压缩")
                    btn.config(state="normal", text=name)
                    self.lbl_delta.config(text=f"{name}: {before}→{after} 字符" + ("" if changed else " (NO-OP, 无需变更)"))
                    self.nb.select(self.mem_views["organized" if op == "organize" else "compressed"])
                    self._refresh_mem()
                elif kind == "err":
                    self._append(f"⚠ 出错: {payload}\n", "sys")
                    self.btn_send.config(state="normal", text="发送\n(Ctrl+Enter)")
                    self.btn_org.config(state="normal", text="🗂 记忆整理"); self.btn_cmp.config(state="normal", text="🗜 记忆压缩")
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()
