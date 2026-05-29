import customtkinter as ctk
import tkinter as tk
import threading
import math
import time
import re
import numpy as np
import pythoncom
from PIL import Image, ImageTk

from tutor import claude, tts
 
# ── Colour palette ─────────────────────────────────────────────────────────────
BG          = "#0D0E1A"   # deep navy
BG2         = "#13152A"   # slightly lighter panel
ORBTOP      = "#C850C0"   # magenta
ORBBOT      = "#4158D0"   # electric blue
ORBACC      = "#FFCC70"   # amber accent
GLOW1       = "#C850C0"
GLOW2       = "#4158D0"
TEXT_MAIN   = "#E8E8F0"
TEXT_DIM    = "#5A5A7A"
INPUT_BG    = "#1A1C30"
INPUT_BORD  = "#2A2D4A"
SEND_COL    = "#C850C0"
SEND_HOV    = "#9B3DA0"
WHITE       = "#FFFFFF"
 
ctk.set_appearance_mode("dark")
 
 
# ── Colour blend helper ────────────────────────────────────────────────────────
def _blend(c1: str, c2: str, t: float) -> str:
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return f"#{round(r1+t*(r2-r1)):02x}{round(g1+t*(g2-g1)):02x}{round(b1+t*(b2-b1)):02x}"
 
def _fade(hex_col: str, alpha: float) -> str:
    return _blend(hex_col, BG, 1 - alpha)
 
 
