import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np
import subprocess
import os
import tempfile
from datetime import datetime
import sys
import platform
import time
import math

def get_adb_path():
    # Macのデフォルトパスを明示的に指定
    adb_path = os.path.expanduser("/opt/homebrew/bin/adb")
    if os.path.exists(adb_path):
        return adb_path
    else:
        # システムからADBを探すフォールバック
        try:
            result = subprocess.run(["which", "adb"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
        except Exception:
            return None

def resource_path(relative_path):
     if hasattr(sys, '_MEIPASS'):
         return os.path.join(sys._MEIPASS, relative_path)
     return os.path.join(os.path.abspath("."), relative_path)

class PlayerIconDetector:
    def __init__(self):
        self.lower_red1 = np.array([0, 120, 100])
        self.upper_red1 = np.array([5, 255, 255])
        self.lower_red2 = np.array([175, 120, 100])
        self.upper_red2 = np.array([180, 255, 255])
        self.min_width = 30
        self.max_width = 31
        self.min_height = 34
        self.max_height = 40

        self.crop_x = 0
        self.crop_y = 440
        self.crop_width = 1080
        self.crop_height = 1215

        self.resize_width = 640
        self.resize_height = 720

    def crop_image(self, image):
        return image[self.crop_y:self.crop_y+self.crop_height, self.crop_x:self.crop_x+self.crop_width]

    def resize_for_display(self, image):
        return cv2.resize(image, (self.resize_width, self.resize_height))

    def detect_icon(self, image_path):
        if not os.path.exists(image_path):
            raise ValueError(f"画像ファイルが見つかりません: {image_path}")

        original_image = cv2.imread(image_path)
        if original_image is None:
            raise ValueError("画像の読み込みに失敗しました")

        cropped_image = self.crop_image(original_image)
        
        # コントラスト強調
        lab = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16, 16))
        cl = clahe.apply(l)
        enhanced_lab = cv2.merge((cl, a, b))
        enhanced_image = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        
        # 画像の明るさに基づいてフィルタリング強度を調整
        avg_brightness = np.mean(cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY))
        blur_size = 7
        
        # ガウシアンブラー適用
        blurred = cv2.GaussianBlur(enhanced_image, (blur_size, blur_size), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        hsv = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, self.lower_red1, self.upper_red1)
        mask2 = cv2.inRange(hsv, self.lower_red2, self.upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.medianBlur(mask, 3)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        
        scale_x = self.resize_width / cropped_image.shape[1]
        scale_y = self.resize_height / cropped_image.shape[0]
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            top_edge_y = y
            
            # 面積によるフィルタリング
            area = cv2.contourArea(contour)
            if area < 410 or area > 750:
                continue
            
            # 縦横比によるフィルタリング
            aspect_ratio = float(w) / h
            if not (0.6 <= aspect_ratio <= 1.0):
                continue
            
            # 円形度チェック
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            if circularity < 0.1:
                continue
            
            # 凸性チェック
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / hull_area if hull_area > 0 else 0
            if solidity < 0.1:
                continue
            
            # サイズによるフィルタリング
            if not (self.min_width <= w <= self.max_width and 
                    self.min_height <= h <= self.max_height):
                continue
            
            # 検出された領域の色一貫性をチェック
            roi = cropped_image[y:y+h, x:x+w]
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mask_roi1 = cv2.inRange(hsv_roi, self.lower_red1, self.upper_red1)
            mask_roi2 = cv2.inRange(hsv_roi, self.lower_red2, self.upper_red2)
            mask_roi = cv2.bitwise_or(mask_roi1, mask_roi2)
            red_ratio = cv2.countNonZero(mask_roi) / (w * h)
            if red_ratio < 0.4:
                continue

            # 検出結果を保存
            original_coords = {
                'x': x + w//2,
                'y': top_edge_y,
                'width': w,
                'height': h,
                'confidence': cv2.contourArea(contour)
            }
            
            resized_coords = {
                'x': int(round((x + w//2) * scale_x)),
                'y': int(round(top_edge_y * scale_y)),
                'width': int(round(w * scale_x)),
                'height': int(round(h * scale_y)),
                'confidence': cv2.contourArea(contour)
            }
            
            resized_center_coords = {
                'x': resized_coords['x'] - 9,
                'y': resized_coords['y'] + 45
            }
            
            results.append({
                'original': original_coords,
                'resized': resized_coords,
                'resized_center': resized_center_coords
            })

        results.sort(key=lambda x: (x['original']['x'], x['original']['y']))
        return results, cropped_image

    def visualize_results(self, image, results):
        visualized_image = image.copy()
        
        for result in results:
            original = result['original']
            resized_center = result['resized_center']
            x, y = original['x'], original['y']
            w, h = original['width'], original['height']

            cv2.rectangle(visualized_image, (x - w//2, y), (x + w//2, y + h), (0, 255, 0), 2)
            cv2.circle(visualized_image, (x, y), 3, (0, 0, 255), -1)
            text = f'P: ({x}, {y}) {w}x{h}'
            cv2.putText(visualized_image, text, (x + 10, y + 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            cx, cy = x - 15, y + 76
            cv2.circle(visualized_image, (cx, cy), 3, (255, 0, 0), -1)
            center_text = f'C: ({resized_center["x"]}, {resized_center["y"]})'
            cv2.putText(visualized_image, center_text, (cx + 10, cy), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        return visualized_image

class CombinedDetectorUI:
    def __init__(self, parent):
        self.parent = parent
        self.icon_detector = PlayerIconDetector()
        
        self.screenshot_dir = resource_path("screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

        self.setup_ui()
        self.image_path = None
        self.cropped_image = None

    def setup_ui(self):
        self.main_frame = tk.Frame(self.parent)
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, padx=5)

        self.preview_label = tk.Label(self.left_frame)
        self.preview_label.pack()

        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, padx=5, fill="y")

        self.upload_btn = tk.Button(self.right_frame, text="画像をアップロード", command=self.upload_image)
        self.upload_btn.pack(pady=5)

        self.screenshot_btn = tk.Button(self.right_frame, text="スクリーンショットを撮影", command=self.take_screenshot)
        self.screenshot_btn.pack(pady=5)

        self.result_text = tk.Text(self.right_frame, height=20, width=35)
        self.result_text.pack(pady=5, fill="y")

    def check_adb_devices(self):
        """ADBデバイスが接続されているか確認する"""
        adb_path = get_adb_path()
        if not adb_path:
            messagebox.showerror("エラー", "ADBが見つかりません。Android SDKがインストールされているか、PATHが正しく設定されているか確認してください。")
            return False

        try:
            result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=5)
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [device for device in devices if device.strip() and not device.strip().endswith('offline')]
            if connected_devices:
                return True
            else:
                messagebox.showerror("エラー", "接続されているAndroidデバイスが見つかりません。デバイスが正しく接続されているか確認してください。")
                return False
        except subprocess.TimeoutExpired:
            messagebox.showerror("エラー", "ADBコマンドがタイムアウトしました。デバイスが応答していません。")
            return False
        except Exception as e:
            messagebox.showerror("エラー", f"ADBコマンドの実行中にエラーが発生しました: {str(e)}")
            return False

    def take_screenshot(self):
        """ADBを使用してスクリーンショットを撮影する"""
        if not self.check_adb_devices():
            return

        adb_path = get_adb_path()
        if not adb_path:
            messagebox.showerror("エラー", "ADBが見つかりません。")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.screenshot_dir, f"screenshot_{timestamp}.png")

            adb_result = subprocess.run([adb_path, "exec-out", "screencap", "-p"], capture_output=True, timeout=5)
            if adb_result.returncode != 0:
                raise subprocess.SubprocessError("ADBコマンドが失敗しました")

            with open(screenshot_path, 'wb') as f:
                f.write(adb_result.stdout)

            if not os.path.exists(screenshot_path):
                raise FileNotFoundError("スクリーンショットファイルが作成されませんでした")

            time.sleep(0.001)
            self.process_image(screenshot_path)

        except subprocess.TimeoutExpired:
            messagebox.showerror("エラー", "スクリーンショット撮影がタイムアウトしました")
        except subprocess.SubprocessError as e:
            messagebox.showerror("エラー", f"スクリーンショット撮影に失敗しました: {str(e)}")
        except Exception as e:
            messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {str(e)}")

    def upload_image(self):
        file_path = filedialog.askopenfilename(
            title="画像を選択",
            filetypes=[("画像ファイル", "*.png *.jpg *.jpeg")]
        )
        if file_path:
            self.process_image(file_path)

    def process_image(self, image_path):
        self.image_path = image_path
        try:
            results, self.cropped_image = self.icon_detector.detect_icon(image_path)
            self.display_icon_results(results)
            visualized = self.icon_detector.visualize_results(self.cropped_image, results)
            self.display_preview(visualized)
        except Exception as e:
            messagebox.showerror("エラー", f"画像処理中にエラーが発生しました: {str(e)}")

    def display_icon_results(self, results):
        self.result_text.delete(1.0, tk.END)
        if results:
            self.result_text.insert(tk.END, "検出結果:\n")
            for i, result in enumerate(results, 1):
                resized = result['resized']
                original = result['original']
                resized_center = result['resized_center']
                text = (f"検出 {i}:\n"
                        f"  P座標 (リサイズ後): ({resized['x']}, {resized['y']})\n"
                        f"  P座標 (元画像): ({original['x']}, {original['y']})\n"
                        f"  中心座標 (リサイズ後): ({resized_center['x']}, {resized_center['y']})\n")
                self.result_text.insert(tk.END, text)
        else:
            self.result_text.insert(tk.END, "指定されたサイズ範囲のアイコンが検出されませんでした\n")

    def display_preview(self, image):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        # シミュレーターのサイズに合わせる
        target_width = 640  # MonsterStrikeSimulatorのfield_widthと同じ
        target_height = 720 # MonsterStrikeSimulatorのfield_heightと同じ
        pil_image = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(pil_image)
        self.preview_label.configure(image=photo)
        self.preview_label.image = photo

class CombinedToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("スタジアムツール")
        
        # メインコンテナの作成
        self.main_container = ttk.Notebook(root)
        self.main_container.pack(expand=True, fill="both")
        
        # タブの作成
        self.simulator_tab = ttk.Frame(self.main_container)
        self.detector_tab = ttk.Frame(self.main_container)
        
        self.main_container.add(self.simulator_tab, text="反射シミュレーター")
        self.main_container.add(self.detector_tab, text="座標検出")
        
        # タブ切り替えイベントの設定
        self.main_container.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # 各機能の初期化
        self.init_simulator()
        self.init_detector()
        
        # 左右キーでのタブ切り替えを設定
        self.setup_tab_navigation()
        
        # MacOSのCommandキー用にキーボードショートカットを変更
        self.root.bind("<Command-Up>", self.on_command_up)
        self.root.bind("<Command-Down>", self.on_command_down)

    def on_command_up(self, event):
        """Command+↑で角度を10度増加"""
        if hasattr(self, 'simulator'):
            self.simulator.increase_angle_by_ten(event)

    def on_command_down(self, event):
        """Command+↓で角度を10度減少"""
        if hasattr(self, 'simulator'):
            self.simulator.decrease_angle_by_ten(event)

    def on_tab_change(self, event):
        """タブが切り替わったときの処理"""
        current_tab = self.main_container.select()
        if current_tab == str(self.simulator_tab):
            # シミュレータータブが選択されたときはキャンバスにフォーカスを設定
            self.simulator.canvas.focus_set()

    def setup_tab_navigation(self):
        """左右キーでのタブ切り替え機能を設定"""
        self.root.bind("<Left>", self.previous_tab)
        self.root.bind("<Right>", self.next_tab)

    def next_tab(self, event):
        """次のタブに切り替え"""
        current = self.main_container.index("current")
        if current < self.main_container.index("end") - 1:
            self.main_container.select(current + 1)

    def previous_tab(self, event):
        """前のタブに切り替え"""
        current = self.main_container.index("current")
        if current > 0:
            self.main_container.select(current - 1)

    def init_simulator(self):
        self.simulator = MonsterStrikeSimulator(self.simulator_tab)

    def init_detector(self):
        self.detector = CombinedDetectorUI(self.detector_tab)

class MonsterStrikeSimulator:
    def __init__(self, parent):
        self.parent = parent
        
        # フィールドサイズの設定
        self.field_width = 640
        self.field_height = 720
        
        # スクリーンショット保存ディレクトリの設定
        self.screenshot_dir = resource_path("screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
        
        # フィールドの余白設定
        self.margin = 5
        
        # メインフレームの作成
        self.main_frame = tk.Frame(parent, bg="gray")
        self.main_frame.pack(padx=self.margin, pady=self.margin, side=tk.LEFT)
        
        # キャンバスの作成
        self.canvas = tk.Canvas(parent, width=self.field_width, height=self.field_height, bg="black")
        self.canvas.pack(side=tk.LEFT)
        
        # その他の初期化
        self.init_variables()
        self.create_control_panel()
        self.setup_bindings()
        self.draw_field()

    def init_variables(self):
        # 背景画像の初期化
        self.background_image = None
        self.background_image_tk = None
        self.background_id = None
        
        # 障害物リストと選択状態の初期化
        self.obstacles = []
        self.selected_obstacle = None
        
        # 軌道の描画用
        self.trajectory = []
        
        # リアルタイムシミュレーションのフラグ
        self.is_dragging_start = False
        
        # スクリーンショット保存ディレクトリの作成
        self.screenshot_dir = os.path.join(os.path.expanduser("~"), "MonsterStrikeSimulator")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    def create_control_panel(self):
        # コントロールパネルの作成
        self.control_panel = tk.Frame(self.parent, width=300, height=self.field_height)
        self.control_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 発射角度入力
        self.create_angle_controls()
        
        # 最大反射回数の設定
        self.create_reflection_controls()
        
        # 開始位置入力
        self.create_start_position_controls()
        
        # 障害物制御
        self.create_obstacle_controls()
        
        # ボタン類
        self.create_action_buttons()
        
        # 座標表示エリア
        self.create_coordinates_display()

    def create_angle_controls(self):
        self.angle_frame = tk.Frame(self.control_panel)
        self.angle_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.angle_frame, text="発射角度 (0-1023):").pack(side=tk.LEFT)
        self.angle_var = tk.StringVar(value="512")
        self.angle_entry = tk.Entry(self.angle_frame, textvariable=self.angle_var, width=6)
        self.angle_entry.pack(side=tk.LEFT, padx=5)

    def create_reflection_controls(self):
        self.max_reflection_frame = tk.Frame(self.control_panel)
        self.max_reflection_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.max_reflection_frame, text="最大反射回数:").pack(side=tk.LEFT)
        self.max_reflection_var = tk.StringVar(value="10")
        self.max_reflection_entry = tk.Entry(self.max_reflection_frame, 
                                           textvariable=self.max_reflection_var, width=6)
        self.max_reflection_entry.pack(side=tk.LEFT, padx=5)

    def create_start_position_controls(self):
        self.start_pos_frame = tk.Frame(self.control_panel)
        self.start_pos_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.start_pos_frame, text="開始位置:").pack(anchor=tk.W)
        
        # X座標
        self.start_pos_x_frame = tk.Frame(self.start_pos_frame)
        self.start_pos_x_frame.pack(fill=tk.X)
        tk.Label(self.start_pos_x_frame, text="X:").pack(side=tk.LEFT)
        self.start_x_var = tk.StringVar(value="320")
        self.start_x_entry = tk.Entry(self.start_pos_x_frame, textvariable=self.start_x_var, width=6)
        self.start_x_entry.pack(side=tk.LEFT, padx=5)
        
        # Y座標
        self.start_pos_y_frame = tk.Frame(self.start_pos_frame)
        self.start_pos_y_frame.pack(fill=tk.X)
        tk.Label(self.start_pos_y_frame, text="Y:").pack(side=tk.LEFT)
        self.start_y_var = tk.StringVar(value="600")
        self.start_y_entry = tk.Entry(self.start_pos_y_frame, textvariable=self.start_y_var, width=6)
        self.start_y_entry.pack(side=tk.LEFT, padx=5)

    def create_obstacle_controls(self):
        self.obstacle_frame = tk.Frame(self.control_panel)
        self.obstacle_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.obstacle_frame, text="障害物:").pack(anchor=tk.W)
        
        # 障害物タイプ選択
        self.obstacle_type_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_type_frame.pack(fill=tk.X)
        
        self.obstacle_type = tk.StringVar(value="circle")
        tk.Radiobutton(self.obstacle_type_frame, text="円", variable=self.obstacle_type, value="circle").pack(side=tk.LEFT)
        tk.Radiobutton(self.obstacle_type_frame, text="正方形", variable=self.obstacle_type, value="square").pack(side=tk.LEFT)
        
        # サイズ設定
        self.obstacle_size_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_size_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_size_frame, text="サイズ:").pack(side=tk.LEFT)
        self.obstacle_size_var = tk.StringVar(value="60")
        self.obstacle_size_entry = tk.Entry(self.obstacle_size_frame, textvariable=self.obstacle_size_var, width=6)
        self.obstacle_size_entry.pack(side=tk.LEFT, padx=5)
        
        # 位置設定
        self.create_obstacle_position_controls()
        
        # 耐久回数設定
        self.create_obstacle_durability_controls()

    def create_obstacle_position_controls(self):
        # X座標
        self.obstacle_pos_x_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_pos_x_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_pos_x_frame, text="X:").pack(side=tk.LEFT)
        self.obstacle_x_var = tk.StringVar(value="320")
        self.obstacle_x_entry = tk.Entry(self.obstacle_pos_x_frame, textvariable=self.obstacle_x_var, width=6)
        self.obstacle_x_entry.pack(side=tk.LEFT, padx=5)
        
        # Y座標
        self.obstacle_pos_y_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_pos_y_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_pos_y_frame, text="Y:").pack(side=tk.LEFT)
        self.obstacle_y_var = tk.StringVar(value="300")
        self.obstacle_y_entry = tk.Entry(self.obstacle_pos_y_frame, textvariable=self.obstacle_y_var, width=6)
        self.obstacle_y_entry.pack(side=tk.LEFT, padx=5)

    def create_obstacle_durability_controls(self):
        self.obstacle_durability_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_durability_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_durability_frame, text="耐久回数:").pack(side=tk.LEFT)
        self.obstacle_durability_var = tk.StringVar(value="3")
        self.obstacle_durability_entry = tk.Entry(self.obstacle_durability_frame, 
                                                textvariable=self.obstacle_durability_var, width=6)
        self.obstacle_durability_entry.pack(side=tk.LEFT, padx=5)

    def create_action_buttons(self):
        self.button_frame = tk.Frame(self.control_panel)
        self.button_frame.pack(padx=10, pady=10, fill=tk.X)
        
        tk.Button(self.button_frame, text="障害物追加", command=self.add_obstacle).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="障害物削除", command=self.remove_obstacle).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="リセット", command=self.reset).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="背景画像を設定", command=self.load_background).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="背景画像を削除", command=self.clear_background).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="設定を保存", command=self.save_configuration).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="設定を読み込み", command=self.load_configuration).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="スクリーンショット撮影", command=self.take_screenshot).pack(fill=tk.X, pady=2)

    def create_coordinates_display(self):
        self.coordinates_frame = tk.Frame(self.control_panel)
        self.coordinates_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.coordinates_frame, text="座標情報:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        
        self.coordinates_scrollbar = tk.Scrollbar(self.coordinates_frame)
        self.coordinates_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.coordinates_text = tk.Text(self.coordinates_frame, height=5, width=30,
                                      yscrollcommand=self.coordinates_scrollbar.set)
        self.coordinates_text.pack(fill=tk.BOTH, expand=True)
        self.coordinates_scrollbar.config(command=self.coordinates_text.yview)

    def setup_bindings(self):
        # マウスイベント
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # キーボードイベント - キャンバスにフォーカスを持たせる
        self.canvas.bind("<Up>", self.increase_angle)
        self.canvas.bind("<Down>", self.decrease_angle)
        self.canvas.focus_set()  # キャンバスにフォーカスを設定
        
        # 入力値の変更検出
        self.angle_var.trace_add("write", self.on_input_change)
        self.start_x_var.trace_add("write", self.on_input_change)
        self.start_y_var.trace_add("write", self.on_input_change)
        self.max_reflection_var.trace_add("write", self.on_input_change)

    def increase_angle(self, event=None):  # event=None を追加
        try:
            current_angle = int(self.angle_var.get())
            new_angle = min(1023, current_angle + 1)
            self.angle_var.set(str(new_angle))
            self.simulate()  # 即座にシミュレーションを更新
        except ValueError:
            pass

    def decrease_angle(self, event=None):  # event=None を追加
        try:
            current_angle = int(self.angle_var.get())
            new_angle = max(0, current_angle - 1)
            self.angle_var.set(str(new_angle))
            self.simulate()  # 即座にシミュレーションを更新
        except ValueError:
            pass

    def check_adb_devices(self):
        """ADBデバイスが接続されているか確認する"""
        adb_path = get_adb_path()
        if not adb_path:
            messagebox.showerror("エラー", "ADBが見つかりません。Android SDKがインストールされているか、PATHが正しく設定されているか確認してください。")
            return False

        try:
            result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=5)
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [device for device in devices if device.strip() and not device.strip().endswith('offline')]
            if connected_devices:
                return True
            else:
                messagebox.showerror("エラー", "接続されているAndroidデバイスが見つかりません。デバイスが正しく接続されているか確認してください。")
                return False
        except subprocess.TimeoutExpired:
            messagebox.showerror("エラー", "ADBコマンドがタイムアウトしました。デバイスが応答していません。")
            return False
        except Exception as e:
            messagebox.showerror("エラー", f"ADBコマンドの実行中にエラーが発生しました: {str(e)}")
            return False

    def take_screenshot(self):
        """ADBを使用してスクリーンショットを撮影する"""
        if not self.check_adb_devices():
            return

        adb_path = get_adb_path()
        if not adb_path:
            messagebox.showerror("エラー", "ADBが見つかりません。")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.screenshot_dir, f"screenshot_{timestamp}.png")

            adb_result = subprocess.run([adb_path, "exec-out", "screencap", "-p"], capture_output=True, timeout=5)
            if adb_result.returncode != 0:
                raise subprocess.SubprocessError("ADBコマンドが失敗しました")

            with open(screenshot_path, 'wb') as f:
                f.write(adb_result.stdout)

            if not os.path.exists(screenshot_path):
                raise FileNotFoundError("スクリーンショットファイルが作成されませんでした")

            time.sleep(0.001)
            self.process_image(screenshot_path)

        except subprocess.TimeoutExpired:
            messagebox.showerror("エラー", "スクリーンショット撮影がタイムアウトしました")
        except subprocess.SubprocessError as e:
            messagebox.showerror("エラー", f"スクリーンショット撮影に失敗しました: {str(e)}")
        except Exception as e:
            messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {str(e)}")

    def process_image(self, image_path):
        """スクリーンショット画像を処理して背景として設定する"""
        try:
            image = Image.open(image_path)
            
            # 画像を指定された座標でクロップ
            crop_x, crop_y, crop_width, crop_height = 0, 440, 1080, 1215
            image = image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))
            
            # フィールドのサイズにリサイズ
            image = image.resize((self.field_width, self.field_height), Image.LANCZOS)
            
            # Tkinter用に変換
            self.background_image_tk = ImageTk.PhotoImage(image)
            self.background_image = image
            
            # 画面を再描画
            self.draw_field()
            
            # シミュレーションを再実行
            self.simulate()
            
        except Exception as e:
            messagebox.showerror("エラー", f"画像処理中にエラーが発生しました: {str(e)}")

    def load_background(self):
        file_path = filedialog.askopenfilename(
            title="背景画像を選択",
            filetypes=[("画像ファイル", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        
        if file_path:
            self.process_image(file_path)

    def clear_background(self):
        self.background_image = None
        self.background_image_tk = None
        self.background_id = None
        self.draw_field()

    def draw_field(self):
        self.canvas.delete("all")
        
        # 背景画像の描画
        if self.background_image_tk:
            self.background_id = self.canvas.create_image(
                self.field_width // 2, 
                self.field_height // 2, 
                image=self.background_image_tk
            )
        
        # フィールドの枠を描画
        self.canvas.create_rectangle(0, 0, self.field_width, self.field_height, outline="white")
        
        # グリッド線を描画
        self.draw_grid()
        
        # 障害物を描画
        self.draw_obstacles()
        
        # 開始位置を描画
        self.draw_start_position()
        
        # 軌道を描画
        self.draw_trajectory()

    def draw_grid(self):
        grid_margin = 30
        
        # グリッド線の縁を描画
        self.canvas.create_rectangle(
            grid_margin, grid_margin, 
            self.field_width - grid_margin, self.field_height - grid_margin, 
            outline="pink", dash=(3, 3), width=2
        )
        
        # 縦9分割のグリッド線
        rows = 9
        row_height = (self.field_height - 2 * grid_margin) / rows
        for i in range(1, rows):
            y = grid_margin + i * row_height
            self.canvas.create_line(
                grid_margin, y, 
                self.field_width - grid_margin, y, 
                fill="pink", dash=(2, 2), width=2
            )
        
        # 横8分割のグリッド線
        cols = 8
        col_width = (self.field_width - 2 * grid_margin) / cols
        for i in range(1, cols):
            x = grid_margin + i * col_width
            self.canvas.create_line(
                x, grid_margin, 
                x, self.field_height - grid_margin, 
                fill="pink", dash=(2, 2), width=2
            )

    def draw_obstacles(self):
        for i, obstacle in enumerate(self.obstacles):
            color = "yellow" if i == self.selected_obstacle else "white"
            if obstacle["type"] == "circle":
                size = obstacle["size"]
                x, y = obstacle["x"], obstacle["y"]
                self.canvas.create_oval(x-size, y-size, x+size, y+size, outline=color, width=2)
                
                if "durability" in obstacle:
                    self.canvas.create_text(x, y, text=str(obstacle["durability"]), fill="white")
            else:  # square
                size = obstacle["size"]
                x, y = obstacle["x"], obstacle["y"]
                self.canvas.create_rectangle(x-size, y-size, x+size, y+size, outline=color, width=2)

    def draw_start_position(self):
        try:
            start_x = int(self.start_x_var.get())
            start_y = int(self.start_y_var.get())
            self.canvas.create_oval(start_x-45, start_y-45, start_x+45, start_y+45, outline="red", width=4)
        except ValueError:
            pass

    def draw_trajectory(self):
        if self.trajectory:
            for i in range(1, len(self.trajectory)):
                x1, y1 = self.trajectory[i-1]
                x2, y2 = self.trajectory[i]
                self.canvas.create_line(x1, y1, x2, y2, fill="green", width=5)
                
                if i > 1 and i < len(self.trajectory)-1:
                    self.canvas.create_oval(x1-30, y1-30, x1+30, y1+30, outline="lime", width=5)
            
            if len(self.trajectory) > 0:
                last_x, last_y = self.trajectory[-1]
                self.canvas.create_oval(last_x-30, last_y-30, last_x+30, last_y+30, outline="lime", width=5)

    def simulate(self):
        try:
            start_x = int(self.start_x_var.get())
            start_y = int(self.start_y_var.get())
            angle_val = int(self.angle_var.get())
            max_reflections = int(self.max_reflection_var.get())
            
            # 角度の変換 (0-1023 → ラジアン)
            angle_rad = (angle_val / 1024.0) * 2 * math.pi
            
            # 初期速度ベクトル (速度の大きさは一定)
            velocity = 0.2
            vx = velocity * math.cos(angle_rad)
            vy = velocity * math.sin(angle_rad)
            
            # 軌道の計算
            self.trajectory = [(start_x, start_y)]
            x, y = start_x, start_y
            
            # 障害物のコピーを作成（シミュレーション中に修正するため）
            temp_obstacles = []
            for obstacle in self.obstacles:
                temp_obstacle = obstacle.copy()
                if "durability" in obstacle:
                    temp_obstacle["durability"] = obstacle["durability"]
                temp_obstacles.append(temp_obstacle)
            
            reflection_count = 0
            while reflection_count < max_reflections:
                reflection_occurred = False
                
                # 次の位置の計算
                next_x = x + vx
                next_y = y + vy
                
                # キャラクターの半径
                radius = 30
                
                # フィールド境界での反射チェック
                if next_x - radius <= 0 or next_x + radius >= self.field_width:
                    vx = -vx
                    reflection_occurred = True
                    reflection_count += 1
                
                if next_y - radius <= 0 or next_y + radius >= self.field_height:
                    vy = -vy
                    reflection_occurred = True
                    reflection_count += 1
                
                # 障害物との衝突チェック
                obstacle_hit_index = None
                for i, obstacle in enumerate(temp_obstacles):
                    if obstacle["type"] == "circle":
                        size = obstacle["size"]
                        obstacle_x, obstacle_y = obstacle["x"], obstacle["y"]
                        
                        # キャラクターと障害物の中心間の距離を計算
                        dx = next_x - obstacle_x
                        dy = next_y - obstacle_y
                        distance = math.sqrt(dx*dx + dy*dy)
                        
                        # 円としての衝突判定
                        if distance <= (radius + size):
                            # 内接する正方形の領域に基づいて反射方向を決定
                            if abs(dx) > abs(dy):
                                vx = -vx
                            else:
                                vy = -vy
                            
                            # 耐久回数を減らす
                            if "durability" in obstacle:
                                obstacle["durability"] -= 1
                                if obstacle["durability"] <= 0:
                                    obstacle_hit_index = i
                            
                            reflection_occurred = True
                            reflection_count += 1
                            break
                    else:  # square
                        size = obstacle["size"]
                        obstacle_x, obstacle_y = obstacle["x"], obstacle["y"]
                        
                        # 正方形との衝突判定
                        left_edge = obstacle_x - size
                        right_edge = obstacle_x + size
                        top_edge = obstacle_y - size
                        bottom_edge = obstacle_y + size
                        
                        # 各辺との接触判定
                        touching_left = next_x - radius <= right_edge and next_x > right_edge
                        touching_right = next_x + radius >= left_edge and next_x < left_edge
                        touching_top = next_y - radius <= bottom_edge and next_y > bottom_edge
                        touching_bottom = next_y + radius >= top_edge and next_y < top_edge
                        
                        # 拡張した範囲を考慮
                        expanded_left = left_edge - radius
                        expanded_right = right_edge + radius
                        expanded_top = top_edge - radius
                        expanded_bottom = bottom_edge + radius
                        
                        if (expanded_left <= next_x <= expanded_right and
                            expanded_top <= next_y <= expanded_bottom):
                            
                            if touching_left or touching_right:
                                vx = -vx
                            elif touching_top or touching_bottom:
                                vy = -vy
                            else:
                                # 角との衝突
                                corners = [
                                    (left_edge, top_edge),
                                    (right_edge, top_edge),
                                    (left_edge, bottom_edge),
                                    (right_edge, bottom_edge)
                                ]
                                
                                min_dist = float('inf')
                                for corner_x, corner_y in corners:
                                    dist = math.sqrt((next_x - corner_x)**2 + (next_y - corner_y)**2)
                                    if dist < min_dist:
                                        min_dist = dist
                                
                                if min_dist <= radius:
                                    vx = -vx
                                    vy = -vy
                            
                            reflection_occurred = True
                            reflection_count += 1
                            break
                
                # 障害物が壊れた場合、一時リストから削除
                if obstacle_hit_index is not None:
                    temp_obstacles.pop(obstacle_hit_index)
                
                # 位置の更新
                x += vx
                y += vy
                
                # 反射が発生した場合のみ軌道に追加
                if reflection_occurred:
                    self.trajectory.append((x, y))
                
                # 反射回数が最大値に達した場合は終了
                if reflection_count >= max_reflections:
                    self.trajectory.append((x, y))
                    break
            
            self.draw_field()
        except ValueError:
            # エラーが発生した場合は軌道をクリア
            self.trajectory = []
            self.draw_field()

    def add_obstacle(self):
        try:
            x = int(self.obstacle_x_var.get())
            y = int(self.obstacle_y_var.get())
            size = int(self.obstacle_size_var.get())
            obstacle_type = self.obstacle_type.get()
            
            obstacle = {
                "type": obstacle_type,
                "x": x,
                "y": y,
                "size": size
            }
            
            if obstacle_type == "circle":
                durability = int(self.obstacle_durability_var.get())
                obstacle["durability"] = durability
                obstacle["max_durability"] = durability
            
            self.obstacles.append(obstacle)
            self.selected_obstacle = len(self.obstacles) - 1
            self.draw_field()
            
            self.simulate()
            self.update_coordinates_display()
        except ValueError:
            messagebox.showerror("エラー", "数値を正しく入力してください")

    def remove_obstacle(self):
        if self.selected_obstacle is not None and 0 <= self.selected_obstacle < len(self.obstacles):
            self.obstacles.pop(self.selected_obstacle)
            self.selected_obstacle = None
            self.draw_field()
            self.simulate()

    def reset(self):
        self.trajectory = []
        self.obstacles = []
        self.selected_obstacle = None
        self.draw_field()
        self.update_coordinates_display()

    def save_configuration(self):
        file_path = filedialog.asksaveasfilename(
            title="設定を保存",
            defaultextension=".json",
            filetypes=[("JSON ファイル", "*.json")]
        )
        
        if file_path:
            try:
                import json
                config_data = {
                    "obstacles": self.obstacles,
                    "start_position": {
                        "x": int(self.start_x_var.get()),
                        "y": int(self.start_y_var.get())
                    },
                    "angle": int(self.angle_var.get()),
                    "max_reflections": int(self.max_reflection_var.get())
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)
                
                messagebox.showinfo("成功", f"設定を保存しました: {file_path}")
            except Exception as e:
                messagebox.showerror("エラー", f"設定の保存に失敗しました: {str(e)}")

    def load_configuration(self):
        file_path = filedialog.askopenfilename(
            title="設定を読み込み",
            filetypes=[("JSON ファイル", "*.json")]
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                if "obstacles" in config_data:
                    self.obstacles = config_data["obstacles"]
                
                if "start_position" in config_data:
                    self.start_x_var.set(str(config_data["start_position"]["x"]))
                    self.start_y_var.set(str(config_data["start_position"]["y"]))
                
                if "angle" in config_data:
                    self.angle_var.set(str(config_data["angle"]))
                
                if "max_reflections" in config_data:
                    self.max_reflection_var.set(str(config_data["max_reflections"]))
                
                self.draw_field()
                self.simulate()
                self.update_coordinates_display()
                
                messagebox.showinfo("成功", f"設定を読み込みました: {file_path}")
            except Exception as e:
                messagebox.showerror("エラー", f"設定の読み込みに失敗しました: {str(e)}")

    def update_coordinates_display(self):
        self.coordinates_text.delete(1.0, tk.END)
        
        if self.obstacles:
            self.coordinates_text.insert(tk.END, "障害物:\n")
            for i, obstacle in enumerate(self.obstacles):
                obj_type = "円" if obstacle["type"] == "circle" else "正方形"
                durability_info = ""
                if obstacle["type"] == "circle" and "durability" in obstacle:
                    durability_info = f", 耐久={obstacle['durability']}"
                
                self.coordinates_text.insert(tk.END, 
                    f"{i+1}: {obj_type}, X={obstacle['x']}, Y={obstacle['y']}, サイズ={obstacle['size']}{durability_info}\n")
        else:
            self.coordinates_text.insert(tk.END, "障害物: なし\n")

    def on_canvas_click(self, event):
        x, y = event.x, event.y
        
        try:
            start_x = int(self.start_x_var.get())
            start_y = int(self.start_y_var.get())
            if (start_x - 15 <= x <= start_x + 15 and 
                start_y - 15 <= y <= start_y + 15):
                self.is_dragging_start = True
                self.start_x_var.set(str(x))
                self.start_y_var.set(str(y))
                self.simulate()
                return
        except ValueError:
            pass
        
        for i, obstacle in enumerate(self.obstacles):
            x, y = obstacle["x"], obstacle["y"]
            size = obstacle["size"]
            if (x - size <= event.x <= x + size and 
                y - size <= event.y <= y + size):
                self.selected_obstacle = i
                
                self.obstacle_type.set(obstacle["type"])
                self.obstacle_size_var.set(str(obstacle["size"]))
                self.obstacle_x_var.set(str(obstacle["x"]))
                self.obstacle_y_var.set(str(obstacle["y"]))
                
                if obstacle["type"] == "circle" and "durability" in obstacle:
                    self.obstacle_durability_var.set(str(obstacle["durability"]))
                else:
                    self.obstacle_durability_var.set("3")
                
                self.draw_field()
                return
        
        self.selected_obstacle = None
        self.is_dragging_start = False
        self.draw_field()

    def on_canvas_drag(self, event):
        if self.is_dragging_start:
            self.start_x_var.set(str(event.x))
            self.start_y_var.set(str(event.y))
            self.update_coordinates_display()
            return
            
        if self.selected_obstacle is not None:
            self.obstacles[self.selected_obstacle]["x"] = event.x
            self.obstacles[self.selected_obstacle]["y"] = event.y
            
            self.obstacle_x_var.set(str(event.x))
            self.obstacle_y_var.set(str(event.y))
            
            self.simulate()
            self.update_coordinates_display()

    def on_canvas_release(self, event):
        self.is_dragging_start = False

    def increase_angle_by_ten(self, event):
        """角度を10度増加"""
        try:
            current_angle = int(self.angle_var.get())
            new_angle = min(1023, current_angle + 10)
            self.angle_var.set(str(new_angle))
            self.simulate()  # 即座にシミュレーションを更新
        except ValueError:
            pass

    def decrease_angle_by_ten(self, event):
        """角度を10度減少"""
        try:
            current_angle = int(self.angle_var.get())
            new_angle = max(0, current_angle - 10)
            self.angle_var.set(str(new_angle))
            self.simulate()  # 即座にシミュレーションを更新
        except ValueError:
            pass
        
    def on_input_change(self, *args):
        self.simulate()
        self.update_coordinates_display()

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedToolApp(root)
    root.mainloop()            