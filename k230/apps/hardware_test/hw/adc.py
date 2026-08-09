import lvgl as lv

class ADCTestPage:
    def __init__(self, app, parent, config, text_config):
        self.app = app
        self.parent = parent
        self.config = config
        self.text_config = text_config
        self.content = None
        self.chart = None
        self.value_label = None
        self.channel_dropdown = None
        self.adc_timer = None
        self.current_channel = 0
        self.adc_values = [0] * 100  # 存储100个采样点
        self.chart_series = None

    def display(self):
        # 清理之前的内容
        self.parent.clean()


        # 创建主容器
        self.content = lv.obj(self.parent)
        self.content.set_size(lv.pct(100), lv.pct(100))
        self.content.set_style_pad_all(0, 0)
        self.content.set_style_border_width(0, 0)
        self.content.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)
        self.content.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # 标题
        title = lv.label(self.content)
        title.set_text("ADC测试")
        title.set_style_text_font(lv.font_yb_cn_16, 0)
        title.set_style_text_color(lv.color_hex(0x333333), 0)
        title.align(lv.ALIGN.TOP_LEFT, 0, 10)

        # 创建卡片容器
        card = lv.obj(self.content)
        card.set_size(lv.pct(95), lv.pct(80))
        card.align_to(title, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        card.set_style_radius(15, 0)
        card.set_style_bg_color(lv.color_hex(0xffffff), 0)
        card.set_style_shadow_width(20, 0)
        card.set_style_shadow_ofs_y(5, 0)
        card.set_style_shadow_color(lv.color_hex(0xcccccc), 0)
        card.set_style_shadow_opa(lv.OPA._30, 0)
        card.set_style_pad_all(20, 0)

        # 控制面板区域
        control_panel = lv.obj(card)
        control_panel.set_size(lv.pct(100), 50)
        control_panel.set_style_radius(10, 0)
        control_panel.set_style_bg_color(lv.color_hex(0xf8f8f8), 0)
        control_panel.set_style_pad_all(10, 0)
        control_panel.set_style_border_width(0, 0)
        control_panel.set_flex_flow(lv.FLEX_FLOW.ROW)
        control_panel.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        # 通道选择下拉菜单
        channel_label = lv.label(control_panel)
        channel_label.set_text("ADC通道:")
        channel_label.set_style_text_font(lv.font_yb_cn_16, 0)

        self.channel_dropdown = lv.dropdown(control_panel)
        self.channel_dropdown.set_options("通道0\n通道1\n通道2\n通道3")
        self.channel_dropdown.set_style_text_font(lv.font_yb_cn_16, 0)
        self.channel_dropdown.set_width(120)
        self.channel_dropdown.add_event(self.on_channel_changed, lv.EVENT.VALUE_CHANGED, None)

        # 当前值显示
        value_container = lv.obj(control_panel)
        value_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        value_container.set_style_border_width(0, 0)
        value_container.set_size(150, 40)
        value_container.set_style_pad_all(0, 0)

        value_title = lv.label(value_container)
        value_title.set_text("当前值:")
        value_title.set_style_text_font(lv.font_yb_cn_16, 0)
        value_title.align(lv.ALIGN.LEFT_MID, 0, 0)

        self.value_label = lv.label(value_container)
        self.value_label.set_text("0")
        self.value_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.value_label.set_style_text_color(lv.color_hex(0x1a73e8), 0)
        self.value_label.align_to(value_title, lv.ALIGN.OUT_RIGHT_MID, 10, 0)

        # 图表区域
        chart_container = lv.obj(card)
        chart_container.set_size(lv.pct(100), lv.pct(75))
        chart_container.align_to(control_panel, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        chart_container.set_style_bg_color(lv.color_hex(0xffffff), 0)
        chart_container.set_style_border_width(1, 0)
        chart_container.set_style_border_color(lv.color_hex(0xe0e0e0), 0)
        chart_container.set_style_pad_all(10, 0)
        chart_container.set_style_radius(10, 0)

        # 创建图表
        self.chart = lv.chart(chart_container)
        self.chart.set_size(lv.pct(95), lv.pct(95))
        self.chart.center()
        self.chart.set_type(lv.chart.TYPE.LINE)
        self.chart.set_point_count(100)
        self.chart.set_range(lv.chart.AXIS.PRIMARY_Y, 0, 4095)  # ADC范围通常是0-4095(12位)
        self.chart.set_div_line_count(5, 10)
        
        # 设置图表样式
        self.chart.set_style_line_width(2, lv.PART.ITEMS)
        self.chart.set_style_bg_color(lv.color_hex(0xfafafa), 0)
        self.chart.set_style_border_color(lv.color_hex(0xdedede), 0)
        self.chart.set_style_border_width(1, 0)
        
        # 添加Y轴标签
        self.chart.set_axis_tick(lv.chart.AXIS.PRIMARY_Y, 10, 5, 6, 2, True, 50)
        
        # 添加X轴标签
        self.chart.set_axis_tick(lv.chart.AXIS.PRIMARY_X, 10, 5, 10, 2, True, 50)

        # 添加数据系列
        self.chart_series = self.chart.add_series(lv.color_hex(0x1a73e8), lv.chart.AXIS.PRIMARY_Y)
        
        # 初始化图表数据
        for i in range(100):
            self.chart.set_point_value(self.chart_series, i, 0)

        # 启动定时器，模拟ADC数据采集
        if self.adc_timer is not None:
            lv.timer_del(self.adc_timer)
        self.adc_timer = lv.timer_create(self.update_adc_value, 100, None)

    def on_channel_changed(self, e):
        selected = self.channel_dropdown.get_selected()
        self.current_channel = selected
        # 这里可以实际切换ADC通道

    def update_adc_value(self, timer):
        # 这里应该是实际读取ADC值的代码
        # 示例中使用随机值模拟
        import random
        value = random.randint(0, 4095)
        
        # 更新当前值显示
        self.value_label.set_text(str(value))
        
        # 更新图表数据
        self.adc_values.pop(0)
        self.adc_values.append(value)
        
        # 更新图表
        for i, v in enumerate(self.adc_values):
            self.chart.set_point_value(self.chart_series, i, v)
        
        self.chart.refresh()

    def cleanup(self):
        if self.adc_timer is not None:
            lv.timer_del(self.adc_timer)
            self.adc_timer = None