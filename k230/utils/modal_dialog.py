import lvgl as lv

class ModalDialog:
    def __init__(self, parent=None, font_14=lv.font_montserrat_14, font_16=lv.font_montserrat_16):
        """初始化模态对话框
        
        Args:
            parent: 父容器，默认为None(使用lv.scr_act())
        """
        self.parent = parent if parent else lv.scr_act()
        self.modal = None
        self.box = None
        self.title_label = None
        self.content_label = None
        self.icon = None
        self.buttons = []
        self.callbacks = []
        self.font_14 = font_14
        self.font_16 = font_16
        
    def _btn_event_cb(self, evt):
        """按钮事件回调处理"""
        code = evt.get_code()
        btn = lv.btn.__cast__(evt.get_target())
        
        if code == lv.EVENT.CLICKED:
            # 查找点击的是哪个按钮
            for idx, b in enumerate(self.buttons):
                if b == btn and idx < len(self.callbacks) and self.callbacks[idx]:
                    # 执行对应的回调函数
                    self.callbacks[idx](self)
            
            # 关闭模态框
            self.close()
    
    def show(self, title="", content="", icon_symbol=None, 
             btn_texts=None, btn_callbacks=None, width=480, height=320):
        """显示模态框
        
        Args:
            title: 模态框标题
            content: 模态框内容
            icon_symbol: 图标符号(lv.SYMBOL_...)
            btn_texts: 按钮文本列表
            btn_callbacks: 按钮回调函数列表
            width: 模态框宽度
            height: 模态框高度
        """
        # 清除之前的模态窗口(如果存在)
        if self.modal:
            self.close()
            
        # 创建半透明背景
        self.modal = lv.obj(self.parent)
        self.modal.set_size(800, 480)  # 全屏尺寸
        self.modal.clear_flag(lv.obj.FLAG.SCROLLABLE)
        self.modal.add_style(self._create_modal_style(), 0)
        
        # 创建对话框容器
        self.box = lv.obj(self.modal)
        self.box.set_size(width, height)
        self.box.center()
        self.box.add_style(self._create_box_style(), 0)
        self.box.clear_flag(lv.obj.FLAG.SCROLLABLE)
        
        # 标题栏
        title_container = lv.obj(self.box)
        title_container.set_size(width, 25)
        title_container.set_pos(0, 0)
        title_container.add_style(self._create_title_container_style(), 0)
        title_container.clear_flag(lv.obj.FLAG.SCROLLABLE)

        # 标题文本
        title_x_offset = 0  # 重置为0，因为内边距已经处理了边距
        if icon_symbol:
            self.icon = lv.label(title_container)
            self.icon.set_text(icon_symbol)
            self.icon.align(lv.ALIGN.LEFT_MID, 0, 0)  # 不需额外偏移
            self.icon.add_style(self._create_icon_style(), 0)
            title_x_offset = 30  # 图标后的间距

        self.title_label = lv.label(title_container)
        self.title_label.set_text(title)
        self.title_label.align(lv.ALIGN.LEFT_MID, title_x_offset, 0)
        self.title_label.add_style(self._create_title_style(), 0)
        
        # 内容区域
        content_container = lv.obj(self.box)
        content_container.set_size(width - 40, height - 140)
        content_container.align(lv.ALIGN.TOP_MID, 0, 30)
        content_container.add_style(self._create_content_container_style(), 0)
        
        # 内容文本
        self.content_label = lv.label(content_container)
        self.content_label.set_text(content)
        self.content_label.set_long_mode(lv.label.LONG.WRAP)
        self.content_label.set_width(width - 80)
        self.content_label.align(lv.ALIGN.TOP_LEFT, 20, 20)
        self.content_label.add_style(self._create_content_style(), 0)
        
        # 按钮区域
        if btn_texts and len(btn_texts) > 0:
            button_container = lv.obj(self.box)
            button_container.set_height(60)
            button_container.set_width(width)
            button_container.align(lv.ALIGN.BOTTOM_MID, 0, 0)
            button_container.add_style(self._create_button_container_style(), 0)
            button_container.clear_flag(lv.obj.FLAG.SCROLLABLE)
            
            # 创建按钮
            btn_count = len(btn_texts)
            btn_width = min(150, (width - 40) // btn_count)
            
            self.buttons = []
            self.callbacks = btn_callbacks if btn_callbacks else [None] * btn_count
            
            for i, text in enumerate(btn_texts):
                btn = lv.btn(button_container)
                btn.set_size(btn_width, 40)
                
                # 计算按钮位置，实现均匀分布
                offset = (width - (btn_width * btn_count)) // (btn_count + 1)
                x_pos = offset * (i + 1) + btn_width * i
                
                btn.set_pos(x_pos, 10)
                btn.add_style(self._create_button_style(i == btn_count - 1), 0)
                btn.add_event(self._btn_event_cb, lv.EVENT.CLICKED, None)
                
                # 按钮文本
                label = lv.label(btn)
                label.set_text(text)
                label.center()

                self.buttons.append(btn)
                
        return self  # 返回self以支持链式调用
    
    def close(self):
        """关闭模态框"""
        if self.modal:
            self.modal.delete()
            self.modal = None
            self.box = None
            self.title_label = None
            self.content_label = None
            self.icon = None
            self.buttons = []
            self.callbacks = []
    
    def _create_modal_style(self):
        """创建模态层样式"""
        style = lv.style_t()
        style.init()
        style.set_bg_color(lv.color_hex(0x000000))
        style.set_bg_opa(lv.OPA._50)
        style.set_radius(0)
        style.set_border_width(0)
        style.set_border_color(lv.color_hex(0x000000))
        return style
    
    def _create_box_style(self):
        """创建对话框容器样式"""
        style = lv.style_t()
        style.init()
        style.set_bg_color(lv.color_hex(0xFFFFFF))
        style.set_radius(16)
        style.set_shadow_width(24)
        style.set_shadow_ofs_y(8)
        style.set_shadow_opa(lv.OPA._20)
        style.set_border_width(0)
        return style
    
    # 标题容器样式函数修改
    def _create_title_container_style(self):
        """创建标题容器样式"""
        style = lv.style_t()
        style.init()
        style.set_bg_opa(lv.OPA.COVER)
        style.set_radius(16)
        style.set_border_width(0)
        style.set_pad_left(20)  # 添加左内边距
        style.set_pad_right(20) # 添加右内边距
        style.set_pad_top(0)
        style.set_pad_bottom(0)
        return style
    
    def _create_title_style(self):
        """创建标题文本样式"""
        style = lv.style_t()
        style.init()
        style.set_text_color(lv.color_hex(0x25201b))
        style.set_text_font(self.font_14)
        return style
    
    def _create_icon_style(self):
        """创建图标样式"""
        style = lv.style_t()
        style.init()
        style.set_text_color(lv.color_hex(0x25201b))
        # style.set_text_font(lv.font_montserrat_14)
        return style
    
    def _create_content_container_style(self):
        """创建内容容器样式"""
        style = lv.style_t()
        style.init()
        style.set_bg_opa(lv.OPA.TRANSP)
        style.set_border_width(0)
        style.set_pad_all(0)
        return style
    
    def _create_content_style(self):
        """创建内容文本样式"""
        style = lv.style_t()
        style.init()
        style.set_text_color(lv.color_hex(0x333333))
        style.set_text_font(self.font_16)
        style.set_text_line_space(5)
        return style
    
    def _create_button_container_style(self):
        """创建按钮容器样式"""
        style = lv.style_t()
        style.init()
        style.set_bg_opa(lv.OPA.TRANSP)
        style.set_border_width(0)
        style.set_pad_all(0)
        return style
    
    def _create_button_style(self, is_primary=False):
        """创建按钮样式
        
        Args:
            is_primary: 是否为主按钮(强调按钮)
        """
        style = lv.style_t()
        style.init()
        if is_primary:
            style.set_bg_color(lv.color_hex(0x6200EE))  # Material主色调
            style.set_text_color(lv.color_hex(0xFFFFFF))
        else:
            style.set_bg_color(lv.color_hex(0xE0E0E0))
            style.set_text_color(lv.color_hex(0x333333))
        style.set_radius(8)
        style.set_shadow_width(0)
        style.set_border_width(0)
        return style
    def close_after(self, ms):
        """在指定毫秒后关闭模态框"""
        timer = lv.timer_create(lambda timer: self.close(), ms, None)
        timer.set_repeat_count(1)  # 只执行一次
        return self  # 支持链式调用
    
    def add_close_listener(self, obj, event):
        """添加关闭监听器，当指定对象触发指定事件时关闭模态框"""
        def event_cb(evt):
            self.close()
            
        obj.add_event(event_cb, event, None)
        return self  # 支持链式调用