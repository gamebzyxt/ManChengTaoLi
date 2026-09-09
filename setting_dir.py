from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QSlider, QFrame, QFormLayout, QLabel, QPushButton, QFileDialog, QLineEdit, QHBoxLayout, QSpinBox
from initialize import *


# 滑块控件
class Slider(QSlider):
    # 重写鼠标弹起事件 -> 设置字体尺寸
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        设置字体尺寸、提示文本、修改配置信息。
        :param event: 事件类型，不需要传递。
        """
        old_value = configure_data.get("字体尺寸", 18)
        # 修改配置信息
        configure_data["字体尺寸"]: int = self.value()
        # 修改提示文本
        self.setToolTip(str(self.value()))
        # 设置字体尺寸
        set_size(str(self.value()))
        logger.info(f"字体尺寸修改: {old_value} -> {self.value()}")


# 设置框架
class SettingFrame(QFrame):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 设置对象名称以便 QSS 识别
        self.setObjectName("settingFrame")
        # 设置整体样式（浅色主题）
        self.setStyleSheet("""
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #999999;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:hover {
                border: 1px solid #999999;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QSlider::groove:horizontal {
                background: #e0e0e0;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1084d8;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 3px;
            }
            QSpinBox {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                height: 0px;
            }
            QSpinBox:hover {
                border: 1px solid #999999;
            }
            QSpinBox:focus {
                border: 1px solid #0078d4;
            }
        """)
        # 创建布局管理器
        form_layout: QFormLayout = QFormLayout()
        # 创建版本号标签
        version_label: QLabel = QLabel("版本号: ", self)
        version_number: QLabel = QLabel(configure_data["版本号"], self)
        # 创建字体标签
        font_label: QLabel = QLabel("字体: ", self)
        font_button: QPushButton = QPushButton("更改字体", self)
        # 连接槽函数
        font_button.clicked.connect(self.choose_font)
        # 创建作者标签
        author_label: QLabel = QLabel("作者: ", self)
        author_text: QLabel = QLabel(configure_data["作者"], self)
        # 创建联系标签
        contact_label: QLabel = QLabel("联系我: ", self)
        contact_text: QLabel = QLabel(
            f'<a href="mailto: {configure_data["联系邮箱"]}">{configure_data["联系邮箱"]}</a>', self)
        # 创建创作背景标签
        background_creation_label: QLabel = QLabel("创作背景: ", self)
        background_creation_text: QLabel = QLabel(configure_data["创作背景"], self)
        background_creation_text.setWordWrap(True)
        # 设置字体尺寸标签
        size_label = QLabel("字体尺寸: ", self)
        size_slider: Slider = Slider(Qt.Horizontal)
        # 默认值
        size_slider.setValue(configure_data["字体尺寸"])
        # 最小值
        size_slider.setMinimum(configure_data["字体最小值"])
        # 最大值
        size_slider.setMaximum(configure_data["字体最大值"])
        # 步长
        size_slider.setSingleStep(1)
        size_slider.setToolTip(str(size_slider.value()))
        # 座右铭（名言名句）
        motto_label = QLabel("座右铭: ", self)
        self.motto_edit = QLineEdit(self)
        self.motto_edit.setText(configure_data.get("名言名句", ""))
        motto_button = QPushButton("确定", self)
        motto_button.clicked.connect(self.apply_motto)
        motto_row = QHBoxLayout()
        motto_row.setContentsMargins(0, 0, 0, 0)
        motto_row.addWidget(self.motto_edit)
        motto_row.addWidget(motto_button)
        # 快进/快退秒数
        fast_forward_spin = QSpinBox(self)
        fast_forward_spin.setRange(0, 3600)
        fast_forward_spin.setValue(configure_data.get("快进秒数", 5))
        fast_forward_spin.valueChanged.connect(lambda v: self._set_int_config("快进秒数", v))
        fast_backward_spin = QSpinBox(self)
        fast_backward_spin.setRange(0, 3600)
        fast_backward_spin.setValue(configure_data.get("快退秒数", 2))
        fast_backward_spin.valueChanged.connect(lambda v: self._set_int_config("快退秒数", v))
        # 加/减音量数
        volume_up_spin = QSpinBox(self)
        volume_up_spin.setRange(0, 100)
        volume_up_spin.setValue(configure_data.get("加音量数", 5))
        volume_up_spin.valueChanged.connect(lambda v: self._set_int_config("加音量数", v))
        volume_down_spin = QSpinBox(self)
        volume_down_spin.setRange(0, 100)
        volume_down_spin.setValue(configure_data.get("减音量数", 5))
        volume_down_spin.valueChanged.connect(lambda v: self._set_int_config("减音量数", v))
        # 设置截图保存路径
        screenshot_label = QLabel("设置截图保存路径: ", self)
        self.screenshot_path_edit = QLineEdit(self)
        self.screenshot_path_edit.setReadOnly(True)
        self._refresh_screenshot_path()
        screenshot_button = QPushButton("更改", self)
        screenshot_button.clicked.connect(self.choose_screenshot_dir)
        screenshot_row = QHBoxLayout()
        screenshot_row.setContentsMargins(0, 0, 0, 0)
        screenshot_row.addWidget(self.screenshot_path_edit)
        screenshot_row.addWidget(screenshot_button)
        # 向布局管理器添加控件
        form_layout.addRow(version_label, version_number)
        form_layout.addRow(author_label, author_text)
        form_layout.addRow(contact_label, contact_text)
        form_layout.addRow(background_creation_label, background_creation_text)
        form_layout.addRow(font_label, font_button)
        form_layout.addRow(size_label, size_slider)
        form_layout.addRow(motto_label, motto_row)
        form_layout.addRow(QLabel("快进秒数: ", self), fast_forward_spin)
        form_layout.addRow(QLabel("快退秒数: ", self), fast_backward_spin)
        form_layout.addRow(QLabel("加音量数: ", self), volume_up_spin)
        form_layout.addRow(QLabel("减音量数: ", self), volume_down_spin)
        form_layout.addRow(screenshot_label, screenshot_row)

        # 启用布局管理器
        self.setLayout(form_layout)

    # 应用座右铭（点击确定才生效）
    def apply_motto(self) -> None:
        old_motto = configure_data.get("名言名句", "")
        motto = self.motto_edit.text()
        configure_data["名言名句"] = motto
        logger.info(f"座右铭修改: {old_motto} -> {motto}")
        # 若尚未加载视频，同步更新索引页显示
        player = configure_data.get("播放器地址")
        if player is None or not getattr(player, 'has_media', lambda: False)():
            blurb_frame = configure_data.get("简介框架地址")
            if blurb_frame is not None and hasattr(blurb_frame, 'video_name'):
                blurb_frame.video_name.setText(motto or "历史的发展是不以人的意志为转移的。 --毛泽东--")

    # 设置整型配置（修改即生效）
    def _set_int_config(self, key: str, value) -> None:
        old_value = configure_data.get(key, 0)
        configure_data[key] = int(value)
        logger.info(f"配置项修改: {key} = {old_value} -> {value}")

    # 刷新截图路径显示（过长则省略号）
    def _refresh_screenshot_path(self) -> None:
        path = configure_data.get("默认截图保存路径", "./Images/Screenshot/")
        self.screenshot_path_edit.setToolTip(path)
        fm = self.screenshot_path_edit.fontMetrics()
        max_width = 280
        if fm.horizontalAdvance(path) > max_width:
            self.screenshot_path_edit.setText(fm.elidedText(path, Qt.ElideMiddle, max_width))
        else:
            self.screenshot_path_edit.setText(path)

    # 选择截图保存目录
    def choose_screenshot_dir(self) -> None:
        current = configure_data.get("默认截图保存路径", "./Images/Screenshot/")
        if not os.path.isabs(current):
            current = os.path.join(Run_Directory, current)
        directory = QFileDialog.getExistingDirectory(self, "选择截图保存目录", current)
        if directory:
            old_path = configure_data.get("默认截图保存路径", "./Images/Screenshot/")
            configure_data["默认截图保存路径"] = directory.replace("\\", "/")
            self._refresh_screenshot_path()
            logger.info(f"截图保存路径修改: {old_path} -> {directory}")
        else:
            logger.info("用户取消了截图保存路径选择")

    # 选择字体
    def choose_font(self) -> None:
        """
        选择字体并设置字体。
        """
        # 指定文件类型过滤器
        options: QFileDialog.Options = QFileDialog.Options()
        filter: str = configure_data["字体过滤器"]
        # 打开文件选择对话框
        response: list = QFileDialog.getOpenFileName(self, "选择文件", f'{configure_data["上次字体选择路径"]}', filter,
                                                     options=options)
        # 判断是否选择了文件
        if response[0]:
            old_font = configure_data.get("字体", "")
            # 设置字体
            set_font(response[0])
            # 修改配置信息
            configure_data["字体"]: str = response[0]
            configure_data["上次字体选择路径"]: str = os.path.dirname(response[0])
            logger.info(f"字体修改: {old_font} -> {response[0]}")
        else:
            logger.info("用户取消了字体选择")

