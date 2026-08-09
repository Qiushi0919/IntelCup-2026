from media.display import *
from media.media import *
import time, os, sys, gc
import lvgl as lv
from machine import TOUCH
from ybUtils.Configuration import Configuration

# DISPLAY_WIDTH = ALIGN_UP(800, 16)
DISPLAY_WIDTH = ALIGN_UP(640, 16)
DISPLAY_HEIGHT = 480

class WelcomeScreen:
    def __init__(self, parent, config):
        self.parent = parent
        self.screen = lv.obj(parent)
        self.screen.set_size(640, DISPLAY_HEIGHT)
        self.screen.set_style_bg_color(lv.color_hex(0x000000), 0)  # 黑色背景
        self.screen.set_style_border_width(0,0)
        self.current_language = "Chinese"
        self.languages = self._scan_languages()
        self.config = config
        self.setup_ui()
        self.confirm_btn_timer = None
        self.confirm_btn_enabled = True
    def _enable_confirm_btn(self, timer):
        """定时器回调函数,重新启用confirm按钮"""
        self.confirm_btn_enabled = True
        self.confirm_btn_timer = None
    def setup_ui(self):
        # 创建一个水平居中的容器
        main_cont = lv.obj(self.screen)
        main_cont.set_size(lv.pct(90), lv.pct(80))
        main_cont.center()
        main_cont.set_style_bg_color(lv.color_hex(0x101010), 0)
        main_cont.set_style_bg_opa(lv.OPA._80, 0)
        main_cont.set_style_border_width(2, 0)
        main_cont.set_style_border_color(lv.color_hex(0x2F2F2F), 0)
        main_cont.set_style_radius(15, 0)
        main_cont.set_style_shadow_width(20, 0)
        main_cont.set_style_shadow_color(lv.color_hex(0x0000FF), 0)
        main_cont.set_style_shadow_opa(lv.OPA._30, 0)
        main_cont.set_style_pad_all(20, 0)
#        main_cont.set_layout(lv.LAYOUT_FLEX)
        main_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        main_cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        main_cont.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        # 创建标题容器
        title_cont = lv.obj(main_cont)
        title_cont.set_size(lv.pct(100), lv.SIZE_CONTENT)
        title_cont.set_style_bg_opa(lv.OPA._0, 0)
        title_cont.set_style_border_width(0, 0)
        title_cont.set_style_pad_all(10, 0)
        title_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        title_cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        # 中文标题
        self.cn_title_label = lv.label(title_cont)
        self.cn_title_label.set_text("欢迎使用亚博智能 K230")
        self.cn_title_label.set_style_text_font(lv.font_yb_cn_22,0)
        self.cn_title_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.cn_title_label.center()  # 初始居中

        # 英文标题
        self.en_title_label = lv.label(title_cont)
        self.en_title_label.set_text("Welcome to Yahboom K230")
        self.en_title_label.set_style_text_color(lv.color_hex(0xCCCCCC), 0)
        self.en_title_label.set_style_pad_top(5, 0)
        self.en_title_label.center()  # 初始居中

        # 创建标题动画
        self._create_title_animations()

        # 创建一条分隔线
        separator = lv.line(main_cont)
        separator.set_style_line_color(lv.color_hex(0x3F3F3F), 0)
        separator.set_style_line_width(2, 0)
        separator.set_style_pad_ver(10, 0)

        # 设置分隔线的点
        line_points = [{"x": 0, "y": 0}, {"x": int(main_cont.get_width() * 0.8), "y": 0}]
        separator.set_points(line_points, 2)

        # 创建语言选择区域
        select_cont = lv.obj(main_cont)
        select_cont.set_size(lv.pct(80), lv.SIZE_CONTENT)
        select_cont.set_style_bg_opa(lv.OPA._0, 0)
        select_cont.set_style_border_width(0, 0)
        select_cont.set_style_pad_all(10, 0)
        select_cont.set_style_pad_top(20, 0)
