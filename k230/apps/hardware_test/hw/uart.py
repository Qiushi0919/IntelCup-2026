import lvgl as lv

class UARTTestPage:
    def __init__(self, app, parent, config, text_config):
        self.app = app
        self.parent = parent
        self.config = config
        self.text_config = text_config
        self.content = None
        self.uart_port_dropdown = None
        self.baud_rate_dropdown = None
        self.tx_textarea = None
        self.rx_textarea = None
        self.uart_timer = None
        self.current_uart_port = 0
        self.current_baud_rate = 115200
        self.rx_buffer = ""
        self.tx_count = 0
        self.rx_count = 0
        self.tx_count_label = None
        self.rx_count_label = None
        self.auto_receive = True

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
        title.set_text("UART测试")
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
        card.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        card.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)

        # UART配置面板
        config_panel = lv.obj(card)
        config_panel.set_size(lv.pct(100), 60)
        config_panel.set_style_radius(10, 0)
        config_panel.set_style_bg_color(lv.color_hex(0xf8f8f8), 0)
        config_panel.set_style_pad_all(10, 0)
        config_panel.set_style_border_width(0, 0)
        config_panel.set_flex_flow(lv.FLEX_FLOW.ROW)
        config_panel.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        # UART端口选择
        port_container = lv.obj(config_panel)
        port_container.set_size(180, 40)
        port_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        port_container.set_style_border_width(0, 0)
        port_container.set_style_pad_all(0, 0)
        port_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        port_container.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        port_label = lv.label(port_container)
        port_label.set_text("串口:")
        port_label.set_style_text_font(lv.font_yb_cn_16, 0)

        self.uart_port_dropdown = lv.dropdown(port_container)
        self.uart_port_dropdown.set_options("UART0\nUART1\nUART2")
        self.uart_port_dropdown.set_style_text_font(lv.font_yb_cn_16, 0)
        self.uart_port_dropdown.set_width(100)
        self.uart_port_dropdown.align_to(port_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.uart_port_dropdown.add_event(self.on_uart_port_changed, lv.EVENT.VALUE_CHANGED, None)

        # 波特率选择
        baud_container = lv.obj(config_panel)
        baud_container.set_size(220, 40)
        baud_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        baud_container.set_style_border_width(0, 0)
        baud_container.set_style_pad_all(0, 0)
        baud_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        baud_container.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        baud_label = lv.label(baud_container)
        baud_label.set_text("波特率:")
        baud_label.set_style_text_font(lv.font_yb_cn_16, 0)

        self.baud_rate_dropdown = lv.dropdown(baud_container)
        self.baud_rate_dropdown.set_options("9600\n19200\n38400\n57600\n115200")
        self.baud_rate_dropdown.set_selected(4)  # 默认选115200
        self.baud_rate_dropdown.set_style_text_font(lv.font_yb_cn_16, 0)
        self.baud_rate_dropdown.set_width(120)
        self.baud_rate_dropdown.align_to(baud_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.baud_rate_dropdown.add_event(self.on_baud_rate_changed, lv.EVENT.VALUE_CHANGED, None)

        # 自动接收开关
        recv_container = lv.obj(config_panel)
        recv_container.set_size(150, 40)
        recv_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        recv_container.set_style_border_width(0, 0)
        recv_container.set_style_pad_all(0, 0)
        recv_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        recv_container.set_flex_align(lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        recv_label = lv.label(recv_container)
        recv_label.set_text("自动接收:")
        recv_label.set_style_text_font(lv.font_yb_cn_16, 0)

        self.recv_switch = lv.switch(recv_container)
        self.recv_switch.set_size(50, 25)
        self.recv_switch.align_to(recv_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.recv_switch.add_state(lv.STATE.CHECKED)
        self.recv_switch.add_event(self.on_recv_switch, lv.EVENT.VALUE_CHANGED, None)
        self.recv_switch.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.PART.MAIN)
        self.recv_switch.set_style_bg_color(lv.color_hex(0x1a73e8), lv.PART.INDICATOR)
        self.recv_switch.set_style_border_width(0, lv.PART.MAIN)

        # 数据统计面板
        stats_panel = lv.obj(card)
        stats_panel.set_size(lv.pct(100), 40)
        stats_panel.set_style_bg_opa(lv.OPA.TRANSP, 0)
        stats_panel.set_style_border_width(0, 0)
        stats_panel.set_style_pad_all(0, 0)
        stats_panel.set_style_pad_top(15, 0)
        stats_panel.set_style_pad_bottom(5, 0)
        stats_panel.set_flex_flow(lv.FLEX_FLOW.ROW)
        stats_panel.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        # 发送计数
        tx_stats = lv.obj(stats_panel)
        tx_stats.set_size(200, 30)
        tx_stats.set_style_bg_opa(lv.OPA.TRANSP, 0)
        tx_stats.set_style_border_width(0, 0)
        tx_stats.set_style_pad_all(0, 0)
        tx_stats.set_flex_flow(lv.FLEX_FLOW.ROW)
        tx_stats.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        tx_title = lv.label(tx_stats)
        tx_title.set_text("发送字节数:")
        tx_title.set_style_text_font(lv.font_yb_cn_16, 0)
        
        self.tx_count_label = lv.label(tx_stats)
        self.tx_count_label.set_text("0")
        self.tx_count_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.tx_count_label.set_style_text_color(lv.color_hex(0x1a73e8), 0)
        self.tx_count_label.align_to(tx_title, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        
        # 接收计数
        rx_stats = lv.obj(stats_panel)
        rx_stats.set_size(200, 30)
        rx_stats.set_style_bg_opa(lv.OPA.TRANSP, 0)
        rx_stats.set_style_border_width(0, 0)
        rx_stats.set_style_pad_all(0, 0)
        rx_stats.set_flex_flow(lv.FLEX_FLOW.ROW)
        rx_stats.set_flex_align(lv.FLEX_ALIGN.END, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        
        rx_title = lv.label(rx_stats)
        rx_title.set_text("接收字节数:")
        rx_title.set_style_text_font(lv.font_yb_cn_16, 0)
        
        self.rx_count_label = lv.label(rx_stats)
        self.rx_count_label.set_text("0")
        self.rx_count_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.rx_count_label.set_style_text_color(lv.color_hex(0x1a73e8), 0)
        self.rx_count_label.align_to(rx_title, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        
        # 清除按钮
        clear_btn = lv.btn(stats_panel)
        clear_btn.set_size(80, 30)
        clear_btn.set_style_radius(15, 0)
        clear_btn.set_style_bg_color(lv.color_hex(0xff5722), 0)
        clear_btn.add_event(self.on_clear_stats, lv.EVENT.CLICKED, None)
        
        clear_label = lv.label(clear_btn)
        clear_label.set_text("清除计数")
        clear_label.set_style_text_font(lv.font_yb_cn_16, 0)
        clear_label.set_style_text_color(lv.color_hex(0xffffff), 0)
        clear_label.center()

        # 数据交互区域
        data_panel = lv.obj(card)
        data_panel.set_size(lv.pct(100), lv.pct(70))
        data_panel.set_style_pad_all(0, 0)
        data_panel.set_style_border_width(0, 0)
        data_panel.set_style_bg_opa(lv.OPA.TRANSP, 0)
        data_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        data_panel.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)

        # 发送区域
        tx_section = lv.obj(data_panel)
        tx_section.set_size(lv.pct(100), lv.pct(40))
        tx_section.set_style_radius(10, 0)
        tx_section.set_style_bg_color(lv.color_hex(0xf8f8f8), 0)
        tx_section.set_style_pad_all(10, 0)
        tx_section.set_style_border_width(0, 0)
        tx_section.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        tx_section.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)

        tx_header = lv.obj(tx_section)
        tx_header.set_size(lv.pct(100), 30)
        tx_header.set_style_bg_opa(lv.OPA.TRANSP, 0)
        tx_header.set_style_border_width(0, 0)
        tx_header.set_style_pad_all(0, 0)
        tx_header.set_flex_flow(lv.FLEX_FLOW.ROW)
        tx_header.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        tx_title = lv.label(tx_header)
        tx_title.set_text("发送数据")
        tx_title.set_style_text_font(lv.font_yb_cn_16, 0)
        tx_title.set_style_text_color(lv.color_hex(0x333333), 0)

        # 发送按钮
        send_btn = lv.btn(tx_header)
        send_btn.set_size(80, 30)
        send_btn.set_style_radius(15, 0)
        send_btn.set_style_bg_color(lv.color_hex(0x1a73e8), 0)
        send_btn.add_event(self.on_send_data, lv.EVENT.CLICKED, None)

        send_label = lv.label(send_btn)
        send_label.set_text("发送")
        send_label.set_style_text_font(lv.font_yb_cn_16, 0)
        send_label.set_style_text_color(lv.color_hex(0xffffff), 0)
        send_label.center()

        # 发送文本区域
        self.tx_textarea = lv.textarea(tx_section)
        self.tx_textarea.set_size(lv.pct(100), lv.pct(80))
        self.tx_textarea.set_style_text_font(lv.font_yb_cn_16, 0)
        self.tx_textarea.set_placeholder_text("输入要发送的数据...")
        self.tx_textarea.set_one_line(False)
        self.tx_textarea.set_text("Hello UART")

        # 接收区域
        rx_section = lv.obj(data_panel)
        rx_section.set_size(lv.pct(100), lv.pct(60))
        rx_section.set_style_radius(10, 0)
        rx_section.set_style_bg_color(lv.color_hex(0xf8f8f8), 0)
        rx_section.set_style_pad_all(10, 0)
        rx_section.set_style_border_width(0, 0)
        rx_section.set_style_pad_top(20, 0)
        rx_section.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        rx_section.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)

        rx_header = lv.obj(rx_section)
        rx_header.set_size(lv.pct(100), 30)
        rx_header.set_style_bg_opa(lv.OPA.TRANSP, 0)
        rx_header.set_style_border_width(0, 0)
        rx_header.set_style_pad_all(0, 0)
        rx_header.set_flex_flow(lv.FLEX_FLOW.ROW)
        rx_header.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

        rx_title = lv.label(rx_header)
        rx_title.set_text("接收数据")
        rx_title.set_style_text_font(lv.font_yb_cn_16, 0)
        rx_title.set_style_text_color(lv.color_hex(0x333333), 0)

        # 清除接收按钮
        clear_rx_btn = lv.btn(rx_header)
        clear_rx_btn.set_size(80, 30)
        clear_rx_btn.set_style_radius(15, 0)
        clear_rx_btn.set_style_bg_color(lv.color_hex(0xff5722), 0)
        clear_rx_btn.add_event(self.on_clear_rx, lv.EVENT.CLICKED, None)

        clear_rx_label = lv.label(clear_rx_btn)
        clear_rx_label.set_text("清除")
        clear_rx_label.set_style_text_font(lv.font_yb_cn_16, 0)
        clear_rx_label.set_style_text_color(lv.color_hex(0xffffff), 0)
        clear_rx_label.center()

        # 接收文本区域
        self.rx_textarea = lv.textarea(rx_section)
        self.rx_textarea.set_size(lv.pct(100), lv.pct(80))
        self.rx_textarea.set_style_text_font(lv.font_yb_cn_16, 0)
        self.rx_textarea.set_placeholder_text("接收到的数据将显示在这里...")
        self.rx_textarea.set_one_line(False)
        self.rx_textarea.set_style_bg_color(lv.color_hex(0xffffff), 0)

        # 启动UART接收定时器
        if self.uart_timer is not None:
            lv.timer_del(self.uart_timer)
            
        if self.auto_receive:
            self.uart_timer = lv.timer_create(self.uart_receive_task, 100, None)

    def on_uart_port_changed(self, e):
        selected = self.uart_port_dropdown.get_selected()
        self.current_uart_port = selected
        self.reconfigure_uart()

    def on_baud_rate_changed(self, e):
        selected = self.baud_rate_dropdown.get_selected()
        baud_rates = [9600, 19200, 38400, 57600, 115200]
        self.current_baud_rate = baud_rates[selected]
        self.reconfigure_uart()

    def on_recv_switch(self, e):
        self.auto_receive = self.recv_switch.has_state(lv.STATE.CHECKED)
        
        if self.auto_receive:
            # 启动UART接收定时器
            if self.uart_timer is None:
                self.uart_timer = lv.timer_create(self.uart_receive_task, 100, None)
        else:
            # 停止UART接收定时器
            if self.uart_timer is not None:
                lv.timer_del(self.uart_timer)
                self.uart_timer = None

    def on_send_data(self, e):
        data = self.tx_textarea.get_text()
        if data:
            # 这里实际发送数据
            # uart_send(self.current_uart_port, data)
            
            # 更新发送计数
            self.tx_count += len(data)
            self.tx_count_label.set_text(str(self.tx_count))

    def on_clear_rx(self, e):
        self.rx_textarea.set_text("")
        self.rx_buffer = ""

    def on_clear_stats(self, e):
        self.tx_count = 0
        self.rx_count = 0
        self.tx_count_label.set_text("0")
        self.rx_count_label.set_text("0")

    def uart_receive_task(self, timer):
        if not self.auto_receive:
            return
            
        # 这里实际接收数据
        # 模拟接收数据
        import random
        if random.random() < 0.3:  # 30%概率收到数据
            received = "Received data " + str(int(random.random() * 100))
            
            # 更新接收计数
            self.rx_count += len(received)
            self.rx_count_label.set_text(str(self.rx_count))
            
            # 更新接收区域
            self.rx_buffer += received + "\n"
            
            # 限制缓冲区大小，防止内存溢出
            if len(self.rx_buffer) > 4000:
                self.rx_buffer = self.rx_buffer[-4000:]
                
            self.rx_textarea.set_text(self.rx_buffer)
            
            # 滚动到底部
            self.rx_textarea.scroll_to_end()

    def reconfigure_uart(self):
        # 这里实际重新配置UART
        # uart_configure(self.current_uart_port, self.current_baud_rate)
        pass

    def cleanup(self):
        # 停止UART接收定时器
        if self.uart_timer is not None:
            lv.timer_del(self.uart_timer)
            self.uart_timer = None
            
        # 关闭UART
        # uart_close(self.current_uart_port)
        pass