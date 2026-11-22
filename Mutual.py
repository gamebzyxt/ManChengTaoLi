import time
import cv2
import subprocess
import os
from PySide6.QtCore import Qt, QObject, QTimer, QPropertyAnimation, Signal, QSize, QSizeF, QPoint, QEasingCurve, QUrl
from PySide6.QtGui import QMouseEvent, QKeyEvent, QPixmap, QIcon, QBrush, QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QTableView, QFrame, QProgressBar, QLabel, QComboBox, QVBoxLayout, QHBoxLayout, \
    QGraphicsOpacityEffect, QSizePolicy, QToolButton, QGraphicsView, QGraphicsScene, QSplitter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from initialize import *


# 图标目录
IMAGE_DIR = os.path.join(Run_Directory, 'Images')


class ClickableLabel(QLabel):
    """可点击的图片标签 -> 用于居中的播放/暂停按钮。"""
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 接受左键按下，避免事件冒泡到父控件导致重复触发
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # 在控件范围内左键弹起时触发点击
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class VideoWidget(QFrame):
    """视频显示控件"""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("videoWidget")
        # 空白/播放结束时的底色用白色（黑底太沉闷）
        self.setStyleSheet("#videoWidget { background-color: #FFFFFF; }")
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
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 视频画面不拦截鼠标事件，交给父控件处理（进入/移动/点击）
        self.video_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # 居中按钮（图片形式）
        self.center_button = ClickableLabel(self)
        self.center_button.setObjectName("centerButton")
        self.center_button.setFixedSize(80, 80)
        self.center_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_button.setPixmap(self.play_icon.pixmap(44, 44))
        self.center_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.7); border-radius: 40px;")
        self.center_button.hide()
        # 点击图标 -> 播放/暂停
        self.center_button.clicked.connect(self.toggle_play_pause)

        # 截图按钮（居中播放/暂停图标的左侧）
        self.camera_button = ClickableLabel(self)
        self.camera_button.setFixedSize(64, 64)
        self.camera_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_button.setPixmap(self.camera_icon.pixmap(48, 48))
        self.camera_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.6); border-radius: 32px;")
        self.camera_button.setToolTip("截图")
        self.camera_button.hide()
        self.camera_button.clicked.connect(self.take_screenshot)

        # +10s 按钮（居中播放/暂停图标的右上）
        self.forward_button = ClickableLabel(self)
        self.forward_button.setFixedSize(64, 64)
        self.forward_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.forward_button.setPixmap(self.forward_icon.pixmap(52, 44))
        self.forward_button.setStyleSheet("background-color: rgba(255, 255, 255, 0.6); border-radius: 32px;")
        self.forward_button.setToolTip("快进 10 秒")
        self.forward_button.hide()
        self.forward_button.clicked.connect(self.seek_forward)

        # -10s 按钮（居中播放/暂停图标的右下）
        self.backward_button = ClickableLabel(self)
        self.backward_button.setFixedSize(64, 64)
        self.backward_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        if event.button() == Qt.MouseButton.LeftButton:
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
            if event.key() == Qt.Key.Key_Left and (player.is_playing or player.paused):
                # 快退
                player.set_position(player.current_position - configure_data["快退秒数"] * 1000)
            elif event.key() == Qt.Key.Key_Right and (player.is_playing or player.paused):
                # 快进
                player.set_position(player.current_position + configure_data["快进秒数"] * 1000)
            elif event.key() == Qt.Key.Key_Up and (player.is_playing or player.paused):
                # 加音量
                player.set_volume(player.volume + configure_data["加音量数"])
            elif event.key() == Qt.Key.Key_Down and (player.is_playing or player.paused):
                # 减音量
                player.set_volume(player.volume - configure_data["减音量数"])
            elif event.key() == Qt.Key.Key_Space and (player.is_playing or player.paused):
                # 暂停、播放
                self.toggle_play_pause()
            elif event.key() == Qt.Key.Key_M and (player.is_playing or player.paused):
                # 获取表格地址
                table: QTableView = configure_data["表格页地址"]
                # 添加标记
                table.add_row([player.current_position, ""])
            elif event.key() == Qt.Key.Key_S and (player.is_playing or player.paused):
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


