# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import threading
import requests
from datetime import datetime
import pygame
import socket
import ctypes

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter.messagebox as messagebox
from tkinter import PhotoImage

import sounddevice as sd  # لإظهار أجهزة الصوت المتاحة

CONFIG_FILE = "config.json"
API_URL = "http://api.aladhan.com/v1/timings"
OFFLINE_UPDATE_INTERVAL = 3600  # 1 ساعة للتحديث عند وجود إنترنت
CHECK_INTERVAL = 5              # فحص الصلاة كل 5 ثواني
ADHAN_DURATION = 15             # مدة الأذان بالثواني

CITIES = {
    "الرياض": (24.7136, 46.6753),
    "دمياط": (31.4165, 31.8133),
    "القاهرة": (30.0444, 31.2357),
    "دبي": (25.276987, 55.296249),
    "الدوحة": (25.2854, 51.5310),
    "الكويت": (29.3759, 47.9774),
    "مسقط": (23.5859, 58.4059),
    "بغداد": (33.3152, 44.3661),
    "بيروت": (33.8938, 35.5018),
    "الخرطوم": (15.5007, 32.5599),
    "مكة": (21.3891, 39.8579),
    "المدينة المنورة": (24.5247, 39.5692),
    "جدة": (21.2854, 39.2376),
    "الجزائر": (36.7538, 3.0422),
    "تونس": (36.8065, 10.1815),
    "الدار البيضاء": (33.5731, -7.5898),
    "الخبر": (26.2172, 50.1971),
    "الأحساء": (25.3603, 49.5846),
    "إسطنبول": (41.0082, 28.9784),
    "دوزجا": (40.8438, 31.1565),    
}

TIMEZONE_MAPPING = {
    "الرياض": "Asia/Riyadh",
    "دمياط": "Africa/Cairo",
    "القاهرة": "Africa/Cairo",
    "دبي": "Asia/Dubai",
    "الدوحة": "Asia/Qatar",
    "الكويت": "Asia/Kuwait",
    "مسقط": "Asia/Muscat",
    "بغداد": "Asia/Baghdad",
    "بيروت": "Asia/Beirut",
    "الخرطوم": "Africa/Khartoum",
    "مكة": "Asia/Riyadh",
    "المدينة المنورة": "Asia/Riyadh",
    "جدة": "Asia/Riyadh",
    "الجزائر": "Africa/Algiers",
    "تونس": "Africa/Tunis",
    "الدار البيضاء": "Africa/Casablanca",
    "الخبر": "Asia/Riyadh",
    "الأحساء": "Asia/Riyadh",
    "إسطنبول": "Europe/Istanbul",
    "دوزجا": "Europe/Istanbul",
}

METHOD_MAPPING = {
    "الرياض": 4,
    "دمياط": 5,
    "القاهرة": 5,
    "دبي": 4,
    "الدوحة": 4,
    "الكويت": 4,
    "مسقط": 4,
    "بغداد": 5,
    "بيروت": 5,
    "الخرطوم": 5,
    "مكة": 4,
    "المدينة المنورة": 4,
    "جدة": 4,
    "الجزائر": 2,
    "تونس": 2,
    "الدار البيضاء": 2,
    "الخبر": 4,
    "الأحساء": 4,
    "إسطنبول": 13,
    "دوزجا": 13,
}

# ترتيب الصلاة حسب طلبك مع اسم عرض عربي
VALID_PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
PRAYER_NAMES_AR = {
    "Fajr": "الفجر",
    "Dhuhr": "الظهر",
    "Asr": "العصر",
    "Maghrib": "المغرب",
    "Isha": "العشاء"
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def add_to_startup():
    try:
        import winreg
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, "PrayerAppBySMRH", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"خطأ في إضافة بدء التشغيل: {e}")

def check_already_running():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 65432))
        return sock
    except socket.error:
        return None

