import time
import cv2
import numpy as np
import subprocess
import tempfile
import os
import threading
from PyQt5.QtCore import Qt, QObject, QTimer, QPropertyAnimation, pyqtSignal, QSize, QPoint, QEasingCurve
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QImage, QPixmap, QIcon
from PyQt5.QtWidgets import QTableView, QFrame, QProgressBar, QLabel, QComboBox, QVBoxLayout, QHBoxLayout, QSplitter, QGraphicsOpacityEffect, QSizePolicy, QToolButton
from initialize import *


# 图标目录
IMAGE_DIR = os.path.join(Run_Directory, 'Images')


class ClickableLabel(QLabel):
    """可点击的图片标签 -> 用于居中的播放/暂停按钮。"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 接受左键按下，避免事件冒泡到父控件导致重复触发
        if event.button() == Qt.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # 在控件范围内左键弹起时触发点击
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class VideoWidget(QFrame):
    """视频显示控件"""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("videoWidget")
        self.setStyleSheet("#videoWidget { background-color: #000; }")
        # 开启鼠标追踪，使鼠标移动（无需按键）即可触发 mouseMoveEvent
        self.setMouseTracking(True)

        # 加载居中按钮图标（从配置文件读取，支持用户自定义）
        self.play_icon = QIcon(os.path.join(Run_Directory, configure_data.get("播放按钮图标", "./Images/play.png")))
        self.pause_icon = QIcon(os.path.join(Run_Directory, configure_data.get("暂停按钮图标", "./Images/pause.png")))
        # 加载侧边按钮图标（从配置文件读取，支持用户自定义）
        self.camera_icon = QIcon(os.path.join(Run_Directory, configure_data.get("截图按钮图标", "./Images/camera.png")))
        self.forward_icon = QIcon(os.path.join(Run_Directory, configure_data.get("快退10s按钮图标", "./Images/speed_back_10s.png")))
        self.backward_icon = QIcon(os.path.join(Run_Directory, configure_data.get("快进10s按钮图标", "./Images/speed_up_10s.png")))
        
        # 记录图标加载状态
        for name, icon in [("播放按钮图标", self.play_icon), ("暂停按钮图标", self.pause_icon),
                           ("截图按钮图标", self.camera_icon), ("快退10s按钮图标", self.forward_icon),
                           ("快进10s按钮图标", self.backward_icon)]:
            if icon.isNull():
                logger.warning(f"{name}加载失败，图标为空")
            else:
                logger.info(f"{name}加载成功")

        # 视频标签
        self.video_label = QLabel(self)
        self.video_label.setObjectName("videoLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 视频画面不拦截鼠标事件，交给父控件处理（进入/移动/点击）
        self.video_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 居中按钮（图片形式）
        self.center_button = ClickableLabel(self)
        self.center_button.setObjectName("centerButton")
        self.center_button.setFixedSize(80, 80)
        self.center_button.setAlignment(Qt.AlignCenter)
        self.center_button.setPixmap(self.play_icon.pixmap(44, 44))
        self.center_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.7); border-radius: 40px;")
        self.center_button.hide()
        # 点击图标 -> 播放/暂停
        self.center_button.clicked.connect(self.toggle_play_pause)

        # 截图按钮（居中播放/暂停图标的左侧）
        self.camera_button = ClickableLabel(self)
        self.camera_button.setFixedSize(64, 64)
        self.camera_button.setAlignment(Qt.AlignCenter)
        self.camera_button.setPixmap(self.camera_icon.pixmap(48, 48))
        self.camera_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.6); border-radius: 32px;")
        self.camera_button.setToolTip("截图")
        self.camera_button.hide()
        self.camera_button.clicked.connect(self.take_screenshot)

        # +10s 按钮（居中播放/暂停图标的右上）
        self.forward_button = ClickableLabel(self)
        self.forward_button.setFixedSize(64, 64)
        self.forward_button.setAlignment(Qt.AlignCenter)
        self.forward_button.setPixmap(self.forward_icon.pixmap(52, 44))
        self.forward_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.6); border-radius: 32px;")
        self.forward_button.setToolTip("快进 10 秒")
        self.forward_button.hide()
        self.forward_button.clicked.connect(self.seek_forward)

        # -10s 按钮（居中播放/暂停图标的右下）
        self.backward_button = ClickableLabel(self)
        self.backward_button.setFixedSize(64, 64)
        self.backward_button.setAlignment(Qt.AlignCenter)
        self.backward_button.setPixmap(self.backward_icon.pixmap(52, 44))
        self.backward_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.6); border-radius: 32px;")
        self.backward_button.setToolTip("快退 10 秒")
        self.backward_button.hide()
        self.backward_button.clicked.connect(self.seek_backward)

        # 透明度效果
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.0)
        self.center_button.setGraphicsEffect(self.opacity_effect)

        # 动画
        self.show_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.show_animation.setDuration(300)
        self.show_animation.setEndValue(1.0)

        self.hide_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.hide_animation.setDuration(300)
        self.hide_animation.setEndValue(0.0)

        # 定时器（鼠标离开后延迟隐藏控制区）
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_controls)

        # 底部控制台（覆盖在视频底部，鼠标进入时滑出）
        self._center_icon_is_pause = False
        self.console = Console(self)
        self.console.setFixedHeight(72)
        self._console_visible = False
        self.console.move(0, self.height())

        # 控制台滑动动画
        self.console_animation = QPropertyAnimation(self.console, b"pos", self)
        self.console_animation.setDuration(220)
        self.console_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 控制台按钮 -> 播放/暂停、重播
        self.console.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.console.replay_button.clicked.connect(self.replay_video)

    def _slide_console(self, y: int) -> None:
        """将控制台滑动到指定 y 坐标。"""
        self.console_animation.stop()
        self.console_animation.setStartValue(self.console.pos())
        self.console_animation.setEndValue(QPoint(0, y))
        self.console_animation.start()

    def show_controls(self) -> None:
        """显示控制区（居中按钮 + 底部控制台）并重置 5 秒无操作自动隐藏计时。"""
        if not self._has_media():
            self.hide_controls()
            return
        self.sync_controls()
        # 居中按钮
        self.center_button.show()
        self.show_animation.stop()
        self.show_animation.start()
        # 侧边按钮
        self.camera_button.show()
        self.forward_button.show()
        self.backward_button.show()
        # 底部控制台从下滑出
        if not self._console_visible:
            self._console_visible = True
            self._slide_console(self.height() - self.console.height())
        # 5 秒无鼠标移动则自动隐藏
        self.hide_timer.start(5000)

    def hide_controls(self) -> None:
        """隐藏控制区（居中按钮 + 侧边按钮 + 底部控制台）。"""
        self.hide_timer.stop()
        self.hide_animation.stop()
        self.hide_animation.start()
        QTimer.singleShot(300, self.center_button.hide)
        self.camera_button.hide()
        self.forward_button.hide()
        self.backward_button.hide()
        if self._console_visible:
            self._console_visible = False
            self._slide_console(self.height())

    def schedule_hide_controls(self) -> None:
        """鼠标离开后短暂延迟隐藏。"""
        self.hide_timer.stop()
        self.hide_timer.start(400)

    def cancel_hide_controls(self) -> None:
        """取消隐藏。"""
        self.hide_timer.stop()

    def sync_controls(self) -> None:
        """同步居中图标与控制台播放/暂停图标。"""
        self._update_center_icon()
        if hasattr(self, 'console'):
            self.console.sync_play_button()

    def _has_media(self) -> bool:
        """是否已加载视频。"""
        player = configure_data.get("播放器地址")
        return player is not None and bool(getattr(player, 'has_media', lambda: False)())

    def _update_center_icon(self) -> None:
        """根据播放状态更新居中图标：播放中显示暂停图标，否则显示播放图标。"""
        player = configure_data.get("播放器地址")
        is_playing = player is not None and getattr(player, 'is_playing', False)
        if is_playing != self._center_icon_is_pause:
            self._center_icon_is_pause = is_playing
            if is_playing:
                self.center_button.setPixmap(self.pause_icon.pixmap(44, 44))
            else:
                self.center_button.setPixmap(self.play_icon.pixmap(44, 44))

    def toggle_play_pause(self) -> None:
        """播放/暂停切换（点击居中图标、视频区域或控制台按钮均可触发）。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None or not bool(getattr(player, 'has_media', lambda: False)()):
                return
            if player.is_playing:
                player.pause()
                logger.info("视频暂停")
            elif player.paused:
                player.resume()
                logger.info("视频恢复播放")
            else:
                player.play()
                logger.info("视频开始播放")
            self.sync_controls()
            self.show_controls()
        except Exception as e:
            logger.error(f"播放/暂停切换失败: {e}")

    def replay_video(self) -> None:
        """从头重播当前视频。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None or not bool(getattr(player, 'has_media', lambda: False)()):
                return
            player.replay()
            logger.info("视频重播")
            self.sync_controls()
            self.show_controls()
        except Exception as e:
            logger.error(f"重播失败: {e}")

    def take_screenshot(self) -> None:
        """截图当前视频帧。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None or not bool(getattr(player, 'has_media', lambda: False)()):
                return
            path = player.screenshot()
            if path:
                logger.info(f"截图保存成功: {path}")
            else:
                logger.warning("截图保存失败")
            self.show_controls()
        except Exception as e:
            logger.error(f"截图失败: {e}")

    def seek_forward(self) -> None:
        """快进 10 秒。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None or not bool(getattr(player, 'has_media', lambda: False)()):
                return
            old_pos = player.current_position
            player.set_position(old_pos + 10000)
            logger.info(f"快进10秒: {old_pos}ms -> {player.current_position}ms")
            self.show_controls()
        except Exception as e:
            logger.error(f"快进失败: {e}")

    def seek_backward(self) -> None:
        """快退 10 秒。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None or not bool(getattr(player, 'has_media', lambda: False)()):
                return
            old_pos = player.current_position
            player.set_position(old_pos - 10000)
            logger.info(f"快退10秒: {old_pos}ms -> {player.current_position}ms")
            self.show_controls()
        except Exception as e:
            logger.error(f"快退失败: {e}")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """重写鼠标单击事件 -> 点击视频区域任意位置播放/暂停。"""
        if event.button() == Qt.LeftButton:
            self.toggle_play_pause()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """重写鼠标移动事件"""
        self.show_controls()

    def enterEvent(self, event: QMouseEvent) -> None:
        """重写进入事件"""
        self.show_controls()
        # 对全按键进行捕获
        self.grabKeyboard()

    def leaveEvent(self, event: QMouseEvent) -> None:
        """重写离开事件"""
        self.schedule_hide_controls()
        # 解除对全按键进行捕获
        self.releaseKeyboard()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """重写按键按下事件"""
        try:
            # 获取播放器地址
            player: VideoPlayer = configure_data["播放器地址"]

            # 根据对应的按键做对应的操作
            if event.key() == Qt.Key_Left and (player.is_playing or player.paused):
                # 快退
                player.set_position(player.current_position - configure_data["快退秒数"] * 1000)
            elif event.key() == Qt.Key_Right and (player.is_playing or player.paused):
                # 快进
                player.set_position(player.current_position + configure_data["快进秒数"] * 1000)
            elif event.key() == Qt.Key_Up and (player.is_playing or player.paused):
                # 加音量
                player.set_volume(player.volume + configure_data["加音量数"])
            elif event.key() == Qt.Key_Down and (player.is_playing or player.paused):
                # 减音量
                player.set_volume(player.volume - configure_data["减音量数"])
            elif event.key() == Qt.Key_Space and (player.is_playing or player.paused):
                # 暂停、播放
                self.toggle_play_pause()
            elif event.key() == Qt.Key_M and (player.is_playing or player.paused):
                # 获取表格地址
                table: QTableView = configure_data["表格页地址"]
                # 添加标记
                table.add_row([player.current_position, ""])
            elif event.key() == Qt.Key_S and (player.is_playing or player.paused):
                # 获取表格、简介控件地址
                table: QTableView = configure_data["表格页地址"]
                blurb_frame: QFrame = configure_data["简介框架地址"]
                # 获取简介、索引数据
                blurb_data: str = blurb_frame.video_blur.toPlainText()
                index_data: list = table.get_data()
                # 创建数据用于写入文件
                hash_dict: dict = {
                    "简介": blurb_data,
                    "索引": index_data
                }
                # 写入文件
                with open(os.path.join(Run_Directory, f'Configure/Index/{blurb_frame.video_name.toolTip()}.json'), 'w+', encoding='utf-8') as fp:
                    json.dump(hash_dict, fp, indent=4, ensure_ascii=False)
        except Exception as e:
            pass

    def resizeEvent(self, event) -> None:
        """重写调整尺寸事件"""
        # 调整视频标签大小
        self.video_label.resize(self.size())
        # 按新宽度重新绘制当前帧（拖动分割条/改窗口大小都即时生效）
        player = configure_data.get("播放器地址")
        if player is not None and hasattr(player, 'redraw_frame'):
            player.redraw_frame()
        # 计算中心坐标
        cx = self.width() // 2
        cy = self.height() // 2
        # 调整居中按钮位置
        self.center_button.move(
            cx - self.center_button.width() // 2,
            cy - self.center_button.height() // 2
        )
        # 调整侧边按钮位置（截图最左，快进/快退最右，Y 坐标不变）
        margin = 24
        self.camera_button.move(
            margin,
            cy - self.camera_button.height() // 2
        )
        self.forward_button.move(
            self.width() - self.forward_button.width() - margin,
            cy - self.forward_button.height() // 2 - 56
        )
        self.backward_button.move(
            self.width() - self.backward_button.width() - margin,
            cy - self.backward_button.height() // 2 + 56
        )
        # 调整底部控制台位置（保持显示/隐藏状态）
        self.console.resize(self.width(), self.console.height())
        if self._console_visible:
            self.console.move(0, self.height() - self.console.height())
        else:
            self.console.move(0, self.height())


