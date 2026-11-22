import os
import sys
import psutil
import json
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget, QMessageBox
from PySide6.QtGui import QIcon
from HandBook import *
from Mutual import *
from initialize import *


# 主窗口类
class TaoLi(QWidget):
    # 初始化方法
    def __init__(self, parent=None) -> None:
        """
        :param parent: 该类的父类，QT的任何类。
        """
        # 调用父类初始化方法
        super().__init__(parent=parent)
        # 设置标题
        self.setWindowTitle(configure_data["程序名称"])
        # 设置窗口初始尺寸
        self.resize(configure_data["窗口初始大小"][0], configure_data["窗口初始大小"][1])
        # 设置图标
        try:
            icon_path = os.path.join(Run_Directory, configure_data["程序图标"])
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.info(f"程序图标加载成功: {icon_path}")
            else:
                logger.warning(f"程序图标文件不存在: {icon_path}")
        except Exception as e:
            logger.error(f"程序图标加载失败: {e}")
        
        _font = self.font()
        _font.setPixelSize(18)
        self.setFont(_font)
        # 修改主程序窗口地址
        configure_data["主程序窗口地址"]: TaoLi = self
        # 创建布局管理器和分割器布局管理器
        horizontal_layout: QHBoxLayout = QHBoxLayout()
        splitter: QSplitter = QSplitter()
        # 创建手册框架
        self.hand_book: HandBook = HandBook(self)
        # 交互框架
        self.mutual: Mutual = Mutual(self)
        # 设置布局管理器四周间距
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        # 向布局管理器添加控件并设置布局管理器
        splitter.addWidget(self.hand_book)
        splitter.addWidget(self.mutual)
        splitter.setSizes([300, 700])
        horizontal_layout.addWidget(splitter)
        self.setLayout(horizontal_layout)
        # 设置字体
        try:
            font_path = os.path.join(Run_Directory, configure_data["字体"])
            if os.path.exists(font_path):
                set_font(font_path)
                logger.info(f"字体加载成功: {font_path}")
            else:
                logger.warning(f"字体文件不存在: {font_path}")
        except Exception as e:
            logger.error(f"字体加载失败: {e}")
        # 设置字体尺寸
        set_size(configure_data["字体尺寸"])

    # 重写摧毁事件 -> 保存/更新数据
    def closeEvent(self, event) -> None:
        """
        重写摧毁事件 -> 保存/更新数据
        :param event: 事件类型，不需要传递。
        """
        logger.info("程序关闭")
        try:
            # 获取视频目录控件
            widget: VideoList = self.hand_book.widget(0)
            # 获取播放器
            player: VideoPlayer = configure_data["播放器地址"]
            # 判断视频状态做清理操作
            if player and (player.is_playing or player.paused):
                # 停止视频播放
                player.stop()
                # 获取定时器地址
                timer: QTimer = configure_data["定时器地址"]
                if timer:
                    # 暂停定时器
                    timer.stop()
            # 更新序列
            update_sequence(widget.get_sequence())
            logger.info("视频序列已保存")
        except Exception as e:
            logger.error(f"关闭事件处理失败: {e}")
        finally:
            # 将配置文件中的地址数据设为null -> 以防止报错
            configure_data["主程序窗口地址"] = None
            configure_data["播放器地址"] = None
            configure_data["播放列表地址"] = None
            configure_data["表格页地址"] = None
            configure_data["定时器地址"] = None
            configure_data["简介框架地址"] = None
            # 更新配置文件
            try:
                with open(os.path.join(Run_Directory, 'Configure/program.json'), 'w+', encoding='utf-8') as fp:
                    json.dump(configure_data, fp, indent=4, ensure_ascii=False)
            except Exception as e:
                pass


# 检查程序是否已运行
def check_running() -> bool:
    """
    检查程序是否已运行
    :return: 如果已运行返回True，否则返回False
    """
    try:
        # 获取当前脚本的完整路径
        current_script = os.path.abspath(__file__)
        # 获取所有Python进程
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] in ['python.exe', 'pythonw.exe']:
                    cmdline = proc.info.get('cmdline', [])
                    # 检查命令行参数中是否包含当前脚本的路径
                    if any(current_script in arg for arg in cmdline):
                        python_processes.append(proc)
            except:
                pass
        # 过滤掉当前进程
        other_processes = [p for p in python_processes if p.pid != os.getpid()]
        return len(other_processes) > 0
    except Exception as e:
        return False


# 显示"程序已运行"提示弹窗
def show_already_running_dialog() -> None:
    """
    显示"程序已经运行，请勿再次运行"提示弹窗。
    """
    box = QMessageBox()
    box.setWindowTitle(configure_data.get("程序名称", "满城桃李"))
    box.setText("程序已经运行，请勿再次运行")
    box.setIcon(QMessageBox.Warning)
    # 设置窗口图标为配置文件里的程序图标
    try:
        icon_path = os.path.join(Run_Directory, configure_data.get("程序图标", ""))
        if os.path.exists(icon_path):
            box.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    box.exec()


# 播放外部视频
def play_external_video(app, man_cheng, second_parameter: str) -> None:
    """
    播放外部视频
    :param app: QApplication实例
    :param man_cheng: 主窗口实例
    :param second_parameter: 视频文件路径
    """
    try:
        # 判断文件后缀是否符合要求
        file_ext = f'.{second_parameter.split(".")[-1].lower()}'
        if file_ext in configure_data["可识别格式"]:
            item_data: list = [os.path.basename(os.path.abspath(second_parameter)), os.path.abspath(second_parameter)]
            logger.info(f"外部视频: {second_parameter}, 扩展名: {file_ext}")
            # 获取索引、列表控件地址
            index_widget: IndexWidget = man_cheng.hand_book.widget(1)
            list_widget: VideoList = man_cheng.hand_book.widget(0)
            # 若不在列表中则添加（相当于手动添加，只是入口不同）
            if fingerprint(second_parameter) not in video_hash:
                add_item(list_widget, item_data)
                logger.info("外部视频已添加到列表")
            else:
                logger.info("视频已在列表中，直接播放")
            # 播放视频
            play_video_external(item_data, index_widget)
        else:
            logger.warning(f"不支持的视频格式: {file_ext}")
            # 退出程序
            sys.exit(0)
    except Exception as e:
        logger.error(f"播放外部视频失败: {e}")


# 主函数
def main():
    """
    主函数
    """
    logger.info("=" * 50)
    logger.info("程序启动")

    # 创建应用程序（Qt6 已默认启用高 DPI 缩放，无需手动声明）
    app = QApplication(sys.argv)

    # 检查程序是否已运行
    if check_running():
        logger.warning("程序已在运行，退出")
        # 显示提示弹窗后退出
        show_already_running_dialog()
        sys.exit(0)

    # 创建主程序窗口类并显示
    man_cheng = TaoLi()
    man_cheng.show()
    logger.info("主窗口显示完成")

    # 处理命令行参数
    if len(app.arguments()) > 1:
        second_parameter: str = app.arguments()[1]
        # 判断是否是文件并文件是否存在
        if os.path.exists(second_parameter) and not os.path.isdir(second_parameter):
            logger.info(f"检测到命令行参数: {second_parameter}")
            play_external_video(app, man_cheng, second_parameter)

    # 进入事件循环
    sys.exit(app.exec())


# 调试
if __name__ == '__main__':
    main()