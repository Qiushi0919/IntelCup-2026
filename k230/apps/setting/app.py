import lvgl as lv
from ybMain.base_app import BaseApp
from ybUtils.Configuration import Configuration


import sys, os, _thread

sys.path.append(os.getcwd())

from apps.setting.dialog_helper import DialogHelper

# 导入所有设置页面
from apps.setting.device_settings import DeviceSettingsPage
from apps.setting.wifi_settings import WiFiSettingsPage
from apps.setting.hotspot_settings import HotspotSettingsPage
from apps.setting.display_settings import DisplaySettingsPage
from apps.setting.sound_settings import SoundSettingsPage
from apps.setting.security_settings import SecuritySettingsPage
from apps.setting.datetime_settings import DateTimeSettingsPage
from apps.setting.personalization_settings import PersonalizationSettingsPage
from apps.setting.language_settings import LanguageSettingsPage
from apps.setting.more_setting import MoreSettingsPage


# 全局异常处理函数
def safe_execute(func, *args, **kwargs):
    """安全执行函数，捕获异常但不让程序崩溃"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        pass
        pass
        return None


# LVGL引用错误定义
class LvReferenceError(Exception):
    """LVGL对象引用错误，通常是对象已被删除"""
    pass


class App(BaseApp):
    def __init__(self, app_manager):
        try:
            with open("/sdcard/apps/setting/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            pass
            img_bg = None
            
        try:
            with open("/sdcard/apps/setting/dock_icon.png", 'rb') as f:
                bg_image_cache = f.read()
                dock_icon = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
                self.dock_icon = dock_icon
        except Exception as e:
            self.dock_icon = None
        self.app_manager = app_manager            
        # 加载配置
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        pass
            
        super().__init__(app_manager, name=self.text_config.get_section("System")["Settings"], icon=img_bg)
        
        pass
        # 设置类别和名称映射
        self.category_mapping = {
            self.text_config.get_section("Settings")["my_device"]["title"]: "device",
            self.text_config.get_section("Settings")["WLAN"]["title"]: "wifi",
            # self.text_config.get_section("Settings")["AP"]["title"]: "hotspot",
            # self.text_config.get_section("Settings")["display"]["title"]: "display", 
            self.text_config.get_section("Settings")["sound"]["title"]: "sound",
            # self.text_config.get_section("Settings")["security"]["title"]: "security",
            # self.text_config.get_section("Settings")["time_date"]["title"]: "datetime",
            # self.text_config.get_section("Settings")["personalization"]["title"]: "personalization",
            self.text_config.get_section("Settings")["language"]["title"]: "language",
            # self.text_config.get_section("Settings")["more"]["title"]: "more",
        }
        
        self.content = None
        self.category_list = None
        self.detail_panel = None
        self.current_category = None
        self.dialog_helper = None
        self.model_dialog = None

        self.current_selected_option = None
        
        # 初始化设置页面
        self.setting_pages = {}
        
        self.ybnet = app_manager.ybnet
        
        # 设置对象引用字典，用于检测对象是否有效
        self.lv_objects = {}

    def _check_obj_valid(self, obj):
        """检查LVGL对象是否有效"""
        try:
            # 尝试访问对象的一个属性，如果对象已被删除会引发异常
            _ = obj.get_style_bg_color(0)
            return True
        except Exception:
            return False

    def _init(self):
        try:
            # 创建主内容区域
            self.text_config = self.app_manager.text_config
            
            self.content = lv.obj(self.screen)
            self.lv_objects['content'] = self.content
            self.content.set_size(lv.pct(100), 420)
            self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
            self.content.set_style_pad_all(0, 0)
            self.content.set_style_border_width(0, 0)
            self.content.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条
            self.content.set_scroll_dir(lv.DIR.NONE)  # 禁用滚动方向
            self.content.set_style_bg_color(lv.color_hex(0x272223), 0)

            # 创建分割视图（左：类别列表，右：详情）
            safe_execute(self._create_split_view)
            
            # 创建对话框助手
            pass
            self.dialog_helper = DialogHelper(self.screen, self.text_config)

            # pass
            # # 已在父组件中创建
            
            pass
            # 初始化设置页面
            safe_execute(self._init_setting_pages)
            
            pass
        
            # 默认选择第一个类别
            first_category = list(self.category_mapping.keys())[0]
            pass
            safe_execute(self._select_category, first_category)
            
            pass
        except Exception as e:
            print(e)
    
    def initialize(self):
        _thread.start_new_thread(self._init, ())

    def _init_setting_pages(self):
        """初始化所有设置页面"""
        try:
            self.setting_pages = {}
            # 使用异常处理包装每个页面的初始化
            try:
                self.setting_pages["device"] = DeviceSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["wifi"] = WiFiSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["hotspot"] = HotspotSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            # try:
            #     self.setting_pages["display"] = DisplaySettingsPage(self, self.detail_panel, self.config, self.text_config)
            # except Exception as e:
            #     pass
                
            try:
                self.setting_pages["sound"] = SoundSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["security"] = SecuritySettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["datetime"] = DateTimeSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["personalization"] = PersonalizationSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["language"] = LanguageSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
            try:
                self.setting_pages["more"] = MoreSettingsPage(self, self.detail_panel, self.config, self.text_config)
            except Exception as e:
                pass
                
        except Exception as e:
            pass

    def _create_split_view(self):
        """创建左侧类别列表和右侧详情的分割视图"""
        try:
            # 创建水平弹性容器
            flex_container = lv.obj(self.content)
            self.lv_objects['flex_container'] = flex_container
            flex_container.set_size(lv.pct(100), lv.pct(100))
            flex_container.set_flex_flow(lv.FLEX_FLOW.ROW)
            flex_container.set_style_pad_all(0, 0)
            flex_container.set_style_pad_column(0, 0)  # 确保子对象之间无间距
            flex_container.set_style_border_width(0, 0)
            flex_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
            flex_container.set_scroll_dir(lv.DIR.NONE)
            flex_container.set_style_bg_color(lv.color_hex(0x282c34), 0)

            # 左侧类别面板（30%宽度）
            self.category_list = lv.list(flex_container)
            self.lv_objects['category_list'] = self.category_list
            self.category_list.set_size(lv.pct(30), lv.pct(100))
            self.category_list.set_style_radius(0, 0)
            self.category_list.set_style_bg_color(lv.color_hex(0xf0f0f0), 0)
            self.category_list.set_style_pad_all(0, 0)
            self.category_list.set_style_pad_row(0, 0)  # 确保列表项无间距
            self.category_list.set_style_border_width(0, 0)
            self.category_list.set_style_margin_all(0, 0)  # 移除外边距
            self.category_list.set_flex_flow(lv.FLEX_FLOW.COLUMN)

            # 创建类别按钮
            for category in self.category_mapping.keys():
                btn = lv.btn(self.category_list)
                self.lv_objects[f'btn_{category}'] = btn
                btn.set_size(lv.pct(100), 50)
                btn.set_style_radius(0, 0)
                btn.set_style_bg_color(lv.color_hex(0xf0f0f0), 0)
                btn.set_style_bg_color(lv.color_hex(0xdddddd), lv.STATE.PRESSED)
                btn.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.STATE.FOCUSED)
                btn.set_style_border_width(0, 0)
                btn.set_style_pad_all(0, 0)
                btn.set_style_margin_all(0, 0)  # 移除按钮外边距

                label = lv.label(btn)
                self.lv_objects[f'label_{category}'] = label
                label.set_text(category)
                label.set_style_text_color(lv.color_hex(0x333333), 0)
                label.center()

                def safe_callback(e, cat=category):
                    safe_execute(self._select_category, cat)
                btn.add_event(safe_callback, lv.EVENT.CLICKED, None)

            # 右侧详情面板（70%宽度）
            self.detail_panel = lv.obj(flex_container)
            self.lv_objects['detail_panel'] = self.detail_panel
            self.detail_panel.set_size(lv.pct(70), lv.pct(100))
            self.detail_panel.set_style_radius(0, 0)
            self.detail_panel.set_style_bg_color(lv.color_hex(0xffffff), 0)
            self.detail_panel.set_style_pad_all(0, 0)  # 改为 0，避免内边距
            self.detail_panel.set_style_border_width(0, 0)
            self.detail_panel.set_style_margin_all(0, 0)  # 移除外边距
            self.detail_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
            self.detail_panel.set_scroll_dir(lv.DIR.VER)
            self.detail_panel.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
        except Exception as e:
            print(f"Error: {e}")  
        
    def _select_category(self, category):
        """显示所选类别的项目"""
        try:
            pass
            if not self._check_obj_valid(self.detail_panel):
                pass
                safe_execute(self._init)
                return
                
            self.current_category = category
            
            # 清空详情面板
            if self._check_obj_valid(self.detail_panel):
                self.detail_panel.clean()
            
            # 获取类别对应的页面
            page_key = self.category_mapping.get(category)
            if page_key and page_key in self.setting_pages:
                page = self.setting_pages[page_key]
                try:
                    page.display()
                except Exception as e:
                    pass
                    # 如果是引用错误，尝试重新初始化该页面
                    if "Referenced object was deleted" in str(e) or isinstance(e, LvReferenceError):
                        pass
                        try:
                            # 动态获取页面类
                            page_class = globals()[page_key.capitalize() + "SettingsPage"] 
                            self.setting_pages[page_key] = page_class(self, self.detail_panel, self.config, self.text_config)
                            self.setting_pages[page_key].display()
                        except Exception as init_err:
                            pass
            else:
                pass
        except Exception as e:
            pass
    
    def show_dropdown(self, event, item):
        """显示下拉选项对话框"""
        try:
            pass
            if "options" in item:
                options = item["options"]
                pass
            else:
                options = ["选项 1", "选项 2", "选项 3"]
                pass
            
            # 定义安全回调
            def safe_option_selected(selected_option, i=item):
                safe_execute(self._on_option_selected, i, selected_option)
            
            # 创建模态对话框
            self.dialog_helper.create_dialog("选择 " + item["name"], options, safe_option_selected)
        except Exception as e:
            pass
    
    def _on_option_selected(self, item, selected_option):
        """处理下拉框选项选择"""
        try:
            pass
            # 更新项目值
            item["value"] = selected_option
            self.current_selected_option = selected_option
            
            # 更新语言配置
            if item["name"] == "选择语言":
                try:
                    if selected_option == "Chinese" or selected_option == "zh_cn":
                        self.config.set_value("language", "text_path", "/sdcard/configs/languages/zh_cn.json")
                    else:
                        self.config.set_value("language", "text_path", "/sdcard/configs/languages/en.json")
                    self.config.save_to_file('/sdcard/configs/sys_config.json')
                    pass
                except Exception as config_err:
                    pass
            
            # 刷新详情面板
            if self._check_obj_valid(self.detail_panel):
                safe_execute(self._select_category, self.current_category)
            
            # 调用项目回调
            if "callback" in item:
                try:
                    item["callback"](None)
                except Exception as callback_err:
                    pass
        except Exception as e:
            pass
    
    def deinitialize(self):
        """清理资源"""
        try:
            pass
            # 清理LVGL对象引用
            for key in list(self.lv_objects.keys()):
                self.lv_objects[key] = None
            self.lv_objects.clear()
            
            # 清理设置页面
            for key in list(self.setting_pages.keys()):
                try:
                    if hasattr(self.setting_pages[key], 'cleanup'):
                        self.setting_pages[key].cleanup()
                except Exception:
                    pass
                self.setting_pages[key] = None
            self.setting_pages.clear()
            
            # 清理其他引用
            self.content = None
            self.category_list = None
            self.detail_panel = None
            self.dialog_helper = None
        except Exception as e:
            pass