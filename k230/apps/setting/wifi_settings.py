from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
from ybUtils.YbNetwork import YbNetwork
from ybUtils.Configuration import *

class WiFiSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        try:
            super().__init__(app, detail_panel, config)
            self.ybnet = YbNetwork()
            self.text_config = text_config
            self.wifi_list_container = None
            self.wifi_networks = []
            self.scanning = False
            self.connecting_ssid = None
            self.wifi_operation_timer = None
            self.connection_state = "idle"
            self.pending_operation = None
            self.switch_disabled = False
            self.wifi_switch_obj = None  # 存储开关的全局引用
        except Exception as e:
            pass

    def display(self):
        """显示WiFi设置页面"""
        try:
            self.detail_panel.clean()
            self.detail_items = []
            
            title = self._create_title(self.text_config.get_section("Settings")["WLAN"]["title"])
            pass
            self._create_divider()
            
            wifi_item = {"name": self.text_config.get_section("Settings")["WLAN"]["Status"], 
                        "type": "switch", 
                        "config_section": "WLAN", 
                        "config_key": "status", 
                        "value": self.config.get_section("WLAN")["status"], 
                        "callback": self._on_wifi_switch}
            container = lv.obj(self.detail_panel)
            container.set_size(lv.pct(100), 70)
            container.set_style_pad_all(15, 0)
            container.set_style_radius(10, 0)
            container.set_style_border_width(1, 0)
            container.set_style_border_color(lv.color_hex(0x21a366), 0)
            container.set_style_bg_color(lv.color_hex(0xe2efda), 0)
            container.set_style_shadow_width(10, 0)
            container.set_style_shadow_color(lv.color_hex(0x888888), 0)
            container.set_style_shadow_opa(10, 0)
            container.set_style_margin_bottom(15, 0)
            container.set_flex_flow(lv.FLEX_FLOW.ROW)
            container.set_flex_align(lv.FLEX_ALIGN.SPACE_BETWEEN, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
            container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
            container.set_scroll_dir(lv.DIR.NONE)
            label = lv.label(container)
            label.set_text(self.text_config.get_section("Settings")["WLAN"]["cant_connect_info"])
            label.set_style_text_font(self.app.app_manager.font_16, 0)
            label.set_style_text_color(lv.color_hex(0x333333), 0)
            label.set_width(lv.pct(98))  # 设置固定宽度
            label.set_long_mode(lv.label.LONG.SCROLL_CIRCULAR)  # 循环滚动
            self.create_item(wifi_item)
            self.wifi_list_container = lv.obj(self.detail_panel)
            self.wifi_list_container.set_size(lv.pct(100), lv.SIZE_CONTENT)
            self.wifi_list_container.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
            self.wifi_list_container.set_style_border_width(1, 0)
            self.wifi_list_container.set_style_border_color(lv.color_hex(0xDDDDDD), 0)
            self.wifi_list_container.set_style_radius(10, 0)
            self.wifi_list_container.set_style_pad_all(0, 0)
            self.wifi_list_container.set_flex_flow(lv.FLEX_FLOW.COLUMN)
            
            if self.config.get_section("WLAN")["status"] == 1:
                self._start_wifi_scan()
                self.wifi_list_container.clear_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.wifi_list_container.add_flag(lv.obj.FLAG.HIDDEN)
        except Exception as e:
            pass

    def _create_title(self, text):
        """创建标题"""
        try:
            title = lv.label(self.detail_panel)
            title.set_text(text)
            title.set_width(lv.pct(100))
            title.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
            return title
        except Exception as e:
            pass
            return None

    def _create_divider(self):
        """创建分隔线"""
        try:
            line = lv.line(self.detail_panel)
            points = [{"x": 0, "y": 0}, {"x": self.detail_panel.get_width() - 20, "y": 0}]
            line.set_points(points, 2)
            line.set_style_line_width(1, 0)
            line.set_style_line_color(lv.color_hex(0xdddddd), 0)
            line.set_style_margin_top(5, 0)
            line.set_style_margin_bottom(15, 0)
        except Exception as e:
            pass

    def _on_wifi_switch(self, event):
        """WiFi开关回调"""
        try:
            if self.switch_disabled:
                return
                
            sw = lv.switch.__cast__(event.get_target())
            state = sw.get_state() & lv.STATE.CHECKED
            
            # 保存开关引用
            self.wifi_switch_obj = sw
            
            # 设置开关为禁用状态
            self.switch_disabled = True
            sw.add_state(lv.STATE.DISABLED)

            # 处理开关状态
            if state:
                self.wifi_list_container.clear_flag(lv.obj.FLAG.HIDDEN)
                self._start_wifi_scan()
                saved_ssid = self.config.get_section("WLAN").get("SSID", "")
                if saved_ssid:
                    self._schedule_wifi_connect(saved_ssid)
            else:
                self._schedule_wifi_disconnect()
            
            # 使用普通函数作为回调而不传递任何参数
            lv.timer_create(self._enable_switch_cb, 3000, None)
            
        except Exception as e:
            print(f"WiFi switch error: {e}")

    def _enable_switch_cb(self, timer):
        """定时器回调函数，不尝试从定时器获取任何东西"""
        try:
            # 使用全局保存的引用
            if self.wifi_switch_obj:
                self.wifi_switch_obj.clear_state(lv.STATE.DISABLED)
            self.switch_disabled = False
            
            # 不确定_del方法是否存在，使用try块来保护
            try:
                timer._del()
            except:
                pass
        except Exception as e:
            print(f"Enable switch timer error: {e}")
        
    def _schedule_wifi_connect(self, ssid):
        """安排WiFi连接任务"""
        print("Scheduling WiFi connect...")
        try:
            if self.wifi_operation_timer:
                self.wifi_operation_timer._del()
                self.wifi_operation_timer = None
            
            self.connection_state = "connecting"
            self.connecting_ssid = ssid
            self._update_wifi_list()
            
            password = self.config.get_section("WLAN").get("PASSWORD", "")
            
            self.wifi_operation_timer = lv.timer_create(
                lambda timer: self._process_wifi_connect(ssid, password), 100, None
            )
        except Exception as e:
            pass

    def _process_wifi_connect(self, ssid, password):
        """处理WiFi连接过程"""
        print("_process_wifi_connect...")
        try:
            print("start try ..")
            if self.ybnet.check_wifi_exists(self.ybnet.SCAN_WIFI(), ssid):
                success = self.ybnet.CONNECT_WIFI(ssid, password)
                print(success)
                
                self.connection_state = "idle"
                print(success, ssid, password)
                if success:
                    self.connecting_ssid = ssid
                    self.connection_state = "connected"
                    self.config.set_value("WLAN", "SSID", self.connecting_ssid)
                    self.app.app_manager.logic_wifi_status = 1
                    self.config.save_to_file('/sdcard/configs/sys_config.json')
                    print("logic_wifi_status", self.app.app_manager.logic_wifi_status)
                else:
                    pass
                    self.connecting_ssid = None
                    self.connection_state = "idle"
                    self.app.app_manager.logic_wifi_status = 0
                    print("logic_wifi_status", self.app.app_manager.logic_wifi_status)
                    
                self._update_wifi_list()
            else:
                pass
                self.connecting_ssid = None
                self.connection_state = "idle"
                self._update_wifi_list()
        except Exception as e:
            print("error on connect wifi ", e)
        finally:
            try:
                if self.wifi_operation_timer:
                    self.wifi_operation_timer._del()
                    self.wifi_operation_timer = None
            except Exception as e:
                pass

    def _schedule_wifi_disconnect(self):
        """安排WiFi断开连接任务"""
        try:
            if self.wifi_operation_timer:
                self.wifi_operation_timer._del()
                self.wifi_operation_timer = None
            
            self.connection_state = "disconnecting"
            self.wifi_list_container.add_flag(lv.obj.FLAG.HIDDEN)
            
            self.wifi_operation_timer = lv.timer_create(
                self._process_wifi_disconnect, 100, None
            )
        except Exception as e:
            pass

    def _process_wifi_disconnect(self, timer):
        """处理WiFi断开连接过程"""
        try:
            self.app.app_manager.logic_wifi_status = 0
            success = self.ybnet.DISCONNECT_WIFI()
            self.connection_state = "idle"
            self.connecting_ssid = None
            pass
        except Exception as e:
            pass
        finally:
            try:
                if self.wifi_operation_timer:
                    self.wifi_operation_timer._del()
                    self.wifi_operation_timer = None
            except Exception as e:
                pass

    def _start_wifi_scan(self):
        """开始扫描WiFi"""
        try:
            if self.scanning:
                return
            self.scanning = True
            self.wifi_list_container.clean()
            scanning_label = lv.label(self.wifi_list_container)
            self.text_config.get_section("Settings")["WLAN"]["cant_connect_info"]
            scanning_label.set_text(f"{lv.SYMBOL.REFRESH} {self.text_config.get_section('Settings')['WLAN']['is_scanning']}")
            scanning_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            scanning_label.set_width(lv.pct(100))
            scanning_label.set_style_pad_all(15, 0)
            
            scan_timer = lv.timer_create(self._perform_wifi_scan, 1000, None)
            scan_timer.set_repeat_count(1)
        except Exception as e:
            pass

    def _perform_wifi_scan(self, timer):
        """执行WiFi扫描"""
        try:
            self.wifi_networks = self._scan_wifi_networks()
            self._update_wifi_list()
            self.scanning = False
        except Exception as e:
            pass
        finally:
            try:
                timer._del()
            except Exception as e:
                pass

    def _scan_wifi_networks(self):
        """扫描WiFi网络"""
        try:
            pass
            networks = []
            seen_ssids = set()
            raw_networks = self.ybnet.SCAN_WIFI()
            
            for wifi in raw_networks:
                try:
                    ssid = wifi.ssid.decode('utf-8')
                    if ssid in seen_ssids:
                        continue
                    seen_ssids.add(ssid)
                    networks.append({
                        "ssid": ssid,
                        "rssi": wifi.rssi if hasattr(wifi, 'rssi') else -50,
                        "security": wifi.security if hasattr(wifi, 'security') else True
                    })
                except Exception as e:
                    pass
                    continue
                    
            networks.sort(key=lambda x: x["rssi"], reverse=True)
            return networks
        except Exception as e:
            pass
            return []

    def _update_wifi_list(self):
        """更新WiFi列表显示"""
        try:
            self.wifi_list_container.clean()
            
            if not self.wifi_networks:
                no_networks_label = lv.label(self.wifi_list_container)
                no_networks_label.set_text(f"{self.text_config.get_section('Settings')['WLAN']['is_searching']}")
                no_networks_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
                no_networks_label.set_width(lv.pct(100))
                no_networks_label.set_style_pad_all(15, 0)
                return
                
            # current_ssid = self.config.get_section("WLAN").get("SSID", "")
            current_ssid = self.connecting_ssid
            
            wifi_info = self.ybnet.get_wifi_info()
            if wifi_info:
                current_ssid = wifi_info.ssid.decode('utf-8')
                self.connection_state = "connected"
            
            for i, network in enumerate(self.wifi_networks):
                try:
                    ssid = network["ssid"]
                    rssi = network["rssi"]
                    
                    item = lv.obj(self.wifi_list_container)
                    item.set_size(lv.pct(100), lv.SIZE_CONTENT)
                    item.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
                    item.set_style_bg_opa(255, 0)
                    item.set_style_border_width(0, 0)
                    item.set_style_pad_ver(12, 0)
                    item.set_style_pad_hor(15, 0)
                    
                    if i < len(self.wifi_networks) - 1:
                        item.set_style_border_width(1, lv.PART.MAIN | lv.STATE.DEFAULT)
                        item.set_style_border_side(lv.BORDER_SIDE.BOTTOM, lv.PART.MAIN | lv.STATE.DEFAULT)
                        item.set_style_border_color(lv.color_hex(0xEEEEEE), lv.PART.MAIN | lv.STATE.DEFAULT)
                    
                    item.add_event(lambda e, wifi=ssid: self._on_wifi_item_click(wifi), lv.EVENT.CLICKED, None)
                    
                    ssid_label = lv.label(item)
                    ssid_label.set_text(ssid)
                    ssid_label.set_long_mode(lv.label.LONG.DOT)
                    ssid_label.set_width(lv.pct(70))
                    
                    signal_icon = lv.label(item)
                    if rssi > -50:
                        signal_icon.set_text(lv.SYMBOL.WIFI)
                    elif rssi > -70:
                        signal_icon.set_text(lv.SYMBOL.WIFI)
                    else:
                        signal_icon.set_text(lv.SYMBOL.WIFI)
                    signal_icon.set_style_text_color(lv.color_hex(0x555555), 0)
                    signal_icon.align(lv.ALIGN.RIGHT_MID, -25, 0)
                    pass
                    pass
                    if ssid == current_ssid or ssid == self.connecting_ssid:
                        pass
                        if self.connection_state == "connecting" and ssid == self.connecting_ssid:
                            connecting_label = lv.label(item)
                            connecting_label.set_text(f"{self.text_config.get_section('Settings')['WLAN']['is_connecting']}")
                            connecting_label.set_style_text_color(lv.color_hex(0x888888), 0)
                            connecting_label.align(lv.ALIGN.RIGHT_MID, -50, 0)
                        elif ssid == current_ssid and self.connection_state == "connected":
                            check_icon = lv.label(item)
                            check_icon.set_text(lv.SYMBOL.OK)
                            check_icon.set_style_text_color(lv.color_hex(0x888888), 0)
                            check_icon.align(lv.ALIGN.RIGHT_MID, -50, 0)
                    
                    if network.get("security", True):
                        lock_icon = lv.label(item)
                        lock_icon.set_text(lv.SYMBOL.SETTINGS)
                        lock_icon.set_style_text_color(lv.color_hex(0x555555), 0)
                        lock_icon.align(lv.ALIGN.RIGHT_MID, 0, 0)
                except Exception as e:
                    pass
                    continue
        except Exception as e:
            pass

    def _on_wifi_item_click(self, ssid):
        """WiFi列表项点击回调"""
        try:
            print(f"WiFi item clicked: {ssid}")
            current_ssid = self.config.get_section("WLAN").get("SSID", "")
            if ssid == current_ssid and self.connection_state=="connected":
                wifi_info = self.ybnet.get_wifi_info()
                if wifi_info:
                    self.app.model_dialog.show(
                        title=wifi_info.ssid,
                        content=f"{self.text_config.get_section("Settings")["WLAN"]["IP"]}: {wifi_info.ip} \n {self.text_config.get_section("Settings")["WLAN"]["rssi"]}: {wifi_info.rssi}",
                        icon_symbol=lv.SYMBOL.WIFI,
                        btn_texts=[self.text_config.get_section("System")["Ok"]],
                        width=480,
                        height=300
                    )
                return
            else:
                self.app.dialog_helper.create_wifi_password_dialog(ssid, lambda password: self._connect_wifi(ssid, password))
        except Exception as e:
            pass

    def _connect_wifi(self, ssid, password, *args):
        """连接WiFi"""
        try:
            pass
            self._save_wifi_config(ssid, password)
            self._schedule_wifi_connect(ssid)
        except Exception as e:
            pass

    def _save_wifi_config(self, ssid, password):
        """保存WiFi配置"""
        try:
            pass
            self.config.set_value("WLAN", "SSID", ssid)
            self.config.set_value("WLAN", "PASSWORD", password)
            self.config.save_to_file('/sdcard/configs/sys_config.json')
            pass
        except Exception as e:
            pass