# ── Main app ───────────────────────────────────────────────────────────────────
class SpanishTutorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Spanish Tutor")
        self.geometry("780x570")
        self.resizable(False, False)
        self.configure(fg_color=BG)
 
        self.app_state = "idle"   # idle | thinking | speaking
        # Precompute pixel distance map for smooth PIL orb rendering
        _s = 320
        _Y, _X = np.ogrid[:_s, :_s]
        self._dist = np.sqrt((_X - _s//2)**2 + (_Y - _s//2)**2).astype(np.float32)
        self._orb_ref = None   # prevent GC of PhotoImage
        self._build_ui()
        self.after(60, self._animate)
 
    # ── UI build ───────────────────────────────────────────────────────────────
 
    def _build_ui(self):
        # Title
        ctk.CTkLabel(
            self,
            text="Tutor AI",
            font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
            text_color=TEXT_DIM,
        ).pack(pady=(28, 0))
 
        # Orb canvas — centrepiece
        self.canvas = tk.Canvas(
            self, width=320, height=320,
            bg=BG, highlightthickness=0,
        )
        self.canvas.pack(pady=(8, 0))
 
        # Status label
        self.status_var = tk.StringVar(value="¿Qué quieres practicar hoy?")
        ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=TEXT_DIM,
        ).pack(pady=(6, 22))
 
        # Input row
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=48, pady=(0, 32))
        input_frame.columnconfigure(0, weight=1)
 
        self.entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type in Spanish or English...",
            font=ctk.CTkFont("Outfit", 16),
            fg_color=INPUT_BG,
            border_color=INPUT_BORD,
            border_width=1,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_DIM,
            corner_radius=20,
            height=52,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self._send())
 
        self.send_btn = ctk.CTkButton(
            input_frame,
            text="➜",
            font=ctk.CTkFont("Segoe UI", 18),
            fg_color=SEND_COL,
            hover_color=SEND_HOV,
            text_color=WHITE,
            corner_radius=20,
            width=40,
            height=52,
            command=self._send,
        )
        self.send_btn.grid(row=0, column=1)
 
    # ── Pipeline ───────────────────────────────────────────────────────────────
 
    def _send(self):
        text = self.entry.get().strip()
        if not text or self.app_state != "idle":
            return
        self.entry.delete(0, "end")
        self._set_state("thinking")
        threading.Thread(target=self._pipeline, args=(text,), daemon=True).start()
 
    def _pipeline(self, text: str):
        pythoncom.CoInitialize()
        try:
            full_reply = claude(text)

            # Strip [SPEED:N] silently
            speed = 0
            speed_match = re.match(r'^\[SPEED:(-?\d+)\]', full_reply.strip())
            if speed_match:
                speed = max(-10, min(0, int(speed_match.group(1))))
                full_reply = full_reply[speed_match.end():].strip()

            self.after(0, lambda: self._set_state("speaking"))
            tts(full_reply, rate=speed)   # tts() handles [EN]/[ES] tags internally
            self.after(0, lambda: self._set_state("idle"))
        except Exception as e:
            print(f"Pipeline error: {e}")
            self.after(0, lambda: self._set_state("idle"))
 
    # ── State ──────────────────────────────────────────────────────────────────
 
    def _set_state(self, state: str):
        self.app_state = state
        messages = {
            "idle":     "¿Qué quieres practicar hoy?",
            "thinking": "pensando...",
            "speaking": "hablando...",
        }
        self.status_var.set(messages[state])
        is_idle = state == "idle"
        self.send_btn.configure(state="normal" if is_idle else "disabled")
        self.entry.configure(state="normal" if is_idle else "disabled")
 
    # ── Orb renderer ───────────────────────────────────────────────────────────

    def _render_orb(self, radius: float, col_a: str, col_b: str, dim: float = 1.0) -> ImageTk.PhotoImage:
        """Render a smooth anti-aliased radial gradient orb via PIL."""
        def h(c): return np.array([int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)], np.float32)
        ca, cb, bg = h(col_a), h(col_b), h(BG)
        t = np.clip(self._dist / radius, 0.0, 1.0)
        rgb = ca * (1 - t[:,:,None]) + cb * t[:,:,None]
        rgb *= dim
        feather = np.clip((radius + 18 - self._dist) / 18, 0.0, 1.0)
        rgb = rgb * feather[:,:,None] + bg * (1 - feather[:,:,None])
        photo = ImageTk.PhotoImage(Image.fromarray(rgb.clip(0, 255).astype(np.uint8)))
        self._orb_ref = photo
        return photo

    # ── Animation ──────────────────────────────────────────────────────────────
 
    def _animate(self):
        c = self.canvas
        c.delete("all")
        t = time.time()
        cx, cy = 160, 160
 
        if self.app_state == "idle":
            self._draw_orb_idle(c, cx, cy, t)
        elif self.app_state == "thinking":
            self._draw_orb_thinking(c, cx, cy, t)
        else:
            self._draw_orb_speaking(c, cx, cy, t)
 
        self.after(30, self._animate)
 
    # -- idle: slow breathing glow orb -----------------------------------------
    def _draw_orb_idle(self, c, cx, cy, t):
        breath = 0.5 + 0.5 * math.sin(t * 0.9)

        photo = self._render_orb(
            radius=72 + 4 * breath,
            col_a=ORBBOT,
            col_b=_blend(ORBBOT, ORBTOP, 0.7 + 0.3 * breath),
            dim=0.85 + 0.15 * breath,
        )
        c.create_image(cx, cy, image=photo, anchor="center")

        # outer glow rings
        for i in range(5, 0, -1):
            r = 95 + i * 14 + breath * 8
            alpha = 0.04 + 0.02 * breath
            col = _fade(GLOW1 if i % 2 == 0 else GLOW2, alpha * (6 - i) / 5)
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=2, fill="")

        # shimmer lines inside orb
        """for k in range(6):
            angle = t * 0.4 + k * math.pi / 3
            x1 = cx + 30 * math.cos(angle)
            y1 = cy + 30 * math.sin(angle)
            x2 = cx + 65 * math.cos(angle + 0.5)
            y2 = cy + 65 * math.sin(angle + 0.5)
            alpha = 0.15 + 0.1 * math.sin(t * 1.2 + k)
            c.create_line(x1, y1, x2, y2, fill=_fade(WHITE, max(0, alpha)), width=1)

        c.create_oval(cx-28, cy-34, cx+6, cy-12, fill=_fade(WHITE, 0.18), outline="")"""
 
    # -- thinking: rotating particle ring --------------------------------------
    def _draw_orb_thinking(self, c, cx, cy, t):
        photo = self._render_orb(72, ORBBOT, _blend(ORBBOT, ORBTOP, 0.4), dim=0.5)
        c.create_image(cx, cy, image=photo, anchor="center")

        # orbiting particles
        n = 10
        for i in range(n):
            angle = t * 2.2 + i * (2 * math.pi / n)
            pulse = 0.5 + 0.5 * math.sin(t * 4 + i * 0.9)
            ring_r = 100 + 12 * math.sin(t * 1.5 + i)
            x = cx + ring_r * math.cos(angle)
            y = cy + ring_r * math.sin(angle)
            dot_r = 3 + 3 * pulse
            col = _fade(_blend(GLOW2, GLOW1, (math.sin(angle) + 1) / 2), 0.3 + 0.7 * pulse)
            c.create_oval(x-dot_r, y-dot_r, x+dot_r, y+dot_r, fill=col, outline="")

        c.create_oval(cx-28, cy-34, cx+6, cy-12, fill=_fade(WHITE, 0.10), outline="")
 
    # -- speaking: ripple waves radiating outward ------------------------------
    def _draw_orb_speaking(self, c, cx, cy, t):
        pulse = 0.5 + 0.5 * math.sin(t * 3.5)

        photo = self._render_orb(
            radius=72 + pulse * 10,
            col_a=ORBBOT,
            col_b=_blend(ORBBOT, ORBTOP, 0.8 + 0.2 * pulse),
            dim=0.9 + 0.1 * pulse,
        )
        c.create_image(cx, cy, image=photo, anchor="center")

        # radiating rings
        for i in range(5):
            phase = (t * 1.8 + i * 0.38) % 1.9
            r = 80 + phase * 85
            alpha = max(0.0, (1.0 - phase / 1.9) * 0.7)
            col = _blend(_fade(GLOW1, alpha), _fade(GLOW2, alpha), 0.5)
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=2, fill="")

        c.create_oval(cx-28, cy-34, cx+6, cy-12, fill=_fade(WHITE, 0.20 + 0.08 * pulse), outline="")
 
 
# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SpanishTutorApp()
    app.mainloop()