class Progress(QProgressBar):
    """进度条控件"""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """重写鼠标点击事件 -> 视频跳转"""
        try:
            # 获取播放器地址
            player: VideoPlayer = configure_data["播放器地址"]
            # 计算点击位置对应的视频位置
            if player.duration > 0:
                position = int(player.duration * event.pos().x() / self.width())
                player.set_position(position)
                # 立即更新进度条显示
                self.setValue(position)
                # 通知控制台更新时间标签
                console = self.parent()
                if isinstance(console, Console):
                    console.update_time_label()
        except Exception as e:
            pass


class VideoPlayer:
    """视频播放器类"""

    def __init__(self, parent=None):
        self.parent = parent
        self.cap = None
        self.is_playing = False
        self.paused = False
        self.current_position = 0
        self.duration = 0
        self.volume = 50
        self.playback_rate = 1.0

        # 音频相关
        self.audio_process = None
        self.audio_paused = False
        self.audio_position = 0
        self.video_path = None
        self.audio_temp = None        # 抽取出的音频临时文件路径
        self.audio_rate = 1.0         # 该音频临时文件已应用的倍速
        self.audio_loaded_path = None # 已加载进 pygame 的音频路径
        self._temp_files = []         # 所有生成过的音频临时文件（用于清理）
        self.current_frame = None     # 最近一帧（BGR），用于截图
        self._play_start_clock = 0.0    # 同步基准：单调时钟
        self._play_start_position = 0   # 同步基准：视频位置(ms)

    def set_video_output(self, video_widget):
        """设置视频输出控件"""
        self.video_widget = video_widget

    def has_media(self) -> bool:
        """是否已加载视频文件。"""
        return bool(self.video_path)

    def set_media(self, media_url):
        """设置媒体文件"""
        # 释放之前的资源
        self.stop()
        try:
            self.video_path = media_url.toLocalFile()
            logger.info(f"设置媒体文件: {self.video_path}")
            self._open_video()
            self._prepare_audio()
        except Exception as e:
            logger.error(f"设置媒体文件失败: {e}")

    def _open_video(self):
        """打开当前视频文件并获取时长信息。"""
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            logger.error(f"视频文件打开失败: {self.video_path}")
            return
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.duration = int(frame_count / fps * 1000)
        logger.info(f"视频已打开: {self.video_path}, 时长: {self.duration}ms, FPS: {fps}")
        # 通知控制台更新进度条最大值
        timer = configure_data.get("定时器地址")
        if timer is not None and isinstance(getattr(timer, 'parent', lambda: None)(), Console):
            console = timer.parent()
            console.progress.setMaximum(self.duration)
            console.update_time_label()

    def replay(self):
        """从头重播当前视频。"""
        if not self.video_path:
            return
        try:
            logger.info(f"重播视频: {self.video_path}")
            self.stop()
            self._open_video()
            self.current_position = 0
            self.play()
        except Exception as e:
            logger.error(f"重播失败: {e}")

    def screenshot(self):
        """保存当前帧为截图（原视频尺寸），返回保存路径。"""
        if not self.video_path or self.current_frame is None:
            logger.warning("截图失败: 无视频帧可截图")
            return None
        try:
            # 截图保存根目录（相对路径基于程序运行目录）
            base_dir = configure_data.get("默认截图保存路径", "./Images/Screenshot/")
            if not os.path.isabs(base_dir):
                base_dir = os.path.normpath(os.path.join(Run_Directory, base_dir))
            # 以文件指纹作为子目录
            fingerprint_dir = fingerprint(self.video_path)
            sub_dir = os.path.join(base_dir, fingerprint_dir)
            os.makedirs(sub_dir, exist_ok=True)
            # 帧数与时间戳
            frame_no = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) if self.cap else 0
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(sub_dir, f"{timestamp}_{frame_no}.png")
            i = 1
            while os.path.exists(path):
                path = os.path.join(sub_dir, f"{timestamp}_{frame_no}_{i}.png")
                i += 1
            if cv2.imwrite(path, self.current_frame):
                logger.info(f"截图已保存: {path}")
                return path
            logger.error("截图保存失败: cv2.imwrite 返回 False")
            return None
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def _ensure_mixer(self) -> bool:
        """初始化 pygame.mixer，返回是否可用。"""
        try:
            import pygame
            if not pygame.mixer.get_init():
                try:
                    pygame.mixer.init(frequency=44100, size=-16, channels=2)
                except Exception:
                    pygame.mixer.init()
            return pygame.mixer.get_init() is not None
        except Exception as e:
            return False

    def _atempo_filter(self, rate: float) -> str:
        """把任意倍速转成 atempo 滤镜链（atempo 单段限 0.5~2.0）。"""
        if rate <= 0:
            rate = 1.0
        parts = []
        while rate > 2.0:
            parts.append('atempo=2.0')
            rate /= 2.0
        while rate < 0.5:
            parts.append('atempo=0.5')
            rate /= 0.5
        parts.append(f'atempo={rate:.6f}')
        return ','.join(parts)

    def _cleanup_audio_file(self) -> None:
        """删除所有音频临时文件。"""
        for f in getattr(self, '_temp_files', []):
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        self._temp_files = []
        self.audio_temp = None
        self.audio_rate = 1.0
        self.audio_loaded_path = None

    def _extract_audio_async(self) -> None:
        """后台线程：用 ffmpeg 把当前视频音频抽成临时 WAV（带当前倍速）。"""
        video_path = self.video_path
        rate = self.playback_rate
        if not video_path:
            return
        self._audio_gen = getattr(self, '_audio_gen', 0) + 1
        gen = self._audio_gen

        def worker():
            temp_file = os.path.join(tempfile.gettempdir(), f"mctl_{os.getpid()}_{gen}_{int(time.time() * 1000)}.wav")
            try:
                cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-ac', '2', '-ar', '44100',
                       '-af', self._atempo_filter(rate), temp_file]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                   timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
                if gen != self._audio_gen:
                    # 已有更新的提取任务，丢弃本次结果
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    return
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    self.audio_temp = temp_file
                    self.audio_rate = rate
                    if hasattr(self, '_temp_files'):
                        self._temp_files.append(temp_file)
                elif os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _prepare_audio(self) -> None:
        """为当前视频准备音频（清理旧音频并后台抽取）。"""
        self._cleanup_audio_file()
        self._extract_audio_async()

    def start_audio(self, position=0):
        """从指定位置(毫秒)播放音频；音频未就绪时忽略，稍后由 update_frame 补启动。"""
        if not self.video_path or not self.audio_temp or not os.path.exists(self.audio_temp):
            return
        try:
            if not self._ensure_mixer():
                return
            import pygame
            if self.audio_loaded_path != self.audio_temp:
                pygame.mixer.music.load(self.audio_temp)
                self.audio_loaded_path = self.audio_temp
            pygame.mixer.music.set_volume(self.volume / 100.0)
            # 关键：WAV 已按 audio_rate 变速，定位位置需按比例换算
            start_sec = max(0, position / 1000.0 / self.audio_rate)
            pygame.mixer.music.play(0, start=start_sec)
        except Exception as e:
            pass



    def play(self):
        """播放视频"""
        if self.cap and not self.is_playing and not self.paused:
            try:
                self.is_playing = True
                self.paused = False

                # 记录同步基准（单调时钟，与音频对齐）
                self._play_start_clock = time.perf_counter()
                self._play_start_position = self.current_position

                # 启动定时器更新帧（固定短间隔，追帧由 update_frame 完成）
                self.timer = QTimer(self.parent)
                self.timer.timeout.connect(self.update_frame)
                self.timer.start(16)

                # 启动音频（音频未就绪时由 update_frame 补启动）
                self.start_audio(self.current_position)
            except Exception as e:
                self.is_playing = False

    def resume(self):
        """恢复播放"""
        if self.cap and not self.is_playing and self.paused:
            try:
                self.is_playing = True
                self.paused = False

                # 记录同步基准（从当前位置继续）
                self._play_start_clock = time.perf_counter()
                self._play_start_position = self.current_position

                # 启动定时器更新帧
                self.timer = QTimer(self.parent)
                self.timer.timeout.connect(self.update_frame)
                self.timer.start(16)

                # 从当前位置恢复音频
                self.start_audio(self.current_position)
            except Exception as e:
                self.is_playing = False

    def pause(self):
        """暂停播放"""
        if self.is_playing:
            try:
                self.paused = True
                self.is_playing = False

                # 停止定时器
                if hasattr(self, 'timer'):
                    self.timer.stop()

                # 暂停音频（保留播放位置）
                try:
                    import pygame
                    if pygame.mixer.get_init() and self.audio_loaded_path:
                        pygame.mixer.music.pause()
                except Exception:
                    pass
            except Exception as e:
                pass

    def stop(self):
        """停止播放"""
        try:
            self.is_playing = False
            self.paused = False
            self.current_position = 0

            # 停止定时器
            if hasattr(self, 'timer'):
                self.timer.stop()

            # 释放视频
            if self.cap:
                self.cap.release()
                self.cap = None

            # 停止音频
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass

            # 清空视频显示
            if hasattr(self, 'video_widget') and self.video_widget:
                self.video_widget.video_label.setPixmap(QPixmap())
        except Exception as e:
            pass

    def update_frame(self):
        """更新视频帧 -> 以单调时钟为基准与音频对齐，落后时补帧追上。"""
        if not self.cap or not self.is_playing:
            return

        try:
            # 计算应到达的视频位置（时钟基准，与音频同步）
            elapsed = (time.perf_counter() - self._play_start_clock) * 1000
            target = self._play_start_position + elapsed * self.playback_rate
            target = max(0, min(target, self.duration))

            # 视频落后则补帧追上（最多 240 帧，防止异常跑飞）
            frame = None
            guard = 0
            while self.current_position < target and guard < 240:
                ret, f = self.cap.read()
                if not ret:
                    self.stop()
                    return
                frame = f
                self.current_frame = f
                self.current_position = int(self.cap.get(cv2.CAP_PROP_POS_MSEC))
                guard += 1

            # 显示最新一帧
            if frame is not None:
                self._display_frame(frame)

            # 音频抽取完成后，若正在播放则补启动
            if self.audio_temp and self.audio_loaded_path != self.audio_temp:
                self.start_audio(self.current_position)
        except Exception as e:
            pass

    def _display_frame(self, frame):
        """把 BGR 帧按视频区域宽度缩放后显示（宽度与区域一致）。"""
        if frame is None:
            return
        if not hasattr(self, 'video_widget') or not self.video_widget:
            return
        if not hasattr(self.video_widget, 'video_label'):
            return
        label = self.video_widget.video_label
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        # 按视频区域宽度缩放（保持宽高比）
        if label.width() > 0:
            pixmap = pixmap.scaledToWidth(label.width(), Qt.SmoothTransformation)
        label.setPixmap(pixmap)

    def redraw_frame(self):
        """按当前视频区域尺寸重新绘制当前帧（区域大小改变时调用）。"""
        if self.current_frame is not None:
            self._display_frame(self.current_frame)

    def set_position(self, position):
        """设置播放位置"""
        if self.cap:
            try:
                # 确保位置在有效范围内
                position = max(0, min(position, self.duration))
                old_pos = self.current_position
                self.cap.set(cv2.CAP_PROP_POS_MSEC, position)
                self.current_position = position
                logger.info(f"设置播放位置: {old_pos}ms -> {position}ms")

                # 更新音频位置并重置同步基准
                if self.is_playing:
                    self._play_start_clock = time.perf_counter()
                    self._play_start_position = position
                    self.start_audio(position)
            except Exception as e:
                logger.error(f"设置播放位置失败: {e}")

    def set_volume(self, volume):
        """设置音量"""
        try:
            old_volume = self.volume
            self.volume = max(0, min(100, volume))
            logger.info(f"设置音量: {old_volume} -> {self.volume}")
            # 实时调整音量，无需重启音频
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(self.volume / 100.0)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"设置音量失败: {e}")

    def set_playback_rate(self, rate):
        """设置播放速率"""
        try:
            if rate == self.playback_rate:
                return
            old_rate = self.playback_rate
            self.playback_rate = rate
            logger.info(f"设置播放速率: {old_rate}x -> {rate}x")

            # 重置同步基准（视频从当前位置按新速率继续）
            if self.is_playing:
                self._play_start_clock = time.perf_counter()
                self._play_start_position = self.current_position

            # 停止当前音频，按新速率重新抽取；就绪后由 update_frame 自动接上
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass
            self._extract_audio_async()
        except Exception as e:
            logger.error(f"设置播放速率失败: {e}")


