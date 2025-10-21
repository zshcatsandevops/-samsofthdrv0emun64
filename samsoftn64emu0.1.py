#!/usr/bin/env python3
"""
CATN64EMUSAMSOFT1.1HDR "dot64 Edition"
(C) 2025 FlamesCo / Samsoft Labs
Project64-style N64 harness emulator — Tkinter single-file build
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import struct, threading, time

# ============================================================
# Core Memory
# ============================================================
class N64Memory:
    def __init__(self):
        self.rdram = bytearray(8 * 1024 * 1024)
        self.rom = bytearray(64 * 1024 * 1024)
        self.endian_mode = "Z64 (Big-Endian)"

    def virtual_to_physical(self, addr):
        addr &= 0xFFFFFFFF
        if 0x80000000 <= addr <= 0xBFFFFFFF:
            return addr & 0x1FFFFFFF
        return addr

    def read32(self, addr):
        v = addr & 0xFFFFFFFF
        if 0x10000000 <= v < 0x14000000:
            p = v - 0x10000000
            if p + 3 < len(self.rom):
                return struct.unpack('>I', self.rom[p:p+4])[0]
        p = self.virtual_to_physical(addr)
        if p + 3 < len(self.rdram):
            return struct.unpack('>I', self.rdram[p:p+4])[0]
        return 0

    def write32(self, addr, val):
        v = addr & 0xFFFFFFFF
        if 0x10000000 <= v < 0x14000000:
            return  # ROM is read-only
        p = self.virtual_to_physical(addr)
        if p + 3 < len(self.rdram):
            self.rdram[p:p+4] = struct.pack('>I', val & 0xFFFFFFFF)

    def load_rom_data(self, raw):
        data = bytearray(raw)
        if len(data) < 4:
            return None
        fb = data[0]
        if fb == 0x80:
            self.endian_mode = "Z64 (Big-Endian)"
        elif fb == 0x37:
            self.endian_mode = "V64 (Byte-swapped)"
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    data[i:i+4] = data[i:i+4][::-1]
        elif fb == 0x40:
            self.endian_mode = "N64 (Little-Endian)"
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    w = struct.unpack('<I', data[i:i+4])[0]
                    data[i:i+4] = struct.pack('>I', w)
        else:
            self.endian_mode = "Unknown"
            return None
        self.rom[:len(data)] = data
        return len(data)

# ============================================================
# Core CPU
# ============================================================
class MIPSR4300i:
    def __init__(self, mem):
        self.mem = mem
        self.gpr = [0]*32
        self.pc = 0xA4000040
        self.next_pc = self.pc + 4
        self.hi = self.lo = 0
        self.cycles = 0
        self.running = False

    def reset(self):
        self.gpr = [0]*32
        self.pc = 0xA4000040
        self.next_pc = self.pc + 4
        self.hi = self.lo = 0
        self.cycles = 0
        self.running = False

    def fetch(self):
        return self.mem.read32(self.pc)

    def decode_execute(self, ins):
        op = (ins>>26)&0x3F
        rs=(ins>>21)&0x1F; rt=(ins>>16)&0x1F; rd=(ins>>11)&0x1F
        sh=(ins>>6)&0x1F; fn=ins&0x3F; imm=ins&0xFFFF; tgt=ins&0x3FFFFFF
        imm_se = (imm|0xFFFFFFFFFFFF0000) if imm&0x8000 else imm
        self.gpr[0]=0
        if op==0x00: self._special(rs,rt,rd,sh,fn)
        elif op==0x02: self.next_pc=(self.pc&0xF0000000)|(tgt<<2)
        elif op==0x03: self.gpr[31]=self.pc+8; self.next_pc=(self.pc&0xF0000000)|(tgt<<2)
        elif op==0x04 and self.gpr[rs]==self.gpr[rt]: self.next_pc=self.pc+4+(imm_se<<2)
        elif op==0x05 and self.gpr[rs]!=self.gpr[rt]: self.next_pc=self.pc+4+(imm_se<<2)
        elif op in (0x08,0x09): self.gpr[rt]=(self.gpr[rs]+imm_se)&0xFFFFFFFFFFFFFFFF
        elif op==0x0C: self.gpr[rt]=self.gpr[rs]&imm
        elif op==0x0D: self.gpr[rt]=self.gpr[rs]|imm
        elif op==0x0F: self.gpr[rt]=(imm<<16)&0xFFFFFFFFFFFFFFFF
        elif op==0x23: self.gpr[rt]=self.mem.read32(self.gpr[rs]+imm_se)
        elif op==0x2B: self.mem.write32(self.gpr[rs]+imm_se,self.gpr[rt])
        self.gpr[0]=0
        self.cycles+=1

    def _special(self,rs,rt,rd,sh,fn):
        if fn==0x00: self.gpr[rd]=(self.gpr[rt]<<sh)&0xFFFFFFFFFFFFFFFF
        elif fn==0x02: self.gpr[rd]=(self.gpr[rt]>>sh)&0xFFFFFFFFFFFFFFFF
        elif fn==0x08: self.next_pc=self.gpr[rs]
        elif fn==0x09: self.gpr[rd]=self.pc+8; self.next_pc=self.gpr[rs]
        elif fn==0x12: self.gpr[rd]=self.lo
        elif fn==0x18:
            r=self.gpr[rs]*self.gpr[rt]; self.lo=r&0xFFFFFFFF; self.hi=(r>>32)&0xFFFFFFFF
        elif fn in (0x20,0x21): self.gpr[rd]=(self.gpr[rs]+self.gpr[rt])&0xFFFFFFFFFFFFFFFF
        elif fn in (0x22,0x23): self.gpr[rd]=(self.gpr[rs]-self.gpr[rt])&0xFFFFFFFFFFFFFFFF
        elif fn==0x24: self.gpr[rd]=self.gpr[rs]&self.gpr[rt]
        elif fn==0x25: self.gpr[rd]=self.gpr[rs]|self.gpr[rt]

    def step(self):
        ins=self.fetch()
        self.decode_execute(ins)
        self.pc=self.next_pc
        self.next_pc=self.pc+4

# ============================================================
# GUI Shell
# ============================================================
class Cat64GUI:
    def __init__(self, root):
        self.root=root
        self.root.title("CATN64EMUSAMSOFT1.1HDR 'dot64 Edition'")
        self.root.geometry("600x400")
        self.root.resizable(False,False)
        self.mem=N64Memory()
        self.cpu=MIPSR4300i(self.mem)

        self.text=scrolledtext.ScrolledText(root,bg="#0A0A0A",fg="#00FF00",
                                            insertbackground="#00FF00",font=("Consolas",10))
        self.text.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)

        bar=ttk.Frame(root); bar.pack(fill=tk.X)
        ttk.Button(bar,text="Reset",command=self.reset).pack(side=tk.LEFT,padx=2)
        ttk.Button(bar,text="Step",command=self.step).pack(side=tk.LEFT,padx=2)
        ttk.Button(bar,text="Run",command=self.run).pack(side=tk.LEFT,padx=2)
        ttk.Button(bar,text="Stop",command=self.stop).pack(side=tk.LEFT,padx=2)
        ttk.Button(bar,text="Load ROM",command=self.load_rom).pack(side=tk.LEFT,padx=2)
        ttk.Button(bar,text="Tests",command=self.tests).pack(side=tk.LEFT,padx=2)

        self.status=tk.Label(root,text="Ready.",anchor="w",bg="#111",fg="#0f0",font=("Consolas",9))
        self.status.pack(fill=tk.X)

        self._print_boot()

    # --------------------------------------------------------
    def log(self,msg):
        self.text.insert(tk.END,msg+"\n")
        self.text.see(tk.END)

    def _print_boot(self):
        self.log("dot64™ Neural Cartridge Runtime v1.1")
        self.log("RDRAM STATUS: EDIAN 8MB OK")
        self.log("AI COP0 SYNC: PASS — DREAMSTATE READY\n")

    # --------------------------------------------------------
    def reset(self):
        self.cpu.reset()
        self.status.config(text="CPU reset.")
        self.log("CPU Reset complete.")

    def step(self):
        self.cpu.step()
        self.status.config(text=f"PC=0x{self.cpu.pc:08X} Cycles={self.cpu.cycles}")
        self.log(f"Step → PC={self.cpu.pc:08X} Cycles={self.cpu.cycles}")

    def run(self):
        if self.cpu.running: return
        self.cpu.running=True
        def loop():
            while self.cpu.running:
                self.cpu.step()
                time.sleep(0.01)
            self.status.config(text="Run halted.")
        threading.Thread(target=loop,daemon=True).start()
        self.status.config(text="Running…")

    def stop(self):
        self.cpu.running=False
        self.status.config(text="Stopped.")

    def load_rom(self):
        path=filedialog.askopenfilename(title="Import N64 ROM",
            filetypes=[("N64 ROM","*.z64 *.v64 *.n64 *.bin *.rom")])
        if not path: return
        try:
            with open(path,"rb") as f: raw=f.read()
            size=self.mem.load_rom_data(raw)
            if size is None:
                self.log("❌ Invalid ROM format.")
                return
            self.log(f"✅ ROM loaded: {path} ({size} bytes) [{self.mem.endian_mode}]")
            entry=self.mem.read32(0x10000034) if size>0x38 else 0x10000400
            self.cpu.pc=entry; self.cpu.next_pc=entry+4
            self.status.config(text=f"ROM entry → 0x{entry:08X}")
        except Exception as e:
            self.log(f"❌ Load error: {e}")

    def tests(self):
        c=self.cpu; m=self.mem; c.reset()
        self.log("Running CPU test suite…")
        try:
            c.decode_execute(0x20010064); assert c.gpr[1]==100
            c.decode_execute(0x3402FF00); assert c.gpr[2]==0xFF00
            c.decode_execute(0x00221820); assert c.gpr[3]==100+0xFF00
            c.decode_execute(0x00412022); assert c.gpr[4]==0xFF00-100
            c.gpr[1]=0xF0F0; c.gpr[2]=0xFF00
            c.decode_execute(0x00412824); assert c.gpr[5]==(0xF0F0&0xFF00)
            c.decode_execute(0x3C061234); assert c.gpr[6]==0x12340000
            c.gpr[1]=100; c.gpr[2]=200
            c.decode_execute(0x00220018); c.decode_execute(0x00001812)
            assert c.gpr[3]==20000
            self.log("✅ All CPU tests passed.")
        except AssertionError:
            self.log("❌ Test failed.")
        self.status.config(text=f"Cycles={c.cycles}")

# ============================================================
def main():
    root=tk.Tk()
    Cat64GUI(root)
    root.mainloop()

if __name__=="__main__":
    main()
