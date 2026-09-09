import time
from PyQt5.QtCore import QObject, Qt, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QContextMenuEvent, QIcon
from PyQt5.QtWidgets import QVBoxLayout, QFrame, QLabel, QTextEdit, QTableView, QHeaderView, QMenu, QAction
from initialize import *


# 索引窗口
class IndexWidget(QWidget):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 绘制ui
        self.create_control()

    # 创建控件
    def create_control(self) -> None:
        """
        创建控件。
        """
        # 创建布局管理器
        vertical: QVBoxLayout = QVBoxLayout()

        # 创建简介框架
        self.blurb_frame: BlurbFrame = BlurbFrame(self)
        # 创建表格控件
        self.pointer_table: PointerTable = PointerTable(self)

        # 向布局管理器中添加控件
        vertical.addWidget(self.blurb_frame, 1)
        vertical.addWidget(self.pointer_table, 9)
        # 启用布局管理器
        self.setLayout(vertical)


# 简介框架
class BlurbFrame(QFrame):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 创建布局管理器
        vertical: QVBoxLayout = QVBoxLayout()

        # 创建名称标签
        self.video_name: QLabel = QLabel(self)
        self.video_name.setWordWrap(True)
        # 从配置读取名言名句显示（为空时使用默认）
        self.video_name.setText(configure_data.get("名言名句") or "历史的发展是不以人的意志为转移的。 --毛泽东--")
        # 创建文本框
        self.video_blur: QTextEdit = QTextEdit(self)
        self.video_blur.setEnabled(False)
        # 添加控件地址 -> 方便后续操作
        configure_data["简介框架地址"] = self
        # 向布局管理器中添加控件
        vertical.addWidget(self.video_name, 3)
        vertical.addWidget(self.video_blur, 7)
        # 启用布局管理器
        self.setLayout(vertical)

    # 更新文本数据
    def update_text(self, item_data: list) -> dict:
        """
        更新文本数据，即视频名称/简介。
        :param item_data: 所点击的item数据，格式为["名称", "真实路径"]。
        :return: 返回简介（字典），格式为{"简介": "数据"}。
        """
        logger.info(f"更新视频信息: {item_data[0]}")
        # 更新视频名称标签
        self.video_name.setText(item_data[0])
        file_hash = fingerprint(item_data[1])
        self.video_name.setToolTip(file_hash)
        logger.info(f"视频文件指纹: {file_hash}")
        # 解除文本框不可修改状态
        self.video_blur.setEnabled(True)
        hash_dict: dict = index_file(item_data[1])
        self.video_blur.setText(hash_dict["简介"])
        if hash_dict["简介"]:
            logger.info("加载视频简介成功")
        else:
            logger.info("视频简介为空")

        return hash_dict


# 指针表格
class PointerTable(QTableView):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 设置表格地址 -> 方便后续操作
        configure_data["表格页地址"] = self
        # 创建一个QStandardItemModel对象，指定行数和列数
        self.model: QStandardItemModel = QStandardItemModel(0, 2)
        # 设置水平表头标签
        self.model.setHorizontalHeaderLabels(['索引', '说明'])
        # 将模型设置到表格视图
        self.setModel(self.model)
        # 自动调整列宽
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 连接槽函数
        self.doubleClicked.connect(self.video_jump)

    # 删除行
    def pop_row(self, row: int) -> None:
        """
        :param row: 需要删除的行号。
        """
        logger.info(f"删除索引行: 行号={row}")
        # 删除传递的行号
        self.model.removeRow(row)

    # 添加多行
    def add_rows(self, datas: list) -> None:
        """
        添加多行数据。
        :param datas: 格式为[[int, "说明"], ...]。
        """
        # 删除行 -> 防止上个视频的索引数据比当前多
        self.model.removeRows(0, self.model.rowCount())
        # 添加行，第一列设置为只读状态
        for row in range(len(datas)):
            # 创建item，第一列设置为只读状态
            item_0: QStandardItem = QStandardItem(str(datas[row][0]))
            item_0.setFlags(item_0.flags() & ~Qt.ItemIsEditable)
            item_0.setEditable(False)
            # 设置提示文本为正常时间格式
            item_0.setToolTip(time.strftime('%H:%M:%S', time.gmtime(datas[row][0] / 1000)))
            item_1: QStandardItem = QStandardItem(str(datas[row][1]))
            # 将item添加到模型
            self.model.setItem(row, 0, item_0)
            self.model.setItem(row, 1, item_1)

    # 添加一行数据
    def add_row(self, data: list) -> None:
        """
        添加一行数据。
        :param data: 格式为[int, "说明"]。
        """
        logger.info(f"添加索引行: 时间点={data[0]}ms, 说明={data[1]}")
        # 获取总行数，在末尾添加一行
        row: int = self.model.rowCount()
        # 第一列设置为只读状态
        item_0: QStandardItem = QStandardItem(str(data[0]))
        item_0.setFlags(item_0.flags() & ~Qt.ItemIsEditable)
        item_0.setEditable(False)
        # 设置提示文本为正常时间格式
        item_0.setToolTip(time.strftime('%H:%M:%S', time.gmtime(data[0] / 1000)))
        item_1: QStandardItem = QStandardItem(str(data[1]))
        # 将item添加到模型
        self.model.setItem(row, 0, item_0)
        self.model.setItem(row, 1, item_1)

    # 视频跳转
    def video_jump(self, index: QModelIndex) -> None:
        """
        视频跳转。
        :param index: 模型下标，不需要传递。
        """
        # 判断是否是第一列双击
        if index.column():
            return
        # 获取帧数
        frame_rate: int = int(self.model.index(index.row(), 0).data())
        logger.info(f"用户点击索引跳转视频到: {frame_rate}ms")
        # 获取播放器地址
        player = configure_data["播放器地址"]
        # 设置视频帧数
        player.set_position(frame_rate)

    # 获取数据
    def get_data(self) -> list:
        """
        获取表格各行数据并返回。
        :return: 将行数据通过列表返回，格式为[[int, "说明"], ...]
        """
        # 索引列表
        index_data: list = []
        # 动态获取数据
        for row in range(self.model.rowCount()):
            index_data.append([int(self.model.index(row, 0).data()), self.model.index(row, 1).data()])
        return index_data

    # 重写父类鼠标双击事件
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        在item上鼠标右击出现菜单栏。
        :param event: 事件类型，不需要传递。
        """
        # 获取右击行数
        row: int = self.rowAt(event.pos().y())
        # 判断是否在item上右击
        if row != -1:
            logger.info(f"用户在索引行{row}上右键点击")
            # 创建菜单栏
            menu: QMenu = QMenu(self)
            # 创建动作
            delete_action = QAction(QIcon(os.path.join(Run_Directory, configure_data["右键菜单栏删除图标"])), "删除行", self)
            # 绑定动作
            delete_action.triggered.connect(lambda: self.pop_row(row))
            # 添加动作
            menu.addAction(delete_action)
            # 进入菜单栏事件循环，并设置鼠标右击时的全局坐标为菜单栏位置
            menu.exec_(event.globalPos())
        else:
            return

