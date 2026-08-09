import lvgl as lv
class CustomKeyboard:
    def __init__(self, parent, recorder=None):
        print("Initializing Custom Keyboard...")
        self.parent = parent
        self.recorder = recorder
        self.keyboard_visible = False
        self.v2t_status = 0
        self.v2t_res = None
        
        # 创建键盘
        self.create_keyboard()
        # 创建临时输入显示区域
        self.create_temp_input_area()
        # 默认隐藏键盘
        self.keyboard.add_flag(lv.obj.FLAG.HIDDEN)
        self.temp_input_display.add_flag(lv.obj.FLAG.HIDDEN)
        print("Custom Keyboard initialized")
        
    def create_keyboard(self):
        # 创建键盘
        self.keyboard = lv.keyboard(self.parent)
        self.keyboard.set_size(lv.pct(100), lv.pct(40))
        self.keyboard.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.keyboard.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)  # iPad风格浅灰色背景
        self.keyboard.set_style_radius(0, 0)  # 无圆角
        self.keyboard.set_style_shadow_width(5, 0)  # 轻微阴影
        self.keyboard.set_style_shadow_opa(lv.OPA._20, 0)

        # 创建语音输入界面 - 完全重新设计
        self.voice_input_keyboard = lv.obj(self.keyboard)
        self.voice_input_keyboard.set_size(lv.pct(100), lv.pct(100))
        self.voice_input_keyboard.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.voice_input_keyboard.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)
        self.voice_input_keyboard.set_style_pad_all(15, 0)
        self.voice_input_keyboard.add_flag(lv.obj.FLAG.HIDDEN)

        # 顶部返回按钮区域
        top_container = lv.obj(self.voice_input_keyboard)
        top_container.set_size(lv.pct(100), 50)
        top_container.align(lv.ALIGN.TOP_MID, 0, 0)
        top_container.set_style_bg_opa(0, 0)  # 透明背景
        top_container.set_style_border_width(0, 0)
        top_container.set_style_pad_all(0, 0)

        # 返回按钮 - 更简洁的设计
        vi_ret_btn = lv.btn(top_container)
        vi_ret_btn.set_size(40, 40)
        vi_ret_btn.align(lv.ALIGN.LEFT_MID, 5, 0)
        vi_ret_btn.set_style_radius(20, 0)  # 圆形按钮
        vi_ret_btn.set_style_bg_color(lv.color_hex(0xE9E9EB), 0)  # 浅灰色背景
        vi_ret_btn.add_event(self.vi_ret_btn_click, lv.EVENT.CLICKED, None)

        # 返回按钮上的图标
        ret_label = lv.label(vi_ret_btn)
        ret_label.set_text(lv.SYMBOL.LEFT)  # 左箭头符号
        ret_label.center()

        # 提示文本 - 放在顶部更容易看到
        self.vi_hint_label = lv.label(top_container)
        self.vi_hint_label.set_text("轻触麦克风图标开始录音")
        self.vi_hint_label.align(lv.ALIGN.CENTER, 0, 0)
        self.vi_hint_label.set_style_text_color(lv.color_hex(0x666666), 0)  # 更深的灰色更容易看清

        # 中央区域 - 用于显示状态和波形
        center_container = lv.obj(self.voice_input_keyboard)
        center_container.set_size(lv.pct(100), 80)
        center_container.align_to(top_container, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)
        center_container.set_style_bg_opa(0, 0)  # 透明背景
        center_container.set_style_border_width(0, 0)
        center_container.set_style_pad_all(0, 0)

        # 创建波形显示区域 - 重新设计为更简洁的圆形波纹
        self.vi_wave_area = lv.obj(center_container)
        self.vi_wave_area.set_size(300, 80)
        self.vi_wave_area.align(lv.ALIGN.CENTER, 0, 0)
        self.vi_wave_area.set_style_bg_opa(0, 0)  # 完全透明背景
        self.vi_wave_area.set_style_border_width(0, 0)
        self.vi_wave_area.set_style_pad_all(0, 0)
        self.vi_wave_area.add_flag(lv.obj.FLAG.HIDDEN)  # 默认隐藏

        # 创建同心圆波形动画
        for i in range(5):
            wave_circle = lv.obj(self.vi_wave_area)
            wave_circle.set_size(20, 20)  # 初始大小
            wave_circle.align(lv.ALIGN.CENTER, 0, 0)  # 居中对齐
            wave_circle.set_style_radius(lv.RADIUS_CIRCLE, 0)  # 完全圆形
            wave_circle.set_style_border_width(2, 0)  # 只有边框
            wave_circle.set_style_bg_opa(0, 0)  # 透明背景
            wave_circle.set_style_border_color(lv.color_hex(0x007AFF), 0)  # iOS蓝色边框
            wave_circle.set_style_border_opa(lv.OPA._50, 0)  # 半透明
            setattr(self, f'wave_circle_{i}', wave_circle)

        # 底部区域 - 放置录音按钮
        bottom_container = lv.obj(self.voice_input_keyboard)
        bottom_container.set_size(lv.pct(100), 90)
        bottom_container.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        bottom_container.set_style_bg_opa(0, 0)  # 透明背景
        bottom_container.set_style_border_width(0, 0)
        bottom_container.set_style_pad_all(0, 0)

        # 录音按钮 - 更大更明显
        self.vi_btn = lv.btn(bottom_container)
        self.vi_btn.set_size(80, 80)  # 大圆形按钮
        self.vi_btn.align(lv.ALIGN.CENTER, 0, 5)
        self.vi_btn.set_style_radius(40, 0)  # 圆形
        self.vi_btn.set_style_bg_color(lv.color_hex(0x007AFF), 0)  # iOS蓝色
        self.vi_btn.set_style_shadow_width(10, 0)  # 添加阴影增强立体感
        self.vi_btn.set_style_shadow_opa(lv.OPA._30, 0)
        self.vi_btn.add_event(self.vi_btn_click, lv.EVENT.CLICKED, None)

        # 麦克风图标
        self.vi_label = lv.label(self.vi_btn)
        self.vi_label.set_text(lv.SYMBOL.PLAY)  # 使用音频图标
        self.vi_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)  # 白色
        self.vi_label.set_style_text_font(lv.font_yb_cn_18, 0)  # 更大的图标
        self.vi_label.center()

        # 添加键盘事件
        self.keyboard.add_event(self.custom_keyboard_event_cb, lv.EVENT.VALUE_CHANGED, None)
        self.keyboard.set_mode(lv.keyboard.MODE.TEXT_LOWER)
        self.voice_input_keyboard.add_flag(lv.obj.FLAG.HIDDEN)

    def create_temp_input_area(self):
        # 创建键盘上方的临时输入显示区域
        self.temp_input_display = lv.textarea(self.parent)
        self.temp_input_display.set_size(lv.pct(100), 60)
        self.temp_input_display.align_to(self.keyboard, lv.ALIGN.OUT_TOP_MID, 0, 0)
        self.temp_input_display.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.temp_input_display.set_style_border_width(1, 0)
        self.temp_input_display.set_style_border_color(lv.color_hex(0xDDDDDD), 0)
        self.temp_input_display.set_style_pad_all(10, 0)
        self.temp_input_display.set_one_line(False)
        self.temp_input_display.add_flag(lv.obj.FLAG.HIDDEN)  # 默认隐藏
        self.temp_input_display.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
        self.temp_input_display.set_text("")
        
        # 为textarea添加内容变化事件
        self.temp_input_display.add_event(self.on_textarea_changed, lv.EVENT.VALUE_CHANGED, None)
        
        # 设置键盘与临时输入区关联
        self.keyboard.set_textarea(self.temp_input_display)

    def show_keyboard(self, text=""):
        print("Showing keyboard...")
        try:
            # 显示键盘和临时输入显示区
            self.keyboard.clear_flag(lv.obj.FLAG.HIDDEN)
            self.temp_input_display.clear_flag(lv.obj.FLAG.HIDDEN)
            self.keyboard_visible = True
            
            # 设置文本和光标位置
            self.temp_input_display.set_text(text)
            self.temp_input_display.set_cursor_pos(len(text))
            self.temp_input_display.add_state(lv.STATE.FOCUSED)
            
            print("Keyboard shown successfully")
        except Exception as e:
            print(f"Error showing keyboard: {e}")
            print(e)
        
        # 返回当前键盘高度，方便调整布局
        return self.keyboard.get_height() + self.temp_input_display.get_height()

    def hide_keyboard(self, evt=None):
        print("Hiding keyboard...")
        try:
            # 隐藏键盘和临时输入显示框
            self.keyboard.add_flag(lv.obj.FLAG.HIDDEN)
            self.temp_input_display.add_flag(lv.obj.FLAG.HIDDEN)
            self.keyboard_visible = False
            
            # 取消焦点
            lv.group_focus_obj(None)
            
            print("Keyboard hidden successfully")
        except Exception as e:
            print(f"Error hiding keyboard: {e}")
            print(e)
        
        return True  # 键盘已成功隐藏
        
    def is_visible(self):
        return self.keyboard_visible
        
    def get_text(self):
        return self.temp_input_display.get_text()
        
    def set_text(self, text):
        self.temp_input_display.set_text(text)
    
    def clear_text(self):
        self.temp_input_display.set_text("")
        
    def is_point_on_keyboard(self, point):
        # 检查点是否在键盘或临时输入区域上
        keyboard_area = lv.area_t()
        self.keyboard.get_coords(keyboard_area)
        
        temp_area = lv.area_t()
        self.temp_input_display.get_coords(temp_area)
        
        # 检查点是否在键盘区域内
        in_keyboard = (point.x >= keyboard_area.x1 and
                      point.x <= keyboard_area.x2 and
                      point.y >= keyboard_area.y1 and
                      point.y <= keyboard_area.y2)
                      
        # 检查点是否在临时输入区域内
        in_temp = (point.x >= temp_area.x1 and
                  point.x <= temp_area.x2 and
                  point.y >= temp_area.y1 and
                  point.y <= temp_area.y2)
                  
        return in_keyboard or in_temp

    # 键盘事件回调
    def custom_keyboard_event_cb(self, e):
        kb = lv.keyboard.__cast__(e.get_target())
        code = e.get_code()
        btn_id = kb.get_selected_btn()

        if code == lv.EVENT.VALUE_CHANGED:
            key_txt = kb.get_btn_text(btn_id)
            if btn_id == 36:  # 假设这是语音按钮
                self.keyboard.set_mode(lv.keyboard.MODE.TEXT_LOWER)
                self.voice_input_keyboard.clear_flag(lv.obj.FLAG.HIDDEN)
            print(btn_id, key_txt)

    # 文本区域变化事件
    def on_textarea_changed(self, evt):
        print("text area changed")
    
    # 返回按钮事件
    def vi_ret_btn_click(self, e):
        # 如果正在录音，取消录音
        if hasattr(self, 'record_timer'):
            self.record_timer._del()
            delattr(self, 'record_timer')

        # 隐藏语音输入界面
        self.voice_input_keyboard.add_flag(lv.obj.FLAG.HIDDEN)
    
    # 语音按钮点击事件
    def vi_btn_click(self, event):
        btn = lv.btn.__cast__(event.get_target())
        if btn.has_state(lv.STATE.DISABLED):
            return

        self.vi_label.set_text(lv.SYMBOL.STOP)
        self.vi_wave_area.clear_flag(lv.obj.FLAG.HIDDEN)
        self.vi_hint_label.set_text("请讲话...")
        btn.add_state(lv.STATE.DISABLED)
        btn.set_style_bg_color(lv.color_hex(0xFF3B30), 0)
        self.animate_voice_waves()

        self.countdown_label = lv.label(self.voice_input_keyboard)
        self.countdown_seconds = 5
        self.countdown_label.set_text(f"{self.countdown_seconds}s")
        self.countdown_label.align(lv.ALIGN.TOP_MID, 0, 50)
        self.countdown_label.set_style_text_color(lv.color_hex(0x007AFF), 0)
        self.countdown_label.set_style_text_font(lv.font_yb_cn_18, 0)

        def recording_done(timer):
            try:
                if hasattr(self, 'countdown_label') and self.countdown_label:
                    self.countdown_label.delete()
                if hasattr(self, 'wave_anims'):
                    for anim in self.wave_anims:
                        lv.anim_del(anim, None)
                    delattr(self, 'wave_anims')
                timer._del()
                if hasattr(self, 'countdown_timer'):
                    self.countdown_timer._del()
                    delattr(self, 'countdown_timer')
            except Exception as e:
                print(f"Error in recording_done: {e}")

        def countdown_timer_cb(timer):
            try:
                self.countdown_seconds -= 1
                if self.countdown_seconds > 0:
                    self.countdown_label.set_text(f"{self.countdown_seconds}s")
                else:
                    timer._del()
                    lv.timer_create(recording_done, 1, None)
            except Exception as e:
                print(f"Error in countdown_timer_cb: {e}")

        self.countdown_timer = lv.timer_create(countdown_timer_cb, 1000, None)
        _thread.start_new_thread(self.voice_to_text, ())        
        
    # 语音波形动画
    def animate_voice_waves(self):
        for i in range(5):
            circle = getattr(self, f'wave_circle_{i}')

            # 创建尺寸动画
            anim = lv.anim_t()
            anim.init()
            anim.set_var(circle)
            anim.set_values(20, 120 + i * 20)  # 从小到大
            anim.set_time(1000 + i * 300)  # 不同时间的动画
            anim.set_repeat_count(lv.ANIM_REPEAT_INFINITE)
            anim.set_path_cb(lv.anim_t.path_ease_out)

            # 自定义设置回调函数
            def cb(circle, val):
                circle.set_size(val, val)
                circle.align(lv.ALIGN.CENTER, 0, 0)
                # 降低透明度随尺寸增大
                opacity = max(10, int(120 - val/2))
                circle.set_style_border_opa(opacity, 0)

            anim.set_custom_exec_cb(lambda a, val: cb(circle, val))
            anim.start()

            # 存储动画引用
            if not hasattr(self, 'wave_anims'):
                self.wave_anims = []
            self.wave_anims.append(anim)
            
    # 语音识别处理
    def voice_to_text(self):
        if not self.recorder:
            print("No recorder available")
            return
            
        wav_path = "/data/tmp_v.wav"

        if self.recorder.record_to_file(6, wav_path):
            self.vi_hint_label.set_text("识别中 ...")
            self.vi_btn.add_state(lv.STATE.DISABLED)
            print("开始转换base64...")
            base64_result = self.recorder.file_to_base64(wav_path)
            print("base64转换完成...")
            if base64_result:
                self.v2t_status = 1
                res = json.loads(req(base64_result[1], base64_result[0]))

                self.v2t_status = 0
                self.v2t_res = res
                print(res)
                if res["err_no"] == 0:
                    print("识别完毕")
                    strs = "".join(res["result"])
                    self.temp_input_display.add_text(strs)

                    self.vi_label.set_text(lv.SYMBOL.PLAY)
                    self.vi_wave_area.add_flag(lv.obj.FLAG.HIDDEN)
                    self.vi_hint_label.set_text("轻触麦克风图标开始录音")
                    self.vi_btn.clear_state(lv.STATE.DISABLED)
                    self.vi_btn.set_style_bg_color(lv.color_hex(0x007AFF), 0)
                    self.v2t_res = None

                    self.hide_keyboard(None)
                else:
                    print("识别失败，请重试")
                    self.vi_label.set_text(lv.SYMBOL.PLAY)
                    self.vi_wave_area.add_flag(lv.obj.FLAG.HIDDEN)
                    self.vi_hint_label.set_text("识别失败，请重试")
                    self.vi_btn.clear_state(lv.STATE.DISABLED)
                    self.vi_btn.set_style_bg_color(lv.color_hex(0x007AFF), 0)
                    self.v2t_res = None
                
                    
                print("finish refresh")
            else:
                print("Base64 conversion failed")
                self.reset_voice_input_state()
        else:
            print("Recording failed")
            self.reset_voice_input_state()
        
    def reset_voice_input_state(self):
        """重置语音输入状态"""
        self.vi_label.set_text(lv.SYMBOL.PLAY)
        self.vi_wave_area.add_flag(lv.obj.FLAG.HIDDEN)
        self.vi_hint_label.set_text("轻触麦克风图标开始录音")
        self.vi_btn.clear_state(lv.STATE.DISABLED)
        self.vi_btn.set_style_bg_color(lv.color_hex(0x007AFF), 0)