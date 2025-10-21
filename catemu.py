#!/usr/bin/env python3
"""
SAMSOFTN64EMU – Project64 0.1 Harness Recreation (Pure Python)
© 2025 FlamesCo & Samsoft — samsoftemun64v0
"""

import tkinter as tk
import time, threading, random

# ===============================================================
# CONSTANTS
# ===============================================================
RDRAM_SIZE = 0x00800000  # 8 MB
FB_WIDTH, FB_HEIGHT = 320, 240
HZ = 60
FRAME_TIME = 1.0 / HZ

# ===============================================================
# MEMORY + BUS
# ===============================================================
def be_load32(mem, off):
    return (mem[off]<<24)|(mem[off+1]<<16)|(mem[off+2]<<8)|mem[off+3]
def be_store32(mem, off, val):
    mem[off]=(val>>24)&255; mem[off+1]=(val>>16)&255
    mem[off+2]=(val>>8)&255; mem[off+3]=val&255

class MemoryBus:
    def __init__(self):
        self.rdram = bytearray(RDRAM_SIZE)
        self.regs  = {}
    def read32(self, addr):
        if addr < len(self.rdram)-4:
            return be_load32(self.rdram, addr)
        return self.regs.get(addr, 0)
    def write32(self, addr, val):
        if addr < len(self.rdram)-4:
            be_store32(self.rdram, addr, val)
        else:
            self.regs[addr] = val & 0xFFFFFFFF

# ===============================================================
# CPU (R4300i skeleton)
# ===============================================================
class CPU:
    def __init__(self, bus):
        self.bus = bus
        self.reg = [0]*32
        self.pc = 0x80000000
        self.running = False
    def step(self):
        # placeholder: emulate some bus writes for demo
        base = 0x00000000
        color = random.randint(0,0xFFFFFF)
        for y in range(FB_HEIGHT):
            for x in range(FB_WIDTH):
                off = base + (y*FB_WIDTH+x)*4
                be_store32(self.bus.rdram, off, 0xFF000000|color)
        time.sleep(0.01)
        return 1

# ===============================================================
# VI (Video Interface)
# ===============================================================
class VideoInterface:
    def __init__(self, bus):
        self.bus = bus
        self.width = FB_WIDTH
        self.height = FB_HEIGHT
        self.fb_base = 0
        self.fb = bytearray(FB_WIDTH*FB_HEIGHT*4)
        self.dirty = True
    def render(self, photo: tk.PhotoImage):
        """Render RDRAM framebuffer into PhotoImage"""
        mem = self.bus.rdram
        rows=[]
        idx=0
        for y in range(self.height):
            row=[]
            for x in range(self.width):
                a=mem[idx]; r=mem[idx+1]; g=mem[idx+2]; b=mem[idx+3]
                row.append(f"#{r:02x}{g:02x}{b:02x}")
                idx+=4
            rows.append("{"+" ".join(row)+"}")
        photo.put(" ".join(rows))
        self.dirty=False

# ===============================================================
# EMULATOR CORE
# ===============================================================
class EmulatorCore:
    def __init__(self):
        self.bus=MemoryBus()
        self.cpu=CPU(self.bus)
        self.vi=VideoInterface(self.bus)
        self.running=False
        self.paused=False
        self.thread=None
        self.fps=0.0
    def start(self):
        if self.running: return
        self.running=True; self.cpu.running=True
        self.thread=threading.Thread(target=self.loop,daemon=True); self.thread.start()
    def stop(self):
        self.running=False; self.cpu.running=False
    def loop(self):
        last=time.time(); frames=0
        while self.running:
            if not self.paused: self.cpu.step()
            now=time.time()
            if now-last>=1.0:
                self.fps=frames/(now-last)
                frames=0; last=now
            frames+=1

# ===============================================================
# GUI (Project64-style)
# ===============================================================
class SamsoftGUI:
    def __init__(self, root):
        self.root=root
        self.root.title("SAMSOFTN64EMU – Project64 Harness")
        self.root.geometry("640x480")
        self.emu=EmulatorCore()
        self.canvas=tk.Canvas(root,bg="black")
        self.canvas.pack(fill=tk.BOTH,expand=True)
        self.photo=tk.PhotoImage(width=FB_WIDTH,height=FB_HEIGHT)
        self.img=self.canvas.create_image(0,0,anchor=tk.NW,image=self.photo)
        # toolbar
        tb=tk.Frame(root,bg="#333")
        tb.pack(fill=tk.X)
        tk.Button(tb,text="Start",command=self.start).pack(side=tk.LEFT)
        tk.Button(tb,text="Pause",command=self.pause).pack(side=tk.LEFT)
        tk.Button(tb,text="Stop",command=self.stop).pack(side=tk.LEFT)
        self.fps_label=tk.Label(tb,text="FPS: 0",fg="lime",bg="#333")
        self.fps_label.pack(side=tk.RIGHT)
        self.update_loop()
    def start(self): self.emu.start()
    def stop(self): self.emu.stop()
    def pause(self): self.emu.paused=not self.emu.paused
    def update_loop(self):
        if self.emu.cpu.running:
            self.emu.vi.render(self.photo)
            self.fps_label.config(text=f"FPS: {self.emu.fps:4.1f}")
        self.root.after(16,self.update_loop)

# ===============================================================
# ENTRY
# ===============================================================
if __name__=="__main__":
    root=tk.Tk()
    SamsoftGUI(root)
    root.mainloop()
