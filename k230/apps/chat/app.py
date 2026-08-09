import lvgl as lv
from ybMain.base_app import BaseApp
from ybUtils.Configuration import Configuration

from media.display import *
from media.media import *
import time, os, sys, gc
import lvgl as lv
from machine import TOUCH
import json
# from ybUtils.spark_chat import *
from ybUtils.LLM import LLM
import _thread
from ybUtils.KeyBoardManager import KeyboardManager

DISPLAY_WIDTH = ALIGN_UP(640, 16)
DISPLAY_HEIGHT = 480

# 定义颜色
COLOR_PRIMARY = lv.color_hex(0x131a23)
COLOR_BG = lv.color_hex(0xF5F5F5)
# COLOR_CHAT_BG = lv.color_hex(0xFFFFFF)
COLOR_CHAT_BG = lv.color_hex(0x404142)
COLOR_SELF_MSG = lv.color_hex(0xDCF8C6)
COLOR_OTHER_MSG = lv.color_hex(0xECEFF1)
COLOR_TEXT = lv.color_hex(0x333333)
COLOR_INPUT_BG = lv.color_hex(0xFFFFFF)


# 修改后的ChatUI类
class ChatUI:
    def __init__(self,app,recorder=None):
        
        self.app = app
        self.scr = lv.scr_act()
        self.scr.set_scroll_dir(lv.DIR.NONE)
        lv.scr_load(self.scr)
        self.recorder = recorder
        self.create_header()
        self.create_chat_area()
        self.create_input_area()
        self.keyboard_mgr = KeyboardManager(self.scr, self.ta)
        self.chat_history = []
        self.v2t_status = 0
        self.v2t_res = None
        

    def create_header(self):
        
        self.header = lv.obj(self.scr)
        self.header.set_size(lv.pct(100), 50)
        self.header.align(lv.ALIGN.TOP_MID, 0, 0)
        self.header.set_style_bg_color(COLOR_PRIMARY, 0)
        self.header.set_style_pad_all(0, 0)
        self.header.set_style_radius(0, 0)
        self.header.set_style_border_width(0, 0)
        self.title = lv.label(self.header)
        self.title.set_text(self.app.text_config.get_section("Chat")["title"])
        self.title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        self.title.center()
        
        back_btn = lv.btn(self.header)
        back_btn.set_size(100, 45)
        back_btn.align(lv.ALIGN.LEFT_MID, 8, 0)
        back_btn.set_style_bg_opa(0, 0)  # 透明背景
        back_btn.set_style_shadow_width(0, 0)  # 无阴影
        back_btn.set_style_border_width(0, 0)  # 无边框
        back_btn.set_style_pad_all(0, 0)  # 无内边距
        
        # 后退图标 (YAHBOOM K230 STYLE的箭头)
        back_label = lv.label(back_btn)
        back_label.align(lv.ALIGN.LEFT_MID, 8, 0)
        back_label.set_text(lv.SYMBOL.LEFT)  # Unicode左箭头
        back_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)  # YAHBOOM K230 STYLE蓝色
        back_btn.add_event(self.app.on_back, lv.EVENT.CLICKED, None)
        
    def create_chat_area(self):
        
        self.chat_container = lv.obj(self.scr)
        self.chat_container.set_size(lv.pct(100), DISPLAY_HEIGHT - 110)  # 固定高度
        self.chat_container.align_to(self.header, lv.ALIGN.OUT_BOTTOM_MID, 0, 0)
        self.chat_container.set_style_bg_color(COLOR_CHAT_BG, 0)
        self.chat_container.set_style_border_width(0, 0)
        self.chat_container.set_style_radius(0, 0)
        self.chat_list = lv.obj(self.chat_container)
        self.chat_list.set_size(640, DISPLAY_HEIGHT - 110)
        self.chat_list.align(lv.ALIGN.TOP_MID, 0, 0)
        self.chat_list.set_style_pad_all(5, 0)
        self.chat_list.set_style_border_width(0, 0)
        self.chat_list.set_style_bg_color(COLOR_CHAT_BG, 0)
        self.chat_list.add_flag(lv.obj.FLAG.SCROLLABLE)
        self.chat_list.set_scroll_dir(lv.DIR.VER)
        self.chat_list.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.chat_list.set_style_pad_column(10, 0)
        self.chat_list.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.chat_container.clear_flag(lv.obj.FLAG.SCROLLABLE)
        
    def create_input_area(self):
        
        self.input_area = lv.obj(self.scr)
        self.input_area.set_size(lv.pct(100), 60)
        self.input_area.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.input_area.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.input_area.set_style_pad_all(20, 0)
        self.input_area.set_style_radius(0, 0)
        self.input_area.set_style_border_width(1, 0)
        self.input_area.set_style_border_color(lv.color_hex(0xDDDDDD), 0)
        self.input_area.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.input_area.clear_flag(lv.obj.FLAG.SCROLLABLE)
        self.ta = lv.textarea(self.input_area)
        self.ta.set_size(lv.pct(80), 44)
        self.ta.align(lv.ALIGN.LEFT_MID, 5, 0)
        self.ta.set_placeholder_text("...")
        self.ta.set_one_line(False)
        self.ta.set_style_bg_color(COLOR_INPUT_BG, 0)
        self.ta.set_style_radius(22, 0)
        self.ta.set_style_pad_all(10, 0)
        self.ta.set_cursor_click_pos(True)
        self.ta.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.send_btn = lv.btn(self.input_area)
        self.send_btn.set_size(lv.pct(10), 44)
        self.send_btn.align_to(self.ta, lv.ALIGN.OUT_RIGHT_MID, 8, 0)
        self.send_btn.set_style_bg_color(lv.color_hex(0x00a5fd), 0)
        self.send_btn.set_style_radius(40, 0)
        self.send_label = lv.label(self.send_btn)
        self.send_label.set_text(lv.SYMBOL.GPS)
        self.send_label.center()
        self.ta.add_event(self.on_textarea_clicked, lv.EVENT.CLICKED, None)
        self.ta.add_event(self.on_textarea_focused, lv.EVENT.FOCUSED, None)
        self.send_btn.add_event(self.on_send_clicked, lv.EVENT.CLICKED, None)
        self.send_btn.add_flag(lv.obj.FLAG.CLICKABLE)
        
    def on_textarea_focused(self, evt):
        
        try:
            self.keyboard_mgr.show()
            lv.timer_create(self.delayed_scroll_to_bottom, 50, None)
            
        except Exception as e:
            
            pass

    def delayed_scroll_to_bottom(self, timer):
        self.scroll_to_bottom()
        timer._del()

    def on_textarea_clicked(self, evt):
        
        try:
            self.keyboard_mgr.show()
            self.scroll_to_bottom()
            
        except Exception as e:
            
            pass

    def hide_keyboard(self, evt):
        
        try:
            self.keyboard_mgr.hide()
            lv.timer_create(self.delayed_scroll_to_bottom, 50, None)
            
        except Exception as e:
            
            pass

    def on_send_clicked(self, evt):
        
        try:
            msg_text = self.ta.get_text()
            
            if msg_text.strip() != "":
                self.add_message(msg_text, True)
                time.sleep_us(1)
                self.add_message("I am thinking ...", False)
                time.sleep_us(1)
                _thread.start_new_thread(self.chat, (msg_text,))
                self.ta.set_text("")
                if self.keyboard_mgr.keyboard_visible:
                    self.hide_keyboard(None)
            
        except Exception as e:
            
            pass

    def chat(self, text):
        messages = [{"role": "user", "content": self.app.text_config.get_section("Chat")["prompt"]}]
        total_length = 0
        max_length = 300
        for t in (self.chat_history):
            if t[0] == 'I am thinking ...':
                continue
            content = t[0]
            is_true = t[1]
            msg_length = len(content)
            if total_length + msg_length > max_length:
                break
            messages.append({"role": "user" if is_true else "assistant", "content": content})
            total_length += msg_length
        gc.collect()
        print("k:", self.app.api_key, self.app.api_type, self.app.api_model)
        spark = LLM(self.app.api_key, self.app.api_type)
        response = spark.chat(messages, model=self.app.api_model)
        resp = ""
        try:
            if "error" in response:
                resp = f"ERROR: {response['error']}"
            elif "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0].get("message", {}).get("content", "")
                resp = f"{content}"
                if len(resp) >= 400:
                    resp = f"{resp} ....."
            else:
                resp = "error"
        except Exception as e:
            resp = "sorry, some error happened"
        self.delete_last_message()
        self.add_message(resp, False)
        
    def delete_last_message(self):
        try:
            # 检查是否有消息可以删除
            if not self.chat_history:
                print("没有消息可以删除")
                return False

            # 获取聊天列表中的最后一个子对象（即最后一个消息项）
            chat_list_children = self.chat_list.get_child_cnt()
            if chat_list_children <= 0:
                print("聊天列表中没有消息项")
                return False

            # 获取最后一个消息项
            last_item = self.chat_list.get_child(chat_list_children - 1)
            if last_item is None:
                print("无法获取最后一个消息项")
                return False

            # 从历史记录中移除最后一条消息
            self.chat_history.pop()

            # 删除UI中的消息项
            last_item.delete()

            # 刷新滚动条位置
            lv.timer_create(self.delayed_scroll_to_bottom, 50, None)

            return True
        except Exception as e:
            print("删除最后一条消息时出错:", e)
            return False
        
    def add_message(self, text, is_self):
        try:
            item = lv.obj(self.chat_list)
            item.set_width(lv.pct(100))
            item.set_style_bg_opa(0, 0)
            item.set_style_border_width(0, 0)
            item.set_style_pad_all(0, 0)
            item.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
            item.clear_flag(lv.obj.FLAG.SCROLLABLE)
            content_width = self.chat_list.get_content_width()
            max_width = int(content_width * 0.45)
            font_height = 16
            line_space = 2
            temp_label = lv.label(self.scr)
            temp_label.set_text(self.app.text_config.get_section("Chat")["prompt"][0])
            temp_label.set_style_text_font(temp_label.get_style_text_font(0), 0)
            temp_label.refr_size()
            char_width = temp_label.get_width()
            temp_label.set_text("")
            if len(text) > 0:
                chars_per_line = max(1, int((max_width - 20) / (char_width+1)))
                lines = text.split('\n')
                estimated_lines = 0
                for line in lines:
                    if line:
                        line_count = max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                        estimated_lines += line_count
                    else:
                        estimated_lines += 1
            else:
                estimated_lines = 1
            temp_label.add_flag(lv.obj.FLAG.HIDDEN)
            temp_label.delete()
            bubble = lv.obj(item)
            bubble.set_style_radius(15, 0)
            bubble.set_style_pad_all(10, 0)
            bubble.clear_flag(lv.obj.FLAG.SCROLLABLE)
            bubble.set_style_bg_color(COLOR_SELF_MSG if is_self else COLOR_OTHER_MSG, 0)
            msg_label = lv.label(bubble)
            msg_label.set_style_text_color(COLOR_TEXT, 0)
            msg_label.set_long_mode(lv.label.LONG.WRAP)
            msg_label.set_text(text)
            msg_label.set_width(min(max_width, char_width * len(text)))
            msg_label.refr_size()
            msg_label.refr_pos()
            label_width = msg_label.get_width()
            bubble_height = max(font_height, font_height * estimated_lines + line_space * (estimated_lines*4 - 10))
            bubble_height += 20
            bubble.set_size(label_width + 20, bubble_height)
            bubble.refr_size()
            bubble.refr_pos()
            bubble.align(lv.ALIGN.TOP_RIGHT if is_self else lv.ALIGN.TOP_LEFT, -5 if is_self else 5, 0)
            msg_label.center()
            item.set_height(bubble.get_height() + 10)
            self.chat_history.append((text, is_self))
            lv.timer_create(self.delayed_scroll_to_bottom, 50, None)
        except Exception as e:
            print(e)

    def scroll_to_bottom(self):
        
        try:
            if self.chat_list.get_child_cnt() > 0:
                scroll_target = self.chat_list.get_scroll_bottom() * 2
                self.chat_list.scroll_to_y(scroll_target, lv.ANIM.ON)
                
        except Exception as e:
            print(e)
            pass

