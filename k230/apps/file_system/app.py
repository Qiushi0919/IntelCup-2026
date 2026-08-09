import lvgl as lv
from ybMain.base_app import BaseApp
import os,time
from ybMain.base_app import BaseApp
from ybUtils.Configuration import Configuration
from ybUtils.modal_dialog import ModalDialog

def get_file_info(file_path):
    try:
        # 获取文件状态信息
        stat_info = os.stat(file_path)
        
        # 判断文件类型
        if stat_info[0] & 0x4000:  # 目录
            file_type = 'directory'
        else:
            file_type = 'file'
        
        # 文件位置
        file_location = file_path
        
        # 文件大小（以KB为单位）
        file_size_kb = stat_info[6] / 1024  # 转换为KB
        
        return (file_type, file_location, file_size_kb)
    
    except OSError as e:
        pass
        return None

class App(BaseApp):
    def __init__(self, app_manager):
        try:
            with open("/sdcard/apps/file_system/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            pass
            img_bg = None
        self.app_manager = app_manager            
        # 加载配置
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        super().__init__(app_manager, self.text_config.get_section("System")["FileSystem"], icon=img_bg)
        self.pl = app_manager.pl
        self.texts = self.text_config.get_section("FileSystem")
        
        # 文件管理器相关变量
        self.current_path = "/data"  # 起始路径设为/data
        self.path_history = []
        self.file_list = None
        self.path_label = None
        self.content = None
        self.model_dialog = None

    def initialize(self):
        """初始化文件管理系统界面"""
        # 创建文件管理器主体内容区
        self.text_config = self.app_manager.text_config
        self.content = lv.obj(self.screen)
        self.content.set_size(lv.pct(100), 420)
        self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.content.set_style_bg_color(lv.color_hex(0xf8f9fa), 0)
        self.content.set_style_border_width(0, 0)
        self.content.set_style_pad_all(5, 0)
        
        # 已在父组件中创建
        
        
        # 创建状态栏
        self.create_status_bar()
        
        # 创建文件列表
        self.create_file_list()
        
        # 加载当前目录文件
        self.load_directory()
    
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = lv.obj(self.content)
        status_bar.set_size(lv.pct(100), lv.pct(10))
        status_bar.align(lv.ALIGN.TOP_MID, 0, 0)
        status_bar.set_style_bg_color(lv.color_hex(0xc4c4c4), 0)
        status_bar.set_style_radius(0, 0)
        status_bar.set_style_border_width(0, 0)
        status_bar.set_style_pad_all(5, 0)
        status_bar.set_flex_flow(lv.FLEX_FLOW.ROW)
        status_bar.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 返回按钮
        back_btn = lv.btn(status_bar)
        back_btn.set_size(40, 30)
        back_btn.add_event(self.on_back_clicked, lv.EVENT.CLICKED, None)
        back_btn.set_style_bg_color(lv.color_hex(0xc4c4c4), 0)  # 深蓝色按钮
        back_btn.set_style_shadow_width(0, 0)
        
        back_label = lv.label(back_btn)
        back_label.set_style_text_color(lv.color_black(), 0)
        back_label.set_text(lv.SYMBOL.LEFT)
        back_label.center()
        
        # 当前路径标签
        self.path_label = lv.label(status_bar)
        self.path_label.set_text(self.current_path)
        self.path_label.set_style_text_color(lv.color_black(), 0)
        self.path_label.set_long_mode(lv.label.LONG.SCROLL_CIRCULAR)
        self.path_label.set_width(lv.pct(80))
        
    def create_file_list(self):
        """创建文件列表"""
        self.file_list = lv.list(self.content)
        self.file_list.set_size(lv.pct(100), lv.pct(90))
        self.file_list.center()
        self.file_list.set_style_bg_color(lv.color_white(), 0)
        self.file_list.set_style_border_width(0, 0)
        self.file_list.set_style_pad_all(2, 0)
        self.file_list.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        
        # 为列表项设置样式
        # 为列表项设置样式
        style_btn = lv.style_t()
        style_btn.init()
        style_btn.set_bg_color(lv.color_white())
        style_btn.set_border_width(0)
        style_btn.set_radius(8)
        style_btn.set_pad_all(10)  # 使用内边距而不是外边距
        style_btn.set_shadow_width(5)
        style_btn.set_shadow_ofs_y(2)
        style_btn.set_shadow_opa(lv.OPA._30)
        style_btn.set_shadow_color(lv.color_hex(0xaaaaaa))

        # 设置外边距
        style_btn.set_margin_left(5)
        style_btn.set_margin_right(5)
        style_btn.set_margin_top(5)
        style_btn.set_margin_bottom(5)

        
        self.file_list.add_style(style_btn, lv.PART.MAIN)
        
    def load_directory(self):
        """加载当前目录的内容到列表中"""
        self.file_list.clean()
        self.path_label.set_text(self.current_path)
        
        try:
            # 获取当前目录的文件和文件夹
            items = os.listdir(self.current_path)
            
            # 首先添加文件夹
            for item in sorted(items):
                full_path = self.current_path
                if self.current_path != "/":
                    full_path += "/"
                full_path += item
                
                try:
                    # 检查是否为目录 - 修复stat返回值处理方式
                    stat_result = os.stat(full_path)
                    # MicroPython中，stat_result[0]存储文件模式，需要按位检查是否为目录
                    is_dir = (stat_result[0] & 0x4000) != 0
                    
                    if is_dir:
                        folder_text = self.texts["folder"]
                        btn = self.file_list.add_btn(lv.SYMBOL.DIRECTORY, f"{item} ({folder_text})")
                        btn.set_style_bg_color(lv.color_hex(0xfafafa), 0)
                        
                        # 使用函数避免闭包问题
                        btn.add_event(self.create_folder_event_handler(full_path), lv.EVENT.CLICKED, None)
                except Exception as e:
                    pass
            
            # 然后添加文件
            for item in sorted(items):
                full_path = self.current_path
                if self.current_path != "/":
                    full_path += "/"
                full_path += item
                
                try:
                    # 检查是否为文件 - 修复stat返回值处理方式
                    stat_result = os.stat(full_path)
                    # MicroPython中，stat_result[0]存储文件模式，需要按位检查是否为目录
                    is_dir = (stat_result[0] & 0x4000) != 0
                    
                    if not is_dir:
                        # 根据文件扩展名选择图标
                        icon = lv.SYMBOL.FILE
                        file_text = self.texts["file"]
                        if item.endswith(".py") or item.endswith(".mpy"):
                            icon = lv.SYMBOL.FILE
                            file_text = self.texts["code"]
                        elif (item.endswith(".txt") or item.endswith(".log") or 
                            item.endswith(".md") or item.endswith(".json")):
                            icon = lv.SYMBOL.FILE
                            file_text = self.texts["text"]
                        elif (item.endswith(".jpg") or item.endswith(".jpeg") or 
                            item.endswith(".png") or item.endswith(".bmp")):
                            icon = lv.SYMBOL.IMAGE
                            file_text = self.texts["img"]
                        elif (item.endswith(".mp4") or item.endswith(".265") or 
                            item.endswith(".264")):
                            icon = lv.SYMBOL.VIDEO
                            file_text = self.texts["video"]
                        elif (item.endswith(".wav")):
                            icon = lv.SYMBOL.AUDIO                        
                            file_text = self.texts["audio"]
                        btn = self.file_list.add_btn(icon, f"{item} ({file_text})")
                        btn.set_style_bg_color(lv.color_white(), 0)
                        
                        # 使用函数避免闭包问题
                        btn.add_event(self.create_file_event_handler(full_path), lv.EVENT.CLICKED, None)
                except Exception as e:
                    pass
                    
        except Exception as e:
            # 如果出错，添加错误消息
            error_text = self.texts["error"]
            self.file_list.add_btn(lv.SYMBOL.WARNING, f"{error_text}: {str(e)}")
            pass
    
    def create_folder_event_handler(self, path):
        """创建文件夹点击事件处理函数"""
        def event_handler(evt):
            self.on_folder_clicked(evt, path)
        return event_handler

    def create_file_event_handler(self, path):
        """创建文件点击事件处理函数"""
        def event_handler(evt):
            self.on_file_clicked(evt, path)
        return event_handler    
    
    def on_folder_clicked(self, evt, path):
        """处理文件夹点击事件"""
        if evt.get_code() == lv.EVENT.CLICKED:
            # 保存当前路径到历史记录
            self.path_history.append(self.current_path)
            
            # 更新当前路径并加载新目录
            self.current_path = path
            self.load_directory()
    
    def on_file_clicked(self, evt, path):
        """处理文件点击事件"""
        if evt.get_code() == lv.EVENT.CLICKED:
            # 创建文件信息弹窗
            file_info = get_file_info(path)
            file_text = self.texts["file"]
            item = path.replace('\\', '/').split('/')[-1]
            icon = lv.SYMBOL.FILE
            if item.endswith(".py") or item.endswith(".mpy"):
                icon = lv.SYMBOL.FILE
                file_text = self.texts["code"]
            elif (item.endswith(".txt") or item.endswith(".log") or 
                item.endswith(".md") or item.endswith(".json")):
                icon = lv.SYMBOL.FILE
                file_text = self.texts["text"]
            elif (item.endswith(".jpg") or item.endswith(".jpeg") or 
                item.endswith(".png") or item.endswith(".bmp")):
                icon = lv.SYMBOL.IMAGE
                file_text = self.texts["img"]
            elif (item.endswith(".mp4") or item.endswith(".265") or 
                item.endswith(".264")):
                icon = lv.SYMBOL.VIDEO
                file_text = self.texts["video"]
            elif (item.endswith(".wav")):     
                icon = lv.SYMBOL.AUDIO                 
                file_text = self.texts["audio"]          
            try:
                self.model_dialog.show(
                    title=item,
                    content=f"{self.text_config.get_section("FileSystem")["file_type"]}:{file_text}\n{self.text_config.get_section("FileSystem")["file_position"]}:{path}\n{self.text_config.get_section("FileSystem")["file_size"]}:{file_info[2]}KB",
                    icon_symbol=icon,
                    btn_texts=[self.text_config.get_section("System")["Ok"]],
                    width=480,
                    height=300
                )
            except Exception as e:
                pass
            
            pass
    
    def on_back_clicked(self, evt):
        """处理返回按钮点击事件"""
        if evt.get_code() == lv.EVENT.CLICKED:
            if self.path_history:
                # 从历史记录中恢复上一个路径
                self.current_path = self.path_history.pop()
                self.load_directory()
            elif self.current_path != "/":
                # 如果没有历史记录但不在根目录，返回上一级
                self.current_path = "/".join(self.current_path.split("/")[:-1])
                if self.current_path == "":
                    self.current_path = "/"
                self.load_directory()
    
    def deinitialize(self):
        """清理资源"""
        # 清除文件管理器的相关对象和变量
        if self.file_list:
            self.file_list.delete()
            self.file_list = None
        
        if self.path_label:
            self.path_label.delete()
            self.path_label = None
        
        if self.content:
            self.content.delete()
            self.content = None
            
        self.current_path = "/data"
        self.path_history = []