class Console(QFrame):
    """控制台框架 -> 进度条、播放/暂停、重播、时长、倍速"""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("console")
        self.setStyleSheet(
            "#console { background-color: rgba(255, 255, 255, 0.95); border-radius: 8px; }"
            "QToolButton { background: transparent; border: none; }"
            "QLabel { color: #333333; }"
            "QComboBox {"
            "   background-color: #ffffff;"
            "   color: #333333;"
            "   border: 1px solid #cccccc;"
            "   border-radius: 4px;"
            "   padding: 4px 8px;"
            "   min-width: 60px;"
            "}"
            "QComboBox:hover {"
            "   border: 1px solid #999999;"
            "}"
            "QComboBox::drop-down {"
            "   subcontrol-origin: padding;"
            "   subcontrol-position: top right;"
            "   width: 20px;"
            "   border-left: 1px solid #cccccc;"
            "}"
            "QComboBox::down-arrow {"
            "   image: url(" + os.path.join(Run_Directory, configure_data.get("下拉列表箭头图标", "./Images/arrow_down.png")).replace("\\", "/") + ");"
            "   width: 12px;"
            "   height: 12px;"
            "}"
            "QComboBox QAbstractItemView {"
            "   background-color: #ffffff;"
            "   color: #333333;"
            "   border: 1px solid #cccccc;"
            "   selection-background-color: #0078d4;"
            "   selection-color: #ffffff;"
            "   outline: none;"
            "}"
            "QProgressBar {"
            "   border: none;"
            "   background-color: #e0e0e0;"
            "   border-radius: 3px;"
            "}"
            "QProgressBar::chunk {"
            "   background-color: #0078d4;"
            "   border-radius: 3px;"
            "}"
        )
        # 开启鼠标追踪，使在控制台上移动也能刷新显示计时
        self.setMouseTracking(True)

        # 图标（从配置文件读取，支持用户自定义）
        self.play_icon = QIcon(os.path.join(Run_Directory, configure_data.get("播放按钮图标", "./Images/play.png")))
        self.pause_icon = QIcon(os.path.join(Run_Directory, configure_data.get("暂停按钮图标", "./Images/pause.png")))
        self.replay_icon = QIcon(os.path.join(Run_Directory, configure_data.get("重播按钮图标", "./Images/replay.png")))
        self._is_playing = False

        # 播放/暂停按钮
        self.play_pause_button = QToolButton(self)
        self.play_pause_button.setIconSize(QSize(26, 26))
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setToolTip("播放/暂停")
        self.play_pause_button.setAutoRaise(True)

        # 重播按钮
        self.replay_button = QToolButton(self)
        self.replay_button.setIconSize(QSize(26, 26))
        self.replay_button.setIcon(self.replay_icon)
        self.replay_button.setToolTip("重播")
        self.replay_button.setAutoRaise(True)

        # 时长标签
        self.length_label = QLabel("0:00/0:00", self)

        # 倍速下拉框
        self.speed_spinner = QComboBox(self)
        self.speed_spinner.addItems(configure_data["倍速"])
        self.speed_spinner.currentTextChanged.connect(self.update_speed)

        # 进度条
        self.progress = Progress(self)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)

        # 控制按钮行
        controls = QHBoxLayout()
        controls.setContentsMargins(10, 0, 10, 2)
        controls.setSpacing(10)
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.replay_button)
        controls.addWidget(self.length_label)
        controls.addStretch(1)
        controls.addWidget(self.speed_spinner)

        # 整体布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addWidget(self.progress)
        layout.addLayout(controls)

        # 定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_length)
        configure_data["定时器地址"] = self.timer

    def sync_play_button(self) -> None:
        """根据播放状态更新播放/暂停按钮图标。"""
        player = configure_data.get("播放器地址")
        is_playing = player is not None and getattr(player, 'is_playing', False)
        if is_playing != self._is_playing:
            self._is_playing = is_playing
            self.play_pause_button.setIcon(self.pause_icon if is_playing else self.play_icon)

    def update_length(self) -> None:
        """更新进度与时长（定时器回调，持续运行以同步状态）。"""
        try:
            player = configure_data.get("播放器地址")
            if player is None:
                return
            if getattr(player, 'duration', 0) > 0:
                if self.progress.maximum() != player.duration:
                    self.progress.setMaximum(player.duration)
                self.progress.setValue(player.current_position)
                self.update_time_label()
            else:
                self.progress.setValue(0)
                self.length_label.setText("0:00/0:00")
                self.length_label.adjustSize()
            # 同步居中图标与播放/暂停按钮（如播放结束、状态变化）
            parent = self.parent()
            if hasattr(parent, 'sync_controls'):
                parent.sync_controls()
        except Exception as e:
            pass

    def update_time_label(self):
        """更新时间标签"""
        try:
            player = configure_data.get("播放器地址")
            if player is None:
                return
            if getattr(player, 'duration', 0) > 0:
                current_time = time.strftime("%H:%M:%S", time.gmtime(player.current_position / 1000))
                total_time = time.strftime("%H:%M:%S", time.gmtime(player.duration / 1000))
                self.length_label.setText(f"{current_time}/{total_time}")
                self.length_label.adjustSize()
            else:
                self.length_label.setText("0:00/0:00")
                self.length_label.adjustSize()
        except Exception as e:
            pass

    def update_speed(self, text: str) -> None:
        """更新倍速"""
        try:
            player = configure_data.get("播放器地址")
            if player is not None:
                player.set_playback_rate(float(text))
                logger.info(f"倍速已设置为: {text}x")
        except Exception as e:
            logger.error(f"更新倍速失败: {e}")

    def mouseMoveEvent(self, event) -> None:
        """鼠标在控制台上移动 -> 重置自动隐藏计时。"""
        parent = self.parent()
        if hasattr(parent, 'show_controls'):
            parent.show_controls()
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:
        """鼠标进入控制台 -> 保持显示并重置计时。"""
        parent = self.parent()
        if hasattr(parent, 'show_controls'):
            parent.show_controls()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """鼠标离开控制台 -> 延迟隐藏。"""
        parent = self.parent()
        if hasattr(parent, 'schedule_hide_controls'):
            parent.schedule_hide_controls()
        super().leaveEvent(event)