class MonoTimeLabel(QLabel):
    """时长标签：强制等宽字体 + 固定宽度，保证刷新时不抖动。

    时间文本每秒都在变（"00:00:01" -> "00:00:02"）。如果用程序全局字体
    （用户可能选仿宋等比例字体），不同数字的宽度并不一致，每换一次数字
    Qt 都要重新计算标签尺寸并重排，表现出来就是文字上下跳动、位置偏移。

    这里做了三件事：
    1. 使用等宽字体，任何数字组合宽度都相同；
    2. 宽度固定为"最长形态"的宽度，之后不再随文本变化；
    3. 设置 keep_mono_font 标记，让 initialize.set_font / set_size 跳过它，
       否则用户改字体时会把它覆盖回比例字体。
    """

    # 供 initialize.set_font / set_size 识别并跳过
    keep_mono_font = True

    # 最长的显示形态，用于预留宽度
    SAMPLE = "00:00:00/00:00:00"

    def __init__(self, parent=None) -> None:
        super().__init__(self.SAMPLE, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = QFont()
        font.setFamilies(["Consolas", "Courier New", "DejaVu Sans Mono", "monospace"])
        font.setStyleHint(QFont.StyleHint.Monospace)
        # 明确声明等宽特性，避免被任何"按字符宽度"的推算覆盖
        font.setFixedPitch(True)
        self.setFont(font)
        self.refresh_time_width()

    def refresh_time_width(self) -> None:
        """按当前字体重新计算并固定宽度（字号变化后需要重算）。"""
        self.ensurePolished()
        fm = self.fontMetrics()
        # boundingRect 包含字形侧边距；sizeHint 额外考虑内边距，取两者较大值
        width = max(fm.boundingRect(self.SAMPLE).width(),
                    self.sizeHint().width(),
                    fm.horizontalAdvance(self.SAMPLE))
        # 留一点余量给不同渲染后端的取整差异
        self.setFixedWidth(width + 10)

    def set_time(self, text: str) -> None:
        """更新文本；内容没变就不动，避免无谓的重绘。"""
        if self.text() != text:
            self.setText(text)


class Progress(QProgressBar):
    """进度条控件：支持单击跳转与按住拖动连续跳转。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._dragging = False

    def _seek_to(self, x: int) -> None:
        """按横向像素位置换算成视频时间点并跳转。"""
        try:
            player: VideoPlayer = configure_data["播放器地址"]
            if player is None or player.duration <= 0:
                return
            width = max(1, self.width())
            # 夹紧到控件范围内，避免拖出边界时越界
            x = min(max(x, 0), width)
            position = int(player.duration * x / width)
            player.set_position(position)
            # 立即更新进度条显示
            self.setValue(position)
            # 通知控制台更新时间标签
            console = self.parent()
            if isinstance(console, Console):
                console.update_time_label()
        except Exception as e:
            logger.error(f"进度条跳转失败: {e}")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """按下：立即跳转并进入拖动状态。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._seek_to(int(event.position().x()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """拖动：持续跟随鼠标位置跳转。"""
        if self._dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._seek_to(int(event.position().x()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """松开：结束拖动，并定位到最终位置。"""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._seek_to(int(event.position().x()))
            event.accept()
            return
        super().mouseReleaseEvent(event)


def probe_duration(path: str) -> float:
    """用 ffprobe 读取媒体时长（秒），失败或读取不到返回 0。"""
    kwargs = {}
    if hasattr(subprocess, 'CREATE_NO_WINDOW'):
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'default=nw=1:nk=1', path],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=30, **kwargs)
        return max(0.0, float(result.stdout.decode('utf-8', 'ignore').strip()))
    except Exception:
        return 0.0


class _VideoResizeFilter(QObject):
    """把视频容器的尺寸变化转交给 VideoPlayer。

    Qt 的 installEventFilter 只接受 QObject，而 VideoPlayer 是普通 Python 类
    （它需要在 QApplication 就绪前就能被构造），所以用这个小对象代劳。
    """

    def __init__(self, player) -> None:
        super().__init__()
        self._player = player

    def eventFilter(self, obj, event) -> bool:
        try:
            if event.type() in (event.Type.Resize, event.Type.Show):
                self._player._fit_video_window()
        except Exception:
            pass
        return False


class VideoPlayer:

    """视频播放器（Qt Multimedia 内核）

    播放引擎完全交给 Qt 自带的 FFmpeg 多媒体后端：
    - 音视频由同一个引擎解码，共享同一条时钟。声音和画面天然对齐，
      不存在"两个时钟各走各的、越播越偏"的问题。
    - 画面由 QVideoWidget 直接渲染（GPU/RHI 路径），4K 也不会把主线程拖慢；
      帧数据不进入 Python，没有任何逐帧转换开销。
    - 打开即解码（暂停态），用户点开就能看到首帧。
    - 播放位置统一取 QMediaPlayer.position()，它是解码器给出的真实时间轴，
      seek / 倍速 / 暂停后都不会跳变。

    对外接口保持原样：has_media / set_media / play / pause / resume / stop /
    replay / screenshot / set_position / set_volume / set_playback_rate /
    set_video_output / update_frame / redraw_frame，以及
    is_playing / paused / current_position / duration / volume 属性。
    """

    # 视频区域底色：无视频时白色（不刺眼），有视频时黑色
    BG_IDLE = (255, 255, 255)   # 空载 / 播放结束 / 停止
    BG_ACTIVE = (0, 0, 0)       # 已加载视频（含暂停）

    def __init__(self, parent=None):
        self.parent = parent
        self.video_path = None
        self.playback_rate = 1.0
        self._volume = 50
        self._volume_before_mute = 50
        self._opened = False

        # 媒体对象（惰性创建，保证在 QApplication 就绪后）
        self._player = None
        self._audio = None
        self._video_item = None       # QGraphicsVideoItem：真正渲染视频的图元
        self._video_view = None       # QGraphicsView：承载图元的普通控件
        self._video_scene = None      # 图元所在的图形场景
        self._video_window = None     # 兼容字段（与 _video_view 相同）
        self._video_host = None        # 承载画面的 VideoWidget
        self._resize_filter = None     # 尺寸监听器（QObject，见 _VideoResizeFilter）

        # ---- 平滑位置时钟 ----
        # Qt 后端只在音视频包边界上发 positionChanged，间隔在 20~120ms 之间乱跳，
        # 直接拿 position() 画进度条会一顿一顿的。这里以信号到达为“校钟点”，
        # 两次信号之间用单调时钟按倍速外推，进度条就能匀速走动。
        self._pos_anchor_ms = 0.0      # 校钟点的媒体位置
        self._pos_anchor_clock = 0.0   # 校钟点对应的 perf_counter
        self._pos_anchor_rate = 1.0    # 校钟时的倍速
        self._pos_frozen = False       # 暂停/停止时冻结（不外推）

        self._make_player()

    # ------------------------------------------------------------------ 初始化
    def _make_player(self) -> None:
        """创建 QMediaPlayer 与音频输出。"""
        p = QMediaPlayer()
        ao = QAudioOutput()
        p.setAudioOutput(ao)
        try:
            ao.setVolume(self._volume / 100.0)
        except Exception:
            pass
        p.errorOccurred.connect(self._on_error)
        p.mediaStatusChanged.connect(self._on_media_status)
        p.playbackStateChanged.connect(self._on_state_changed)
        p.positionChanged.connect(self._on_position_changed)
        self._player = p
        self._audio = ao

    # ------------------------------------------------------------------ 平滑时钟
    def _anchor_position(self) -> None:
        """把当前真实位置记为新的校钟点。"""
        self._pos_anchor_ms = float(self._player.position())
        self._pos_anchor_clock = time.perf_counter()
        self._pos_anchor_rate = float(self.playback_rate) or 1.0

    def _on_position_changed(self, pos: int) -> None:
        """后端位置更新：只作为校钟点，不直接用于显示。"""
        self._pos_anchor_ms = float(pos)
        self._pos_anchor_clock = time.perf_counter()
        self._pos_anchor_rate = float(self.playback_rate) or 1.0

    def smooth_position(self) -> int:
        """返回平滑过的播放位置（毫秒）。

        播放中：校钟点 + 已流逝时间 × 倍速；
        其余情况：直接用真实位置，不外推。
        """
        try:
            if self._pos_frozen or not self.is_playing:
                return max(0, int(self._player.position()))
            elapsed = (time.perf_counter() - self._pos_anchor_clock) * 1000.0
            value = self._pos_anchor_ms + elapsed * self._pos_anchor_rate
            # 上限保护：外推最多领先真实位置 250ms，
            # 避免解码卡顿导致进度条跑到画面前面去。
            real = float(self._player.position())
            if value > real + 250.0:
                value = real + 250.0
            total = float(self.duration)
            if total > 0:
                value = min(value, total)
            return max(0, int(value))
        except Exception:
            return max(0, int(self._player.position()))

    def _on_error(self, error, error_string: str = "") -> None:
        if error_string:
            logger.error(f"播放器错误: {error_string}")

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info("播放结束")
            # 播放结束：画面区域恢复白底（黑底长时间停留太沉闷）
            self._set_bg_active(False)
            try:
                self._video_host.sync_controls()
            except Exception:
                pass
        elif status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            # 时长要等媒体真正载入后才有值，这时才能设置进度条范围
            if not self._opened:
                self._opened = True
            # 媒体已载入：画面区域使用黑底
            self._set_bg_active(True)
            self._notify_console()
            try:
                self._video_host.sync_controls()
            except Exception:
                pass

    def _on_state_changed(self, state) -> None:
        # 状态切换后重新校钟，避免用旧锚点外推出错误位置
        self._anchor_position()
        try:
            if self._video_host is not None:
                self._video_host.sync_controls()
        except Exception:
            pass

    # ------------------------------------------------------------------ 输出控件
    def set_video_output(self, video_widget):
        """把 QVideoWidget 放进 VideoWidget，作为它的子控件铺满整个区域。

        画面由 Qt Multimedia 的 GPU 渲染路径直接绘制，帧数据不进入 Python。

        这里用 QGraphicsView + QGraphicsVideoItem 而不是 QVideoWidget：
        QVideoWidget 是原生窗口（native window），在 Z 序上永远压在所有普通子控件
        之上，居中播放/暂停、截图、±10s 这些按钮会被它整个盖住看不见。
        QGraphicsVideoItem 是普通图元，和普通控件一样参与正常绘制与遮挡。
        """
        try:
            self._video_host = video_widget
            # 隐藏原来的 QLabel（画面改由图形视图显示）
            try:
                video_widget.video_label.hide()
            except Exception:
                pass

            # 图形场景 + 视图（普通控件，可被其它按钮正常叠放）
            scene = QGraphicsScene(video_widget)
            # 场景底色随播放状态切换：无视频时为白色（不刺眼），有视频时转黑
            scene.setBackgroundBrush(self._idle_brush())
            view = QGraphicsView(scene, video_widget)
            view.setFrameShape(QFrame.Shape.NoFrame)
            view.setStyleSheet("background: transparent; border: none;")
            view.viewport().setAutoFillBackground(False)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # 缩放采样改为平滑：720p 视频在中等窗口下会被缩到 60% 左右，
            # 默认的快速采样在这个比例会产生明显锯齿/噪点。
            # 该设置只影响绘制阶段的采样方式，不介入解码与音画同步。
            view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # 鼠标事件交给 VideoWidget 处理（进入/移动/点击）
            view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            view.setGeometry(video_widget.rect())
            view.lower()
            view.show()

            item = QGraphicsVideoItem()
            item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            scene.addItem(item)

            self._video_scene = scene
            self._video_view = view
            self._video_item = item
            self._video_window = view
            self._player.setVideoOutput(item)
            # 尺寸跟随视频区域。
            # 注意：installEventFilter 要求过滤器必须是 QObject，
            # 而 VideoPlayer 本身是普通类，所以用一个内部 QObject 代劳。
            if self._resize_filter is None:
                self._resize_filter = _VideoResizeFilter(self)
            try:
                video_widget.removeEventFilter(self._resize_filter)
            except Exception:
                pass
            video_widget.installEventFilter(self._resize_filter)
            self._fit_video_window()
            # 画面层级放到最底，按钮都在它上面
            self._raise_overlays()
            # 未加载视频时保持白底
            self._set_bg_active(False)
        except Exception as e:
            logger.error(f"设置视频输出失败: {e}")

    def _raise_overlays(self) -> None:
        """把交互控件提到画面之上（图形视图本身是普通控件，会被后创建的控件盖住）。"""
        host = self._video_host
        if host is None:
            return
        view = getattr(self, '_video_view', None)
        if view is None:
            return
        try:
            view.lower()
            for name in ('center_button', 'camera_button', 'forward_button', 'backward_button'):
                btn = getattr(host, name, None)
                if btn is not None:
                    btn.raise_()
            console = getattr(host, 'console', None)
            if console is not None:
                console.raise_()
        except Exception as e:
            logger.error(f"调整控件层级失败: {e}")

    def eventFilter(self, obj, event):
        """兼容保留：实际过滤器是 _VideoResizeFilter。"""
        try:
            if obj is self._video_host and event.type() in (event.Type.Resize, event.Type.Show):
                self._fit_video_window()
        except Exception:
            pass
        return False

    def _set_bg_active(self, active: bool) -> None:
        """切换视频区域底色。

        有视频时用黑底（黑边不刺眼）；没有视频时优先显示用户自定义背景图，
        未启用或图片无效时回退到白色。
        底色统一由图形场景的 backgroundBrush 负责，视图本身保持透明，
        否则视图的白底会盖住场景里绘制的背景图。
        """
        color = self.BG_ACTIVE if active else self.BG_IDLE
        try:
            if self._video_scene is not None:
                self._video_scene.setBackgroundBrush(self._idle_brush() if not active
                                                     else QBrush(QColor(*color)))
            if self._video_view is not None:
                self._video_view.setStyleSheet("background: transparent; border: none;")
                self._video_view.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
                self._video_view.viewport().setAutoFillBackground(False)
                self._video_view.viewport().update()
        except Exception as e:
            logger.error(f"切换视频区域底色失败: {e}")

    def _idle_brush(self) -> QBrush:
        """构造空闲状态的背景画刷。

        启用自定义背景图且图片可读时返回图片画刷，否则返回纯白画刷。

        处理要点：
        1. QBrush 的贴图不会缩放，必须自己把图片缩放到视频区域尺寸，
           否则只会显示原图左上角一小块。
        2. 保持宽高比缩放 + 平滑转换：图片按原比例缩放到能放进视频区域，
           再居中摆放，四周留白；不拉伸变形、也不裁切内容。
        3. 不透明度来自配置项"背景图片不透明度"（0-100）：
           Qt 的画刷没有独立的透明度，这里把图片与白底预先合成一张
           半透明效果的新图，再作为贴图画刷使用。
        """
        try:
            if not configure_data.get("启用自定义背景图片", False):
                return QBrush(QColor(*self.BG_IDLE))
            path = configure_data.get("背景图片路径", "")
            if not path:
                return QBrush(QColor(*self.BG_IDLE))
            if not os.path.isabs(path):
                path = os.path.join(Run_Directory, path)
            image = QImage(path)
            if image.isNull():
                logger.warning(f"背景图片无法读取: {path}")
                return QBrush(QColor(*self.BG_IDLE))

            # 目标尺寸 = 视频区域当前大小（尚未布局时给个兜底尺寸）
            view = self._video_view
            target_w, target_h = (view.width(), view.height()) if view is not None else (0, 0)
            if target_w <= 0 or target_h <= 0:
                target_w, target_h = 1280, 720

            # 保持宽高比缩放 + 平滑转换：只限制"能放进视频区域"，
            # 不留黑边也不变形；缩放后居中摆放，四周由白底填充。
            fitted = image.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            offset_x = (target_w - fitted.width()) // 2
            offset_y = (target_h - fitted.height()) // 2

            opacity = max(0, min(100, int(configure_data.get("背景图片不透明度", 50))))
            canvas = QPixmap(target_w, target_h)
            canvas.fill(QColor(*self.BG_IDLE))
            painter = QPainter(canvas)
            painter.setOpacity(opacity / 100.0)
            painter.drawImage(offset_x, offset_y, fitted)
            painter.end()
            return QBrush(canvas)
        except Exception as e:
            logger.error(f"构建背景画刷失败: {e}")
            return QBrush(QColor(*self.BG_IDLE))

    def refresh_background(self) -> None:
        """背景设置变更后由外部调用：重新绘制空闲背景。

        仅在没有视频时生效，播放中不打断画面。
        """
        if self.has_media():
            return
        self._set_bg_active(False)

    def _fit_video_window(self) -> None:
        """让画面视图铺满视频区域，并让视频图元等比缩放居中。"""
        view = getattr(self, '_video_view', None)
        item = getattr(self, '_video_item', None)
        if view is None or self._video_host is None:
            return
        try:
            rect = self._video_host.rect()
            view.setGeometry(rect)
            view.lower()
            if item is not None:
                # 图元尺寸 = 视图可视区域，由 KeepAspectRatio 保证画面不拉伸
                item.setSize(QSizeF(rect.width(), rect.height()))
            # 窗口尺寸变化后背景图需要按新尺寸重新合成
            if self._video_scene is not None and not self.has_media():
                self._video_scene.setBackgroundBrush(self._idle_brush())
            self._raise_overlays()
        except Exception as e:
            logger.error(f"调整画面尺寸失败: {e}")

    # ------------------------------------------------------------------ 媒体
    def has_media(self) -> bool:
        """是否已加载视频文件。"""
        return bool(self.video_path)

    def _clear_source(self) -> None:
        """清空当前媒体源。"""
        self._player.setSource(QUrl())

    def _open_media(self) -> None:
        """让 Qt 载入当前文件（载入后处于暂停态，并显示首帧）。"""
        self._opened = False
        # 有视频了，画面区域转黑底
        self._set_bg_active(True)
        self._player.setSource(QUrl.fromLocalFile(self.video_path))
        # 载入即暂停：解码出首帧显示，但不播放
        self._player.pause()

    def set_media(self, media_url):
        """设置媒体文件。"""
        try:
            self.stop()
            self.video_path = media_url.toLocalFile()
            logger.info(f"设置媒体文件: {self.video_path}")
            self._open_media()
            self._opened = True
            self._notify_console()
        except Exception as e:
            logger.error(f"设置媒体文件失败: {e}")

    def _notify_console(self):
        """通知控制台更新进度条范围。"""
        try:
            timer = configure_data.get("定时器地址")
            if timer is not None and isinstance(getattr(timer, 'parent', lambda: None)(), Console):
                console = timer.parent()
                console.progress.setMaximum(max(0, self.duration))
                console.update_time_label()
        except Exception:
            pass

    def replay(self):
        """从头重播当前视频。"""
        if not self.video_path:
            return
        try:
            logger.info(f"重播视频: {self.video_path}")
            self.set_position(0)
            self._player.play()
        except Exception as e:
            logger.error(f"重播失败: {e}")

    # ------------------------------------------------------------------ 状态
    @property
    def is_playing(self) -> bool:
        try:
            return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            return False

    @property
    def paused(self) -> bool:
        try:
            return self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        except Exception:
            return False

    @property
    def current_position(self) -> int:
        try:
            return max(0, int(self._player.position()))
        except Exception:
            return 0

    @property
    def duration(self) -> int:
        try:
            return max(0, int(self._player.duration()))
        except Exception:
            return 0

    @property
    def volume(self) -> int:
        return self._volume

    # ------------------------------------------------------------------ 控制
    def play(self):
        """开始播放（暂停中则恢复）。"""
        if not self._player:
            return
        try:
            self._pos_frozen = False
            self._player.play()
            self._anchor_position()
            logger.info(f"开始播放: {self.video_path}")
        except Exception as e:
            logger.error(f"播放失败: {e}")

    def resume(self):
        """从暂停处恢复播放。"""
        try:
            self._pos_frozen = False
            self._player.play()
            self._anchor_position()
        except Exception as e:
            logger.error(f"恢复播放失败: {e}")

    def pause(self):
        """暂停播放（保留画面和位置）。"""
        try:
            self._player.pause()
            # 暂停后冻结位置，不再按时钟外推
            self._pos_frozen = True
            logger.info(f"已暂停，位置: {self.current_position}ms")
        except Exception as e:
            logger.error(f"暂停失败: {e}")

    def stop(self):
        """停止播放并清空画面。"""
        try:
            self._pos_frozen = True
            self._player.stop()
            self._pos_anchor_ms = 0.0
            self._pos_anchor_clock = time.perf_counter()
            self._clear_source()
            self._opened = False
            self.video_path = None
            # 没有视频了，画面区域恢复白底
            self._set_bg_active(False)
            if self._video_host is not None:
                try:
                    self._video_host.video_label.clear()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"停止播放失败: {e}")

    def set_position(self, position):
        """跳转到指定位置（毫秒）。"""
        try:
            total = self.duration
            pos = int(position)
            if total > 0:
                pos = max(0, min(pos, total - 1))
            pos = max(0, pos)
            logger.info(f"设置播放位置: {self.current_position}ms -> {pos}ms")
            self._player.setPosition(pos)
            # 跳转后立刻重新校钟，否则平滑时钟会沿旧位置外推
            self._pos_anchor_ms = float(pos)
            self._pos_anchor_clock = time.perf_counter()
            self._pos_anchor_rate = float(self.playback_rate) or 1.0
        except Exception as e:
            logger.error(f"设置播放位置失败: {e}")

    def set_volume(self, volume):
        """设置音量（0-100）。"""
        try:
            old = self._volume
            self._volume = max(0, min(100, int(volume)))
            logger.info(f"设置音量: {old} -> {self._volume}")
            self._audio.setVolume(self._volume / 100.0)
        except Exception as e:
            logger.error(f"设置音量失败: {e}")

    def set_playback_rate(self, rate):
        """设置播放倍速（音视频同倍速，天然同步）。"""
        try:
            self.playback_rate = float(rate)
            self._player.setPlaybackRate(self.playback_rate)
            # 倍速变了，外推斜率也要跟着变
            self._anchor_position()
            logger.info(f"设置播放速率: {self.playback_rate}x")
        except Exception as e:
            logger.error(f"设置播放速率失败: {e}")

    # ------------------------------------------------------------------ 画面
    def update_frame(self):
        """保持接口兼容：渲染由 Qt 自动完成，这里只同步控制台显示。"""
        try:
            if self._video_host is not None:
                self._fit_video_window()
        except Exception:
            pass

    def redraw_frame(self):
        """窗口尺寸变化时调用：同步嵌入窗格大小。"""
        self._fit_video_window()

    def screenshot(self):
        """保存当前帧为截图，返回保存路径。

        QVideoWidget 的帧不进 Python，因此用视频文件 + 当前时间点重解一帧，
        效果与截取当前画面一致，还能拿到原始分辨率。
        """
        if not self.video_path:
            logger.warning("截图失败: 无视频文件")
            return None
        try:
            position = self.current_position / 1000.0
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                logger.error("截图失败: 视频无法打开")
                return None
            cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000)
            ok, frame = cap.read()
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            cap.release()
            if not ok or frame is None:
                logger.warning("截图失败: 无法解出该时间点的画面")
                return None

            base_dir = configure_data.get("默认截图保存路径", "./Images/Screenshot/")
            if not os.path.isabs(base_dir):
                base_dir = os.path.normpath(os.path.join(Run_Directory, base_dir))
            sub_dir = os.path.join(base_dir, fingerprint(self.video_path))
            os.makedirs(sub_dir, exist_ok=True)
            frame_no = int(position * fps) if fps > 0 else 0
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(sub_dir, f"{timestamp}_{frame_no}.png")
            i = 1
            while os.path.exists(path):
                path = os.path.join(sub_dir, f"{timestamp}_{frame_no}_{i}.png")
                i += 1
            if cv2.imwrite(path, frame):
                logger.info(f"截图已保存: {path}")
                return path
            logger.error("截图保存失败: cv2.imwrite 返回 False")
            return None
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None




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
            "   border-radius: 6px;"
            "}"
            "QProgressBar::chunk {"
            "   background-color: #0078d4;"
            "   border-radius: 6px;"
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

        # 时长标签（等宽字体 + 固定宽度，刷新时不抖动）
        self.length_label = MonoTimeLabel(self)

        # 倍速下拉框
        self.speed_spinner = QComboBox(self)
        self.speed_spinner.addItems(configure_data["倍速"])
        self.speed_spinner.currentTextChanged.connect(self.update_speed)

        # 进度条
        self.progress = Progress(self)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setRange(0, 1)  # 初始最小范围，避免 QProgressBar 默认 -1「忙」态
        self.progress.setValue(0)

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
        # 进度条每帧都要重画，必须用精确计时器：
        # 默认的 CoarseTimer 精度只有 ±5% 且受系统调度压制，
        # 实测回调间隔会在 14~129ms 之间乱跳，进度条看起来就一顿一顿的。
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_length)
        configure_data["定时器地址"] = self.timer

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """点击控制台空白处不播放/暂停视频。

        控制台是进度条的父控件，文字标签、按钮之间的空隙都属于它。
        这些点击不该穿透到视频区域触发播放/暂停，否则很容易误触。
        进度条、按钮等子控件会自己处理点击，不会走到这里。
        """
        event.accept()

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
                # 用平滑位置：后端 position() 只在包边界更新，直接画会一顿一顿
                self.progress.setValue(max(0, min(player.smooth_position(), player.duration)))
                self.update_time_label()
            else:
                self.progress.setValue(0)
                self.length_label.set_time(MonoTimeLabel.SAMPLE)
            # 同步居中图标与播放/暂停按钮（如播放结束、状态变化）
            parent = self.parent()
            if hasattr(parent, 'sync_controls'):
                parent.sync_controls()
        except Exception as e:
            pass

    def update_time_label(self):
        """更新时间标签。

        宽度已经由 MonoTimeLabel 固定，这里只更新文本，
        不做任何尺寸调整，避免每秒钟一次的布局重排。
        """
        try:
            player = configure_data.get("播放器地址")
            if player is None:
                return
            if getattr(player, 'duration', 0) > 0:
                pos = player.smooth_position()
                current_time = time.strftime("%H:%M:%S", time.gmtime(pos / 1000))
                total_time = time.strftime("%H:%M:%S", time.gmtime(player.duration / 1000))
                text = f"{current_time}/{total_time}"
            else:
                text = MonoTimeLabel.SAMPLE
            self.length_label.set_time(text)
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
        """添加媒体并开始播放。

        兼容传入 QUrl；旧版 QMediaContent 已不在 Qt6 中，故只在确实带有
        canonicalUrl 时才做转换。
        """
        try:
            if isinstance(media_content, QUrl):
                url = media_content
            elif hasattr(media_content, 'canonicalUrl'):
                url = media_content.canonicalUrl()
            else:
                logger.warning(f"不支持的媒体对象: {type(media_content)}")
                return
            self.player.set_media(url)
            # 自动开始播放
            self.play()
        except Exception as e:
            logger.error(f"添加媒体失败: {e}")

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