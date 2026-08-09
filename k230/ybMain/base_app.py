import lvgl as lv
from ybUtils.modal_dialog import ModalDialog
import time
from machine import Timer

# 自定义调试打印函数，可通过修改此变量来控制是否输出调试信息
DEBUG_ENABLED = False

def debug_print(*args, **kwargs):
    """自定义调试输出函数，方便后续关闭调试输出"""
    if DEBUG_ENABLED:
        print(*args, **kwargs)

class BaseApp:
    def __init__(self, app_manager, name, icon=None):
        debug_print(f"[BaseApp.__init__] 初始化应用: {name}")
        self.app_manager = app_manager
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        self.name = name
        self.icon = icon
        self.screen = None
        self.model_dialog = None
        self.icon_btn = None  # 保存图标按钮的引用
        # 预先获取屏幕尺寸，避免重复获取
        self.disp = lv.disp_get_default()
        self.disp_w = self.disp.get_hor_res()
        self.disp_h = self.disp.get_ver_res()
        self.back_lock = False  # 用于锁定返回按钮，避免多次点击
    
    def release_back_lock(self, timer=None):
        self.back_lock = False
        try:
            timer._del()
        except:
            pass
        
    
    def create_icon(self, parent):
        """创建在主屏幕上显示的应用图标"""
        debug_print(f"[create_icon] 创建应用图标: {self.name}")
        self.icon_btn = lv.btn(parent)
        # 设置图标样式
        icon_label = lv.label(self.icon_btn)
        icon_label.set_text(self.name)
        self.icon_btn.add_event(self.on_icon_clicked, lv.EVENT.CLICKED, None)
        debug_print(f"[create_icon] 图标创建完成: {self.name}")
        return self.icon_btn
    
    def on_icon_clicked(self, evt=None):
        """当应用图标被点击时调用
        
        参数设计为可选，以兼容不同的调用方式
        """
        debug_print(f"[on_icon_clicked] 图标被点击: {self.name}")
        self.launch_with_animation()
    
    def launch_with_animation(self):
        """带动画效果启动应用"""
        debug_print(f"[launch_with_animation] 开始启动应用: {self.name}")
        # 创建新屏幕
        self.screen = lv.obj()
        self.screen.set_style_text_font(self.app_manager.font_16, 0)
        debug_print("[launch_with_animation] 新屏幕已创建")
        
        # 获取图标的坐标和尺寸 (一次性获取并存储)
        icon_coords = lv.area_t()
        self.icon_btn.get_coords(icon_coords)
        icon_x = icon_coords.x1
        icon_y = icon_coords.y1
        icon_w = icon_coords.x2 - icon_coords.x1
        icon_h = icon_coords.y2 - icon_coords.y1
        start_radius = min(icon_w, icon_h)//2
        debug_print(f"[launch_with_animation] 图标坐标: x={icon_x}, y={icon_y}, w={icon_w}, h={icon_h}")
        debug_print(f"[launch_with_animation] 屏幕尺寸: w={self.disp_w}, h={self.disp_h}")
        
        # 先设置屏幕大小为图标大小，并定位到图标位置
        self.screen.set_size(icon_w, icon_h)
        self.screen.set_pos(icon_x, icon_y)
        self.screen.set_style_radius(start_radius, 0)  # 开始时是圆形
        self.screen.set_style_opa(0, 0)  # 开始时是透明的
        debug_print(f"[launch_with_animation] 初始屏幕设置: 大小={icon_w}x{icon_h}, 位置=({icon_x},{icon_y}), 圆角={start_radius}")
        
        # 添加标题栏和初始化应用内容，但先隐藏它们
        debug_print("[launch_with_animation] 创建标题栏")
        self._create_title_bar()
        self.title_bar.add_flag(lv.obj.FLAG.HIDDEN)
        debug_print("[launch_with_animation] 创建对话框")
        self.model_dialog = ModalDialog(self.screen, font_16=self.app_manager.font_16)
        
        # 显示屏幕
        debug_print("[launch_with_animation] 加载屏幕")
        lv.scr_load(self.screen)
        
        # 性能优化：创建一个综合动画对象，减少单独的动画对象数量
        # 使用一个动画对象处理多个属性变化，减少回调函数的数量
        anim = lv.anim_t()
        anim.init()
        anim.set_var(self.screen)
        anim.set_time(300)
        anim.set_path_cb(lv.anim_t.path_ease_out)
        anim.set_custom_exec_cb(lambda a, val: self._combined_anim_exec(val, icon_x, icon_y, start_radius))
        anim.set_values(0, 100)  # 使用百分比进度
        anim.set_ready_cb(self._on_anim_ready)
        debug_print("[launch_with_animation] 启动综合动画")
        anim.start()
        debug_print("[launch_with_animation] 所有动画已启动")

    def _combined_anim_exec(self, progress, start_x, start_y, start_radius):
        """综合动画执行函数，同时处理位置、大小、圆角和不透明度"""
        # 计算当前值 (仅在调试开启时输出日志)
        if DEBUG_ENABLED:
            debug_print(f"[_combined_anim_exec] 动画进度: {progress}%")
        
        # 位置变化（从图标位置到屏幕起始位置）
        current_x = start_x * (100 - progress) / 100
        current_y = start_y * (100 - progress) / 100
        self.screen.set_pos(int(current_x), int(current_y))
        
        # 尺寸变化（从图标尺寸到屏幕全尺寸）
        size_progress = progress / 100
        current_w = int(start_x + (self.disp_w - start_x) * size_progress)
        current_h = int(start_y + (self.disp_h - start_y) * size_progress)
        self.screen.set_size(current_w, current_h)
        
        # 圆角变化（从圆形到直角）
        current_radius = int(start_radius * (100 - progress) / 100)
        self.screen.set_style_radius(current_radius, 0)
        
        # 不透明度变化（从透明到不透明）
        current_opacity = int(255 * progress / 100)
        self.screen.set_style_opa(current_opacity, 0)
    
    def _on_anim_ready(self, anim):
        debug_print("[_on_anim_ready] 启动动画完成")
        # 动画完成后，显示标题栏
        self.title_bar.clear_flag(lv.obj.FLAG.HIDDEN)
        debug_print("[_on_anim_ready] 显示标题栏")
        
        # 可以选择为标题栏添加淡入动画
        debug_print("[_on_anim_ready] 创建标题栏淡入动画")
        anim = lv.anim_t()
        anim.init()
        anim.set_var(self.title_bar)
        anim.set_values(0, 255)
        anim.set_time(0)
        anim.set_path_cb(lv.anim_t.path_ease_out)
        anim.set_custom_exec_cb(lambda a, val: self._set_title_opacity(val))
        anim.set_ready_cb(self._on_anim_ready_2)
        anim.start()
        debug_print("[_on_anim_ready] 标题栏淡入动画已启动")
    
    def _set_title_opacity(self, v):
        if DEBUG_ENABLED:
            debug_print(f"[_set_title_opacity] 设置标题栏不透明度: {v}")
        self.title_bar.set_style_opa(v, 0)
        
    def _on_anim_ready_2(self, anim):
        debug_print("[_on_anim_ready_2] 标题栏动画完成，初始化应用")
        self.initialize() 
        
    def launch(self):
        """启动应用(无动画)"""
        debug_print(f"[launch] 直接启动应用(无动画): {self.name}")
        # 创建新屏幕
        self.screen = lv.obj()
        self.screen.set_style_text_font(self.app_manager.font_16, 0)
        # 添加标题栏
        self._create_title_bar()
        
        self.model_dialog = ModalDialog(self.screen, font_16=self.app_manager.font_16)
                
        # 应用特定初始化
        self.initialize()
        
        # 显示屏幕
        lv.scr_load(self.screen)
        debug_print(f"[launch] 应用启动完成: {self.name}")

    def _create_title_bar(self):
        """创建标题栏"""
        debug_print("[_create_title_bar] 开始创建标题栏")
        # 标题栏容器
        title_bar = lv.obj(self.screen)
        title_bar.set_size(lv.pct(100), 60)  # 略微增加高度
        title_bar.align(lv.ALIGN.TOP_MID, 0, 0)
        title_bar.set_style_bg_color(lv.color_hex(0x110704), 0)
        title_bar.set_style_bg_opa(240, 0)  # 略微透明
        title_bar.set_style_border_width(0, 0)  # 无边框
        title_bar.set_style_shadow_width(0, 0)  # 无阴影
        title_bar.set_style_pad_all(0, 0)  # 无内边距
        title_bar.set_style_radius(0, 0)
        title_bar.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条
        title_bar.set_scroll_dir(lv.DIR.NONE)  # 禁用滚动方向
        debug_print("[_create_title_bar] 标题栏容器已创建")
        
        # 底部分隔线 - 优化：使用静态坐标，避免动态分配内存
        line = lv.line(title_bar)
        line_points = [ {"x":0, "y":49}, {"x":lv.pct(100), "y":49} ]
        line.set_points(line_points, 2)
        line.set_style_line_color(lv.color_hex(0xDDDDDD), 0)  # 淡灰色分隔线
        line.set_style_line_width(1, 0)  # 1像素宽
        debug_print("[_create_title_bar] 分隔线已创建")
        
        # 后退按钮 - YAHBOOM K230 STYLE
        back_btn = lv.btn(title_bar)
        back_btn.set_size(100, 70)
        back_btn.align(lv.ALIGN.LEFT_MID, 8, 0)
        back_btn.set_style_bg_opa(0, 0)  # 透明背景
        back_btn.set_style_shadow_width(0, 0)  # 无阴影
        back_btn.set_style_border_width(0, 0)  # 无边框
        back_btn.set_style_pad_all(0, 0)  # 无内边距
        debug_print("[_create_title_bar] 返回按钮已创建")
        
        # 后退图标 (YAHBOOM K230 STYLE的箭头)
        back_label = lv.label(back_btn)
        back_label.align(lv.ALIGN.LEFT_MID, 8, 0)
        back_label.set_text(lv.SYMBOL.LEFT)  # Unicode左箭头
        back_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)  # 白色
        back_btn.add_event(self.on_back, lv.EVENT.CLICKED, None)
        debug_print("[_create_title_bar] 返回图标已创建并绑定事件")
        
        # 标题
        title = lv.label(title_bar)
        title.set_text(self.name)
        title.align(lv.ALIGN.CENTER, 0, 0)
        title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)  # 白色文字
        debug_print(f"[_create_title_bar] 标题文本已创建: {self.name}")
        
        # 保存对象引用以便后续访问
        self.title_bar = title_bar
        self.title_label = title
        debug_print("[_create_title_bar] 标题栏创建完成")
    
    def on_back(self, evt=None):
        """返回主屏幕，带动画效果"""
        debug_print("[on_back] 返回按钮被点击，准备返回主界面")
        if self.back_lock:
            debug_print("[on_back] lock")
            return
        
        self._close_with_animation()

    def _close_with_animation(self):
        debug_print("[_close_with_animation] 开始关闭动画")
        try:
            """带动画效果关闭应用"""
            
            # 获取图标和当前屏幕信息
            icon_coords = lv.area_t()
            current_coords = lv.area_t()
            
            self.icon_btn.get_coords(icon_coords)
            self.screen.get_coords(current_coords)
            
            icon_x = icon_coords.x1
            icon_y = icon_coords.y1
            icon_w = icon_coords.x2 - icon_coords.x1
            icon_h = icon_coords.y2 - icon_coords.y1
            
            current_x = current_coords.x1
            current_y = current_coords.y1
            
            debug_print(f"[_close_with_animation] 图标坐标: x={icon_x}, y={icon_y}, w={icon_w}, h={icon_h}")
            debug_print(f"[_close_with_animation] 当前屏幕坐标: x={current_x}, y={current_y}")
            
            # 先隐藏标题栏
            debug_print("[_close_with_animation] 隐藏标题栏")
            self.title_bar.add_flag(lv.obj.FLAG.HIDDEN)
            
            # 优化：使用单个简单动画, 只做Y轴移动
            anim = lv.anim_t()
            anim.init()
            anim.set_var(self.screen)
            anim.set_time(0)  # 速度更快，更流畅
            anim.set_values(current_y, 100)
            anim.set_path_cb(lv.anim_t.path_ease_in)
            
            # 使用 set_custom_exec_cb 替代 set_exec_cb，因为 Python 回调需要用 custom
            anim.set_custom_exec_cb(lambda a, y: self.screen.set_y(y))
            anim.set_ready_cb(self._on_close_anim_ready)
            
            debug_print(f"[_close_with_animation] Y坐标动画: {current_y} -> 100")
            anim.start()
            debug_print("[_close_with_animation] 关闭动画已启动")
        except lv.LvReferenceError as lve:
            debug_print(f"[_close_with_animation] 发生引用错误: {lve}")
            self.app_manager.go_home()
        except Exception as e:
            debug_print(f"[_close_with_animation] 发生未知错误: {e}")
            self.app_manager.go_home()

    def _on_close_anim_ready(self, anim):
        debug_print("[_on_close_anim_ready] 关闭动画完成，返回主屏幕")
        # 动画完成后返回主屏幕
        self.app_manager.go_home()
        
    def initialize(self):
        """应用程序初始化 - 由子类实现"""
        debug_print(f"[initialize] 初始化应用: {self.name}")
        pass
    
    def deinitialize(self):
        """应用程序清理资源 - 由子类实现"""
        debug_print(f"[deinitialize] 清理应用资源: {self.name}")
        pass