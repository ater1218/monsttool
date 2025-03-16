import tkinter as tk
import math
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import subprocess
import os
import tempfile
from datetime import datetime
import sys

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

class MonsterStrikeSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("モンスターストライク反射軌道シミュレーター")
        
        # フィールドサイズの設定
        self.field_width = 640
        self.field_height = 720
        
        # フィールドの余白設定
        self.margin = 5  # 余白のピクセル数

        # メインフレームの作成（余白を実現するため）
        self.main_frame = tk.Frame(root, bg="gray")
        self.main_frame.pack(padx=self.margin, pady=self.margin, side=tk.LEFT)
        
        # キャンバスの作成
        self.canvas = tk.Canvas(root, width=self.field_width, height=self.field_height, bg="black")
        self.canvas.pack(side=tk.LEFT)
        
        # 背景画像の初期化
        self.background_image = None
        self.background_image_tk = None
        self.background_id = None
        
        # 障害物リスト - 初期化をここに移動
        self.obstacles = []
        self.selected_obstacle = None
        
        # 軌道の描画用
        self.trajectory = []
        
        # リアルタイムシミュレーションのフラグ
        self.is_dragging_start = False
        
        # コントロールパネルの作成
        self.control_panel = tk.Frame(root, width=300, height=self.field_height)
        self.control_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 発射角度入力
        self.angle_frame = tk.Frame(self.control_panel)
        self.angle_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.angle_frame, text="発射角度 (0-1023):").pack(side=tk.LEFT)
        self.angle_var = tk.StringVar(value="512")
        self.angle_entry = tk.Entry(self.angle_frame, textvariable=self.angle_var, width=6)
        self.angle_entry.pack(side=tk.LEFT, padx=5)
        
        # 最大反射回数の設定
        self.max_reflection_frame = tk.Frame(self.control_panel)
        self.max_reflection_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.max_reflection_frame, text="最大反射回数:").pack(side=tk.LEFT)
        self.max_reflection_var = tk.StringVar(value="10")
        self.max_reflection_entry = tk.Entry(self.max_reflection_frame, textvariable=self.max_reflection_var, width=6)
        self.max_reflection_entry.pack(side=tk.LEFT, padx=5)
        
        # 開始位置入力
        self.start_pos_frame = tk.Frame(self.control_panel)
        self.start_pos_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.start_pos_frame, text="開始位置:").pack(anchor=tk.W)
        
        self.start_pos_x_frame = tk.Frame(self.start_pos_frame)
        self.start_pos_x_frame.pack(fill=tk.X)
        tk.Label(self.start_pos_x_frame, text="X:").pack(side=tk.LEFT)
        self.start_x_var = tk.StringVar(value="320")
        self.start_x_entry = tk.Entry(self.start_pos_x_frame, textvariable=self.start_x_var, width=6)
        self.start_x_entry.pack(side=tk.LEFT, padx=5)
        
        self.start_pos_y_frame = tk.Frame(self.start_pos_frame)
        self.start_pos_y_frame.pack(fill=tk.X)
        tk.Label(self.start_pos_y_frame, text="Y:").pack(side=tk.LEFT)
        self.start_y_var = tk.StringVar(value="600")
        self.start_y_entry = tk.Entry(self.start_pos_y_frame, textvariable=self.start_y_var, width=6)
        self.start_y_entry.pack(side=tk.LEFT, padx=5)
        
        # 障害物制御
        self.obstacle_frame = tk.Frame(self.control_panel)
        self.obstacle_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(self.obstacle_frame, text="障害物:").pack(anchor=tk.W)
        
        # 障害物タイプ選択
        self.obstacle_type_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_type_frame.pack(fill=tk.X)
        
        self.obstacle_type = tk.StringVar(value="circle")
        tk.Radiobutton(self.obstacle_type_frame, text="円", variable=self.obstacle_type, value="circle").pack(side=tk.LEFT)
        tk.Radiobutton(self.obstacle_type_frame, text="正方形", variable=self.obstacle_type, value="square").pack(side=tk.LEFT)
        
        # 障害物サイズ
        self.obstacle_size_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_size_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_size_frame, text="サイズ:").pack(side=tk.LEFT)
        self.obstacle_size_var = tk.StringVar(value="60")  # デフォルトサイズを60に変更
        self.obstacle_size_entry = tk.Entry(self.obstacle_size_frame, textvariable=self.obstacle_size_var, width=6)
        self.obstacle_size_entry.pack(side=tk.LEFT, padx=5)
        
        # 障害物位置
        self.obstacle_pos_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_pos_frame.pack(fill=tk.X)
        
        self.obstacle_pos_x_frame = tk.Frame(self.obstacle_pos_frame)
        self.obstacle_pos_x_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_pos_x_frame, text="X:").pack(side=tk.LEFT)
        self.obstacle_x_var = tk.StringVar(value="320")
        self.obstacle_x_entry = tk.Entry(self.obstacle_pos_x_frame, textvariable=self.obstacle_x_var, width=6)
        self.obstacle_x_entry.pack(side=tk.LEFT, padx=5)
        
        self.obstacle_pos_y_frame = tk.Frame(self.obstacle_pos_frame)
        self.obstacle_pos_y_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_pos_y_frame, text="Y:").pack(side=tk.LEFT)
        self.obstacle_y_var = tk.StringVar(value="300")
        self.obstacle_y_entry = tk.Entry(self.obstacle_pos_y_frame, textvariable=self.obstacle_y_var, width=6)
        self.obstacle_y_entry.pack(side=tk.LEFT, padx=5)
        
        # 障害物の耐久回数（円の場合のみ）
        self.obstacle_durability_frame = tk.Frame(self.obstacle_frame)
        self.obstacle_durability_frame.pack(fill=tk.X)
        tk.Label(self.obstacle_durability_frame, text="耐久回数:").pack(side=tk.LEFT)
        self.obstacle_durability_var = tk.StringVar(value="3")
        self.obstacle_durability_entry = tk.Entry(self.obstacle_durability_frame, textvariable=self.obstacle_durability_var, width=6)
        self.obstacle_durability_entry.pack(side=tk.LEFT, padx=5)
        
        # ボタン
        self.button_frame = tk.Frame(self.control_panel)
        self.button_frame.pack(padx=10, pady=10, fill=tk.X)
        
        tk.Button(self.button_frame, text="障害物追加", command=self.add_obstacle).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="障害物削除", command=self.remove_obstacle).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="リセット", command=self.reset).pack(fill=tk.X, pady=2)
        
        # 背景画像ボタン
        tk.Button(self.button_frame, text="背景画像を設定", command=self.load_background).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="背景画像を削除", command=self.clear_background).pack(fill=tk.X, pady=2)

        # button_frame 内に以下を追加
        tk.Button(self.button_frame, text="設定を保存", command=self.save_configuration).pack(fill=tk.X, pady=2)
        tk.Button(self.button_frame, text="設定を読み込み", command=self.load_configuration).pack(fill=tk.X, pady=2)

        tk.Button(self.button_frame, text="スクリーンショット撮影", command=self.take_screenshot).pack(fill=tk.X, pady=2) 
        
        self.screenshot_dir = os.path.join(os.path.expanduser("~"), "MonsterStrikeSimulator")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

        # 座標表示エリアの作成
        self.coordinates_frame = tk.Frame(self.control_panel)
        self.coordinates_frame.pack(padx=10, pady=5, fill=tk.X)

        tk.Label(self.coordinates_frame, text="座標情報:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)

        # スクロール可能なテキストエリア
        self.coordinates_scrollbar = tk.Scrollbar(self.coordinates_frame)
        self.coordinates_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.coordinates_text = tk.Text(self.coordinates_frame, height=5, width=30, 
                                    yscrollcommand=self.coordinates_scrollbar.set)
        self.coordinates_text.pack(fill=tk.BOTH, expand=True)
        self.coordinates_scrollbar.config(command=self.coordinates_text.yview)
        
        # 画面の初期化
        self.draw_field()
        
        # 座標表示を初期化
        self.update_coordinates_display()
        
        # クリックイベントの設定
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # キーボードイベントの設定
        self.root.bind("<Left>", self.decrease_angle)
        self.root.bind("<Right>", self.increase_angle)
        self.root.bind("<Up>", self.increase_angle)
        self.root.bind("<Down>", self.decrease_angle)
        
        # 変更検出のためのトレース
        self.angle_var.trace_add("write", self.on_input_change)
        self.start_x_var.trace_add("write", self.on_input_change)
        self.start_y_var.trace_add("write", self.on_input_change)
        self.max_reflection_var.trace_add("write", self.on_input_change)
        
    def load_background(self):
        file_path = filedialog.askopenfilename(
            title="背景画像を選択",
            filetypes=[("画像ファイル", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        
        if not file_path:
            return  # ユーザーがキャンセルした場合は処理を終了

        try:
            # PILで画像を開く
            image = Image.open(file_path)

            # 画像を指定された座標でクロップ
            crop_x, crop_y, crop_width, crop_height = 0, 440, 1080, 1215
            image = image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))

            # フィールドのサイズにリサイズ
            image = image.resize((self.field_width, self.field_height), Image.LANCZOS)

            # Tkinter用に変換
            self.background_image_tk = ImageTk.PhotoImage(image)
            self.background_image = image

            # 画面を再描画
            try:
                self.draw_field()
            except Exception as e:
                messagebox.showwarning("警告", f"画面の再描画に失敗しました: {str(e)}")

        except Exception as e:
            messagebox.showerror("エラー", f"画像の読み込みに失敗しました: {str(e)}")

    def check_adb_devices(self):
        """ADBに接続されているデバイスを確認する"""
        try:
            result = subprocess.run(
                ["adb", "devices"], 
                capture_output=True, 
                text=True,
                timeout=3
            )
            
            # 出力を解析して接続デバイスの有無を確認
            lines = result.stdout.strip().split('\n')
            
            # 最初の行は「List of devices attached」なので、それ以降の行を確認
            if len(lines) > 1:
                for line in lines[1:]:
                    if line.strip() and not line.strip().endswith('unauthorized') and not line.strip().endswith('offline'):
                        return True
            
            return False
        except Exception:
            return False

    def take_screenshot(self):
        """ADBを使用してAndroidデバイスのスクリーンショットを撮影"""
        import os
        import time
        import subprocess
        from datetime import datetime
        
        if not self.check_adb_devices():
            return

        adb_path = get_adb_path()
        if not adb_path:
            messagebox.showerror("エラー", "ADBが見つかりません。")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.screenshot_dir, f"screenshot_{timestamp}.png")

            adb_result = subprocess.run(
                ["adb", "exec-out", "screencap", "-p"], 
                capture_output=True, 
                timeout=5
            )

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
        """スクリーンショット画像を読み込み、トリミングとリサイズを行って背景に設定"""
        try:
            # PILで画像を開く
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
        
    def clear_background(self):
        self.background_image = None
        self.background_image_tk = None
        self.background_id = None
        self.draw_field()
        
    def draw_field(self):
        self.canvas.delete("all")
        
        # 背景画像を描画
        if self.background_image_tk:
            self.background_id = self.canvas.create_image(
                self.field_width // 2, 
                self.field_height // 2, 
                image=self.background_image_tk
            )
                
        # フィールドの枠を描画
        self.canvas.create_rectangle(0, 0, self.field_width, self.field_height, outline="white")
        
        # グリッド線を描画
        grid_margin = 30  # グリッド線の内側マージン

        # グリッド線の縁を描画（長方形）
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

        # 障害物を描画
        for i, obstacle in enumerate(self.obstacles):
            color = "yellow" if i == self.selected_obstacle else "white"
            if obstacle["type"] == "circle":
                size = obstacle["size"]
                x, y = obstacle["x"], obstacle["y"]
                self.canvas.create_oval(x-size, y-size, x+size, y+size, outline=color, width=2)
                
                # 耐久回数を表示（円の場合のみ）
                if "durability" in obstacle:
                    self.canvas.create_text(x, y, text=str(obstacle["durability"]), fill="white")
            else:  # square
                size = obstacle["size"]
                x, y = obstacle["x"], obstacle["y"]
                self.canvas.create_rectangle(x-size, y-size, x+size, y+size, outline=color, width=2)
        
        # 開始位置を描画
        try:
            start_x = int(self.start_x_var.get())
            start_y = int(self.start_y_var.get())
            self.canvas.create_oval(start_x-45, start_y-45, start_x+45, start_y+45, outline="red", width=4)
        except ValueError:
            pass
        
        # 軌道を描画
        if self.trajectory:
            for i in range(1, len(self.trajectory)):
                x1, y1 = self.trajectory[i-1]
                x2, y2 = self.trajectory[i]
                self.canvas.create_line(x1, y1, x2, y2, fill="green", width=5)
                
                # 反射ポイントを強調表示 (開始点と終点を除く)
                if i > 1 and i < len(self.trajectory)-1:
                    self.canvas.create_oval(x1-30, y1-30, x1+30, y1+30, outline="lime", width=5)
            
            # 最終位置を強調表示
            if len(self.trajectory) > 0:
                last_x, last_y = self.trajectory[-1]
                self.canvas.create_oval(x1-30, y1-30, x1+30, y1+30, outline="lime", width=5)
    
    def on_input_change(self, *args):
        # 入力値が変更されたらリアルタイムで再計算
        self.simulate()
        self.update_coordinates_display()
    
    def increase_angle(self, event):
        try:
            current_angle = int(self.angle_var.get())
            new_angle = min(1023, current_angle + 1)
            self.angle_var.set(str(new_angle))
            # simulate()はトレースで自動的に呼び出される
        except ValueError:
            pass
    
    def decrease_angle(self, event):
        try:
            current_angle = int(self.angle_var.get())
            new_angle = max(0, current_angle - 1)
            self.angle_var.set(str(new_angle))
            # simulate()はトレースで自動的に呼び出される
        except ValueError:
            pass
    
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
            
            # 円障害物の場合は耐久回数を設定
            if obstacle_type == "circle":
                durability = int(self.obstacle_durability_var.get())
                obstacle["durability"] = durability
                obstacle["max_durability"] = durability
            
            self.obstacles.append(obstacle)
            self.selected_obstacle = len(self.obstacles) - 1
            self.draw_field()
            
            # 障害物が追加されたらリアルタイムで再計算
            self.simulate()
            
            # 座標表示を更新
            self.update_coordinates_display()
        except ValueError:
            messagebox.showerror("エラー", "数値を正しく入力してください")
    
    def remove_obstacle(self):
        if self.selected_obstacle is not None and 0 <= self.selected_obstacle < len(self.obstacles):
            self.obstacles.pop(self.selected_obstacle)
            self.selected_obstacle = None
            self.draw_field()
            
            # 障害物が削除されたらリアルタイムで再計算
            self.simulate()

    def update_coordinates_display(self):
        """座標情報テキストエリアを更新する"""
        self.coordinates_text.delete(1.0, tk.END)
        
        # 障害物座標
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
                
                # 例: オブジェクトの半径が 30 の場合
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
                        # 円障害物の判定
                        size = obstacle["size"]
                        obstacle_x, obstacle_y = obstacle["x"], obstacle["y"]
                        
                        # キャラクターの半径（仮定値）
                        character_radius = 30

                        # キャラクターと障害物の中心間の距離を計算
                        dx = next_x - obstacle_x
                        dy = next_y - obstacle_y
                        distance = math.sqrt(dx*dx + dy*dy)
                        
                        # 円としての衝突判定（キャラクター半径 + 障害物半径より小さければ衝突）
                        if distance <= (character_radius + size):
                            # 衝突発生：内接する正方形の領域に基づいて反射方向を決定
                            
                            # 内接する正方形のどの部分に当たったかを判定
                            if abs(dx) > abs(dy):
                                # 左右の壁に衝突
                                vx = -vx
                            else:
                                # 上下の壁に衝突
                                vy = -vy
                            
                            # 耐久回数を減らす
                            if "durability" in obstacle:
                                obstacle["durability"] -= 1
                                # 耐久回数が0になったら障害物を消す
                                if obstacle["durability"] <= 0:
                                    obstacle_hit_index = i
                            
                            reflection_occurred = True
                            reflection_count += 1
                            break
                    else:  # square
                        size = obstacle["size"]
                        obstacle_x, obstacle_y = obstacle["x"], obstacle["y"]
                        
                        # キャラクターの半径
                        character_radius = 30
                        
                        # 正方形の辺との距離を計算
                        left_edge = obstacle_x - size
                        right_edge = obstacle_x + size
                        top_edge = obstacle_y - size
                        bottom_edge = obstacle_y + size
                        
                        # キャラクターが正方形の各辺に接触しているかチェック
                        touching_left = next_x - character_radius <= right_edge and next_x > right_edge
                        touching_right = next_x + character_radius >= left_edge and next_x < left_edge
                        touching_top = next_y - character_radius <= bottom_edge and next_y > bottom_edge
                        touching_bottom = next_y + character_radius >= top_edge and next_y < top_edge
                        
                        # 正方形の範囲を拡張してキャラクターのサイズを考慮
                        expanded_left = left_edge - character_radius
                        expanded_right = right_edge + character_radius
                        expanded_top = top_edge - character_radius
                        expanded_bottom = bottom_edge + character_radius
                        
                        # 拡張した範囲内にキャラクターの中心があるかチェック
                        if (expanded_left <= next_x <= expanded_right and
                            expanded_top <= next_y <= expanded_bottom):
                            
                            # 水平方向の衝突
                            if touching_left or touching_right:
                                vx = -vx
                            # 垂直方向の衝突
                            elif touching_top or touching_bottom:
                                vy = -vy
                            # 角との衝突（どの辺にも触れていない場合）
                            else:
                                # 最も近い角を見つける
                                corners = [
                                    (left_edge, top_edge),    # 左上
                                    (right_edge, top_edge),   # 右上
                                    (left_edge, bottom_edge), # 左下
                                    (right_edge, bottom_edge) # 右下
                                ]
                                
                                # 最も近い角との距離を計算
                                min_dist = float('inf')
                                for corner_x, corner_y in corners:
                                    dist = math.sqrt((next_x - corner_x)**2 + (next_y - corner_y)**2)
                                    if dist < min_dist:
                                        min_dist = dist
                                
                                # 角との衝突判定
                                if min_dist <= character_radius:
                                    # 角からの反射方向を計算（ビリヤードのような反射）
                                    dx = next_x - obstacle_x
                                    dy = next_y - obstacle_y
                                    
                                    # 入射角と同じ角度で反射
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
    
    def reset(self):
        self.trajectory = []
        self.obstacles = []
        self.selected_obstacle = None
        self.draw_field()
        
        # 座標表示を更新
        self.update_coordinates_display()
    
    def on_canvas_click(self, event):
        x, y = event.x, event.y
        
        # 開始位置の近くでクリックした場合、開始位置を移動モードに
        try:
            start_x = int(self.start_x_var.get())
            start_y = int(self.start_y_var.get())
            if (start_x - 15 <= x <= start_x + 15 and 
                start_y - 15 <= y <= start_y + 15):
                self.is_dragging_start = True
                # 開始位置の更新
                self.start_x_var.set(str(x))
                self.start_y_var.set(str(y))
                self.simulate()
                return
        except ValueError:
            pass
        
        # 障害物選択
        for i, obstacle in enumerate(self.obstacles):
            x, y = obstacle["x"], obstacle["y"]
            size = obstacle["size"]
            if (x - size <= event.x <= x + size and 
                y - size <= event.y <= y + size):
                self.selected_obstacle = i
                
                # 障害物の情報をコントロールパネルに反映
                self.obstacle_type.set(obstacle["type"])
                self.obstacle_size_var.set(str(obstacle["size"]))
                self.obstacle_x_var.set(str(obstacle["x"]))
                self.obstacle_y_var.set(str(obstacle["y"]))
                
                # 円の場合は耐久回数も表示
                if obstacle["type"] == "circle" and "durability" in obstacle:
                    self.obstacle_durability_var.set(str(obstacle["durability"]))
                else:
                    self.obstacle_durability_var.set("3")  # デフォルト値
                
                self.draw_field()
                return
        
        # 背景をクリックした場合
        self.selected_obstacle = None
        self.is_dragging_start = False
        self.draw_field()
    
    def on_canvas_drag(self, event):
        # 開始位置をドラッグ中
        if self.is_dragging_start:
            # 開始位置の更新
            self.start_x_var.set(str(event.x))
            self.start_y_var.set(str(event.y))
            # 座標表示を更新
            self.update_coordinates_display()
            return
            
        # 選択した障害物を移動
        if self.selected_obstacle is not None:
            self.obstacles[self.selected_obstacle]["x"] = event.x
            self.obstacles[self.selected_obstacle]["y"] = event.y
            
            # コントロールパネルの値も更新
            self.obstacle_x_var.set(str(event.x))
            self.obstacle_y_var.set(str(event.y))
            
            # リアルタイムで再計算
            self.simulate()
            
            # 座標表示を更新
            self.update_coordinates_display()
    
    def save_configuration(self):
        """現在の障害物と開始位置の設定を保存する"""
        file_path = filedialog.asksaveasfilename(
            title="設定を保存",
            defaultextension=".json",
            filetypes=[("JSON ファイル", "*.json")]
        )
        
        if not file_path:
            return  # ユーザーがキャンセルした場合は処理を終了
        
        try:
            import json
            
            # 保存するデータを作成
            config_data = {
                "obstacles": self.obstacles,
                "start_position": {
                    "x": int(self.start_x_var.get()),
                    "y": int(self.start_y_var.get())
                },
                "angle": int(self.angle_var.get()),
                "max_reflections": int(self.max_reflection_var.get())
            }
            
            # JSONファイルに書き込み
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            
            messagebox.showinfo("成功", f"設定を保存しました: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました: {str(e)}")

    def load_configuration(self):
        """保存された障害物と開始位置の設定を読み込む"""
        file_path = filedialog.askopenfilename(
            title="設定を読み込み",
            filetypes=[("JSON ファイル", "*.json")]
        )
        
        if not file_path:
            return  # ユーザーがキャンセルした場合は処理を終了
        
        try:
            import json
            
            # JSONファイルから読み込み
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 障害物データの読み込み
            if "obstacles" in config_data:
                self.obstacles = config_data["obstacles"]
            
            # 開始位置の読み込み
            if "start_position" in config_data:
                self.start_x_var.set(str(config_data["start_position"]["x"]))
                self.start_y_var.set(str(config_data["start_position"]["y"]))
            
            # 角度の読み込み
            if "angle" in config_data:
                self.angle_var.set(str(config_data["angle"]))
            
            # 最大反射回数の読み込み
            if "max_reflections" in config_data:
                self.max_reflection_var.set(str(config_data["max_reflections"]))
            
            # 画面を再描画し、シミュレーションを実行
            self.draw_field()
            self.simulate()
            
            # 座標表示を更新
            self.update_coordinates_display()
            
            messagebox.showinfo("成功", f"設定を読み込みました: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"設定の読み込みに失敗しました: {str(e)}")

    def on_canvas_release(self, event):
        self.is_dragging_start = False

if __name__ == "__main__":
    root = tk.Tk()
    app = MonsterStrikeSimulator(root)
    root.mainloop()
