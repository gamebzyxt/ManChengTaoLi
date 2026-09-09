import os
import sys
import json
import hashlib
import threading
import logging
from datetime import datetime
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtGui import QFont, QFontDatabase, QIcon
from PyQt5.QtMultimedia import QMediaContent
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QWidget, QMessageBox


# 获取运行目录 -> 当将程序打包成.exe文件并添加到系统环境变量时，获取绝对路径以便找不到路径而报错
Run_Directory: str = os.path.dirname(os.path.realpath(__file__)).replace("_internal", "")

# 配置日志系统
log_dir = os.path.join(Run_Directory, 'Configure/Log')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

# 创建日志记录器
logger = logging.getLogger('ManChengTaoLi')
logger.setLevel(logging.INFO)

# 创建文件处理器
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建日志格式器
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)

# 添加处理器到记录器
if not logger.handlers:
    logger.addHandler(file_handler)

# 读取程序配置文件
try:
    with open(os.path.join(Run_Directory, 'Configure/program.json'), 'r', encoding='utf-8') as fp:
        configure_data: dict = json.load(fp)
    logger.info("配置文件读取成功")
except Exception as e:
    logger.error(f"配置文件读取失败: {e}")
    configure_data = {
        "程序名称": "漫城桃李播放器",
        "窗口初始大小": [1000, 1000],
        "程序图标": "",
        "字体": "",
        "字体尺寸": 18,
        "快退秒数": 10,
        "快进秒数": 10,
        "加音量数": 5,
        "可识别格式": [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"],
        "倍速": ["0.5", "0.75", "1.0", "1.25", "1.5", "2.0"],
        "视频过滤器": "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;所有文件 (*.*)",
        "上次视频选择路径": os.path.expanduser("~"),
        "默认截图保存路径": "./Images/Screenshot/",
        "名言名句": "历史的发展是不以人的意志为转移的。 --毛泽东--",
        "右键菜单栏删除图标": ""
    }

# 获取视频序列
try:
    with open(os.path.join(Run_Directory, 'Configure/sequence.json'), 'r', encoding='utf-8') as fp:
        sequence: list = json.load(fp)["序列"]
    logger.info(f"视频序列读取成功，共 {len(sequence)} 个文件")
except Exception as e:
    logger.error(f"视频序列读取失败: {e}")
    sequence = []

# 全局变量 -> 用于储存视频文件哈希值
video_hash: list = []
# 全局变量 -> 用于保存索引文件
video_name: str = ""


def fingerprint(file_path: str, seed: int = 1024) -> str:
    """
    将传入文件进行哈希，并返回哈希值。
    :param file_path: 文件路径。
    :param seed: 种子值，读取多少字节进行哈希。
    :return: 返回哈希值。
    """
    # 判断文件路径是否合法 -> 目录/文件不存在
    if os.path.isdir(file_path):
        logger.warning(f"路径是目录而非文件: {file_path}")
        return ""
    elif not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return ""

    try:
        # 读取文件
        with open(file_path, 'rb') as f:
            data = f.read(seed)
        return hashlib.sha256(data).hexdigest()
    except Exception as e:
        logger.error(f"文件哈希失败 [{file_path}]: {e}")
        return ""


def add_item(widget: QListWidget, item_data: list) -> None:
    """
    将item添加到列表控件中。
    :param widget: 列表控件。
    :param item_data: 包含item数据的列表，格式为["文本", "提示文本"]。
    """
    try:
        # 创建item，方便后续操作
        item: QListWidgetItem = QListWidgetItem()
        # 设置文本
        item.setText(item_data[0])
        # 设置提示文本
        item.setToolTip(item_data[1])
        # 将创建的item添加到列表中
        widget.addItem(item)
        # 添加文件哈希值
        hash_str = fingerprint(item_data[1])
        if hash_str and hash_str not in video_hash:
            video_hash.append(hash_str)
        logger.info(f"添加视频到列表: {item_data[0]}, 路径: {item_data[1]}, 指纹: {hash_str}")
    except Exception as e:
        logger.error(f"添加item失败: {e}")


def pop_item(widget: QListWidget, item: QListWidgetItem) -> None:
    """
    :param widget: 需要删除的item的列表控件。
    :param item: item数据。
    """
    try:
        # 删除操作
        widget.takeItem(widget.row(item))
        logger.info(f"从列表删除视频: {item.text()}, 路径: {item.toolTip()}")
        # 创建线程对象 -> 删除文件指纹
        thread = threading.Thread(target=clear_fingerprint, args=(item.toolTip(), ))
        # 启动线程对象
        thread.start()
        # 等待多程执行完毕
        thread.join()
    except Exception as e:
        logger.error(f"删除item失败: {e}")


def clear_fingerprint(complete_path: str) -> None:
    """
    清除文件指纹。
    :param complete_path: 文件位置路径。
    """
    try:
        # 尝试文件哈希 -> 可能文件不存在
        hash_str: str = fingerprint(complete_path)
        # 值删除
        if hash_str and hash_str in video_hash:
            video_hash.remove(hash_str)
    except Exception as e:
        pass


def update_sequence(new_sequence: list) -> None:
    """
    更新视频序列。
    :param new_sequence: 新视频序列。
    """
    try:
        # 创建序列字典
        sequence_dict: dict = {
            "序列": new_sequence
        }
        # 写入文件
        with open(os.path.join(Run_Directory, 'Configure/sequence.json'), 'w+', encoding='utf-8') as fp:
            json.dump(sequence_dict, fp, indent=4, ensure_ascii=False)
        logger.info(f"视频序列已更新，共 {len(new_sequence)} 个文件")
    except Exception as e:
        logger.error(f"更新序列失败: {e}")


def index_file(complete_path: str) -> dict:
    """
    获取索引文件，如果没有将创建。
    :param complete_path: 文件位置路径。
    :return: 索引数据，格式为{"简介": "", "索引": [[int, "数据"], ...]}。
    """
    try:
        # 文件哈希
        hash_str: str = fingerprint(complete_path)
        if not hash_str:
            logger.warning(f"无法获取文件指纹: {complete_path}")
            return {"简介": "", "索引": []}
        
        # 创建文件路径 -> 方便后续操作
        file_path: str = os.path.join(Run_Directory, f'Configure/Index/{hash_str}.json')
        # 判断文件是否存在
        if os.path.exists(file_path):
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as fp:
                hash_dict: dict = json.load(fp)
            logger.info(f"索引文件已加载: {file_path}")
            return hash_dict
        
        # 创建数据用于写入文件
        hash_dict: dict = {
            "简介": "",
            "索引": []
        }
        # 创建文件并写入数据
        with open(file_path, 'w+', encoding='utf-8') as fp:
            json.dump(hash_dict, fp, indent=4, ensure_ascii=False)
        logger.info(f"索引文件已创建: {file_path}")

        return hash_dict
    except Exception as e:
        logger.error(f"获取索引文件失败: {e}")
        return {"简介": "", "索引": []}


def play_video_inside(list_widget: QListWidget, item: QListWidgetItem, index_widget: QWidget) -> None:
    """
    播放视频（内部 非程序外部）。
    :param list_widget: 列表控件。
    :param item: item数据，格式为["名称", "真实路径"]。
    :param index_widget: 索引控件。
    """
    global video_name
    try:
        logger.info(f"开始播放内部视频: {item[0]}, 路径: {item[1]}")
        # 判断是否是第一次播放视频 -> 保存索引文件
        if video_name:
            blurb_data: str = index_widget.blurb_frame.video_blur.toPlainText()
            index_data: list = index_widget.pointer_table.get_data()
            # 创建数据用于写入文件
            hash_dict: dict = {
                "简介": blurb_data,
                "索引": index_data
            }
            # 写入文件
            with open(video_name, 'w+', encoding='utf-8') as fp:
                json.dump(hash_dict, fp, indent=4, ensure_ascii=False)
            logger.info(f"上一个视频的索引已保存: {video_name}")

        # 判断文件存不存在
        if not os.path.exists(item[1]):
            logger.warning(f"视频文件不存在，从列表中删除: {item[1]}")
            # 弹出提示弹窗
            try:
                box = QMessageBox()
                box.setWindowTitle(configure_data.get("程序名称", "满城桃李"))
                box.setText(f"视频文件已不存在:\n{item[0]}")
                box.setIcon(QMessageBox.Warning)
                # 设置窗口图标为程序图标
                icon_path = os.path.join(Run_Directory, configure_data.get("程序图标", ""))
                if os.path.exists(icon_path):
                    box.setWindowIcon(QIcon(icon_path))
                box.exec_()
            except Exception as e:
                logger.error(f"显示弹窗失败: {e}")
            # 删除item
            pop_item(list_widget, item)
            return
        
        # 获取索引文件数据
        index_data: dict = index_widget.blurb_frame.update_text(item)
        # 添加行数据
        index_widget.pointer_table.add_rows(index_data["索引"])
        # 获取播放器、播放列表地址
        player: object = configure_data["播放器地址"]
        playlist: object = configure_data["播放列表地址"]
        # 清除视频列表 -> 防止重复播放之前的视频
        playlist.clear()
        content: QMediaContent = QMediaContent(QUrl.fromLocalFile(item[1]))
        playlist.add_media(content)
        playlist.play()
        logger.info(f"视频播放中: {item[1]}")
        # 获取定时器地址 -> 启动定时器
        timer: QTimer = configure_data["定时器地址"]
        timer.start(33)
        # 修改视频名称 -> 用于标记保存索引文件的路径
        video_name = os.path.join(Run_Directory, f'Configure/Index/{fingerprint(item[1])}.json')
    except Exception as e:
        logger.error(f"播放视频（内部）失败: {e}")


def set_font(font_path: str) -> None:
    """
    设置主程序窗口及其子类字体。
    :param font_path: 字体路径。
    """
    try:
        # 获取主程序窗口类
        man_cheng_tao_li_address: QWidget = configure_data["主程序窗口地址"]
        if not man_cheng_tao_li_address:
            return
        
        # 加载字体并设置字体
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                current_font: QFont = QFont(font_families[0])
                # 主程序子类列表
                man_cheng_tao_li_children_address: list = man_cheng_tao_li_address.children()
                # 创建下标 -> 用于判断是否设置完成
                index: int = 0
                # 将所以子类添加到子类列表中
                while index < len(man_cheng_tao_li_children_address):
                    # 再次循环得到子类
                    for widget in man_cheng_tao_li_children_address[index].children():
                        try:
                            # 尝试设置字体 -> 有些控件无设置字体方法
                            widget.setFont(current_font)
                        except:
                            pass
                        # 将子类添加到列表 -> 循环全部子类
                        man_cheng_tao_li_children_address.append(widget)
                    # 下标+1
                    index += 1
                logger.info(f"字体设置成功: {font_path}")
    except Exception as e:
        logger.error(f"设置字体失败: {e}")


def set_size(font_size: str) -> None:
    """
    设置主程序窗口及其子类字体尺寸。
    :param font_size: 字体尺寸。
    """
    try:
        # 获取主程序窗口类
        man_cheng_tao_li_address: QWidget = configure_data["主程序窗口地址"]
        if not man_cheng_tao_li_address:
            return
        
        # 使用 QFont 设置字体大小（不会覆盖样式表）
        font = man_cheng_tao_li_address.font()
        font.setPixelSize(int(font_size))
        man_cheng_tao_li_address.setFont(font)
        
        # 遍历所有子控件并设置字体大小
        for widget in man_cheng_tao_li_address.findChildren(QWidget):
            try:
                widget_font = widget.font()
                widget_font.setPixelSize(int(font_size))
                widget.setFont(widget_font)
            except:
                pass
        logger.info(f"字体尺寸设置成功: {font_size}px")
    except Exception as e:
        logger.error(f"设置字体尺寸失败: {e}")


def play_video_external(item: QListWidgetItem, index_widget: QWidget) -> None:
    """
    播放视频（外部 非程序内部，如命令行参数）。
    :param item: item数据，格式为["名称", "真实路径"]。
    :param index_widget: 索引控件。
    """
    global video_name
    try:
        logger.info(f"开始播放外部视频: {item[0]}, 路径: {item[1]}")
        # 获取索引文件数据
        index_data: dict = index_widget.blurb_frame.update_text(item)
        # 添加行数据
        index_widget.pointer_table.add_rows(index_data["索引"])
        # 获取播放器、播放列表地址
        player: object = configure_data["播放器地址"]
        playlist: object = configure_data["播放列表地址"]
        # 清除视频列表 -> 防止重复播放之前的视频
        playlist.clear()
        content: QMediaContent = QMediaContent(QUrl.fromLocalFile(item[1]))
        playlist.add_media(content)
        playlist.play()
        logger.info(f"外部视频播放中: {item[1]}")
        # 获取定时器地址 -> 启动定时器
        timer: QTimer = configure_data["定时器地址"]
        timer.start(33)
        # 修改视频名称 -> 用于标记保存索引文件的路径
        video_name = os.path.join(Run_Directory, f'Configure/Index/{fingerprint(item[1])}.json')
    except Exception as e:
        logger.error(f"播放视频（外部）失败: {e}")