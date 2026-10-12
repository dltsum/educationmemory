# -*- coding: utf-8 -*-
"""
三层记忆辅导台 · 桌面客户端 (customtkinter 现代暗色 UI)
记忆风格: 三层默认 / Claude Code / Codex / MemGPT (memory_styles.py)
运行: python app_ctk.py   (依赖: pip install customtkinter)
"""
import os, sys, threading, queue
import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_core as mc
import memory_styles as ms
import server  # 复用 CFG/call_llm/DEMOS (__main__ 保护)

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
SYSTEM = "你是一位耐心的中小学辅导老师, 讲解适合学生水平, 善用生活化例子。"
ACC, ACC2, CARD, DIM = "#2b6cb0", "#6b46c1", "#161d2e", "#8b93a7"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("三层记忆辅导台 · 保存 → 整理 → 压缩")
        self.geometry("1320x820")
        self.store = mc.MemoryStore()
        self.history = []
        self.turn_no = 0
        self.style = ms.DEFAULT_STYLE
        self.q = queue.Queue()
        self._build()
        self.after(100, self._poll)

    # ---------------- UI ----------------
    def _build(self):
        # 顶栏
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text="● 三层记忆辅导台", font=("微软雅黑", 18, "bold")).pack(side="left")
        self.lbl_model = ctk.CTkLabel(top, text=f"模型: {server.CFG['model']} · key已预填", text_color=DIM, font=("微软雅黑", 11))
        self.lbl_model.pack(side="left", padx=16)
        ctk.CTkButton(top, text="⚙ 配置", width=84, fg_color="#333c55", command=self._config).pack(side="right")
        ctk.CTkButton(top, text="↺ 重置", width=84, fg_color="#333c55", command=self._reset).pack(side="right", padx=8)

        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(fill="both", expand=True, padx=16, pady=8)
        body.columnconfigure(0, weight=3); body.columnconfigure(1, weight=2); body.rowconfigure(0, weight=1)

        # 左: 对话
        left = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD); left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1); left.columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(left, fg_color="transparent"); hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        ctk.CTkLabel(hdr, text="💬 对话", font=("微软雅黑", 13, "bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="演示方案:", text_color=DIM, font=("微软雅黑", 11)).pack(side="left", padx=(18, 4))
        self.sel_demo = ctk.CTkOptionMenu(hdr, width=280, values=[c["label"] for c in server.DEMOS],
                                          command=self._load_demo, font=("微软雅黑", 11))
        self.sel_demo.set("选择学生档案…"); self.sel_demo.pack(side="left")
        ctk.CTkButton(hdr, text="填入档案", width=76, fg_color="#333c55", command=self._fill_dossier).pack(side="left", padx=6)

        self.chat = ctk.CTkScrollableFrame(left, fg_color="#10182b", corner_radius=10)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)

        self.qbar = ctk.CTkScrollableFrame(left, height=64, orientation="horizontal", fg_color="transparent")
        self.qbar.grid(row=2, column=0, sticky="ew", padx=12)

        ibar = ctk.CTkFrame(left, fg_color="transparent"); ibar.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 12))
        ibar.columnconfigure(0, weight=1)
        self.inp = ctk.CTkTextbox(ibar, height=64, font=("微软雅黑", 12), wrap="word")
        self.inp.grid(row=0, column=0, sticky="ew")
        self.inp.bind("<Control-Return>", lambda e: (self._send(), "break")[1])
        self.btn_send = ctk.CTkButton(ibar, text="发送\nCtrl+Enter", width=92, height=64,
                                      font=("微软雅黑", 12, "bold"), command=self._send)
        self.btn_send.grid(row=0, column=1, padx=(8, 0))

        # 右: 记忆
        right = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD); right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(3, weight=1); right.columnconfigure(0, weight=1)
        rtop = ctk.CTkFrame(right, fg_color="transparent"); rtop.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(rtop, text="🧠 记忆储存", font=("微软雅黑", 13, "bold")).pack(side="left")
        ctk.CTkLabel(rtop, text="记忆风格:", text_color=DIM, font=("微软雅黑", 11)).pack(side="left", padx=(14, 4))
        self.sel_style = ctk.CTkOptionMenu(rtop, width=190, values=list(ms.STYLES),
                                           command=self._set_style, font=("微软雅黑", 11))
        self.sel_style.set(self.style); self.sel_style.pack(side="left")

        stats = ctk.CTkFrame(right, fg_color="transparent"); stats.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        self.stat_lbls = {}
        for i, (k, name) in enumerate([("n_items", "保存条目"), ("raw_chars", "原始字符"), ("organized_chars", "整理字符"), ("compressed_chars", "压缩字符")]):
            f = ctk.CTkFrame(stats, corner_radius=10, fg_color="#1c2540"); f.grid(row=0, column=i, sticky="ew", padx=3)
            stats.columnconfigure(i, weight=1)
            v = ctk.CTkLabel(f, text="0", font=("微软雅黑", 16, "bold"), text_color="#6ea8fe"); v.pack(pady=(6, 0))
            ctk.CTkLabel(f, text=name, font=("微软雅黑", 9), text_color=DIM).pack(pady=(0, 6))
            self.stat_lbls[k] = v

        self.lbl_style_desc = ctk.CTkLabel(right, text=ms.STYLES[self.style]["desc"], text_color=DIM,
                                           font=("微软雅黑", 10), wraplength=380, justify="left")
        self.lbl_style_desc.grid(row=2, column=0, sticky="ew", padx=14)

        self.tabs = ctk.CTkTabview(right, corner_radius=10, fg_color="#10182b",
                                   segmented_button_selected_color=ACC)
        self.tabs.grid(row=3, column=0, sticky="nsew", padx=12, pady=8)
        self.mem_views = {}
        for key, name in [("raw", "原始保存"), ("organized", "整理版"), ("compressed", "压缩版")]:
            self.tabs.add(name)
            t = ctk.CTkTextbox(self.tabs.tab(name), font=("Consolas", 10), wrap="word", fg_color="#10182b")
            t.pack(fill="both", expand=True); t.configure(state="disabled")
            self.mem_views[key] = t

        acts = ctk.CTkFrame(right, fg_color="transparent"); acts.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 4))
        self.btn_org = ctk.CTkButton(acts, text="🗂 记忆整理", height=40, fg_color=ACC2,
                                     font=("微软雅黑", 12, "bold"), command=lambda: self._op("organize"))
        self.btn_org.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_cmp = ctk.CTkButton(acts, text="🗜 记忆压缩", height=40, fg_color=ACC2,
                                     font=("微软雅黑", 12, "bold"), command=lambda: self._op("compress"))
        self.btn_cmp.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_delta = ctk.CTkLabel(right, text="", text_color="#34d399", font=("微软雅黑", 10))
        self.lbl_delta.grid(row=5, column=0, pady=(0, 8))

    # ---------------- 气泡 ----------------
    def _bubble(self, text, mine=False, dim=False):
        wrap = ctk.CTkFrame(self.chat, fg_color="transparent"); wrap.pack(fill="x", pady=4, padx=4)
        b = ctk.CTkLabel(wrap, text=text, wraplength=560, justify="left",
                         font=("微软雅黑", 11 if not dim else 10, "italic" if dim else "normal"),
                         text_color="#8b93a7" if dim else ("#dbe7ff" if mine else "#e5e9f0"),
                         fg_color="transparent" if dim else ("#2b4a7f" if mine else "#1c2540"),
                         corner_radius=10, padx=12, pady=8)
        b.pack(side="right" if mine else "left", anchor="e" if mine else "w")
        self.chat.update_idletasks()
        self.chat._parent_canvas.yview_moveto(1.0)

    # ---------------- 演示方案 ----------------
    def _load_demo(self, _=None):
        idx = [c["label"] for c in server.DEMOS].index(self.sel_demo.get())
        case = server.DEMOS[idx]
        self._fill_dossier()
        for w in self.qbar.winfo_children(): w.destroy()
        for q in case["questions"][:10]:
            ctk.CTkButton(self.qbar, text=q[:16] + ("…" if len(q) > 16 else ""), height=26,
                          fg_color="#1c2540", hover_color="#2b4a7f", text_color=DIM,
                          font=("微软雅黑", 10),
                          command=lambda t=q: (self.inp.delete("1.0", "end"), self.inp.insert("1.0", t))
                          ).pack(side="left", padx=3, pady=3)

    def _fill_dossier(self):
        idx = [c["label"] for c in server.DEMOS].index(self.sel_demo.get()) if self.sel_demo.get() in [c["label"] for c in server.DEMOS] else -1
        if idx < 0: return
        self.inp.delete("1.0", "end"); self.inp.insert("1.0", server.DEMOS[idx]["dossier"])

    # ---------------- 配置 ----------------
    def _config(self):
        d = ctk.CTkToplevel(self); d.title("⚙ 配置"); d.geometry("560x400")
        d.grab_set(); d.attributes("-topmost", True)
        fr = ctk.CTkScrollableFrame(d, fg_color="transparent"); fr.pack(fill="both", expand=True, padx=18, pady=14)

        def lab(t): ctk.CTkLabel(fr, text=t, text_color=DIM, font=("微软雅黑", 11)).pack(anchor="w", pady=(8, 2))
        lab("API Key")
        e_key = ctk.CTkEntry(fr, width=460, show="*"); e_key.insert(0, server.CFG["api_key"]); e_key.pack(anchor="w")
        lab("模型 (OpenCode 内置)")
        cb_model = ctk.CTkOptionMenu(fr, width=460, values=[f"{lbl}  ({mid})" for lbl, mid, _ in MODELS])
        cur = next((i for i, (_, mid, _) in enumerate(MODELS) if mid == server.CFG["model"]), 10)
        cb_model.set(f"{MODELS[cur][0]}  ({MODELS[cur][1]})"); cb_model.pack(anchor="w")
        lab("推理变体")
        cb_var = ctk.CTkOptionMenu(fr, width=460, values=["默认(提供商默认)"] + VARIANTS[MODELS[cur][2]])
        cb_var.set(server.CFG.get("variant") or "默认(提供商默认)"); cb_var.pack(anchor="w")
        lab("max_tokens")
        e_tok = ctk.CTkEntry(fr, width=140); e_tok.insert(0, server.CFG.get("max_tokens", "4000")); e_tok.pack(anchor="w")
        lab("temperature (空=模型默认)")
        e_temp = ctk.CTkEntry(fr, width=140); e_temp.insert(0, server.CFG.get("temperature", "")); e_temp.pack(anchor="w")

        def save():
            server.CFG["api_key"] = e_key.get().strip() or server.CFG["api_key"]
            sel = cb_model.get(); server.CFG["model"] = sel[sel.rfind("(") + 1:-1]
            v = cb_var.get(); server.CFG["variant"] = "" if v.startswith("默认") else v
            server.CFG["max_tokens"] = e_tok.get().strip() or "4000"
            server.CFG["temperature"] = e_temp.get().strip()
            self.lbl_model.configure(text=f"模型: {server.CFG['model']} · key已预填")
            d.destroy()
        ctk.CTkButton(d, text="保存", width=140, command=save).pack(pady=12)

    # ---------------- 记忆风格 ----------------
    def _set_style(self, name):
        self.style = name
        self.lbl_style_desc.configure(text=ms.STYLES[name]["desc"])
        self._refresh_mem()

    # ---------------- 对话 ----------------
    def _msgs(self, question):
        mem = ms.block_with(self.store, self.style)
        return ([{"role": "system", "content": SYSTEM + ("\n\n" + mem if mem else "")}]
                + self.history[-8:] + [{"role": "user", "content": question}])

    def _send(self):
        q = self.inp.get("1.0", "end").strip()
        if not q: return
        self.inp.delete("1.0", "end")
        self.turn_no += 1
        self._bubble(q, mine=True)
        self.btn_send.configure(state="disabled", text="思考中…")
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
        btn.configure(state="disabled", text="⏳ 处理中…")
        before = len(self.store.raw_text()) if kind == "organize" else len(self.store.organized)
        def w():
            try:
                fn = ms.organize_with if kind == "organize" else ms.compress_with
                _, changed = fn(self.store, lambda p: server.call_llm([{"role": "user", "content": p}]), self.style)
                after = len(self.store.organized) if kind == "organize" else len(self.store.compressed)
                self.q.put(("op", (kind, changed, before, after)))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=w, daemon=True).start()

    def _reset(self):
        self.store = mc.MemoryStore(); self.history = []; self.turn_no = 0
        self._bubble("—— 已重置 ——", dim=True); self._refresh_mem()

    # ---------------- 渲染/轮询 ----------------
    def _refresh_mem(self):
        vals = {"n_items": len(self.store.items), "raw_chars": len(self.store.raw_text()),
                "organized_chars": len(self.store.organized), "compressed_chars": len(self.store.compressed)}
        for k, v in vals.items(): self.stat_lbls[k].configure(text=str(v))
        for key, txt in [("raw", self.store.raw_text()), ("organized", self.store.organized), ("compressed", self.store.compressed)]:
            t = self.mem_views[key]; t.configure(state="normal"); t.delete("1.0", "end")
            t.insert("1.0", txt or "(暂无内容)"); t.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "chat":
                    self._bubble(payload)
                    self.btn_send.configure(state="normal", text="发送\nCtrl+Enter")
                    self._refresh_mem()
                elif kind == "op":
                    op, changed, before, after = payload
                    btn, name = (self.btn_org, "🗂 记忆整理") if op == "organize" else (self.btn_cmp, "🗜 记忆压缩")
                    btn.configure(state="normal", text=name)
                    self.lbl_delta.configure(text=f"{name}: {before}→{after} 字符" + ("" if changed else " (NO-OP)"))
                    self.tabs.set("整理版" if op == "organize" else "压缩版")
                    self._refresh_mem()
                elif kind == "err":
                    self._bubble(f"⚠ 出错: {payload}", dim=True)
                    self.btn_send.configure(state="normal", text="发送\nCtrl+Enter")
                    self.btn_org.configure(state="normal", text="🗂 记忆整理")
                    self.btn_cmp.configure(state="normal", text="🗜 记忆压缩")
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()