def create_chat_app(app, recorder=None):
    

    if not app.app_manager.logic_wifi_status:
        print("no wifi")
        try:
            app.model_dialog.show(
                title=app.text_config.get_section("Chat")["title"],
                content=app.text_config.get_section("Chat")["no_internet"],
                icon_symbol=lv.SYMBOL.WARNING,
                btn_texts=[app.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            )
        except Exception as e:
            print(e)
            app.on_back(None)
        return
    chat_app = ChatUI(app, recorder=recorder)
    return chat_app

class App(BaseApp):
    def __init__(self, app_manager):
        try:
            with open("/sdcard/apps/chat/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            pass
            img_bg = None
            
        # 加载配置
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        self.app_manager = app_manager        
        super().__init__(app_manager, self.text_config.get_section("System")["Chat"],icon=img_bg)
        self.pl = app_manager.pl
        self.texts = self.text_config.get_section("Chat")
        self.recorder = app_manager.recorder
        
        self.api_type = self.config.get_section("AI")["LLM"]["api_type"]
        self.api_key = self.config.get_section("AI")["LLM"]["api_key"]
        self.api_model = self.config.get_section("AI")["LLM"]["api_model"]
        
    def initialize(self):
        """初始化计算器界面"""
        # create_chat_app(self,recorder=self.recorder)
        create_chat_app(self, recorder=self.recorder)
        pass
        # # 创建计算器主体内容区
        # content = lv.obj(self.screen)
        # content.set_size(lv.pct(100), lv.pct(90))
        # content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        
        # # 这里添加计算器的实际界面和逻辑
        # # 例如文本显示和按钮网格
        # display = lv.label(content)
        # display.set_size(lv.pct(90), 40)
        # display.align(lv.ALIGN.TOP_MID, 0, 10)
        # display.set_text("0")
        
        # 添加按钮网格等...
        
    def deinitialize(self):
        """清理资源"""
        pass