"""
Kivy GUI to stream Polar H10 data (ECG, HR, RR-interval, 3-axis ACC)
into ONE Lab Streaming Layer outlet with six channels.

Channel map
-----------
0  ECG   [µV]   130 Hz
1  HR    [bpm]  event-driven
2  RRI   [ms]   event-driven
3  AccX  [mG]   52 Hz
4  AccY  [mG]   52 Hz
5  AccZ  [mG]   52 Hz

Author: Luis Jose Alarcon Aneiva (mods), Md Mijanur Rahman (AEON Dashboard Compatibility Fix) – base code by m.m.span@rug.nl
Repo  : https://github.com/markspan/PolarBand2lsl/
"""

# ─────────────────────────────  CONFIG  ──────────────────────────────
logging = False                 # set True to suppress Kivy/bleak console spam

# ───────────────────────────  IMPORTS  ───────────────────────────────
if logging:
    import os
    os.environ["KIVY_NO_CONSOLELOG"] = "1"
    os.environ["BLEAK_LOGGING"] = "0"

import sys, asyncio, threading, struct, logging as pylog
import time #Modification Luis Alarcon
from pylsl               import StreamInfo, StreamOutlet
from kivy.app            import App
from kivy.core.window    import Window
from kivy.uix.boxlayout  import BoxLayout
from kivy.uix.button     import Button
from kivy.uix.label      import Label
from kivy.uix.scrollview import ScrollView
from kivy.animation      import Animation
from kivy.clock          import mainthread

import bleak

# ─────────────────────  BLE constants (Polar)  ───────────────────────
PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"
PMD_DATA    = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"
HRM_CHAR    = "00002A37-0000-1000-8000-00805f9b34fb"   # Heart-Rate Service

# Start-stream commands (Polar proprietary)
ECG_WRITE = bytearray([0x02,0x00,0x00,0x01,0x82,0x00,0x01,0x01,0x0E,0x00])              # 130 Hz
ACC_WRITE = bytearray([0x02,0x02,0x00,0x01,0xC8,0x00,0x01,0x01,0x10,0x00,
                       0x02,0x01,0x08,0x00])                                             # 52 Hz ±8 g

ECG_FS = 130      # Hz
ACC_FS = 52       # Hz
TOTAL_CH = 6
NaN = float('nan')

bleak_logger = pylog.getLogger("bleak")
bleak_logger.setLevel(10000)     # silence Bleak's debug output

