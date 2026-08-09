import lvgl as lv
from ybMain.base_app import BaseApp
from ybUtils.Configuration import Configuration

import sys, os, gc, time,  _thread

sys.path.append(os.getcwd())

from ybUtils.modal_dialog import ModalDialog

# 导入所有页面
from apps.hardware_test.hw.adc import ADCTestPage
from apps.hardware_test.hw.beep import BEEPTestPage
from apps.hardware_test.hw.pwm import PWMTestPage
from apps.hardware_test.hw.rgb import RGBTestPage
from apps.hardware_test.hw.uart import UARTTestPage

class App(BaseApp):
    def __init__(self, app_manager):
        try:
            with open("/sdcard/apps/hardware_test/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            pass
            img_bg = None
        try:
            with open("/sdcard/apps/hardware_test/dock_icon.png", 'rb') as f:
                bg_image_cache = f.read()
                dock_icon = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
                self.dock_icon = dock_icon
        except Exception as e:
            self.dock_icon = None         
        
        self.config = app_manager.config
        self.text_config = app_manager.text_config

        super().__init__(app_manager, name=self.text_config.get_section("System")["HardwareTest"], icon=img_bg)
        
        pass
        
        # 类别和名称映射
        self.category_mapping = {
            # self.text_config.get_section("hardware_test")["adc"]["title"]: "adc",
            self.text_config.get_section("hardware_test")["beep"]["title"]: "beep",
            # self.text_config.get_section("hardware_test")["pwm"]["title"]: "pwm",
            self.text_config.get_section("hardware_test")["rgb"]["title"]: "rgb",
            # self.text_config.get_section("hardware_test")["uart"]["title"]: "uart",
            # self.text_config.get_section("hardware_test")["person_finger_guessing"]["title"]: "person_finger_guessing",
            
            # 其他类别...
        }
        
        self.content = None
        self.category_list = None
        self.detail_panel = None
        self.current_category = None
        self.dialog_helper = None
        self.model_dialog = None

        self.app_manager = app_manager

        
        self.current_selected_option = None
        self.pl = app_manager.pl
        # 初始化页面
        self.hardware_test_pages = {}
        
    def _init(self):
        try:
            # 如果已经存在内容，先清理
            if self.content:
                pass
                self.content.delete()
                self.content = None
                self.category_list = None
                self.detail_panel = None
                self.current_category = None
                self.active_category_btn = None
                self.hardware_test_pages = {}
                
            """初始化界面"""
            pass
            # 创建主内容区域
            self.content = lv.obj(self.screen)
            self.content.set_size(lv.pct(100), 420)
            self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
            self.content.set_style_pad_all(0, 0)
            self.content.set_style_border_width(0, 0)
            self.content.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
            self.content.set_scroll_dir(lv.DIR.NONE)
            self.content.set_style_bg_color(lv.color_hex(0x272223), 0)

            # 创建分割视图（左：类别列表，右：详情）
            self._create_split_view()

            pass
            # 已在父组件中创建
            
            pass
            self._init_hardware_test_pages()
        
            # 默认选择第一个类别
            first_category = list(self.category_mapping.keys())[0]
            # 获取第一个按钮
            if self.category_list and self.category_list.get_child_cnt() > 0:
                first_btn = self.category_list.get_child(0)
                pass
                self._select_category(first_category, first_btn)
            
            pass
        except Exception as e:  
            pass
    
    def initialize(self):
        _thread.start_new_thread(self._init,())
    
    def _init_hardware_test_pages(self):
        """初始化所有页面"""
        try:
            gc.collect()
            try:
                lang_path = self.config.get_section("language").get("text_path", "")
                text_config = Configuration.load_from_file(lang_path)
            except Exception as e:
                pass
                text_config = {}
                
            self.hardware_test_pages = {}
            # self.hardware_test_pages["adc"] = ADCTestPage(self, self.detail_panel, self.config, text_config)
            # pass
            
            self.hardware_test_pages["beep"] = BEEPTestPage(self, self.detail_panel, self.config, text_config)
            pass
            
            # self.hardware_test_pages["pwm"] = PWMTestPage(self, self.detail_panel, self.config, text_config)
            pass
            
            self.hardware_test_pages["rgb"] = RGBTestPage(self, self.detail_panel, self.config, text_config)
            pass
            
            # self.hardware_test_pages["uart"] = UARTTestPage(self, self.detail_panel, self.config, text_config)
            # pass
                      
        except Exception as e:
            print("_init_hardware_test_pages: ", e)
            pass

    def _create_split_view(self):
        """创建左侧类别列表和右侧详情的分割视图"""
        pass
        # 创建水平弹性容器
        flex_container = lv.obj(self.content)
        flex_container.set_size(lv.pct(100), lv.pct(100))
        flex_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        flex_container.set_style_pad_all(0, 0)
        flex_container.set_style_border_width(0, 0)
        flex_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        flex_container.set_scroll_dir(lv.DIR.NONE)
        flex_container.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)  # 稍微亮一点的背景色
        
        # 左侧类别面板（30%宽度）
        self.category_list = lv.list(flex_container)
        self.category_list.set_size(lv.pct(30), lv.pct(100))
        self.category_list.set_style_radius(0, 0)
        # self.category_list.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)  # old
        self.category_list.set_style_bg_color(lv.color_hex(0xffffff), 0)  # 稍微亮一点的背景色
        self.category_list.set_style_pad_all(0, 0)
        self.category_list.set_style_border_width(0,0)
        self.category_list.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        
        # 启用垂直滚动支持（如果类别很多）
        self.category_list.set_scrollbar_mode(lv.SCROLLBAR_MODE.AUTO)
        self.category_list.set_scroll_dir(lv.DIR.VER)

        # 设置滚动条样式
        self.category_list.set_style_bg_opa(lv.OPA._40, lv.PART.SCROLLBAR)
        self.category_list.set_style_bg_color(lv.color_hex(0x9e9e9e), lv.PART.SCROLLBAR)
        self.category_list.set_style_width(6, lv.PART.SCROLLBAR)  # 滚动条宽度
        self.category_list.set_style_radius(3, lv.PART.SCROLLBAR)  # 滚动条圆角
        
        
        # 添加右侧阴影效果，增强深度感
        self.category_list.set_style_shadow_width(15, 0)
        self.category_list.set_style_shadow_ofs_x(5, 0)
        self.category_list.set_style_shadow_ofs_y(0, 0)
        self.category_list.set_style_shadow_color(lv.color_hex(0xcccccc), 0)
        self.category_list.set_style_shadow_opa(lv.OPA._30, 0)
        
        # 创建类别按钮
        pass
        
        # 保存当前选中的按钮引用
        self.active_category_btn = None
        
        for category in self.category_mapping.keys():
            btn = lv.btn(self.category_list)
            btn.set_size(lv.pct(100), 60)  # 稍微增大按钮高度，提高可点击区域
            btn.set_style_radius(0, 0)
            
            # 默认状态
            # btn.set_style_bg_color(lv.color_hex(0xf5f5f5), 0) old
            btn.set_style_bg_color(lv.color_hex(0xffffff), 0)
            btn.set_style_border_width(0, 0)
            btn.set_style_pad_all(10, 0)  # 增加内边距
            btn.set_style_pad_left(20, 0)  # 左侧多一些内边距
            
            
            # 按下状态
            btn.set_style_bg_color(lv.color_hex(0xe8f0fe), lv.STATE.PRESSED)
            
            # 添加左侧边框指示选中项
            btn.set_style_border_side(lv.BORDER_SIDE.LEFT, lv.STATE.CHECKED)
            btn.set_style_border_width(8, lv.STATE.CHECKED)
            btn.set_style_border_color(lv.color_hex(0x22221c), lv.STATE.CHECKED)  # 蓝色边框
            
            btn.set_style_bg_color(lv.color_hex(0xe8f0fe), lv.STATE.CHECKED)  # 淡蓝色背景
            
            # 为按钮添加标签
            label = lv.label(btn)
            label.set_text(category)
            label.set_style_text_color(lv.color_hex(0x333333), 0)
            label.set_style_text_color(lv.color_hex(0x1a73e8), lv.STATE.CHECKED)  # 选中时文字变色
            label.set_align(lv.ALIGN.RIGHT_MID)  # 文本右对齐
            label.set_width(lv.pct(80)) 
            # 设置长文本模式为滚动
            label.set_long_mode(lv.label.LONG.SCROLL)
            
            # 为每个按钮添加独立的点击事件处理
            btn.add_event(lambda e, cat=category, b=btn: self._select_category(cat, b), lv.EVENT.CLICKED, None)
        
        # 右侧详情面板（70%宽度）
        self.detail_panel = lv.obj(flex_container)
        self.detail_panel.set_size(lv.pct(70), lv.pct(100))
        self.detail_panel.set_style_radius(0, 0)
        self.detail_panel.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)
        self.detail_panel.set_style_pad_all(20, 0)  # 增加内边距，内容不会太靠边
        self.detail_panel.set_style_border_width(0, 0)
        self.detail_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.detail_panel.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
        
        spinner = lv.spinner(self.detail_panel, 1000, 60)
        spinner.set_size(50, 50)
        spinner.set_style_arc_width(4, lv.PART.INDICATOR)  # 设置指示器部分的粗细为10像素
        spinner.set_style_arc_width(4, lv.PART.MAIN)       # 设置主体部分的粗细为10像素
        # spinner.set_content_width(5)
        spinner.center()
        # 添加一条细线作为左右面板分隔
        line = lv.line(flex_container)
        line.set_style_line_width(1, 0)
        line.set_style_line_color(lv.color_hex(0xe0e0e0), 0)
        line.set_pos(self.category_list.get_width(), 0)
        
        # 准备线条点
        line_points = [
            {"x": 0, "y": 0},
            {"x": 0, "y": self.content.get_height()}
        ]
        line.set_points(line_points, 2)
        
        pass
    
    def _select_category(self, category, btn):
        """选择类别，并更新UI状态"""
        pass
        
        # 清除之前按钮的选中状态
        if self.active_category_btn:
            self.active_category_btn.clear_state(lv.STATE.CHECKED)
        
        # 设置当前按钮为选中状态
        btn.add_state(lv.STATE.CHECKED)
        self.active_category_btn = btn
        
        # 获取类别对应的页面
        try:
            page_key = self.category_mapping.get(category)
            if page_key and page_key in self.hardware_test_pages:
                page = self.hardware_test_pages[page_key]
                # gc.collect()
                page.display()
            else:
                pass
        except Exception as e:
            print(e)
    
    def on_back(self, evt=None):
        self.app_manager.YbRGB.show_rgb((0,0,0))
        return super().on_back(evt)
    
    def deinitialize(self):
        """清理资源"""
        print("hardware_test deinitialize")
        for page_key, page in self.hardware_test_pages.items():
            if hasattr(page, 'cleanup') and callable(page.cleanup):
                try:
                    page.cleanup()
                except Exception as e:
                    print("cleanup error: ", e)
                    pass
        print("start del")
        # 删除UI元素
        if self.content:
            self.content.delete()
            self.content = None
        
        self.category_list = None
        self.detail_panel = None
        self.current_category = None
        self.active_category_btn = None
        
        # 清空页面字典
        self.hardware_test_pages = {}
        
        # 如果有对话框，也需要清理
        if self.model_dialog:
            self.model_dialog.close()
            self.model_dialog = None
        print("finish del")
        
        gc.collect()