class AdhanPlayer:
    def __init__(self, adhan_file="adhan1.mp3", volume=0.8, output_device=None):
        pygame.mixer.quit()
        pygame.mixer.init()
        self.volume = volume
        self.sound_file = resource_path(adhan_file)
        self.sound = pygame.mixer.Sound(self.sound_file)
        self.sound.set_volume(self.volume)
        self.is_playing = False
        self.output_device = output_device
        # ملاحظة: pygame لا يدعم اختيار جهاز إخراج صوت بشكل مباشر، هنا نخزن الاسم فقط

    def play(self):
        if self.is_playing:
            self.stop()
        self.sound.play(-1)
        self.is_playing = True

    def stop(self):
        if self.is_playing:
            pygame.mixer.stop()
            self.is_playing = False

    def set_volume(self, v):
        self.volume = max(0, min(1, v))
        self.sound.set_volume(self.volume)

    def change_sound(self, new_file):
        was_playing = self.is_playing
        self.stop()
        self.sound_file = resource_path(new_file)
        self.sound = pygame.mixer.Sound(self.sound_file)
        self.sound.set_volume(self.volume)
        if was_playing:
            self.play()

class PrayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("مواقيت الصلاة - By SMRH")
        self.root.geometry("480x680")
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        if os.path.exists(resource_path("icon.ico")):
            self.root.iconbitmap(resource_path("icon.ico"))

        self.style = tb.Style("flatly")
        self.style.configure('TLabel', font=('Tahoma', 12))
        self.style.configure('TButton', font=('Tahoma', 11))
        self.style.configure('TCombobox', font=('Tahoma', 12))
        self.style.configure('TScale', troughcolor='#b5d0e0')

        self.city_names = list(CITIES.keys())
        self.adhan_files = ["adhan1.mp3", "adhan2.mp3"]

        self.audio_devices = self.get_output_devices()

        self.cfg = self.load_config()
        self.player = AdhanPlayer(adhan_file=self.cfg['adhan'], volume=self.cfg['volume'], output_device=self.cfg.get('output_device'))
        self.timings = self.cfg.get("timings", {})
        self.triggered_prayers = set()
        self.updater_thread = None
        self.checker_thread = None
        self.tray_icon = None
        self.is_running = True

        self.current_day = datetime.now().day

        self.create_widgets()

        # ضبط القيم في الواجهة من الإعدادات المحفوظة
        self.city_combo.set(self.cfg.get("city", self.city_names[0]))
        self.adhan_combo.set(self.cfg.get("adhan", self.adhan_files[0]))

        output_dev = self.cfg.get("output_device")
        if output_dev in self.audio_devices:
            self.output_device_combo.set(output_dev)
        else:
            if self.audio_devices:
                self.output_device_combo.set(self.audio_devices[0])
                self.cfg['output_device'] = self.audio_devices[0]
                self.save_config()
            else:
                self.output_device_combo.set("لا يوجد أجهزة إخراج")

        self.vol_scale.set(self.cfg.get("volume", 0.8) * 100)

        # اختر صيغة الوقت: 12 أو 24
        self.time_format_24h = self.cfg.get("time_format_24h", True)
        self.time_format_var.set("24 ساعة" if self.time_format_24h else "12 ساعة")

        self.display_timings()

        self.start_updater()
        self.start_checker()

        add_to_startup()

    def get_output_devices(self):
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev['max_output_channels'] > 0:
                devices.append(f"{idx} - {dev['name']}")
        return devices if devices else ["لا يوجد أجهزة إخراج"]

    def create_widgets(self):
        frame = tb.Frame(self.root, padding=10)
        frame.pack(fill='both', expand=True)

        tb.Label(frame, text="اختر مدينتك:", font=("Tahoma", 14, "bold")).pack(pady=8, anchor="w")
        self.city_var = tb.StringVar()
        self.city_combo = tb.Combobox(frame, textvariable=self.city_var, values=self.city_names, state="readonly", bootstyle="info")
        self.city_combo.pack(fill='x', pady=5)
        self.city_combo.bind("<<ComboboxSelected>>", self.on_city_changed)

        tb.Label(frame, text="اختر صوت الأذان:", font=("Tahoma", 14, "bold")).pack(pady=8, anchor="w")
        self.adhan_var = tb.StringVar()
        self.adhan_combo = tb.Combobox(frame, textvariable=self.adhan_var, values=self.adhan_files, state="readonly", bootstyle="info")
        self.adhan_combo.pack(fill='x', pady=5)
        self.adhan_combo.bind("<<ComboboxSelected>>", self.on_adhan_changed)

        tb.Label(frame, text="اختر جهاز إخراج الصوت:", font=("Tahoma", 14, "bold")).pack(pady=8, anchor="w")
        self.output_device_var = tb.StringVar()
        self.output_device_combo = tb.Combobox(frame, textvariable=self.output_device_var, values=self.audio_devices, state="readonly", bootstyle="info")
        self.output_device_combo.pack(fill='x', pady=5)
        self.output_device_combo.bind("<<ComboboxSelected>>", self.on_output_device_changed)

        tb.Label(frame, text="اختر صيغة الوقت:", font=("Tahoma", 14, "bold")).pack(pady=8, anchor="w")
        self.time_format_var = tb.StringVar()
        self.time_format_combo = tb.Combobox(frame, textvariable=self.time_format_var, values=["24 ساعة", "12 ساعة"], state="readonly", bootstyle="info")
        self.time_format_combo.pack(fill='x', pady=5)
        self.time_format_combo.bind("<<ComboboxSelected>>", self.on_time_format_changed)

        btn_icon_frame = tb.Frame(frame)
        btn_icon_frame.pack(pady=10, fill='x')

        script_dir = os.path.dirname(os.path.abspath(__file__))
        play_icon_path = os.path.join(script_dir, "play_icon.png")
        stop_icon_path = os.path.join(script_dir, "stop_icon.png")

        try:
            self.play_img = PhotoImage(file=play_icon_path)
            self.stop_img = PhotoImage(file=stop_icon_path)
        except Exception:
            self.play_img = None
            self.stop_img = None

        if self.play_img:
            self.play_btn = tb.Button(btn_icon_frame, image=self.play_img, command=self.on_play_clicked, bootstyle="success", width=40)
        else:
            self.play_btn = tb.Button(btn_icon_frame, text="▶", command=self.on_play_clicked, bootstyle="success", width=6)
        self.play_btn.pack(side='left', expand=True, padx=10)

        if self.stop_img:
            self.stop_btn = tb.Button(btn_icon_frame, image=self.stop_img, command=self.on_stop_clicked, bootstyle="danger", width=40)
        else:
            self.stop_btn = tb.Button(btn_icon_frame, text="■", command=self.on_stop_clicked, bootstyle="danger", width=6)
        self.stop_btn.pack(side='left', expand=True, padx=10)

        tb.Button(frame, text="تحديث المواقيت الآن", command=self.update_timings, bootstyle="success").pack(pady=8, fill='x')

        tb.Label(frame, text="مواقيت الصلاة:", font=("Tahoma", 13, "bold")).pack(pady=8, anchor="w")
        self.times_text = tb.Text(frame, height=8, state="disabled", font=("Tahoma", 13))
        self.times_text.pack(fill='both', pady=5)

        tb.Label(frame, text="مستوى الصوت:", font=("Tahoma", 12)).pack(pady=5, anchor="w")
        self.vol_scale = tb.Scale(frame, from_=0, to=100, orient='horizontal', command=self.on_volume_changed, bootstyle="info")
        self.vol_scale.pack(fill='x')

        self.log_text = tb.Text(frame, height=6, state="disabled", font=("Tahoma", 11))
        self.log_text.pack(fill='both', pady=10)

        self.footer_label = tb.Label(frame, text="By SMRH", font=("Tahoma", 11, "italic"))
        self.footer_label.pack(pady=3, anchor="e")

    def format_time(self, time_str):
        # time_str مفترض تكون مثل "HH:MM"
        if not time_str or time_str == "--:--":
            return time_str
        try:
            hour, minute = map(int, time_str.split(":"))
            if self.time_format_24h:
                return f"{hour:02d}:{minute:02d}"
            else:
                suffix = "ص" if hour < 12 else "م"
                hour_12 = hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                return f"{hour_12}:{minute:02d} {suffix}"
        except Exception:
            return time_str

    def display_timings(self):
        self.times_text.configure(state="normal")
        self.times_text.delete("1.0", "end")
        for prayer in VALID_PRAYERS:
            time_str = self.timings.get(prayer, "--:--")
            time_formatted = self.format_time(time_str)
            display_name = PRAYER_NAMES_AR.get(prayer, prayer)
            self.times_text.insert('end', f"{display_name} : {time_formatted}\n")
        self.times_text.configure(state="disabled")

    def on_play_clicked(self):
        if self.player.is_playing:
            self.player.stop()
        self.player.play()
        self.log("تم تشغيل الأذان")

    def on_stop_clicked(self):
        self.player.stop()
        self.log("تم إيقاف الأذان")

    def on_city_changed(self, event):
        self.save_config()
        self.update_timings()

    def on_adhan_changed(self, event):
        selected_adhan = self.adhan_var.get()
        if selected_adhan in self.adhan_files:
            self.player.change_sound(selected_adhan)
            self.save_config()
            self.log(f"تم تغيير صوت الأذان إلى: {selected_adhan}")

    def on_output_device_changed(self, event):
        selected_device = self.output_device_var.get()
        if selected_device not in self.audio_devices:
            self.log("جهاز الإخراج المختار غير متوفر.")
            return
        if self.player.is_playing:
            self.player.stop()
        self.player.output_device = selected_device
        self.cfg['output_device'] = selected_device
        self.save_config()
        self.log(f"تم تغيير جهاز إخراج الصوت إلى: {selected_device}")

    def on_volume_changed(self, val):
        volume = float(val) / 100
        self.player.set_volume(volume)
        self.save_config()

    def on_time_format_changed(self, event):
        val = self.time_format_var.get()
        self.time_format_24h = (val == "24 ساعة")
        self.cfg["time_format_24h"] = self.time_format_24h
        self.save_config()
        self.display_timings()
        self.log(f"تم تغيير صيغة الوقت إلى: {val}")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see('end')

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if "city" not in cfg or cfg["city"] not in self.city_names:
                    cfg["city"] = self.city_names[0]
                if "adhan" not in cfg or cfg["adhan"] not in self.adhan_files:
                    cfg["adhan"] = self.adhan_files[0]
                if "volume" not in cfg:
                    cfg["volume"] = 0.8
                if "timings" not in cfg:
                    cfg["timings"] = {}
                if "output_device" not in cfg or cfg["output_device"] not in self.get_output_devices():
                    devices = self.get_output_devices()
                    cfg["output_device"] = devices[0] if devices else ""
                if "time_format_24h" not in cfg:
                    cfg["time_format_24h"] = True
                return cfg
            except Exception as e:

                print(f"خطأ في تحميل الإعدادات: {e}")
        return {
            "city": self.city_names[0],
            "adhan": self.adhan_files[0],
            "volume": 0.8,
            "timings": {},
            "output_device": self.get_output_devices()[0] if self.get_output_devices() else "",
            "time_format_24h": True
        }

    def save_config(self):
        self.cfg['city'] = self.city_var.get()
        self.cfg['adhan'] = self.adhan_var.get()
        self.cfg['volume'] = self.player.volume
        self.cfg['timings'] = self.timings
        self.cfg['output_device'] = self.output_device_var.get()
        self.cfg['time_format_24h'] = self.time_format_24h
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
            self.log("تم حفظ الإعدادات والمواقيت بنجاح.")
        except Exception as e:
            self.log(f"خطأ في حفظ الإعدادات: {e}")

    def update_timings(self):
        city = self.city_var.get()
        if city not in CITIES:
            self.log("المدينة غير موجودة")
            return False

        lat, lng = CITIES[city]
        timezone = TIMEZONE_MAPPING.get(city, "UTC")
        method = METHOD_MAPPING.get(city, 2)

        params = {
            "latitude": lat,
            "longitude": lng,
            "method": method,
            "timezonestring": timezone,
        }
        try:
            r = requests.get(API_URL, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                timings = data.get("data", {}).get("timings", {})
                clean_timings = {}
                for k, v in timings.items():
                    if k in VALID_PRAYERS:
                        clean_timings[k] = v.split(" ")[0]
                self.timings = clean_timings
                self.display_timings()
                self.save_config()
                self.log(f"تم تحديث المواقيت للمدينة: {city}")
                self.triggered_prayers.clear()
                return True
            else:
                self.log("فشل في جلب المواقيت من الإنترنت")
                return False
        except Exception as e:
            self.log(f"خطأ في جلب المواقيت: {e}")
            return False

    def check_prayer_time_loop(self):
        while self.is_running:
            if not self.timings:
                time.sleep(CHECK_INTERVAL)
                continue

            now = datetime.now()
            current_time_str = now.strftime("%H:%M")

            # إعادة تحديث التواقيت في بداية كل يوم تلقائيًا
            if now.day != self.current_day:
                updated = self.update_timings()
                if updated:
                    self.current_day = now.day

            for prayer in VALID_PRAYERS:
                t_str = self.timings.get(prayer)
                if t_str == current_time_str and prayer not in self.triggered_prayers:
                    self.triggered_prayers.add(prayer)
                    self.log(f"موعد صلاة {PRAYER_NAMES_AR.get(prayer, prayer)} الآن، تشغيل الأذان لمدة {ADHAN_DURATION} ثانية")
                    self.player.play()
                    threading.Thread(target=self.stop_adhan_after_delay, daemon=True).start()

            time.sleep(CHECK_INTERVAL)

    def stop_adhan_after_delay(self):
        time.sleep(ADHAN_DURATION)
        self.player.stop()

    def update_timings_loop(self):
        while self.is_running:
            success = self.update_timings()
            if success:
                interval = OFFLINE_UPDATE_INTERVAL
            else:
                interval = 1800
            for _ in range(int(interval / 5)):
                if not self.is_running:
                    break
                time.sleep(5)

    def minimize_to_tray(self):
        self.root.withdraw()
        if self.tray_icon is None:
            from PIL import Image, ImageDraw
            import pystray

            image = Image.new('RGB', (64, 64), color='#3498db')
            d = ImageDraw.Draw(image)
            d.text((20, 20), "ص", fill="white")
            menu = pystray.Menu(
                pystray.MenuItem("إظهار البرنامج", self.show_from_tray),
                pystray.MenuItem("خروج", self.exit_app)
            )
            self.tray_icon = pystray.Icon("adhan_app", image, "مواقيت الصلاة", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_from_tray(self):
        self.root.deiconify()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def exit_app(self):
        self.is_running = False
        self.player.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def start_updater(self):
        self.updater_thread = threading.Thread(target=self.update_timings_loop, daemon=True)
        self.updater_thread.start()

    def start_checker(self):
        self.checker_thread = threading.Thread(target=self.check_prayer_time_loop, daemon=True)
        self.checker_thread.start()


if __name__ == "__main__":
    sock = check_already_running()
    if not sock:
        messagebox.showwarning("تنبيه", "البرنامج مفتوح بالفعل!")
        sys.exit()

    root = tb.Window(themename="flatly")
    app = PrayerApp(root)
    root.mainloop()
