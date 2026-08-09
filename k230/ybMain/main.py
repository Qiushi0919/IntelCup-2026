import lvgl as lv
import utime as time
from media.display import *
from media.media import *
import os, sys, gc
import lvgl as lv
from machine import TOUCH
import uctypes
import math,network
from machine import Timer
import _thread
from libs.PipeLine import PipeLine
#from ybUtils.ybImg import *
from ybUtils.Configuration import Configuration
import ybUtils.monitor as monitor
from ybUtils.YbNetwork import YbNetwork
from ybUtils.modal_dialog import ModalDialog
from ybUtils.YbKey import YbKey
from ybUtils.YbBuzzer import YbBuzzer
from ybUtils.YbRGB import YbRGB
from ybUtils.YbUart import YbUart, DisabledUart
# uart = None

from ybMain.WelcomeScreen import WelcomeScreen

import machine


##### 检测是否为标准版 #####
from machine import I2C
import sys, time

def check_lcd():
    i2c=I2C(3, freq = 100 * 1000)
    addr_list = i2c.scan()
    print("i2c list:", addr_list)

    for a in addr_list:
        if a == 56:
            print("find lcd")
            return True
    return False

if not check_lcd():
    print("lcd not found, exit program")
    sys.exit()



start_time = time.ticks_ms()
DISPLAY_WIDTH = ALIGN_UP(640, 16)
DISPLAY_HEIGHT = 480

config = None
ybnet = YbNetwork()
YbKey = YbKey()
ybbuzzer = YbBuzzer()
YbRGB = YbRGB()
pl = None

def debug_print(*args):
    print("[DEBUG]", *args)

def display_init():
    global pl, config
    try:
        t = time.ticks_ms()
        YbRGB.show_rgb((82, 139, 255))
        display_mode = "lcd"
        display_size = [DISPLAY_WIDTH, 480]
        rgb888p_size = [640, 480]
        pl = PipeLine(rgb888p_size=rgb888p_size, display_size=display_size, display_mode=display_mode, osd_layer_num=4)
        pl.create(ch1_frame_size=[config.get_section("sensor")["ch1_width"], config.get_section("sensor")["ch1_height"]])
        print("display_init: ", time.ticks_diff(time.ticks_ms(), t))
    except Exception as e:
        debug_print("display_init", e)

def display_deinit():
    try:
        global pl
        pl.destroy()
        time.sleep_ms(50)
    except Exception as e:
        debug_print("display_deinit", e)

def disp_drv_flush_cb(disp_drv, area, color):
    global disp_img1, disp_img2

    try:
        if disp_drv.flush_is_last() == True:
            if disp_img1.virtaddr() == uctypes.addressof(color.__dereference__()):
                Display.show_image(disp_img1)
            else:
                Display.show_image(disp_img2)
        disp_drv.flush_ready()
    except Exception as e:
        debug_print("disp_drv_flush_cb", e)

class touch_screen():
    def __init__(self):
        self.state = lv.INDEV_STATE.RELEASED
        self.indev_drv = lv.indev_create()
        self.indev_drv.set_type(lv.INDEV_TYPE.POINTER)
        self.indev_drv.set_read_cb(self.callback)
        self.touch = TOUCH(0)

    def callback(self, driver, data):
        x, y, state = 0, 0, lv.INDEV_STATE.RELEASED
        tp = self.touch.read(1)
        if len(tp):
            x, y, event = tp[0].x, tp[0].y, tp[0].event
            if event == 2 or event == 3:
                state = lv.INDEV_STATE.PRESSED
        data.point = lv.point_t({'x': x, 'y': y})
        data.state = state

def lvgl_init():
    t = time.ticks_ms()
    global disp_img1, disp_img2, global_touch_dev

    lv.init()

    disp_drv = lv.disp_create(DISPLAY_WIDTH, DISPLAY_HEIGHT)

    disp_drv.set_flush_cb(disp_drv_flush_cb)

    disp_img1 = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.BGRA8888)
    disp_img2 = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.BGRA8888)

    disp_drv.set_draw_buffers(disp_img1.bytearray(), disp_img2.bytearray(), disp_img1.size()*5, lv.DISP_RENDER_MODE.FULL)

    global_touch_dev = touch_screen()

    print("lvgl_init: ", time.ticks_diff(time.ticks_ms(), t))

def get_key_from_value(dictionary, value):
    for k, v in dictionary.items():
        if v == value:
            return k
    return None

def lvgl_deinit():
    try:
        global disp_img1, disp_img2

        lv.deinit()
        del disp_img1
        del disp_img2
    except Exception as e:
        debug_print("lvgl_deinit", e)

def wlan_connect_thread(ssid, password, connection_flag):
    """WiFi连接的线程函数"""
    try:
        ybnet.CONNECT_WIFI(ssid, password)
        connection_flag[0] = True  # 标记连接完成
    except Exception as e:
        debug_print("wlan_connect_thread", e)
        connection_flag[0] = False
    finally:
        _thread.exit()

def check_connection_timer_cb(timer, model_dialog, connection_flag):
    """定时器回调检查连接状态"""
    try:
        if connection_flag[0] is not None:  # 连接状态已确定
            model_dialog.close()
            timer._del()  # 删除定时器
    except Exception as e:
        debug_print("check_connection_timer_cb", e)

def wlan_init():
    global config
    config.set_value("WLAN", "status", 0)
    config.save_to_file('/sdcard/configs/sys_config.json')
    return

def create_black_frosted_style():
    # 创建一个新的样式
    style_black_frosted = lv.style_t()
    style_black_frosted.init()

    # 设置背景颜色为深黑色
    style_black_frosted.set_bg_color(lv.color_make(20, 20, 20))  # 深黑色

    # 设置背景透明度，用于模拟磨砂效果
    # style_black_frosted.set_bg_opa(255)  # 约90%的不透明度

    # 设置背景渐变效果，增强质感
    style_black_frosted.set_bg_grad_color(lv.color_make(40, 40, 40))  # 稍微亮一点的黑色
    style_black_frosted.set_bg_grad_dir(lv.GRAD_DIR.VER)
    style_black_frosted.set_bg_grad_stop(128)  # 中点渐变

    # 添加磨砂感
    style_black_frosted.set_bg_dither_mode(lv.DITHER.ORDERED)

    # 添加轻微的圆角
    style_black_frosted.set_radius(0)

    # 添加微弱阴影增强质感
    style_black_frosted.set_shadow_width(10)
    style_black_frosted.set_shadow_color(lv.color_make(0, 0, 0))
    style_black_frosted.set_shadow_opa(40)
    style_black_frosted.set_shadow_ofs_x(0)
    style_black_frosted.set_shadow_ofs_y(4)
    style_black_frosted.set_shadow_spread(0)

    return style_black_frosted

