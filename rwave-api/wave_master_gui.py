import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from rwave_api import RemoteWave

class RemoteWaveMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("Remote Wave Master for neuroConn TDCS")
        self.mywave = RemoteWave()

        # Scan devices
        self.devices = self.mywave.scan("")
        self.device_entries = []
        for dev in self.devices:
            if isinstance(dev, dict):
                display = dev.get('product_string', str(dev))
            else:
                display = str(dev)
            self.device_entries.append(display)

        self.attached = False

        # Flags to avoid setter calls during initialization
        self._init_in_progress = True

        # Variables (use StringVar so we can validate free text entries)
        self.device_var = tk.StringVar()
        self.dc_curr_var = tk.StringVar(value="0.0")
        self.theta_freq_var = tk.StringVar(value="6.0")
        self.theta_ampl_var = tk.StringVar(value="1.0")
        self.gamma_freq_var = tk.StringVar(value="80.0")
        self.gamma_ampl_var = tk.StringVar(value="0.5")
        self.gamma_mod_depth_var = tk.StringVar(value="100.0")        
        self.gamma_start_var = tk.StringVar(value="0.0")
        self.gamma_stop_var = tk.StringVar(value="180.0")
        self.comp_var = tk.IntVar(value=0)  # 0 additive, 1 modulation
        self.invert_var = tk.IntVar(value=0)  # 0 normal, 1 inverted

        self.status_var = tk.StringVar(value="Device status: -")

        self._build_widgets()

        # traces for checkboxes
        self.comp_var.trace_add("write", lambda *args: self._on_comp_change())
        self.invert_var.trace_add("write", lambda *args: self._on_invert_change())

        self._init_in_progress = False

    def _build_widgets(self):
        frm = ttk.Frame(self.root, padding="10")
        frm.grid(row=0, column=0, sticky='NSEW')
        self.root.columnconfigure(0, weight=1)

        # Device selection
        ttk.Label(frm, text="Select Device:").grid(row=0, column=0, sticky='W')
        self.device_cb = ttk.Combobox(frm, textvariable=self.device_var,
                                      values=self.device_entries, state="readonly",
                                      width=50)
        self.device_cb.grid(row=0, column=1, sticky='W', columnspan=3)
        ttk.Button(frm, text="Connect", command=self.connect).grid(row=0, column=4, padx=5)
        ttk.Button(frm, text="Disconnect", command=self.disconnect).grid(row=0, column=5, padx=5)

        # --- Float input fields (labels + entries) ---
        row = 1
        def make_row(label_text, var, vmin, vmax, setter_callable, label):
            nonlocal row
            ttk.Label(frm, text=label_text).grid(row=row, column=0, sticky='W', pady=4)
            ent = ttk.Entry(frm, textvariable=var, width=12)
            ent.grid(row=row, column=1, sticky='W')

            # Bind Enter and FocusOut
            def apply_change(event=None):
                self._on_float_change(var, vmin, vmax, setter_callable, label)

            ent.bind("<Return>", apply_change)
            ent.bind("<FocusOut>", apply_change)

            row += 1
            return ent
        
        make_row("DC output current (mA) [-4.0..+4.0]:", 
         self.dc_curr_var, -4.0, 4.0, self.mywave.write_dc_current, "DC output current")
        make_row("Theta wave frequency (Hz) [1.0..20.0]:", 
         self.theta_freq_var, 1.0, 20.0, self.mywave.write_freq_theta, "Theta wave frequency")
        make_row("Theta wave amplitude (mA) [0.0..4.0]:", 
         self.theta_ampl_var, 0.0, 4.0, self.mywave.write_ampl_theta, "Theta wave amplitude")
        make_row("Gamma wave frequency (Hz) [40.0..200.0]:", 
         self.gamma_freq_var, 40.0, 200.0, self.mywave.write_freq_gamma1, "Gamma wave frequency")
        make_row("Gamma wave amplitude (mA) [0.0...4.0]:", 
         self.gamma_ampl_var, 0.0, 4.0, self.mywave.write_ampl_gamma1, "Gamma wave amplitude")
        make_row("Gamma wave modulation depth (%) [0.0...100.0]:", 
         self.gamma_mod_depth_var, 0.0, 100.0, self.mywave.write_mdepth_gamma1, "Gamma wave modulation depth")
        make_row("Gamma wave starting angle (°) [0.0..360.0]:", 
         self.gamma_start_var, 0.0, 360.0, self.mywave.write_start_phase_gamma1, "Gamma start")
        make_row("Gamma wave stopping angle (°) [0.0..360.0]:", 
         self.gamma_stop_var, 0.0, 360.0, self.mywave.write_stop_phase_gamma1, "Gamma stop")


        # Checkboxes
        ttk.Checkbutton(frm, text="Wave composition: additive(0) / modulation(1)",
                        variable=self.comp_var).grid(row=row, column=0, columnspan=3, sticky='W', pady=6)
        row += 1
        ttk.Checkbutton(frm, text="Output invert",
                        variable=self.invert_var).grid(row=row, column=0, columnspan=3, sticky='W', pady=6)
        row += 1

        # Buttons Start / Stop
        ttk.Button(frm, text="Wave update/start", command=self._on_start).grid(row=row, column=0, pady=8)
        ttk.Button(frm, text="Wave stop", command=self._on_stop).grid(row=row, column=1, pady=8)
        row += 1

        # Status Label
        ttk.Label(frm, textvariable=self.status_var).grid(row=row, column=0, columnspan=4, sticky='W', pady=6)

    # -------------------------
    # Device connect/disconnect
    # -------------------------
    def connect(self):
        if not self.attached and self.device_var.get():
            try:
                ok = self.mywave.attach(self.device_var.get())
                if ok:
                    self.attached = True
                    self.device_cb.state(['disabled'])
                    self.status_var.set("Device status: attached")
                    # After attach, re-send current UI values to device so GUI and device are synced
                    self._push_all_settings()
                else:
                    messagebox.showerror("Error", "Connect failed (attach returned False).")
            except Exception as e:
                messagebox.showerror("Error", f"Connect failed: {e}")

    def disconnect(self):
        if self.attached:
            try:
                self.mywave.close()
            except Exception as e:
                # close() returns False if no device, but try/except for IO issues
                print("close() exception:", e)
            self.attached = False
            self.device_cb.state(['!disabled'])
            self.status_var.set("Device status: detached")

    # -------------------------
    # Live-updating handlers
    # -------------------------
    def _on_float_change(self, var: tk.StringVar, vmin: float, vmax: float, setter_callable, label):
        """
        Called every time the associated StringVar changes. Parse float, clamp to bounds,
        call the setter_callable(current_float) if device attached. If parsing fails, ignore.
        """
        if self._init_in_progress:
            return
        txt = var.get().strip()
        if txt == "":
            return
        try:
            val = float(txt)
        except ValueError:
            # invalid input - ignore (user typing) -- do not call setter
            return

        # clamp to allowed range
        if val < vmin:
            val = vmin
            var.set(f"{val:.3f}")
        elif val > vmax:
            val = vmax
            var.set(f"{val:.3f}")

        # attempt to call setter immediately (live updating)
        if not self.attached:
            # not attached -> update status but don't raise
            self.status_var.set(f"Device status: not attached (change: {label}={val})")
            return

        try:
            result = setter_callable(val)
            # Many rwave setters return None on success, or False when requires_device fails.
            # We only update status text if no exception.
            self.status_var.set(f"Device status: set {label} = {val}")
        except Exception as e:
            # Show the error but don't crash
            self.status_var.set(f"Device status: failed to set {label}")
            messagebox.showerror("Error", f"Failed to set {label}: {e}")

    def _on_comp_change(self):
        if self._init_in_progress:
            return
        val = int(self.comp_var.get())  # 0 additive, 1 modulation
        if not self.attached:
            self.status_var.set(f"Device status: not attached (composition={val})")
            return
        try:
            self.mywave.set_composition(val)
            self.status_var.set(f"Device status: set composition = {'modulation' if val else 'additive'}")
        except Exception as e:
            self.status_var.set("Device status: failed to set composition")
            messagebox.showerror("Error", f"Failed to set composition: {e}")

    def _on_invert_change(self):
        if self._init_in_progress:
            return
        val = int(self.invert_var.get())  # 0 normal, 1 inverted
        if not self.attached:
            self.status_var.set(f"Device status: not attached (invert={val})")
            return
        try:
            self.mywave.set_output_mode(val)
            self.status_var.set(f"Device status: set output invert = {val}")
        except Exception as e:
            self.status_var.set("Device status: failed to set invert")
            messagebox.showerror("Error", f"Failed to set output invert: {e}")

    # -------------------------
    # Start / Stop wave handling
    # -------------------------
    def _on_start(self):
        if not self.attached:
            messagebox.showwarning("Not attached", "No device attached.")
            return

        def worker():
            try:
                # send start command
                self.mywave.start()
            except Exception as e:
                # if start raised (e.g., not attached), show error
                self.root.after(0, lambda: messagebox.showerror("Start failed", f"start() failed: {e}"))
                self.root.after(0, lambda: self.status_var.set("Device status: failed to start"))
                return

            # wait for ack (timeout ms) - example: wait up to 2000 ms
            try:
                resp, elapsed = self.mywave.wait_for_ack(2000)
                # wait_for_ack returns (-1, elapsed) on timeout OR (last_event, elapsed)
                if resp == -1:
                    self.root.after(0, lambda: self.status_var.set("Device status: failed (no ack)"))
                else:
                    self.root.after(0, lambda: self.status_var.set("Device status: OK (ack received)"))
            except Exception as e:
                # wait_for_ack might return tuple differently or raise
                # handle both styles: if it returned something else above, we covered that.
                self.root.after(0, lambda: self.status_var.set("Device status: failed (wait error)"))
                self.root.after(0, lambda: messagebox.showerror("Ack error", f"wait_for_ack failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_stop(self):
        if not self.attached:
            messagebox.showwarning("Not attached", "No device attached.")
            return
        try:
            self.mywave.stop()
            self.status_var.set("Device status: stopped (stop command sent)")
        except Exception as e:
            messagebox.showerror("Stop failed", f"stop() failed: {e}")
            self.status_var.set("Device status: failed to stop")

    # -------------------------
    # Helper to push UI to device on connect
    # -------------------------
    def _push_all_settings(self):
        """Push all current control values to device after connect so UI + device are synced."""
        # Call setters but ignore exceptions (they'll be shown via messageboxes inside setters)
        try:
            # DC
            try:
                self.mywave.write_dc_current(float(self.dc_curr_var.get()))
            except Exception:
                pass
            # theta wave
            try:
                self.mywave.write_freq_theta(float(self.theta_freq_var.get()))
            except Exception:
                pass
            try:
                self.mywave.write_ampl_theta(float(self.theta_ampl_var.get()))
            except Exception:
                pass
            # gamma wave
            try:
                self.mywave.write_freq_gamma1(float(self.gamma_freq_var.get()))
            except Exception:
                pass
            try:
                self.mywave.write_ampl_gamma1(float(self.gamma_ampl_var.get()))
            except Exception:
                pass
            try:
                self.mywave.write_mdepth_gamma1(float(self.gamma_mdepth_var.get()))
            except Exception:
                pass              
            # start/stop phases
            try:
                self.mywave.write_start_phase_gamma1(float(self.gamma_start_var.get()))
            except Exception:
                pass
            try:
                self.mywave.write_stop_phase_gamma1(float(self.gamma_stop_var.get()))
            except Exception:
                pass
            # composition & invert
            try:
                self.mywave.set_composition(int(self.comp_var.get()))
            except Exception:
                pass
            try:
                self.mywave.set_output_mode(int(self.invert_var.get()))
            except Exception:
                pass
            self.status_var.set("Device status: synced")
        except Exception as e:
            self.status_var.set(f"Device status: sync failed ({e})")

if __name__ == "__main__":
    root = tk.Tk()
    app = RemoteWaveMaster(root)
    root.mainloop()
