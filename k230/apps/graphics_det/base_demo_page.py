import lvgl as lv
import gc
from media.display import *
from media.media import *
import time

class BaseDemoPage:
    def __init__(self, app, detail_panel, config):
        self.app = app
        self.detail_panel = detail_panel
        self.config = config
        self.detail_items = []
        
        # 设置面板的全局样式
        self.detail_panel.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)
        self.detail_panel.set_style_pad_all(20, 0)
    
    def display(self):
        self.detail_panel.clean()
        
        # 创建基本布局
        # 1. 图片
        img = lv.img(self.detail_panel)
        img.set_size(385, 250)
        img.align(lv.ALIGN.TOP_MID, 0, 20)
        # 设置图片源
        img_src = self.get_image_source()
        if img_src:
            try:
                img.set_src(img_src)
            except Exception as e:
                pass
            
        # 4. 按钮
        btn = lv.btn(self.detail_panel)
        btn.set_size(385, 50)
        # 使用绝对对齐方式将按钮固定在屏幕底部中间
        # btn.align(lv.ALIGN.BOTTOM_MID, 0, -20)  # 保持原来的对齐方式
        btn.align(lv.ALIGN.TOP_MID, 0, 240)
        
        btn.set_style_bg_color(lv.color_make(0, 0, 0), 0)  # 设置黑色背景
        btn.set_style_radius(10, 0)  # 圆角
        
        btn_label = lv.label(btn)
        btn_label.set_text(self.get_button_text())
        btn_label.set_style_text_color(lv.color_hex(0xffffff), 0)
        btn_label.center()
                        
        # 2. 标题
        title = lv.label(self.detail_panel)
        title.set_text(self.get_title())
        title.set_style_text_font(self.app.app_manager.font_16, 0)
        title.set_style_text_color(lv.color_hex(0x333333), 0)
        title.align(lv.ALIGN.TOP_MID, 0, 280)
        
        
        
        # 添加按钮点击事件
        btn.add_event(self.on_button_click, lv.EVENT.CLICKED, None)
        
        
        # 3. 详细内容介绍
        description = lv.label(self.detail_panel)
        description.set_text(self.get_description())
        description.set_long_mode(lv.label.LONG.WRAP)
        description.set_width(lv.pct(80))
        description.set_style_text_color(lv.color_hex(0x666666), 0)
        description.align(lv.ALIGN.TOP_MID, 0, 340)
        
        
        # 子类可以添加额外的组件
        self.add_extra_components()

    def run_demo(self, module):
        pass
        if self.app.pl is None:
            pass
        else:
            md = None
            try:
                md = module.YAHBOOM_DEMO(self.app.pl)
                pass
                md.exce_demo(self.text_config.get_section("System")["Loading"])
                pass
            except Exception as e:
                pass
                self.app.model_dialog.show(
                    title=self.text_config.get_section("System")["Error"],
                    content=f"{self.text_config.get_section("System")["Error_text"]["default"]}\n{e}",
                    icon_symbol=lv.SYMBOL.WARNING,
                    btn_texts=[self.text_config.get_section("System")["Ok"]],
                    width=480,
                    height=300
                )
            finally:
                img2 = image.Image(640, 480, image.RGB565)
                img2.clear()
                Display.show_image(img2, 0, 0, Display.LAYER_OSD3)
                
                # 确保md被删除
                if md:
                    del md
                
                # 多次执行gc回收
                gc.collect()
                time.sleep(0.1)  # 给系统一点时间清理
                gc.collect()
                self.app.back_lock = True
                gc.collect()
                time.sleep(0.1)  # 给系统一点时间清理
                gc.collect()
                print("返回锁定时clear")
                lv.timer_create(self.app.release_back_lock, 1000, None)
                print("锁状态", self.app.back_lock)
        
    
    # 以下方法由子类重写
    def get_image_source(self):
        """获取页面图片源，由子类重写"""
        return None
    
    def get_title(self):
        """获取页面标题，由子类重写"""
        return "Default Title"
    
    def get_description(self):
        """获取页面描述，由子类重写"""
        return "Default description text."
    
    def get_button_text(self):
        """获取按钮文字，由子类重写"""
        return "Button"
    
    def on_button_click(self, evt):
        """按钮点击事件处理，由子类重写"""
        pass
    
    def add_extra_components(self):
        """添加额外组件，由子类重写"""
        pass

    
    