import lvgl as lv
from ybUtils.Configuration import Configuration
from ybUtils.KeyBoardManager import KeyboardManager

class DialogHelper:
    def __init__(self, screen, text_config=None):
        self.screen = screen
        self.dialog_obj = None
        self.kb = None
        self.text_config = text_config.get_section("Settings")["dialog_helper"]

    def create_dialog(self, title, options, callback):
        """创建一个带选项的模态对话框"""
        pass
        # 创建覆盖层
        overlay = lv.obj(self.screen)
        overlay.set_style_radius(0,0)
        overlay.set_style_border_width(0,0)
        overlay.set_size(lv.pct(100), lv.pct(100))
        overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        overlay.set_style_bg_opa(120, 0)
        
        # 存储当前对话框的引用
        self.dialog_obj = overlay
        
        # 创建对话框面板
        panel = lv.obj(overlay)
        panel.set_size(lv.pct(80), lv.SIZE_CONTENT)
        panel.center()
        panel.set_style_radius(10, 0)
        panel.set_style_bg_color(lv.color_hex(0xffffff), 0)
        panel.set_style_pad_all(0, 0)
        panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        
        # 对话框标题
        header = lv.obj(panel)
        header.set_size(lv.pct(100), 50)
        header.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)
        header.set_style_pad_all(15, 0)
        header.set_style_border_width(0, 0)
        
        title_label = lv.label(header)
        title_label.set_text(title)
        title_label.center()
        
        # 选项列表容器
        list_container = lv.obj(panel)
        list_container.set_size(lv.pct(100), lv.SIZE_CONTENT)
        list_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        list_container.set_style_border_width(0, 0)
        list_container.set_style_pad_all(0, 0)
        list_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        
        # 添加选项
        pass
        for option in options:
            btn = lv.btn(list_container)
            btn.set_size(lv.pct(100), 50)
            btn.set_style_radius(0, 0)
            btn.set_style_bg_color(lv.color_hex(0xffffff), 0)
            btn.set_style_bg_color(lv.color_hex(0xf0f0f0), lv.STATE.PRESSED)
            btn.set_style_border_width(0, 0)
            btn.set_style_border_side(lv.BORDER_SIDE.BOTTOM, 0)
            btn.set_style_border_color(lv.color_hex(0xeeeeee), 0)
            btn.set_style_border_width(1, 0)
            
            label = lv.label(btn)
            label.set_text(option)
            label.center()
            
            btn.add_event(
                lambda e, opt=option: self._handle_dialog_option(opt, callback),
                lv.EVENT.CLICKED, None
            )
        
        # 取消按钮
        cancel_btn = lv.btn(panel)
        cancel_btn.set_size(lv.pct(100), 50)
        cancel_btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        cancel_btn.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        
        cancel_label = lv.label(cancel_btn)
        cancel_label.set_text(self.text_config["cancel"])
        cancel_label.center()
        
        cancel_btn.add_event(
            lambda e: self.close_dialog(),
            lv.EVENT.CLICKED, None
        )
    
    def _handle_dialog_option(self, option, callback):
        """处理对话框选项选择"""
        pass
        # 关闭对话框
        self.close_dialog()
        
        # 使用选中的选项调用回调
        if callback:
            callback(option)
    
    def close_dialog(self):
        """关闭当前对话框"""
        pass
        if self.dialog_obj:
            self.dialog_obj.delete()
            self.dialog_obj = None

    def create_wifi_password_dialog(self, ssid, save_callback):
        """创建WiFi密码对话框"""
        pass
        # 创建覆盖层
        overlay = lv.obj(self.screen)
        overlay.set_size(lv.pct(100), lv.pct(100))
        overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        overlay.set_style_bg_opa(120, 0)
        
        # 存储当前对话框的引用
        self.dialog_obj = overlay
        
        # 创建对话框面板
        panel = lv.obj(overlay)
        panel.set_size(lv.pct(80), lv.SIZE_CONTENT)
        panel.center()
        panel.set_style_radius(10, 0)
        panel.set_style_border_width(0, 0)
        panel.set_style_bg_color(lv.color_hex(0xffffff), 0)
        panel.set_style_pad_all(20, 0)
        panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        panel.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 对话框标题
        title = lv.label(panel)
        title.set_text(f"{self.text_config["connect_to"]} {ssid}")
        title.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        title.set_width(lv.pct(100))
        
        # 密码容器
        form = lv.obj(panel)
        form.set_size(lv.pct(100), lv.SIZE_CONTENT)
        form.set_style_pad_all(0, 0)
        form.set_style_bg_opa(lv.OPA.TRANSP, 0)
        form.set_style_border_width(0, 0)
        form.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        
        # 密码标签
        pwd_label = lv.label(form)
        pwd_label.set_text(self.text_config["password"])
        
        # 密码输入
        pwd_input = lv.textarea(form)
        pwd_input.set_size(lv.pct(100), 40)
        pwd_input.set_one_line(True)
        pwd_input.set_password_mode(True)
        
        kb = KeyboardManager(self.screen, pwd_input)
        def on_pwd_input_clicked(e):
            kb.show()
            
        def on_pwd_input_focused(e):
            kb.show()
            
        pwd_input.add_event(on_pwd_input_clicked, lv.EVENT.CLICKED, None)
        pwd_input.add_event(on_pwd_input_focused, lv.EVENT.FOCUSED, None)
        
        # 显示密码复选框
        cb = lv.checkbox(form)
        cb.set_text(self.text_config["show_password"])
        
        # 复选框回调
        def on_checkbox_change(e):
            checkbox = lv.checkbox.__cast__(e.get_target())
            checked = checkbox.get_state() & lv.STATE.CHECKED
            pwd_input.set_password_mode(not checked)
            pass
        
        cb.add_event(on_checkbox_change, lv.EVENT.VALUE_CHANGED, None)
        
        # 按钮容器
        btn_container = lv.obj(panel)
        btn_container.set_size(lv.pct(100), 50)
        btn_container.set_style_pad_all(0, 0)
        btn_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        btn_container.set_style_border_width(0, 0)
        btn_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        btn_container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 取消按钮
        cancel_btn = lv.btn(btn_container)
        cancel_btn.set_size(lv.pct(48), 40)
        cancel_btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        cancel_btn.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        cancel_label = lv.label(cancel_btn)
        cancel_label.set_text(self.text_config["cancel"])
        cancel_label.center()

        cancel_btn.add_event(
            lambda e: self.close_dialog(),
            lv.EVENT.CLICKED, None
        )
        
        # 连接按钮
        connect_btn = lv.btn(btn_container)
        connect_btn.set_size(lv.pct(48), 40)
        connect_btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        connect_btn.set_style_text_color(lv.color_hex(0xFFFFFF), 0)

        connect_label = lv.label(connect_btn)
        connect_label.set_text(self.text_config["connect"])
        connect_label.center()

        def on_connect(e):
            password = pwd_input.get_text()
            pass
            self.close_dialog()
            if save_callback:
                save_callback(password)

        # 使用 lambda 忽略可能的额外参数
        connect_btn.add_event(
            lambda e, *args: on_connect(e),
            lv.EVENT.CLICKED,
            None
        )

    def create_time_settings_dialog(self, current_time, save_callback):
        """创建时间设置对话框"""
        pass
        
        # 创建覆盖层
        overlay = lv.obj(self.screen)
        overlay.set_size(lv.pct(100), lv.pct(100))
        overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        overlay.set_style_bg_opa(120, 0)
        
        # 存储当前对话框的引用
        self.dialog_obj = overlay
        
        # 创建对话框面板
        panel = lv.obj(overlay)
        panel.set_size(lv.pct(80), lv.SIZE_CONTENT)
        panel.center()
        panel.set_style_radius(10, 0)
        panel.set_style_bg_color(lv.color_hex(0xffffff), 0)
        panel.set_style_pad_all(20, 0)
        panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        panel.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 对话框标题
        title = lv.label(panel)
        title.set_text("Date and Time Settings")
        title.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        title.set_width(lv.pct(100))
        
        # 日期容器
        date_container = lv.obj(panel)
        date_container.set_size(lv.pct(100), lv.SIZE_CONTENT)
        date_container.set_style_pad_all(0, 0)
        date_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        date_container.set_style_border_width(0, 0)
        date_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        date_container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 年份选择器
        year_roller = lv.roller(date_container)
        years = "\n".join([str(y) for y in range(2020, 2031)])
        year_roller.set_options(years, lv.roller.MODE.NORMAL)
        year_roller.set_visible_row_count(3)
        year_roller.set_selected(current_time[0] - 2020, lv.ANIM.OFF)
        year_roller.set_width(lv.pct(32))
        
        # 月份选择器
        month_roller = lv.roller(date_container)
        months = "\n".join([f"{m:02d}" for m in range(1, 13)])
        month_roller.set_options(months, lv.roller.MODE.NORMAL)
        month_roller.set_visible_row_count(3)
        month_roller.set_selected(current_time[1] - 1, lv.ANIM.OFF)
        month_roller.set_width(lv.pct(32))
        
        # 日期选择器
        day_roller = lv.roller(date_container)
        days = "\n".join([f"{d:02d}" for d in range(1, 32)])
        day_roller.set_options(days, lv.roller.MODE.NORMAL)
        day_roller.set_visible_row_count(3)
        day_roller.set_selected(current_time[2] - 1, lv.ANIM.OFF)
        day_roller.set_width(lv.pct(32))
        
        # 时间容器
        time_container = lv.obj(panel)
        time_container.set_size(lv.pct(100), lv.SIZE_CONTENT)
        time_container.set_style_pad_top(20, 0)
        time_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        time_container.set_style_border_width(0, 0)
        time_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        time_container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 小时选择器
        hour_roller = lv.roller(time_container)
        hours = "\n".join([f"{h:02d}" for h in range(0, 24)])
        hour_roller.set_options(hours, lv.roller.MODE.NORMAL)
        hour_roller.set_visible_row_count(3)
        hour_roller.set_selected(current_time[3], lv.ANIM.OFF)
        hour_roller.set_width(lv.pct(32))
        
        # 分钟选择器
        minute_roller = lv.roller(time_container)
        minutes = "\n".join([f"{m:02d}" for m in range(0, 60)])
        minute_roller.set_options(minutes, lv.roller.MODE.NORMAL)
        minute_roller.set_visible_row_count(3)
        minute_roller.set_selected(current_time[4], lv.ANIM.OFF)
        minute_roller.set_width(lv.pct(32))
        
        # 秒数选择器
        second_roller = lv.roller(time_container)
        seconds = "\n".join([f"{s:02d}" for s in range(0, 60)])
        second_roller.set_options(seconds, lv.roller.MODE.NORMAL)
        second_roller.set_visible_row_count(3)
        second_roller.set_selected(current_time[5], lv.ANIM.OFF)
        second_roller.set_width(lv.pct(32))
        
        # 按钮容器
        btn_container = lv.obj(panel)
        btn_container.set_size(lv.pct(100), 50)
        btn_container.set_style_pad_top(20, 0)
        btn_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        btn_container.set_style_border_width(0, 0)
        btn_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        btn_container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 取消按钮
        cancel_btn = lv.btn(btn_container)
        cancel_btn.set_size(lv.pct(48), 40)
        cancel_btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        cancel_btn.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        
        cancel_label = lv.label(cancel_btn)
        cancel_label.set_text(self.text_config["cancel"])
        cancel_label.center()
        
        cancel_btn.add_event(
            lambda e: self.close_dialog(),
            lv.EVENT.CLICKED, None
        )
        
        # 保存按钮
        save_btn = lv.btn(btn_container)
        save_btn.set_size(lv.pct(48), 40)
        save_btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        save_btn.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        
        save_label = lv.label(save_btn)
        save_label.set_text(self.text_config["save"])
        save_label.center()
        
        def save_time_settings():
            year = 2020 + year_roller.get_selected()
            month = month_roller.get_selected() + 1
            day = day_roller.get_selected() + 1
            hour = hour_roller.get_selected()
            minute = minute_roller.get_selected()
            second = second_roller.get_selected()
            
            time_str = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
            time_tuple = (year,month,day,hour,minute,second)
            pass
            self.close_dialog()
            
            if save_callback:
                save_callback(time_tuple)
            
        save_btn.add_event(
            lambda e: save_time_settings(),
            lv.EVENT.CLICKED, None
        )
    
    