# ───────────────────────────  GUI class  ─────────────────────────────
class BluetoothApp(App):
    busychars = ["o...", ".o..", "..o.", "...o"]

    # ------------------  Build Kivy interface  ------------------
    def build(self):
        if logging and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

        Window.size = (400, 200)
        self.stop_event = asyncio.Event()
        self.busy_label_animation = None

        self.devices_layout = BoxLayout(orientation='vertical')
        self.devices_scroll = ScrollView()
        self.devices_scroll.add_widget(self.devices_layout)

        self.scan_button   = Button(text="Scan for Devices", size_hint=(1, 0.1))
        self.cancel_button = Button(text="Cancel",           size_hint=(1, 0.1))
        self.scan_button.bind  (on_press=self.scan_for_devices)
        self.cancel_button.bind(on_press=self.stop_scanning)

        root = BoxLayout(orientation='vertical')
        for w in (self.scan_button, self.devices_scroll, self.cancel_button):
            root.add_widget(w)
        return root

    # ------------------  BLE discovery  ------------------
    def scan_for_devices(self, _):
        self.scan_button.disabled = True
        self.devices_layout.clear_widgets()
        threading.Thread(target=self.scan).start()

    def scan(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_scan())
        self.scan_button.disabled = False

    async def async_scan(self):
        try:
            devices = await bleak.BleakScanner.discover(return_adv=True, scanning_mode='active')
            for dev, _adv in devices.values():
                if "Polar H10" in str(dev):
                    self.add_device_button(dev)
            self.add_busy_label()
        except Exception as e:
            print(f"[Scan] {e}")

    # ------------------  UI helpers  ------------------
    @mainthread
    def add_device_button(self, dev):
        btn = Button(text=dev.name, size_hint=(1, 0.2))
        btn.bind(on_press=lambda _, addr=dev.address, nm=dev.name: self.connect_to_device(addr, nm, btn))
        self.devices_layout.add_widget(btn)

    @mainthread
    def add_busy_label(self):
        self.busy_label = Label(text="")
        self.devices_layout.add_widget(self.busy_label)
        self.busyvalue = 0

    @mainthread
    def update_busy(self):
        if self.busy_label_animation:
            self.busy_label_animation.cancel(self.busy_label)
        self.busyvalue = (self.busyvalue + 1) % 4
        self.busy_label.text = self.busychars[self.busyvalue]
        self.busy_label_animation = (Animation(color=(0, 0, 1, 1), duration=0.25) +
                                     Animation(color=(1, 1, 1, 1), duration=0.25))
        self.busy_label_animation.start(self.busy_label)

    # ------------------  Connection logic  ------------------
    def connect_to_device(self, addr, name, btn):
        # 1 LSL outlet / 6 channels - COMPATIBILITY FIX: Use consistent sampling rate
        nominal_rate = 130  # Use ECG rate as nominal rate for compatibility
        info = StreamInfo(name + "_POLAR", "Physio", TOTAL_CH, nominal_rate, "float32", addr)
        info.desc().append_child_value("manufacturer", "Polar")
        chs = info.desc().append_child("channels")

        # COMPATIBILITY FIX: Use 'label' instead of 'name' since dashboard looks for labels
        for nm, unit in [("ECG", "microvolts"), ("HR", "bpm"), ("RRI", "ms"),
                         ("AccX", "mG"), ("AccY", "mG"), ("AccZ", "mG")]:
            c = chs.append_child("channel")
            c.append_child_value("label", nm)  # Use 'label' for dashboard compatibility
            c.append_child_value("name", nm)   # Keep name for backward compatibility
            c.append_child_value("unit", unit)
            c.append_child_value("type", nm)

        self.outlet   = StreamOutlet(info, 74, 360)
        self.last_hr  = 0.0  # COMPATIBILITY FIX: Use 0 instead of NaN
        self.last_rri = 0.0  # COMPATIBILITY FIX: Use 0 instead of NaN
        self.last_acc = [0.0, 0.0, 0.0]  # COMPATIBILITY FIX: Use 0 instead of NaN

        # Initialize with reasonable default values
        self.ecg_buffer = []
        self.acc_buffer = []
        self.hr_buffer = []
        self.rri_buffer = []

        self.busy_label.text = "Wait… (≈1 min)"
        btn.disabled = True
        threading.Thread(target=self.connect, args=(addr,)).start()

    def connect(self, addr):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.async_connect(addr))

    async def async_connect(self, addr):
        try:
            async with bleak.BleakClient(addr) as client:
                # Start ECG & ACC in Polar proprietary PMD service
                await client.read_gatt_char(PMD_CONTROL)
                await client.write_gatt_char(PMD_CONTROL, ECG_WRITE)
                await client.write_gatt_char(PMD_CONTROL, ACC_WRITE)
                await client.start_notify(PMD_DATA, self.pmd_data_conv)

                # Subscribe to standard heart-rate characteristic
                await client.start_notify(HRM_CHAR, self.hrm_conv)

                await asyncio.wait_for(self.stop_event.wait(), timeout=None)
                await client.stop_notify(PMD_DATA)
                await client.stop_notify(HRM_CHAR)

        except Exception as e:
            print(f"[Connect] {e}")

    # ----------------  Data parsers  ----------------
    def pmd_data_conv(self, _sender, data: bytearray):
        hdr = data[0]

        # ECG frame (130 Hz) – each sample 3 bytes little-end signed
        if hdr == 0x00:
            payload = data[10:]
            for off in range(0, len(payload), 3):
                ecg = int.from_bytes(payload[off:off+3], "little", signed=True)
                self.push(ecg)

        # ACC frame (52 Hz) – 13 × (x,y,z) int16
        elif hdr == 0x01:
            payload = data[10:]
            for off in range(0, len(payload), 6):
                self.last_acc = list(struct.unpack_from("<hhh", payload, off))
                # COMPATIBILITY FIX: Push with last ECG value instead of NaN
                if hasattr(self, 'last_ecg'):
                    self.push(self.last_ecg)
                else:
                    self.push(0.0)  # Use 0 if no ECG data yet

        self.update_busy()

    def hrm_conv(self, _sender, data: bytearray):
        flags = data[0]; idx = 1
        # Heart-rate (8- or 16-bit)
        self.last_hr = int.from_bytes(data[idx:idx+2], "little") if flags & 0x01 else data[idx]
        idx += 2 if flags & 0x01 else 1
        # COMPATIBILITY FIX: Push with last ECG value instead of NaN
        if hasattr(self, 'last_ecg'):
            self.push(self.last_ecg)
        else:
            self.push(0.0)  # Use 0 if no ECG data yet

        # R-R intervals (units: 1/1024 s)
        if flags & 0x10:
            while idx + 1 < len(data):
                self.last_rri = int.from_bytes(data[idx:idx+2], "little") / 1024.0 * 1000  # Convert to ms
                idx += 2
                # COMPATIBILITY FIX: Push with last ECG value instead of NaN
                if hasattr(self, 'last_ecg'):
                    self.push(self.last_ecg)
                else:
                    self.push(0.0)  # Use 0 if no ECG data yet

    # ----------------  Vector assembler  ----------------
    def push(self, ecg=0.0):  # COMPATIBILITY FIX: Default to 0 instead of NaN
        # Store last ECG value for use in other data types
        if not math.isnan(ecg) and ecg != 0.0:
            self.last_ecg = ecg

        # COMPATIBILITY FIX: Replace NaN with 0 for all values
        hr_val = 0.0 if math.isnan(self.last_hr) else self.last_hr
        rri_val = 0.0 if math.isnan(self.last_rri) else self.last_rri
        acc_vals = [0.0 if math.isnan(x) else x for x in self.last_acc]

        vec = [ecg, hr_val, rri_val, *acc_vals]
        self.outlet.push_sample(vec)

    # ----------------  Shutdown  ----------------
    def stop_scanning(self, _):
        self.stop_event.set()    # Modification Luis Alarcon
        asyncio.sleep(5)
        self.loop.stop()
        App.get_running_app().stop()

# ────────────────────────────  MAIN  ────────────────────────────────
if __name__ == "__main__":
    import math  # Add math import for isnan check
    BluetoothApp().run()