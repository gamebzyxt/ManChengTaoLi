from PySide6.QtCore import QThread, QObject
from PySide6.QtGui import QContextMenuEvent, QIcon, QAction
from PySide6.QtWidgets import QFileDialog, QTabWidget, QMenu
from initialize import *


# 多线程 -> 对文件进行哈希
class FileHash(QThread):
    # 初始化方法
    def __init__(self, files: list, parent: QObject = None) -> None:
        """
        :param files: 需要进行哈希的文件集合路径，格式为[("文件别名", "文件真实路径"), (...), ...]。
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 记录父类地址
        self.widget = parent
        # 文件路径
        self.files: list = files

    # 重写run方法
    def run(self) -> None:
        """
        对文件进行哈希。
        """
        # 非法文件个数 -> 目录/文件不存在标记变量
        illegal_number: int = 0
        # 动态添加item
        for item, index in zip(self.files, range(len(self.files))):
            try:
                # 尝试哈希 -> 文件可能不存在，需要try
                hash_str: str = fingerprint(item[1])
                if not hash_str:
                    logger.warning(f"视频文件无效，跳过: {item[1]}")
                # 判断文件是否有重复
                if hash_str in video_hash:
                    continue
                # 添加到列表
                video_hash.append(hash_str)
                # 添加item
                add_item(self.widget, item)
            except Exception as e:
                logger.error(f"处理文件失败 [{item[1]}]: {e}")
                # 下标减去非法文件个数 -> 否则下次删除引发[IndexError]
                index -= illegal_number
                # 删除文件序列
                try:
                    sequence.pop(index)
                    # 非法文件个数+1
                    illegal_number += 1
                except Exception as e:
                    logger.error(f"从序列中删除文件失败: {e}")


# 视频列表类
class VideoList(QListWidget):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 设置列表元素可拖拽
        self.setDragDropMode(QListWidget.InternalMove)
        # 创建多线程对象
        thread: FileHash = FileHash([(file_name[0], file_name[1]) for file_name in sequence], self)
        # 启动线程对象
        thread.start()

    # 获取视频序列
    def get_sequence(self) -> list:
        """
        获取视频序列，返回列表格式["名字", "真实路径"], ...
        """
        return [[self.item(index).text(), self.item(index).toolTip()] for index in range(self.count())]

    # 重写父类鼠标双击事件
    def mouseDoubleClickEvent(self, event: QContextMenuEvent) -> None:
        """
        鼠标双击事件。
        :param event: 事件类型，不需要传递。
        """
        # 判断是否是在item上双击的
        if self.itemAt(event.pos()) is None:
            logger.info("用户点击添加视频")
            # 指定文件类型过滤器
            options: QFileDialog.Options = QFileDialog.Options()
            filter: str = configure_data["视频过滤器"]
            # 打开文件选择对话框
            response: list = QFileDialog.getOpenFileName(self, "选择文件", f'{configure_data["上次视频选择路径"]}', filter,
                                                   options=options)
            # 判断是否选择了文件
            if response[0]:
                logger.info(f"用户选择视频文件: {response[0]}")
                # 获取文件哈希
                file_hash: str = fingerprint(response[0])
                # 判断文件是否已经存在 -> 列表中是否存在了该文件
                if file_hash in video_hash:
                    logger.info("视频已存在于列表中，跳过添加")
                    return
                # 创建多线程对象-> 添加item
                thread: FileHash = FileHash([(os.path.basename(response[0]), response[0].replace("/", "\\"))], self)
                # 启动线程对象
                thread.start()
                # 修改配置信息
                configure_data["上次视频选择路径"]: str = os.path.dirname(response[0])
            else:
                logger.info("用户取消了视频文件选择")
        else:
            # 播放视频
            item: QListWidgetItem = self.itemAt(event.pos())
            parent_widget: QTabWidget = self.parent()
            logger.info(f"用户双击播放视频: {item.text()}, 路径: {item.toolTip()}")
            play_video_inside(self, item=[item.text(), item.toolTip()], index_widget=parent_widget.widget(1))
            super().mouseDoubleClickEvent(event)

    # 重写菜单栏事件
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        在item上鼠标右击出现菜单栏。
        :param event: 事件类型，不需要传递。
        """
        # 通过鼠标右击的坐标获取item
        item: QListWidgetItem = self.itemAt(event.pos())
        # 判断是否是在item上右击
        if item is not None:
            logger.info(f"用户右键点击视频: {item.text()}")
            # 创建菜单栏
            menu: QMenu = QMenu(self)
            # 创建动作
            delete_action: QAction = QAction(QIcon(os.path.join(Run_Directory, configure_data["右键菜单栏删除图标"])), "删除", self)
            # 绑定动作
            delete_action.triggered.connect(lambda: pop_item(self, item))
            # 添加动作
            menu.addAction(delete_action)
            # 进入菜单栏事件循环，并设置鼠标右击时的全局坐标为菜单栏位置
            menu.exec(event.globalPos())

