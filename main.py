import os
import json
import threading
import keyboard
import pytesseract
from PIL import ImageGrab, Image, ImageTk, ImageDraw
from google_trans_new import google_translator
import tkinter as tk
import pystray
from pystray import MenuItem as item
import ctypes

# 获取显示器缩放比例
ctypes.windll.shcore.SetProcessDpiAwareness(2)
scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100

# ------------------------- 配置管理类 -------------------------
class ConfigManager:
    def __init__(self, path='config.json'):
        self.path = path
        self.config = self.load_config()

        if 'tesseract_path' not in self.config:
            self.config['tesseract_path'] = 'F:/Program Files/Tesseract-OCR/tesseract.exe'
            self.save_config()

    def load_config(self):
        try:
            with open(self.path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "hotkey": "ctrl+shift+t",
                "target_lang": "en",
                "tesseract_path": "F:/Program Files/Tesseract-OCR/tesseract.exe"
            }

    def save_config(self):
        with open(self.path, 'w') as f:
            json.dump(self.config, f, indent=2)

# ------------------------- 精确截图工具类 -------------------------
class ScreenshotTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.root.update_idletasks()
        self.offset_x = self.root.winfo_x()
        self.offset_y = self.root.winfo_y()

        self.canvas = tk.Canvas(self.root, cursor='cross')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start = (0, 0)
        self.rect = None
        self.selection = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        screen_x = self.offset_x + event.x
        screen_y = self.offset_y + event.y
        self.start = (screen_x, screen_y)
        self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red')

    def on_drag(self, event):
        current_x = self.offset_x + event.x
        current_y = self.offset_y + event.y
        self.root.title(f"截图工具 | 当前坐标: {current_x}x{current_y}")
        self.canvas.coords(self.rect, *self._to_canvas(self.start), event.x, event.y)

    def on_release(self, event):
        end_x = self.offset_x + event.x
        end_y = self.offset_y + event.y
        self.selection = (
            min(self.start[0], end_x),
            min(self.start[1], end_y),
            max(self.start[0], end_x),
            max(self.start[1], end_y)
        )
        self.root.destroy()

    def _to_canvas(self, screen_point):
        return (
            screen_point[0] - self.offset_x,
            screen_point[1] - self.offset_y
        )

    def get_selection(self):
        self.root.mainloop()
        return self.selection

# ------------------------- 主应用类 -------------------------
class App:
    def __init__(self):
        self.config = ConfigManager()
        self.icon = None
        self.hotkey = self.config.config['hotkey']
        self.hotkey_handler = None
        self.setup_tray()
        self.register_hotkey()

    def setup_tray(self):
        if not os.path.exists('icon.png'):
            img = Image.new('RGB', (64, 64), 'white')
            img.save('icon.png')

        image = Image.open('icon.png')
        menu = (
            item('Hotkey', self.open_settings),
            item('Exit', self.exit)
        )
        self.icon = pystray.Icon("trans_tool", image, "Screen Translation", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def register_hotkey(self):
        if self.hotkey_handler:
            keyboard.remove_hotkey(self.hotkey_handler)
        self.hotkey_handler = keyboard.add_hotkey(
            self.config.config['hotkey'],
            self.capture_screenshot
        )

    def capture_screenshot(self):
        self.run_in_main_thread(self._capture)

    def _capture(self):
        selector = ScreenshotTool()
        area = selector.get_selection()
        if area:
            img = ImageGrab.grab(bbox=area).convert('RGB')
            self.process_image(img, area)

    def process_image(self, img, area):
        try:
            pytesseract.pytesseract.tesseract_cmd = self.config.config['tesseract_path']
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            
            translator = google_translator()
            translated = translator.translate(text, lang_tgt=self.config.config['target_lang'])
            self.show_overlay(translated, area)
        except Exception as e:
            print(f"处理错误: {e}")

    def show_overlay(self, text, area):
        def _show():
            overlay = tk.Toplevel()
            overlay.overrideredirect(True)
            
            # # 计算缩放后的实际坐标
            # scaled_x1 = int(area[0] * scale_factor)
            # scaled_y1 = int(area[1] * scale_factor)
            # scaled_x2 = int(area[2] * scale_factor)
            # scaled_y2 = int(area[3] * scale_factor)

            scaled_x1 = int(area[0])
            scaled_y1 = int(area[1])
            scaled_x2 = int(area[2])
            scaled_y2 = int(area[3])

            # 初始定位在截图区域的左上角
            window_width = int(area[2] - area[0])
            window_height = int(area[3] - area[1])
            pos_x = scaled_x1
            pos_y = scaled_y1

            # 边界检查
            screen_width = overlay.winfo_screenwidth()
            screen_height = overlay.winfo_screenheight()
            
            # 水平方向调整
            if pos_x + window_width > screen_width:
                pos_x = max(scaled_x1 - window_width - 10, 10)
            
            # 垂直方向调整
            if pos_y + window_height > screen_height:
                pos_y = max(scaled_y1 - window_height - 10, 10)

            overlay.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
            overlay.attributes('-topmost', True)
            overlay.attributes('-alpha', 0.85)

            # 添加内容（保持原有样式）
            label = tk.Label(
                overlay,
                text=text.strip(),
                bg='#333333',
                fg='white',
                font=('微软雅黑', 10),
                wraplength=450,  # 略微减小以适应窗口
                padx=10,
                pady=5
            )
            label.pack(expand=True, fill=tk.BOTH)
            
            close_btn = tk.Button(
                overlay,
                text="×",
                command=overlay.destroy,
                bg='#FF4444',
                fg='white',
                borderwidth=0
            )
            close_btn.place(relx=1.0, x=-2, y=2, anchor=tk.NE)
            print(f"原始区域坐标: {area}")
            print(f"缩放后的坐标: ({scaled_x1}, {scaled_y1}, {scaled_x2}, {scaled_y2})")
            print(f"最终窗口位置: ({pos_x}, {pos_y}, {pos_x + window_width}, {pos_y + window_height})")
            

        self.run_in_main_thread(_show)       
      
   # ---------- 设置界面 ----------
    def open_settings(self):
        self.run_in_main_thread(self._open_settings)

    def _open_settings(self):
        win = tk.Tk()
        win.title("Settings")
        win.geometry("300x150")

        tk.Label(win, text="Hotkey:").pack(pady=5)
        entry = tk.Entry(win)
        entry.insert(0, self.config.config['hotkey'])
        entry.pack(pady=5)

        def save():
            new_hotkey = entry.get().strip()
            if new_hotkey:
                self.config.config['hotkey'] = new_hotkey
                self.config.save_config()
                self.register_hotkey()
                win.destroy()

        tk.Button(win, text="Save", command=save).pack(pady=10)
        win.mainloop()

    # ---------- 工具方法 ----------
    def run_in_main_thread(self, func):
        # 确保GUI操作在主线程执行
        if threading.current_thread() != threading.main_thread():
            win = tk.Tk()
            win.after(0, func)
            win.after(100, win.destroy)
            win.mainloop()
        else:
            func()

    def exit(self):
        self.icon.stop()
        os._exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = App()
    root.mainloop()   