#        select_cont.set_layout(lv.LAYOUT.FLEX)
        select_cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        select_cont.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        # 语言选择区域的组件初始设置为透明
        select_cont.set_style_opa(0, 0)
        separator.set_style_opa(0, 0)

        # 创建语言选择区域的淡入动画
        self._create_selection_animations(select_cont, separator)

        # 语言选择标签
        self.lang_label = lv.label(select_cont)
        self.lang_label.set_text("请选择语言 / Select Language")
        self.lang_label.set_style_text_color(lv.color_hex(0xCCCCCC), 0)
        self.lang_label.set_style_pad_bottom(15, 0)

        # 语言选择框
        self.lang_dropdown = lv.dropdown(select_cont)
        self.lang_dropdown.set_size(lv.pct(80), lv.SIZE_CONTENT)
        self.lang_dropdown.set_style_bg_color(lv.color_hex(0x202020), 0)
        self.lang_dropdown.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.lang_dropdown.set_style_border_color(lv.color_hex(0x3F3F3F), 0)
        self.lang_dropdown.set_style_border_width(2, 0)
        self.lang_dropdown.set_style_radius(8, 0)
        self.lang_dropdown.set_style_pad_all(12, 0)
        # 添加语言选项
        options = ""
        for lang in self.languages:
            options += lang + "\n"

        self.lang_dropdown.set_options(options.strip())
        self.lang_dropdown.set_selected(1)

        
        # 添加语言选择事件
        self.lang_dropdown.add_event(self._dropdown_event_handler, lv.EVENT.VALUE_CHANGED, None)

        # 添加确认按钮
        self.confirm_btn = lv.btn(main_cont)
        self.confirm_btn.set_size(lv.pct(50), 50)
        self.confirm_btn.set_style_bg_color(lv.color_hex(0x0055FF), 0)
        self.confirm_btn.set_style_radius(8, 0)
        self.confirm_btn.set_style_shadow_width(10, 0)
        self.confirm_btn.set_style_shadow_color(lv.color_hex(0x0055FF), 0)
        self.confirm_btn.set_style_shadow_opa(lv.OPA._30, 0)
        self.confirm_btn.set_style_pad_all(10, 0)

        confirm_label = lv.label(self.confirm_btn)
        confirm_label.set_text("确认 / Confirm")
        confirm_label.center()

        # 确认按钮点击事件
        self.confirm_btn.add_event(self._confirm_btn_event_handler, lv.EVENT.CLICKED, None)
        
        # 应用标题动画效果
        self._apply_animations()
        # 修改动画应用方法，为所有组件添加淡入动画

    def _apply_animations(self):
        # 存储所有需要动画的组件和它们的延迟时间
        components = [
            {"obj": self.cn_title_label, "delay": 300},
            {"obj": self.en_title_label, "delay": 800},
            {"obj": self.lang_label, "delay": 1800},
            {"obj": self.lang_dropdown, "delay": 2100},
            {"obj": self.confirm_btn, "delay": 2600}
        ]

        # 为每个组件创建淡入动画
        for comp in components:
            # 初始设置组件为透明
            comp["obj"].set_style_opa(lv.OPA._0, 0)

            # 创建淡入动画
            anim = lv.anim_t()
            anim.init()
            anim.set_var(comp["obj"])
            anim.set_time(1000)
            anim.set_delay(comp["delay"])
            anim.set_values(lv.OPA._0, lv.OPA._100)
            anim.set_path_cb(lv.anim_t.path_ease_out)

            # 创建动画回调
            def make_anim_cb(target_obj):
                def anim_cb(obj, value):
                    target_obj.set_style_opa(value, 0)
                return anim_cb

            anim.set_custom_exec_cb(make_anim_cb(comp["obj"]))
            anim.start()

    def _create_title_animations(self):
        # 创建中文标题动画
        cn_anim = lv.anim_t()
        cn_anim.init()
        cn_anim.set_var(self.cn_title_label)
        cn_anim.set_values(self.screen.get_height() // 2, 100)  # 从屏幕中间到目标位置
        cn_anim.set_time(1000)
        cn_anim.set_path_cb(lv.anim_t.path_ease_out)
        cn_anim.set_custom_exec_cb(lambda a, val: self.cn_title_label.set_y(val))
        cn_anim.start()

        # 创建英文标题动画
        en_anim = lv.anim_t()
        en_anim.init()
        en_anim.set_var(self.en_title_label)
        en_anim.set_values(self.screen.get_height() // 2 + 30, 130)  # 从屏幕中间到目标位置
        en_anim.set_time(1000)
        en_anim.set_path_cb(lv.anim_t.path_ease_out)
        en_anim.set_custom_exec_cb(lambda a, val: self.en_title_label.set_y(val))
        en_anim.start()

    def _create_selection_animations(self, select_cont, separator):
        # 创建分隔线淡入动画
        sep_anim = lv.anim_t()
        sep_anim.init()
        sep_anim.set_var(separator)
        sep_anim.set_values(0, 255)
        sep_anim.set_time(500)
        sep_anim.set_delay(1000)  # 等待标题动画完成
        sep_anim.set_path_cb(lv.anim_t.path_ease_in)
        sep_anim.set_custom_exec_cb(lambda a, val: separator.set_style_opa(val, 0))
        sep_anim.start()

        # 创建选择区域淡入动画
        sel_anim = lv.anim_t()
        sel_anim.init()
        sel_anim.set_var(select_cont)
        sel_anim.set_values(0, 255)
        sel_anim.set_time(500)
        sel_anim.set_delay(1200)  # 稍微延迟于分隔线
        sel_anim.set_path_cb(lv.anim_t.path_ease_in)
        sel_anim.set_custom_exec_cb(lambda a, val: select_cont.set_style_opa(val, 0))
        sel_anim.start()

    def _confirm_btn_event_handler(self, evt):
        if evt.code == lv.EVENT.CLICKED and self.confirm_btn_enabled:
            # 只有在按钮启用状态下才执行点击事件
            print(self.current_language)
            if self.current_language:
                self.config.set_value("language", "text_path", "/sdcard/configs/languages/" + self.current_language + ".json")
                self.config.set_value("SYS_INFO","hello",0)
                self.config.save_to_file('/sdcard/configs/sys_config.json')
                self._fade_out_selection()
            else:
                print("请先选择语言")
                pass

    def _fade_out_selection(self):
        # 获取所有需要淡出的组件
        main_cont = self.screen.get_child(0)  # 主容器

        def create_fade_anim(obj, delay, is_last=False):
            anim = lv.anim_t()
            anim.init()
            anim.set_var(obj)
            anim.set_values(255, 0)
            anim.set_time(500)
            anim.set_delay(delay)
            anim.set_path_cb(lv.anim_t.path_ease_out)

            def make_cb(target):
                def cb(a, val):
                    target.set_style_opa(val, 0)
                return cb

            anim.set_custom_exec_cb(make_cb(obj))

            if is_last:
                anim.set_ready_cb(lambda a: self._show_completion_message())

            anim.start()

        # 为每个组件创建淡出动画
        components = [
            main_cont.get_child(0),  # title_cont
            main_cont.get_child(1),  # separator
            main_cont.get_child(2),  # select_cont
            main_cont.get_child(3),  # confirm_btn
        ]

        for i, comp in enumerate(components):
            create_fade_anim(comp, i * 100, i == len(components) - 1)
    
    def _show_completion_message(self):
        # 创建完成消息标签
        msg_label = lv.label(self.screen)
        msg_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        if self.current_language == "English":
            msg_label.set_text("Language set to English.\n Restarting...")
        else:
            msg_label.set_text("语言设置为中文。\n 系统初始化...")
        msg_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        msg_label.set_style_text_font(lv.font_yb_cn_22, 0)
        msg_label.center()
        msg_label.set_style_opa(0, 0)

        # 创建消息淡入动画
        msg_anim = lv.anim_t()
        msg_anim.init()
        msg_anim.set_var(msg_label)
        msg_anim.set_values(0, 255)
        msg_anim.set_time(500)
        msg_anim.set_path_cb(lv.anim_t.path_ease_in)
        msg_anim.set_custom_exec_cb(lambda a, val: msg_label.set_style_opa(val, 0))
        msg_anim.start()

        # 3秒后重启系统
        def restart_system(timer):
            # 这里添加重启系统的代码
            file_path = "/sdcard/first.txt"
            try:
                os.remove(file_path)
            except Exception as e:
                print("remove_first_file", e)
            finally:
                machine.reset()

        lv.timer_create(restart_system, 3000, None)
    def _get_setting_language(self):
        """获取当前语言设置"""
        return self.config.get_section("language").get("text_path", "").split("/")[-1].split(".")[-2]

    def _scan_languages(self):
        """扫描可用语言"""
        pass
        # 模拟语言扫描结果
        try:
            language_list = os.listdir("/sdcard/configs/languages")
            for i, lang in enumerate(language_list):
                language_list[i] = lang.split(".")[0] if lang.endswith(".json") else lang
            return sorted(language_list, reverse=True)  # 按首字母倒序排序
        except:
            # 如果没有语言文件或读取失败，返回默认语言列表
            return sorted(["Chinese", "English"], reverse=True)  # 倒序排序


    def _dropdown_event_handler(self, event):
        dropdown = lv.dropdown.__cast__(event.get_target())
        if event.get_code() == lv.EVENT.VALUE_CHANGED:
            # 禁用confirm按钮
            self.confirm_btn_enabled = False
            
            # 创建10ms定时器
            if self.confirm_btn_timer:
                self.confirm_btn_timer.del_()
            self.confirm_btn_timer = lv.timer_create(self._enable_confirm_btn, 500, None)
            
            # 原有的dropdown处理逻辑
            option_buffer = " " * 50
            dropdown.get_selected_str(option_buffer, len(option_buffer))
            selected_option = option_buffer.strip()
            self._on_language_change(event, selected_option)

    def _on_language_change(self, event, option):
        pass
        """语言变化回调"""
        current_language = option.strip().replace('\u0000', '')
        print("choose: ", current_language)
        self.current_language = current_language