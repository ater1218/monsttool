import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import subprocess
import os
import time
from datetime import datetime
import sys
import subprocess
import platform

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
        if avg_brightness < 100:  # 暗い画像の場合
            blur_size = 7
        else:  # 明るい画像の場合
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
            min_area = 410  # 最小面積
            max_area = 750 # 最大面積
            if area < min_area or area > max_area:
                continue
            
            # 縦横比によるフィルタリング
            aspect_ratio = float(w) / h
            ideal_ratio = 0.8  # 理想的な縦横比
            ratio_tolerance = 0.2  # 許容誤差
            if not (ideal_ratio - ratio_tolerance <= aspect_ratio <= ideal_ratio + ratio_tolerance):
                continue
            
            # 円形度（どれだけ円に近いか）チェック
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            min_circularity = 0.1 # 最小円形度
            if circularity < min_circularity:
                continue
            
            # 凸性（へこみがないか）チェック
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / hull_area if hull_area > 0 else 0
            min_solidity = 0.1  # 最小凸性
            if solidity < min_solidity:
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
            min_red_ratio = 0.4  # 赤色ピクセルの最小割合
            if red_ratio < min_red_ratio:
                continue
            
            # すべてのフィルタを通過した検出を結果に追加
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

        # 検出結果をx座標、y座標の順にソート
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
    def __init__(self, root):
        self.root = root
        self.root.title("座標検出くん")
        self.icon_detector = PlayerIconDetector()
        
        self.screenshot_dir = resource_path("screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

        self.setup_ui()
        self.image_path = None
        self.cropped_image = None

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root)
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

        max_width = 550
        if pil_image.width > max_width:
            scale = max_width / pil_image.width
            new_height = int(pil_image.height * scale)
            pil_image = pil_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(pil_image)
        self.preview_label.configure(image=photo)
        self.preview_label.image = photo

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedDetectorUI(root)
    root.mainloop()