class Mutual(QFrame):
    """交互框架 -> 视频、视频控制"""

    def __init__(self, parent: QObject = None) -> None:
        # 初始化方法
        super().__init__(parent=parent)
        # 创建布局管理器
        layout: QVBoxLayout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建播放器和视频窗口（控制台内嵌于视频窗口底部）
        self.player: VideoPlayer = VideoPlayer(self)
        self.video_widget: VideoWidget = VideoWidget(self)
        self.player.set_video_output(self.video_widget)
        self.console: Console = self.video_widget.console

        # 向布局管理器中添加控件
        layout.addWidget(self.video_widget)
        self.setLayout(layout)

        # 设置播放器地址 -> 添加控件地址 -> 方便后续操作
        configure_data["播放器地址"]: VideoPlayer = self.player
        configure_data["播放列表地址"]: object = self  # 兼容旧代码

    def add_media(self, media_content):
        """添加媒体"""
        try:
            # 检查media_content的类型
            if hasattr(media_content, 'canonicalUrl'):
                # 如果是QMediaContent对象
                url = media_content.canonicalUrl()
                self.player.set_media(url)
                # 自动开始播放
                self.play()
        except Exception as e:
            pass

    def play(self):
        """播放"""
        try:
            if self.player.paused:
                self.player.resume()
            else:
                self.player.play()
            # 启动定时器
            timer: QTimer = configure_data["定时器地址"]
            timer.start(33)

            # 手动调用一次update_frame，测试视频帧更新逻辑
            self.player.update_frame()
        except Exception as e:
            pass

    def clear(self):
        """清空播放列表"""
        try:
            self.player.stop()
        except Exception as e:
            pass