from video_dir import *
from index_dir import *
from setting_dir import *


# 手册框架
class HandBook(QTabWidget):
    # 初始化方法
    def __init__(self, parent: QObject = None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 创建目录
        self.video_dir: VideoList = VideoList()
        self.index_dir: IndexWidget = IndexWidget()
        self.setting_dir = SettingFrame()
        # 添加页面
        self.addTab(self.video_dir, "视频")
        self.addTab(self.index_dir, "索引")
        self.addTab(self.setting_dir, "关于/设置")

