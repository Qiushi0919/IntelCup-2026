import lvgl as lv

class BaseSettingPage:
    def __init__(self, app, detail_panel, config):
        self.app = app
        self.detail_panel = detail_panel
        self.config = config
        self.detail_items = []
        # 设置面板的全局样式
        self.detail_panel.set_style_bg_color(lv.color_hex(0xffffff), 0)
        self.detail_panel.set_style_pad_all(20, 0)
    
    def create_item(self, item):
        """创建单个设置项目"""
        # 创建项目容器
        container = lv.obj(self.detail_panel)
        container.set_size(lv.pct(100), 70)
        container.set_style_pad_all(15, 0)
        container.set_style_radius(10, 0)
        container.set_style_border_width(1, 0)
        container.set_style_border_color(lv.color_hex(0xe0e0e0), 0)
        container.set_style_bg_color(lv.color_hex(0xffffff), 0)
        container.set_style_shadow_width(10, 0)
        container.set_style_shadow_color(lv.color_hex(0x888888), 0)
        container.set_style_shadow_opa(10, 0)
        container.set_style_margin_bottom(15, 0)
        container.set_flex_flow(lv.FLEX_FLOW.ROW)
        container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        container.set_scroll_dir(lv.DIR.NONE)
        
        # 添加项目到列表供以后引用
        self.detail_items.append({"container": container, "item": item})
        
        # 项目标签
        label = lv.label(container)
        label.set_text(item["name"])
        label.set_style_text_font(self.app.app_manager.font_16, 0)
        label.set_style_text_color(lv.color_hex(0x333333), 0)
        
        # 根据项目类型创建不同的控件
        if item["type"] == "info":
            value = lv.label(container)
            value.set_text(str(item["value"]))
            value.set_style_text_color(lv.color_hex(0x888888), 0)
            value.set_style_text_font(self.app.app_manager.font_16, 0)
            value.set_width(230)  # 设置固定宽度
            value.set_long_mode(lv.label.LONG.SCROLL)  # 设置为滚动模式
            value.set_style_text_align(lv.TEXT_ALIGN.RIGHT, 0)  # 文本右对齐
            
        elif item["type"] == "switch":
            sw = lv.switch(container)
            sw.set_size(50, 25)
            sw.set_style_bg_color(lv.color_hex(0xe0e0e0), 0)
            sw.set_style_bg_color(lv.color_hex(0x2196f3), lv.PART.INDICATOR | lv.STATE.CHECKED)
            
            if item["value"]:
                sw.add_state(lv.STATE.CHECKED)
            
            if "callback" in item:
                sw.add_event(lambda e, i=item: self._handle_switch_change(e, i), lv.EVENT.VALUE_CHANGED, None)
                
        elif item["type"] == "slider":
            slider_container = lv.obj(container)
            slider_container.set_size(150, 40)
            slider_container.set_style_pad_all(0, 0)
            slider_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
            slider_container.set_style_border_width(0, 0)
            
            # 创建滑动条
            slider = lv.slider(slider_container)
            slider.set_size(150, 10)
            slider.center()
            slider.set_range(item["min"], item["max"])
            slider.set_value(item["value"], lv.ANIM.OFF)
            
            # MIUI风格：增加滑动条高度并隐藏滑块
            slider.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.PART.MAIN)
            slider.set_style_bg_color(lv.color_hex(0x2196f3), lv.PART.INDICATOR)
            slider.set_style_height(10, lv.PART.MAIN)
            slider.set_style_height(10, lv.PART.INDICATOR)
            
            # 隐藏滑块
            slider.set_style_bg_opa(0, lv.PART.KNOB)
            slider.set_style_border_width(0, lv.PART.KNOB)
            
            # 值显示标签
            value_label = lv.label(container)
            value_label.set_text(f"{item['value']}%")
            value_label.set_style_text_color(lv.color_hex(0x888888), 0)
            value_label.set_style_text_font(self.app.app_manager.font_16, 0)
            
            def on_slider_changed(e, i=item, vl=value_label):
                slider = lv.slider.__cast__(e.get_target())
                value = slider.get_value()
                vl.set_text(f"{value}%")
                pass
                
                if "config_section" in i and "config_key" in i:
                    self.config.set_value(i["config_section"], i["config_key"], value)
                    self.config.save_to_file('/sdcard/configs/sys_config.json')
                    pass
                
                if "callback" in i:
                    i["callback"](e)
                        
            slider.add_event(on_slider_changed, lv.EVENT.VALUE_CHANGED, None)
        
        elif item["type"] == "button":
            btn = lv.btn(container)
            btn.set_size(180, 45)
            btn.set_style_bg_color(lv.color_make(0, 0, 0), 0)  # 设置黑色背景
            btn.set_style_shadow_width(5, 0)
            btn.set_style_shadow_color(lv.color_hex(0x888888), 0)
            btn.set_style_shadow_opa(50, 0)
            
            btn_label = lv.label(btn)
            btn_label.set_text(item["value"])
            btn_label.center()
            btn_label.set_style_text_color(lv.color_hex(0xffffff), 0)
            btn_label.set_style_text_font(self.app.app_manager.font_16, 0)
            
            if "callback" in item:
                btn.add_event(item["callback"], lv.EVENT.CLICKED, None)
                
        elif item["type"] == "select":
            # 使用LVGL官方的dropdown控件替换自定义的下拉按钮
            dd = lv.dropdown(container)
            dd.set_size(150, 40)
            dd.set_style_bg_color(lv.color_hex(0xffffff), 0)
            dd.set_style_border_color(lv.color_hex(0xe0e0e0), 0)
            dd.set_style_text_color(lv.color_hex(0x333333), 0)
            dd.set_style_text_font(self.app.app_manager.font_16, 0)

            # 设置选项
            if "options" in item and isinstance(item["options"], list):
                dd.set_options("\n".join(item["options"]))
            
            # 设置当前选中的值
            if "value" in item and item["value"]:
                # 在LVGL 8.3中，正确的方法是set_selected
                # 首先找到选项的索引
                if "options" in item and item["value"] in item["options"]:
                    index = item["options"].index(item["value"])
                    dd.set_selected(index)
            
            # 添加事件回调
            def dropdown_event_handler(e, i=item):
                code = e.get_code()
                obj = lv.dropdown.__cast__(e.get_target())
                if code == lv.EVENT.VALUE_CHANGED:
                    option = " " * 50  # 足够大以存储选项
                    obj.get_selected_str(option, len(option))
                    option = option.strip()  # 移除尾部空格
                    pass
                    
                    # 更新配置
                    if "config_section" in i and "config_key" in i:
                        self.config.set_value(i["config_section"], i["config_key"], option)
                        self.config.save_to_file('/sdcard/configs/sys_config.json')
                        pass
                    
                    # 调用项目回调
                    if "callback" in i:
                        i["callback"](e, option)
            
            dd.add_event(dropdown_event_handler, lv.EVENT.ALL, None)
    
    def _handle_switch_change(self, event, item):
        """处理开关状态改变并更新配置"""
        sw = lv.switch.__cast__(event.get_target())
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        
        if "config_section" in item and "config_key" in item:
            self.config.set_value(item["config_section"], item["config_key"], 1 if state else 0)
            self.config.save_to_file('/sdcard/configs/sys_config.json')
            pass
        
        if "callback" in item:
            item["callback"](event)