# 使用示例
def apply_black_frosted_background(obj):
    style = create_black_frosted_style()
    obj.add_style(style, 0)

class AppManager:
    def __init__(self, config, pipeline, recorder, text_config):
        self.apps = {}
        self.app_index = {}
        self.home_screen = None
        self.home_screen_width = 640
        self.current_app = None
        self.current_page = 1
        self.page_count = 1
        self.change_page_lock = False #False时不允许切换页面
        self.dock_apps = []  # 底部Dock栏应用
        self.logic_wifi_status = 0
        self.page_timer = Timer(-1)

        self.recorder = recorder
        self.text_config = text_config

        # 图标布局参数
        self.icon_size = 115  # 图标大小
        self.icon_spacing_x = 30  # 水平间距
        self.icon_spacing_y = 40  # 垂直间距
        self.grid_start_x = 40  # 网格起始x坐标
        self.grid_start_y = 100  # 网格起始y坐标 (状态栏下方)
        self.icons_per_row = 4  # 每行图标数
        self.rows_per_page = 1  # 每页行数
        self.apps_per_page = self.icons_per_row * self.rows_per_page  # 每页应用数

        # 添加滑动翻页需要的变量
        self.touch_start_x = 0
        self.touch_start_y = 0
        self.is_swiping = False
        self.min_swipe_distance = 3  # 最小滑动距离，小于这个距离不算有效滑动

        self.lock_screen = None
        # UART1/IO9 is reserved exclusively for the gimbal motor.  Existing AI
        # apps still receive ``self.uart`` for API compatibility, but it is a
        # no-output object so recognition telemetry cannot reach the motor.
        self.uart = DisabledUart()
        self.gimbal_uart = YbUart(baudrate=115200)
        # 读入配置
        self.config = config

        self.pl = pipeline

        self.ybnet = ybnet

        # 添加背景图片缓存
        self.bg_image_cache = None
        self.bg_img_obj = None

        self.YbKey = YbKey
        self.ybbuzzer = ybbuzzer
        self.YbRGB = YbRGB

        # 添加状态栏更新计数器
        self.status_bar_counter = 0

        self.first_use = False
        
        self.lock_screen_img = None

    def is_first_use(self):
        # 判断是不是第一次上电
        file_path = "/sdcard/first.txt"
        file_name = "first.txt"
        lang = self.text_config
        # 获取/sdcard目录下的所有文件列表
        try:
            files = os.listdir("/sdcard")
            if (file_name in files) or ((lang is None) or (lang=="")):
                # 文件存在，删除它
                debug_print("file exist")
                # os.remove(file_path)
                self.first_use = True
                return True
            else:
                debug_print("file not ex")
                self.first_use = False
                return False
        except Exception as e:
            debug_print("is_first_use", e)
            return False

    def show_hello_page(self):
        try:
            welcome = WelcomeScreen(lv.scr_act(), self.config)
        except Exception as e:
            debug_print("show_hello_page", e)

    def status_bar_manager(self):
        count = 0

        while True:
            try:
                # 减少状态栏更新频率，降低CPU负载
                time.sleep_ms(100)  # 增加睡眠时间以降低CPU使用率

                count += 1
                # 减少WIFI状态检查频率
                if count % 10 == 0:  # 每1秒检查一次WIFI状态
                    try:
                        if network.WLAN(0).isconnected():
                            if self.logic_wifi_status == 0:
                                # 状态异常
                                # 读取配置文件
                                self.signal_label.set_text("")
                                print("wifi status: ", self.logic_wifi_status)
                                ybnet.DISCONNECT_WIFI(10000)
                            else:
                                self.signal_label.set_text(lv.SYMBOL.WIFI)
                        else:
                            self.signal_label.set_text("")
                    except Exception as e:
                        debug_print("wifi_check", e)

                # 减少CPU和内存状态更新频率
                if count % 5 == 0:  # 每0.5秒更新一次系统状态
                    m = gc.sys_heap()
                    self.status_label.set_text(f"CPU: {100-os.cpu_usage()}%   |   Mem: {int((m[1]/m[0] * 100))}%")

                # 重置计数器防止溢出
                if count > 1000:
                    count = 0

            except Exception as e:
                debug_print("status_bar_manager", e)
                time.sleep(2)

    def initialize(self):
        try:
            self.YbRGB.show_rgb((202, 100, 234))
            self.show_loading("Fonts [1/3]")
            self.font_14 = lv.font_yb_cn_16
            self.show_loading("Fonts [2/3]")
            self.font_16 = lv.font_yb_cn_16
            self.show_loading("Fonts [3/3]")
            self.font_18 = None
            self.show_loading("Fonts [Done]")
            self.first_use = self.is_first_use()
            # 创建主屏幕
            self.home_screen = lv.obj()
            self.home_screen.set_size(self.home_screen_width, 480)

            print("first use: ", self.first_use)

            # 设置背景
            if self.config.get_section("display")["wallpaper"] == "":
                # 渐变黑色
                style = create_black_frosted_style()
                # 添加主样式
                self.home_screen.add_style(style, 0)
            else:
                try:
                    with open(self.config.get_section("display")["wallpaper"], 'rb') as f:
                        self.bg_image_cache = f.read()
                        img_bg = lv.img_dsc_t({
                          'data_size': len(self.bg_image_cache),
                          'data': self.bg_image_cache
                        })
                        self.home_screen.set_style_bg_img_src(img_bg, 0)
                except Exception as e:
                    debug_print("load_wallpaper", e)
                    # 创建渐变样式
                    style = create_black_frosted_style()
                    # 添加主样式
                    self.home_screen.add_style(style, 0)
                    
                    
            # 读背景
            try:
                with open(self.config.get_section("display")["LSwallpaper"], 'rb') as f:
                    self.bg_image_cache = f.read()
                    self.lock_screen_img = lv.img_dsc_t({
                        'data_size': len(self.bg_image_cache),
                        'data': self.bg_image_cache
                    })
            except Exception as e:
                print("get lockscreen wallpaper error", e)
            # 创建状态栏
            self.status_bar = lv.obj(self.home_screen)
            self.status_bar.set_size(self.home_screen_width, 60)
            self.status_bar.set_pos(0, 0)
            self.status_bar.set_style_bg_color(lv.color_hex(0x000000), 0)
            self.status_bar.set_style_bg_opa(0, 0)  # 透明
            self.status_bar.set_style_border_width(0, 0)  # 无边框

            self.status_bar_tmp = lv.obj(self.home_screen)
            self.status_bar_tmp.set_size(640-self.home_screen_width, lv.pct(100))
            self.status_bar_tmp.set_pos(self.home_screen_width, 0)
            self.status_bar_tmp.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
            self.status_bar_tmp.set_style_bg_opa(100, 0)
            self.status_bar_tmp.set_style_border_width(0, 0)  # 无边框
            self.status_bar_tmp.set_style_radius(0, 0)

            # 添加时间到状态栏
            self.status_label = lv.label(self.status_bar)
            m = gc.sys_heap()
            self.status_label.set_text(f"CPU: {100-os.cpu_usage()}%   |   Mem: {int((m[1]/m[0] * 100))}%")  # 经典YAHBOOM K230 STYLE时间
            self.status_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            self.status_label.align(lv.ALIGN.LEFT_MID, 0, 0)
            self.status_label.set_style_text_font(lv.font_yb_cn_16, 0)

            # 添加信号图标
            self.signal_label = lv.label(self.status_bar)
            self.signal_label.set_text(lv.SYMBOL.WIFI)
            self.signal_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            self.signal_label.align(lv.ALIGN.RIGHT_MID, -10, 0)
            self.signal_label.set_style_text_font(self.font_16, 0)

            # 添加USB
            self.loading_label = lv.label(self.status_bar)
            self.loading_label.add_flag(lv.obj.FLAG.HIDDEN)
            self.loading_label.set_text(" ")
            self.loading_label.align(lv.ALIGN.RIGHT_MID, -70, 0)

            # 添加以下代码禁用滚动条
            self.status_bar.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条
            self.status_bar.set_scroll_dir(lv.DIR.NONE)  # 禁用滚动方向

            # 创建透明的全屏遮罩以捕获滑动手势
            self.gesture_layer = lv.obj(self.home_screen)
            self.gesture_layer.set_size(lv.pct(100), lv.pct(100))
            self.gesture_layer.set_pos(0, 0)
            self.gesture_layer.set_style_bg_opa(0, 0)  # 完全透明
            self.gesture_layer.set_style_border_width(0, 0)  # 无边框
            self.gesture_layer.set_style_pad_all(0, 0)  # 无内边距

            # 设置手势层在最顶层但点击可穿透到下层
            self.gesture_layer.add_flag(lv.obj.FLAG.CLICKABLE)
            self.gesture_layer.clear_flag(lv.obj.FLAG.CLICK_FOCUSABLE)

            # 添加事件处理
            self.gesture_layer.add_event(self.on_gesture_press, lv.EVENT.PRESSED, None)
            self.gesture_layer.add_event(self.on_gesture_release, lv.EVENT.RELEASED, None)

            # 创建应用容器，用于存放图标，方便切换页面时统一清除
            self.app_container = lv.obj(self.home_screen)
            self.app_container.set_size(lv.pct(100), lv.pct(100))
            self.app_container.set_pos(0, 0)
            self.app_container.set_style_bg_opa(0, 0)  # 完全透明
            self.app_container.set_style_border_width(0, 0)  # 无边框
            self.app_container.set_style_pad_all(0, 0)  # 无内边距
            self.app_container.clear_flag(lv.obj.FLAG.CLICKABLE) # 允许点击穿透，图标自己会响应
            self.app_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF) # 禁用滚动条

            # 创建页面指示器 - YAHBOOM K230 STYLE圆点
            self.page_indicator = lv.obj(self.home_screen)
            self.page_indicator.set_size(120, 30)
            self.page_indicator.set_pos((self.home_screen_width - 120) // 2, DISPLAY_HEIGHT - 135)
            self.page_indicator.set_style_bg_opa(0, 0)  # 透明背景
            self.page_indicator.set_style_border_width(0, 0)  # 无边框
            self.page_indicator.set_flex_flow(lv.FLEX_FLOW.ROW)
            self.page_indicator.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

            # 添加以下代码禁用滚动条
            self.page_indicator.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条
            self.page_indicator.set_scroll_dir(lv.DIR.NONE)  # 禁用滚动方向

            # 创建底部Dock栏 - YAHBOOM K230 STYLE毛玻璃效果
            self.dock = lv.obj(self.home_screen)
            self.dock.set_height(85)  # 只设置高度，宽度稍后设置
            self.dock.set_style_radius(20, 0)  # 圆角
            self.dock.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)  # 白色背景
            self.dock.set_style_bg_opa(50, 0)  # 半透明
            self.dock.set_style_border_width(0, 0)  # 无边框
            self.dock.set_style_shadow_width(15, 0)  # 轻微阴影
            self.dock.set_style_shadow_opa(30, 0)  # 阴影透明度
            self.dock.set_style_shadow_color(lv.color_hex(0x000000), 0)  # 阴影颜色
            self.dock.set_style_shadow_ofs_y(5, 0)  # 阴影偏移
            self.dock.set_flex_flow(lv.FLEX_FLOW.ROW)
            self.dock.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
            self.dock.set_style_pad_column(15, 0)  # 设置列间距为15像素
            self.dock.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条
            self.dock.set_scroll_dir(lv.DIR.NONE)  # 禁用滚动方向

            if self.first_use:
                lv.scr_load(self.home_screen)
                self.YbRGB.show_rgb((245, 245, 245))
                self.show_hello_page()
            else:
                # 扫描并加载所有应用
                self.scan_apps()

                # 更新页面指示器
                self.update_page_indicator()

                # 显示主屏幕
                lv.scr_load(self.home_screen)
                self.open_lock_screen()

                # 使用线程进行状态栏更新以降低主线程负载
                _thread.start_new_thread(self.status_bar_manager, ())
        except Exception as e:
            debug_print("initialize", e)
        finally:
            self.YbRGB.show_rgb((0,0,0))

    def open_lock_screen(self):
        try:
            # 创建锁屏界面
            if self.lock_screen is not None:
                try:
                    self.lock_screen.delete()
                except Exception as e:
                    debug_print("delete_lock_screen", e)
            self.lock_screen = lv.obj(lv.scr_act())
            self.lock_screen.set_size(640, 480)
            self.lock_screen.set_style_bg_color(lv.color_hex(0x000000), 0)
            
            try:
                if self.lock_screen_img:
                    self.lock_screen.set_style_bg_img_src(self.lock_screen_img, 0)
                else:
                    self.lock_screen.set_style_bg_color(lv.color_hex(0x000000), 0)

            except Exception as e:
                debug_print("load_lock_screen_wallpaper", e)
                self.lock_screen.set_style_bg_color(lv.color_hex(0x000000), 0)

            self.lock_screen.set_style_border_width(0, 0)  # 无边框
            self.lock_screen.set_style_radius(0, 0)
            self.lock_screen.add_flag(lv.obj.FLAG.CLICKABLE)
            self.lock_screen.clear_flag(lv.obj.FLAG.CLICK_FOCUSABLE)

            # 添加事件处理
            self.lock_screen.add_event(self.on_gesture_release_when_lock, lv.EVENT.RELEASED, None)
            self.lock_screen.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)  # 禁用滚动条

            self.wifi_label = lv.label(self.lock_screen)
            self.wifi_label.set_text("  ")  # 示例WIFI状态
            self.wifi_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            self.wifi_label.set_style_text_font(lv.font_yb_cn_16, 0)
            self.wifi_label.align(lv.ALIGN.CENTER, 0, 0)

            # 添加上滑解锁提示标签
            self.unlock_label = lv.obj(self.lock_screen)
            self.unlock_label.set_size(120, 5)
            self.unlock_label.set_pos(250, 450)
            self.unlock_label.set_style_radius(3, 0)  # 圆角
            self.unlock_label.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)  # 白色
            self.unlock_label.set_style_bg_opa(200, 0)  # 不完全不透明
            self.unlock_label.set_style_border_width(0, 0)  # 无边框

            # 启动加载动画
            self.anim_on_open_lock_screen()
        except Exception as e:
            debug_print("open_lock_screen", e)

    def anim_on_open_lock_screen(self):
        try:
            # 初始化锁屏位置
            # 创建关闭动画
            anim = lv.anim_t()
            anim.init()
            anim.set_var(self.lock_screen)
            anim.set_values(-10, 0)  # 从当前位置(0)移动到屏幕底部(480)
            anim.set_time(300)  # 动画持续时间300ms
            anim.set_path_cb(lv.anim_t.path_ease_in)  # 添加缓动效果

            # 设置y坐标的动画
            def y_cb(obj, value):
                self.lock_screen.set_y(value)
            anim.set_custom_exec_cb(lambda a,val: y_cb(self.lock_screen,val))
            
            # 设置动画结束回调，强制刷新以避免残留
            def anim_open_ready_cb(anim):
                self.lock_screen.invalidate()
                lv.refr_now(None)
            anim.set_ready_cb(anim_open_ready_cb)

            # 启动动画
            anim.start()
        except Exception as e:
            debug_print("anim_on_open_lock_screen", e)

    def close_lock_screen(self):
        try:
            # 创建关闭动画
            anim = lv.anim_t()
            anim.init()
            anim.set_var(self.lock_screen)
            anim.set_values(0, -470)  # 从当前位置(0)移动到屏幕底部(480)
            anim.set_time(0)  # 动画持续时间300ms
            anim.set_path_cb(lv.anim_t.path_ease_in)  # 添加缓动效果
            m = gc.sys_heap()

            # 设置y坐标的动画
            def y_cb(obj, value):
                self.status_label.set_text(f"CPU: {100-os.cpu_usage()}%   |   Mem: {int((m[1]/m[0] * 100))}%")
                self.lock_screen.set_y(value)
            anim.set_custom_exec_cb(lambda a,val: y_cb(self.lock_screen,val))

            # 设置动画结束回调
            def anim_ready_cb(anim):
                self.status_label.set_text(f"CPU: -- %   |   Mem: -- %")
                self.lock_screen.delete()
                self.lock_screen = None
                self.home_screen.invalidate()
                lv.refr_now(None)

            anim.set_ready_cb(anim_ready_cb)

            # 启动动画
            anim.start()
        except Exception as e:
            debug_print("close_lock_screen", e)

    def on_gesture_release_when_lock(self, event):
        """处理触摸释放事件，判断是否为有效滑动手势"""
        try:
            indev = lv.indev_get_act()
            if indev is not None:
                point = lv.point_t()
                indev.get_vect(point)  # 使用 get_vect 替代 get_point

                # point.x 和 point.y 现在包含了相对于按下位置的位移
                delta_x = point.x
                delta_y = point.y

                if abs(delta_y) > 2 and delta_x < abs(delta_y):
                    if delta_y < 0:
                        self.close_lock_screen()
        except Exception as e:
            debug_print("on_gesture_release_when_lock", e)

    def on_gesture_press(self, event):
        """处理触摸按下事件，记录起始位置"""
        try:
            # 获取按下坐标
            indev = event.get_indev()
            if indev is not None:
                point = lv.point_t()
                indev.get_point(point)
                self.touch_start_x = point.x
                self.touch_start_y = point.y
                self.is_swiping = True
        except Exception as e:
            debug_print("on_gesture_press", e)

    def on_gesture_release(self, event):
        """处理触摸释放事件，判断是否为有效滑动手势"""
        try:
            if not self.is_swiping:
                return

            indev = lv.indev_get_act()
            if indev is not None:
                point = lv.point_t()
                indev.get_vect(point)  # 使用 get_vect 替代 get_point

                # point.x 和 point.y 现在包含了相对于按下位置的位移
                delta_x = point.x
                delta_y = point.y

                # 如果水平滑动距离足够大，且垂直滑动不太大（确保是水平滑动）
                if abs(delta_x) >= abs(delta_y):
                    if abs(delta_x) > self.min_swipe_distance:
                        if delta_x > 0:
                            # 向右滑动，切换到上一页
                            if self.current_page == 1:
                                # 如果在第一页向右滑，循环到最后一页
                                self.change_page(self.page_count)
                            else:
                                self.change_page(self.current_page - 1)
                        else:
                            # 向左滑动，切换到下一页
                            if self.current_page == self.page_count:
                                # 如果在最后一页向左滑，循环到第一页
                                self.change_page(1)
                            else:
                                self.change_page(self.current_page + 1)
                else:
                    if abs(delta_y) > (self.min_swipe_distance):
                        if delta_y > 0:
                            self.open_lock_screen()

            # 重置滑动状态
            self.is_swiping = False
        except Exception as e:
            debug_print("on_gesture_release", e)

    def update_page_indicator(self):
        """更新页面指示器"""
        try:
            # 清理现有指示器
            self.page_indicator.clean()

            # 使用对象池来复用指示器对象
            indicators = []
            for i in range(1, self.page_count + 1):
                if len(indicators) < i:
                    indicator = lv.obj(self.page_indicator)
                    indicator.set_size(13, 13)
                    indicator.set_style_radius(10, 0)  # 圆形指示器
                    indicators.append(indicator)
                else:
                    indicator = indicators[i - 1]

                if i == self.current_page:
                    indicator.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)  # 当前页白色
                    indicator.set_style_bg_opa(255, 0)
                else:
                    indicator.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)  # 其他页也是白色，但透明度不同
                    indicator.set_style_bg_opa(120, 0)
        except Exception as e:
            debug_print("update_page_indicator", e)

    def scan_apps(self):
        """扫描apps文件夹，使用exec动态加载所有应用程序"""
        self.show_loading("Scaning apps ...")
        try:
            # 直接获取apps目录下的内容
            app_dirs = []
            try:
                app_list = os.listdir("/sdcard/apps")

                for item in app_list:
                    # 检查是否是目录
                    try:
                        os.listdir(f"/sdcard/apps/{item}")
                        if not item.startswith("__"):
                            app_dirs.append(item)
                    except Exception as e:
                        print(f"item:{item}: ", e)

            except Exception as e:
                debug_print("scan_app_dirs", e)

            # 读取应用排序配置
            app_order = {}
            try:
                with open("/sdcard/configs/app_order.json", 'r') as f:
                    import json
                    app_order = json.load(f)
            except Exception as e:
                debug_print("load_app_order", e)

            # 准备排序的应用信息
            ordered_apps = []
            for app_dir in app_dirs:
                # 从配置获取顺序，没有配置的默认为100
                order = app_order.get(app_dir, 100)
                ordered_apps.append({"dir": app_dir, "order": order})

            # 先按order排序，相同order的按名称排序
            ordered_apps.sort(key=lambda x: (x['order'], x['dir']))

            apps_number = len(ordered_apps)
            i = 0

            for app_info in ordered_apps:
                app_dir = app_info['dir']
                try:
                    i+=1
                    self.show_loading(f"Loading： __ {app_dir}  [{i}/{apps_number}]")
                    print(f"Loading: {app_dir}  [{i}/{apps_number}]")
                    # 使用exec进行动态导入
                    import_cmd = f"from apps.{app_dir}.app import App as CurrentApp"
                    exec(import_cmd, globals())

                    # 注册应用
                    app_instance = CurrentApp(self)
                    self.register_app(app_instance)
                except Exception as e:
                    print(e)

            # 计算页数
            total_apps = len(self.apps)
            self.page_count = max(1, (total_apps + self.apps_per_page - 1) // self.apps_per_page)

            # 为Dock栏选择应用
            if len(self.apps) > 0:
                dock_app_names = [self.text_config.get_section("System")["Settings"],self.text_config.get_section("System")["AI_face"], self.text_config.get_section("System")["HardwareTest"]]

                # 清空dock_apps列表
                self.dock_apps = []

                # 根据名称查找并添加应用到dock_apps
                for app_name in dock_app_names:
                    if app_name in self.apps:
                        self.dock_apps.append(self.apps[app_name])
                for app in self.dock_apps:
                    self.create_dock_icon(app)

            # 配置Dock栏应用后，动态调整Dock大小
            if len(self.dock_apps) > 0:
                # 计算所需的Dock宽度
                dock_icon_size = 60  # Dock图标大小
                dock_padding = 20    # Dock内边距（每一边）
                dock_spacing = 15    # 图标间距（来自pad_column）

                # 计算所需总宽度 = 所有图标宽度 + 所有间距 + 两侧内边距
                dock_width = (len(self.dock_apps) * dock_icon_size) + ((len(self.dock_apps) - 1) * dock_spacing) + (dock_padding * 2)

                # 设置Dock宽度并居中
                self.dock.set_width(dock_width)
                self.dock.set_pos((self.home_screen_width - dock_width) // 2, DISPLAY_HEIGHT - 100)

        except Exception as e:
            debug_print("scan_apps", e)

    def register_app(self, app):
        """注册应用到应用管理器"""
        try:
            # 确保应用有唯一的名称
            if app.name in self.apps:
                app.name = f"{app.name}_{len(self.apps)}"

            self.apps[app.name] = app
            self.app_index[app.name] = len(self.apps) - 1

            # 在主屏幕添加应用图标
            self.create_app_icon(app)
        except Exception as e:
            debug_print("register_app", e)

    def create_app_icon(self, app):
        """创建应用图标 - 带动画效果"""
        try:
            # 确定图标所在页面和位置
            app_index = self.app_index[app.name]

            app_page = (app_index) // self.apps_per_page + 1

            if app_page != self.current_page:
                return

            # 计算图标在当前页面的索引
            page_index = app_index % self.apps_per_page

            # 计算行和列位置
            row = page_index // self.icons_per_row
            col = page_index % self.icons_per_row

            # 计算图标位置
            icon_x = self.grid_start_x + col * (self.icon_size + self.icon_spacing_x)
            icon_y = self.grid_start_y + row * (self.icon_size + self.icon_spacing_y)

            # 创建图标 - 直接放在应用容器中
            icon = lv.btn(self.app_container)
            icon.set_size(0, 0)  # 初始大小设为0用于动画
            icon.set_pos(icon_x + self.icon_size // 2, icon_y + self.icon_size // 2)  # 从中心点开始
            icon.set_style_radius(18, 0)  # YAHBOOM K230 STYLE圆角矩形图标
            icon.set_style_opa(0, 0)  # 初始透明度为0用于淡入效果

            # 设置图标颜色 - 使用渐变色
            if hasattr(app, 'icon'):
                icon.set_style_bg_opa(0, 0)  # 背景完全透明
                icon.set_style_bg_color(lv.color_hex(0xeeeeee), 0)
                icon.set_style_bg_img_src(app.icon, 0)
            elif hasattr(app, 'color'):
                base_color = app.color
                # 创建一个轻微的渐变效果
                icon.set_style_bg_color(base_color, 0)
                # 计算一个稍微亮一点的颜色用于渐变
                r = ((base_color.ch.red * 1.2) if (base_color.ch.red * 1.2) < 255 else 255)
                g = ((base_color.ch.green * 1.2) if (base_color.ch.green * 1.2) < 255 else 255)
                b = ((base_color.ch.blue * 1.2) if (base_color.ch.blue * 1.2) < 255 else 255)
                lighter_color = lv.color_make(int(r), int(g), int(b))
                icon.set_style_bg_grad_color(lighter_color, 0)
                icon.set_style_bg_grad_dir(lv.GRAD_DIR.VER, 0)
            else:
                # 一些常见的YAHBOOM K230 STYLE应用颜色
                ios_colors = [
                    (0x5AC8FA, 0x2196F3),  # 蓝色
                    (0x4CD964, 0x43A047),  # 绿色
                    (0xFF9500, 0xFB8C00),  # 橙色
                    (0xFF3B30, 0xE53935),  # 红色
                    (0x5856D6, 0x3F51B5),  # 紫色
                ]
                # 使用应用索引来选择颜色
                color_index = app_index % len(ios_colors)
                icon.set_style_bg_color(lv.color_hex(ios_colors[color_index][0]), 0)
                icon.set_style_bg_grad_color(lv.color_hex(ios_colors[color_index][1]), 0)
                icon.set_style_bg_grad_dir(lv.GRAD_DIR.VER, 0)

            # 无边框
            icon.set_style_shadow_width(0, 0)
            icon.set_style_shadow_ofs_y(0, 0)

            # 添加点击事件
            icon.add_event(lambda e: self.launch_app(app.name), lv.EVENT.CLICKED, None)

            app.icon_btn = icon

            # 创建标签但初始设为透明
            label = lv.label(self.app_container)
            label.set_text(app.name)
            label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            label.set_style_text_font(self.font_16, 0)

            # 设置标签宽度为图标宽度
            label.set_width(self.icon_size)

            # 设置文本居中对齐
            label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

            # 计算标签位置 - 确保标签中心和图标中心在同一垂直线上
            label.set_pos(icon_x, icon_y + self.icon_size + 7)

            # 初始透明
            label.set_style_opa(0, 0)

            # 计算动画延迟，根据图标位置稍微错开动画时间，创造波浪效果
            delay_ms = 0  # 减少动画总时间以提高响应性

            # 1. 图标大小动画（从0到最终大小）
            size_anim = lv.anim_t()
            size_anim.init()
            size_anim.set_var(icon)
            size_anim.set_time(0)  # 减少动画时间
            # size_anim.set_time(20)  # 减少动画时间
            size_anim.set_delay(0)
            # size_anim.set_delay(delay_ms)
            size_anim.set_values(0, self.icon_size)
            size_anim.set_path_cb(lv.anim_t.path_overshoot)

            # 自定义动画设置回调函数
            def set_size_cb(obj, size):
                obj.set_size(size, size)
                # 让图标保持居中
                obj.set_pos(icon_x + (self.icon_size - size) // 2, icon_y + (self.icon_size - size) // 2)

            size_anim.set_custom_exec_cb(lambda a, val: set_size_cb(icon, val))
            size_anim.start()

            # 2. 图标透明度动画（淡入）
            opa_anim = lv.anim_t()
            opa_anim.init()
            opa_anim.set_var(icon)
            opa_anim.set_values(0, 255)
            opa_anim.set_time(0)  # 减少动画时间
            opa_anim.set_delay(delay_ms)
            opa_anim.set_path_cb(lv.anim_t.path_ease_out)
            opa_anim.set_custom_exec_cb(lambda a, val: icon.set_style_opa(val, 0))
            opa_anim.start()

            # 3. 标签透明度动画（稍微延迟后淡入）
            label_anim = lv.anim_t()
            label_anim.init()
            label_anim.set_var(label)
            label_anim.set_values(0, 255)
            label_anim.set_time(0)  # 减少动画时间
            label_anim.set_delay(delay_ms)
            label_anim.set_path_cb(lv.anim_t.path_ease_out)
            label_anim.set_custom_exec_cb(lambda a, val: label.set_style_opa(val, 0))
            label_anim.start()

        except lv.LvReferenceError as e:
            debug_print("create_app_icon_ref_error", e)
            # 清理相关资源
            if hasattr(app, 'icon_btn'):
                try:
                    app.icon_btn.delete()
                except Exception as e:
                    debug_print("delete_icon_btn", e)
            return
        except Exception as e:
            debug_print("create_app_icon", e)

    def create_dock_icon(self, app):
        """创建YAHBOOM K230 STYLE的Dock栏图标"""
        try:
            # 创建YAHBOOM K230 STYLEDock图标
            icon = lv.btn(self.dock)
            icon.set_size(60, 60)
            icon.set_style_radius(15, 0)  # YAHBOOM K230 STYLE圆角矩形图标

            # 设置图标颜色 - 使用渐变色
            if hasattr(app, 'dock_icon'):
                print("use dock_icon", app.name)
                icon.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
                icon.set_style_bg_opa(0, 0)  # 背景完全透明
                icon.set_style_bg_img_src(app.dock_icon, 0)
            elif hasattr(app, 'icon'):
                icon.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
                icon.set_style_bg_opa(0, 0)  # 背景完全透明
                icon.set_style_bg_img_src(app.icon, 0)
            elif hasattr(app, 'color'):
                base_color = app.color
                # 创建一个轻微的渐变效果
                icon.set_style_bg_color(base_color, 0)
                # 计算一个稍微亮一点的颜色用于渐变
                r = ((base_color.ch.red * 1.2) if (base_color.ch.red * 1.2) < 255 else 255)
                g = ((base_color.ch.green * 1.2) if (base_color.ch.green * 1.2) < 255 else 255)
                b = ((base_color.ch.blue * 1.2) if (base_color.ch.blue * 1.2) < 255 else 255)
                lighter_color = lv.color_make(int(r), int(g), int(b))
                icon.set_style_bg_grad_color(lighter_color, 0)
                icon.set_style_bg_grad_dir(lv.GRAD_DIR.VER, 0)
            else:
                app_index = self.app_index.get(app.name, 0)
                # 一些常见的YAHBOOM K230 STYLE应用颜色
                ios_colors = [
                    (0x5AC8FA, 0x2196F3),  # 蓝色
                    (0x4CD964, 0x43A047),  # 绿色
                    (0xFF9500, 0xFB8C00),  # 橙色
                    (0xFF3B30, 0xE53935),  # 红色
                    (0x5856D6, 0x3F51B5),  # 紫色
                ]
                # 使用应用索引来选择颜色
                color_index = app_index % len(ios_colors)
                icon.set_style_bg_color(lv.color_hex(ios_colors[color_index][0]), 0)
                icon.set_style_bg_grad_color(lv.color_hex(ios_colors[color_index][1]), 0)
                icon.set_style_bg_grad_dir(lv.GRAD_DIR.VER, 0)

            # 添加YAHBOOM K230 STYLE图标细节
            icon.set_style_shadow_width(3, 0)  # 轻微阴影
            icon.set_style_shadow_opa(80, 0)  # 阴影透明度
            icon.set_style_shadow_ofs_y(2, 0)  # 阴影Y偏移
            icon.set_style_shadow_color(lv.color_hex(0x000000), 0)  # 阴影颜色

            icon.add_event(lambda e: self.launch_dock_app(app.name), lv.EVENT.CLICKED, None)
        except Exception as e:
            debug_print("create_dock_icon", e)

    def release_change_page_lock(self, timer=None):
        self.change_page_lock = False

    def change_page(self, page_number):
        """切换到指定页面 - 移除当前页面的所有图标并创建新页面图标"""
        try:
            if self.change_page_lock:
                return

            self.change_page_lock = True
            self.page_timer.init(mode=Timer.ONE_SHOT, period=100, callback=self.release_change_page_lock)

            if 0 < page_number <= self.page_count and page_number != self.current_page:
                old_page = self.current_page
                self.current_page = page_number

                # 移除旧页面的所有图标和标签
                # 直接清空应用容器
                self.app_container.clean()
                self.home_screen.invalidate()
                # 强制刷新一次以确保旧内容被清除
                lv.refr_now(None)

                # 创建新页面的图标
                app_keys = list(self.apps.keys())

                # 重新创建当前页面的所有应用图标
                for app_name in self.apps:
                    app_index = self.app_index[app_name]
                    app_page = (app_index) // self.apps_per_page + 1
                    if app_page == page_number:
                        self.create_app_icon(self.apps[app_name])
                # 更新页面指示器
                self.update_page_indicator()
        except Exception as e:
            debug_print("change_page", e)
            self.change_page_lock = False

    def launch_dock_app(self, app_name):
        """启动特定应用 - 添加启动动画"""
        try:
            if app_name in self.apps:
                self.current_app = self.apps[app_name]
                self.current_app.launch()
        except Exception as e:
            debug_print("launch_dock_app", e)

    def launch_app(self, app_name):
        """启动特定应用 - 添加启动动画"""
        try:
            if app_name in self.apps:
                self.current_app = self.apps[app_name]
                self.current_app.on_icon_clicked()
        except Exception as e:
            debug_print("launch_app", e)

    def go_home(self):
        """返回主屏幕 - 添加返回动画"""
        try:
            if self.current_app:
                self.current_app.deinitialize()
                self.current_app = None
            lv.scr_load(self.home_screen)
            self.loading_label.set_text(" ")

            # 使用定时器延迟更新状态栏UI
            lv.timer_create(lambda t: self.update_status_bar(), 1, None)  # 1ms后更新状态栏
        except Exception as e:
            debug_print("go_home", e)

    def update_status_bar(self):
        """更新状态栏UI"""
        try:
            m = gc.sys_heap()
            self.status_label.set_text(f"CPU: {100-os.cpu_usage()}%   |   Mem: {int((m[1]/m[0] * 100))}%")
            # self.signal_label.set_text(lv.SYMBOL.WIFI if ybnet.sta.isconnected() else "")
        except Exception as e:
            debug_print("update_status_bar", e)
    def show_loading(self, extra_text=None):
        try:
            img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.ARGB8888)
            img.clear()
            # 设置屏幕宽度变量
            screen_width = 640

            # 设置文字粗细和颜色
            thickness = 5
            text_color = (0, 191, 255)

            # 计算文本的总宽度
            text_width = 320
            # 计算文本起始位置，使其居中
            start_x = (screen_width - text_width) // 2

            # Y字母
            img.draw_line(start_x, 220, start_x + 20, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 20, 240, start_x + 40, 220, color=text_color, thickness=thickness)
            img.draw_line(start_x + 20, 240, start_x + 20, 260, color=text_color, thickness=thickness)

            # a字母
            img.draw_line(start_x + 45, 240, start_x + 65, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 65, 240, start_x + 65, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 70, 260, start_x + 45, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 45, 260, start_x + 45, 240, color=text_color, thickness=thickness)
    #        img.draw_line(start_x + 50, 260, start_x + 50, 240, color=text_color, thickness=thickness)

            # h字母
            img.draw_line(start_x + 80, 220, start_x + 80, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 80, 240, start_x + 100, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 100, 240, start_x + 100, 260, color=text_color, thickness=thickness)

            # b字母
            img.draw_line(start_x + 110, 220, start_x + 110, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 110, 240, start_x + 130, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 130, 240, start_x + 130, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 130, 260, start_x + 110, 260, color=text_color, thickness=thickness)

            # o字母
            img.draw_line(start_x + 140, 240, start_x + 160, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 160, 240, start_x + 160, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 160, 260, start_x + 140, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 140, 260, start_x + 140, 240, color=text_color, thickness=thickness)

            # o字母
            img.draw_line(start_x + 170, 240, start_x + 190, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 190, 240, start_x + 190, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 190, 260, start_x + 170, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 170, 260, start_x + 170, 240, color=text_color, thickness=thickness)

            # m字母
            img.draw_line(start_x + 200, 240, start_x + 200, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 200, 240, start_x + 210, 250, color=text_color, thickness=thickness)
            img.draw_line(start_x + 210, 250, start_x + 220, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 220, 240, start_x + 220, 260, color=text_color, thickness=thickness)

            # K字母
            img.draw_line(start_x + 240, 220, start_x + 240, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 240, 240, start_x + 260, 220, color=text_color, thickness=thickness)
            img.draw_line(start_x + 240, 240, start_x + 260, 260, color=text_color, thickness=thickness)

            # 2字母
            img.draw_line(start_x + 270, 220, start_x + 290, 220, color=text_color, thickness=thickness)
            img.draw_line(start_x + 290, 220, start_x + 290, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 290, 240, start_x + 270, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 270, 240, start_x + 270, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 270, 260, start_x + 290, 260, color=text_color, thickness=thickness)

            # 3字母
            img.draw_line(start_x + 300, 220, start_x + 320, 220, color=text_color, thickness=thickness)
            img.draw_line(start_x + 320, 220, start_x + 320, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 320, 240, start_x + 300, 240, color=text_color, thickness=thickness)
            img.draw_line(start_x + 320, 240, start_x + 320, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 320, 260, start_x + 300, 260, color=text_color, thickness=thickness)

            # 0字母
            img.draw_line(start_x + 330, 220, start_x + 350, 220, color=text_color, thickness=thickness)
            img.draw_line(start_x + 350, 220, start_x + 350, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 350, 260, start_x + 330, 260, color=text_color, thickness=thickness)
            img.draw_line(start_x + 330, 260, start_x + 330, 220, color=text_color, thickness=thickness)

            # 添加文字
            if extra_text:
                img.draw_string_advanced(start_x+10, 280, 15, extra_text)

            Display.show_image(img, layer=Display.LAYER_OSD3)
        except Exception as e:
            debug_print("show_loading", e)

def show_loading(extra_text=None):
    try:
        img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.ARGB8888)
        img.clear()
        # 设置屏幕宽度变量
        screen_width = 640

        # 设置文字粗细和颜色
        thickness = 5
        text_color = (0, 191, 255)

        # 计算文本的总宽度
        text_width = 320
        # 计算文本起始位置，使其居中
        start_x = (screen_width - text_width) // 2

        # Y字母
        img.draw_line(start_x, 220, start_x + 20, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 20, 240, start_x + 40, 220, color=text_color, thickness=thickness)
        img.draw_line(start_x + 20, 240, start_x + 20, 260, color=text_color, thickness=thickness)

        # a字母
        img.draw_line(start_x + 45, 240, start_x + 65, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 65, 240, start_x + 65, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 70, 260, start_x + 45, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 45, 260, start_x + 45, 240, color=text_color, thickness=thickness)
#        img.draw_line(start_x + 50, 260, start_x + 50, 240, color=text_color, thickness=thickness)

        # h字母
        img.draw_line(start_x + 80, 220, start_x + 80, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 80, 240, start_x + 100, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 100, 240, start_x + 100, 260, color=text_color, thickness=thickness)

        # b字母
        img.draw_line(start_x + 110, 220, start_x + 110, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 110, 240, start_x + 130, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 130, 240, start_x + 130, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 130, 260, start_x + 110, 260, color=text_color, thickness=thickness)

        # o字母
        img.draw_line(start_x + 140, 240, start_x + 160, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 160, 240, start_x + 160, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 160, 260, start_x + 140, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 140, 260, start_x + 140, 240, color=text_color, thickness=thickness)

        # o字母
        img.draw_line(start_x + 170, 240, start_x + 190, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 190, 240, start_x + 190, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 190, 260, start_x + 170, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 170, 260, start_x + 170, 240, color=text_color, thickness=thickness)

        # m字母
        img.draw_line(start_x + 200, 240, start_x + 200, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 200, 240, start_x + 210, 250, color=text_color, thickness=thickness)
        img.draw_line(start_x + 210, 250, start_x + 220, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 220, 240, start_x + 220, 260, color=text_color, thickness=thickness)

        # K字母
        img.draw_line(start_x + 240, 220, start_x + 240, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 240, 240, start_x + 260, 220, color=text_color, thickness=thickness)
        img.draw_line(start_x + 240, 240, start_x + 260, 260, color=text_color, thickness=thickness)

        # 2字母
        img.draw_line(start_x + 270, 220, start_x + 290, 220, color=text_color, thickness=thickness)
        img.draw_line(start_x + 290, 220, start_x + 290, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 290, 240, start_x + 270, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 270, 240, start_x + 270, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 270, 260, start_x + 290, 260, color=text_color, thickness=thickness)

        # 3字母
        img.draw_line(start_x + 300, 220, start_x + 320, 220, color=text_color, thickness=thickness)
        img.draw_line(start_x + 320, 220, start_x + 320, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 320, 240, start_x + 300, 240, color=text_color, thickness=thickness)
        img.draw_line(start_x + 320, 240, start_x + 320, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 320, 260, start_x + 300, 260, color=text_color, thickness=thickness)

        # 0字母
        img.draw_line(start_x + 330, 220, start_x + 350, 220, color=text_color, thickness=thickness)
        img.draw_line(start_x + 350, 220, start_x + 350, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 350, 260, start_x + 330, 260, color=text_color, thickness=thickness)
        img.draw_line(start_x + 330, 260, start_x + 330, 220, color=text_color, thickness=thickness)

        # 添加文字
        if extra_text:
            img.draw_string_advanced(start_x+10, 280, 15, extra_text)

        Display.show_image(img, layer=Display.LAYER_OSD3)
    except Exception as e:
        debug_print("show_loading_global", e)

def clear_loading():
    try:
        img2 = image.Image(640, 480, image.RGB565, alpha=0)
        img2.clear()
        Display.show_image(img2, layer=Display.LAYER_OSD3)
    except Exception as e:
        debug_print("clear_loading", e)

def main():
    global config, pl, recorder
    try:
        # 读取配置文件
        config = Configuration.load_from_file('/sdcard/configs/sys_config.json')
        lang_path = config.get_section("language").get("text_path", "")
        text_config = Configuration.load_from_file(lang_path)

        # 初始化显示
        display_init()
        show_loading("[>>>--------------------------] 10%")
        lvgl_init()
        show_loading("[========>--------------------]  30%")
        if pl is not None:
            app_manager = AppManager(config, pl, None, text_config)
            app_manager.initialize()
            show_loading("[==============================] 100%")
            time.sleep_ms(500)
            clear_loading()
        else:
            return

        # 强制刷新一次
        lv.refr_now(None)

        wlan_init()
        # 主循环
        refresh_counter = 0
        gc_counter = 0

        while True:
            refresh_time = lv.task_handler()
            time.sleep_ms(max(refresh_time, 10))  # 确保至少有10ms的间隔

            # 优化垃圾回收
            gc_counter += 1
            if gc_counter >= 100000:
                gc.collect()
                gc_counter = 0

    except Exception as e:
        debug_print("main", e)

def start():
    main()

if __name__ == "__main__":
    start()
