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

# 在程序最开头添加DPI感知
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 修改为Per-Monitor DPI感知

# ------------------------- 配置管理类 -------------------------
class ConfigManager:
    def __init__(self, path='config.json'):
        self.path = path
        self.config = self.load_config()

        # 确保必要配置项存在
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
        
        # 获取物理屏幕尺寸
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # 获取窗口实际物理位置
        self.root.update_idletasks()
        self.offset_x = self.root.winfo_x()
        self.offset_y = self.root.winfo_y()

        self.canvas = tk.Canvas(self.root, cursor='cross')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start = (0, 0)
        self.rect = None
        self.selection = None

        # 绑定事件
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        # 转换为物理屏幕坐标
        screen_x = self.offset_x + event.x
        screen_y = self.offset_y + event.y
        self.start = (screen_x, screen_y)
        # 画布使用相对坐标
        self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red')

    def on_drag(self, event):
        # 实时显示物理坐标
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
        """将屏幕物理坐标转换为画布相对坐标"""
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

    # ---------- 系统托盘设置 ----------
    def setup_tray(self):
        # 生成临时图标（如果没有图标文件）
        if not os.path.exists('icon.png'):
            img = Image.new('RGB', (64, 64), 'white')
            img.save('icon.png')

        image = Image.open('icon.png')
        menu = (
            item('更改热键', self.open_settings),
            item('退出', self.exit)
        )
        self.icon = pystray.Icon("trans_tool", image, "游戏翻译工具", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    # ---------- 热键管理 ----------
    def register_hotkey(self):
        if self.hotkey_handler:
            keyboard.remove_hotkey(self.hotkey_handler)
        self.hotkey_handler = keyboard.add_hotkey(
            self.config.config['hotkey'],
            self.capture_screenshot
        )

    # ---------- 截图处理流程 ----------
    def capture_screenshot(self):
        # 在GUI线程执行
        self.run_in_main_thread(self._capture)

    def _capture(self):
        selector = ScreenshotTool()
        area = selector.get_selection()
        if area:
            img = ImageGrab.grab(bbox=area).convert('RGB')
            # 注释掉截图预览显示
            # self.show_screenshot_preview(img, area)  
            self.process_image(img, area)


    def _draw_crosshair(self, img, area):
        """在截图四角添加定位标记"""
        draw = ImageDraw.Draw(img)
        # 红色十字标记
        cross_size = 10
        corners = [
            (0, 0),  # 左上
            (img.width-1, 0),  # 右上
            (0, img.height-1),  # 左下
            (img.width-1, img.height-1)  # 右下
        ]
        for x, y in corners:
            draw.line((x-cross_size, y, x+cross_size, y), fill='red', width=2)
            draw.line((x, y-cross_size, x, y+cross_size), fill='red', width=2)
        img.save('debug_crosshair.png')

    def show_screenshot_preview(self, img, area):
        def _show():
            preview = tk.Toplevel()
            preview.title(f"截图预览 | 原始尺寸: {img.size} | 5秒关闭")
            
            # 显示物理坐标信息
            info_frame = tk.Frame(preview)
            tk.Label(info_frame, text=f"X: {area[0]}  Y: {area[1]}").pack(side=tk.LEFT)
            tk.Label(info_frame, text=f"宽度: {area[2]-area[0]}px").pack(side=tk.LEFT, padx=10)
            tk.Label(info_frame, text=f"高度: {area[3]-area[1]}px").pack(side=tk.LEFT)
            info_frame.pack(pady=5)

            # 显示带标记的截图
            photo = ImageTk.PhotoImage(img)
            label = tk.Label(preview, image=photo)
            label.image = photo
            label.pack()

            # 自动关闭
            preview.after(5000, preview.destroy)

        self.run_in_main_thread(_show)
    # ---------- OCR与翻译 ----------
    def process_image(self, img, area):
        try:
            # OCR识别
            pytesseract.pytesseract.tesseract_cmd = self.config.config['tesseract_path']
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            
            # 翻译
            translator = google_translator()
            translated = translator.translate(text, lang_tgt=self.config.config['target_lang'])
            print(f"原文: {text.strip()}")
            print(f"译文: {translated.strip()}")

            # 显示结果
            self.show_overlay(translated, area)
        except Exception as e:
            print(f"处理错误: {e}")

    # ---------- 显示翻译结果 ----------
    def show_overlay(self, text, area):
        def _show():
            overlay = tk.Toplevel()
            overlay.overrideredirect(True)
            
            # 准确定位到截图区域下方
            pos_x = area[0]
            pos_y = area[3] + 5
            
            overlay.geometry(f"+{pos_x}+{pos_y}")
            overlay.attributes('-topmost', True)
            overlay.attributes('-alpha', 0.85)

            # 仅显示翻译文本（移除调试信息）
            label = tk.Label(
                overlay,
                text=text.strip(),
                bg='#333333',
                fg='white',
                font=('微软雅黑', 10),
                wraplength=500,
                padx=10,
                pady=5
            )
            label.pack()
            
            # 移除自动关闭代码
            # overlay.after(5000, overlay.destroy)

            # 添加手动关闭按钮
            close_btn = tk.Button(
                overlay,
                text="×",
                command=overlay.destroy,
                bg='#FF4444',
                fg='white',
                borderwidth=0
            )
            close_btn.place(relx=1.0, x=-2, y=2, anchor=tk.NE)

        self.run_in_main_thread(_show)
    # ---------- 设置界面 ----------
    def open_settings(self):
        self.run_in_main_thread(self._open_settings)

    def _open_settings(self):
        win = tk.Tk()
        win.title("设置")
        win.geometry("300x150")

        tk.Label(win, text="快捷键:").pack(pady=5)
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

        tk.Button(win, text="保存", command=save).pack(pady=10)
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


# ------------------------- 启动程序 -------------------------
if __name__ == "__main__":
    # 创建隐藏的主窗口
    root = tk.Tk()
    root.withdraw()

    app = App()

    # 启动主事件循环
    root.mainloop()