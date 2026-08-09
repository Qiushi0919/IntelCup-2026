import lvgl as lv
from ybMain.base_app import BaseApp
import os

class App(BaseApp):
    def __init__(self, app_manager):
        print("DEBUG: Initializing Gallery App")
        try:
            with open("/sdcard/apps/gallery/icon.png", 'rb') as f:
                print("DEBUG: Loading icon image")
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            print(f"DEBUG: Failed to load icon: {e}")
            img_bg = None
            
        self.app_manager = app_manager        
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        super().__init__(app_manager, self.text_config.get_section("System")["Gallery"], icon=img_bg)
        self.pl = app_manager.pl
        self.texts = self.text_config.get_section("Gallery")
        
        self.image_list = []
        self.current_index = 0
        self.img_obj = None
        print("DEBUG: App initialization completed")
        
    def scan_images(self):
        """扫描/data/目录下的所有图片文件"""
        print("DEBUG: Starting image scan")
        # image_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
        image_extensions = ('.png', '.bmp')
        
        def scan_directory(directory):
            try:
                print(f"DEBUG: Scanning directory: {directory}")
                for item in os.listdir(directory):
                    # 使用字符串拼接替代os.path.join
                    full_path = directory + '/' + item if directory.endswith('/') else directory + '/' + item
                    try:
                        # 尝试列出该项目的内容来判断是否为目录
                        os.listdir(full_path)
                        scan_directory(full_path)
                    except:
                        # 不是目录，检查是否为图片文件
                        if any(item.lower().endswith(ext) for ext in image_extensions):
                            print(f"DEBUG: Found image: {full_path}")
                            self.image_list.append(full_path)
            except Exception as e:
                print(f"DEBUG: Error scanning directory {directory}: {e}")
                
        scan_directory('/data')
        print(f"DEBUG: Image scan completed, found {len(self.image_list)} images")
        
    def load_image(self, path):
        """加载图片文件"""
        print(f"DEBUG: Loading image from: {path}")
        try:
            with open(path, 'rb') as f:
                img_data = f.read()
                print(f"DEBUG: Successfully loaded image, size: {len(img_data)} bytes")
                return lv.img_dsc_t({
                    'data_size': len(img_data),
                    'data': img_data
                })
        except Exception as e:
            print(f"DEBUG: Failed to load image: {e}")
            return None
            
    def handle_gesture(self, evt):
        """处理手势事件"""
        print("DEBUG: Handling gesture event")
        try:
            indev = lv.indev_get_act()
            if indev is not None:
                point = lv.point_t()
                indev.get_vect(point)
                
                # 获取滑动距离
                delta_x = point.x
                print(f"DEBUG: Gesture delta_x: {delta_x}")
                
                # 设定最小滑动距离
                min_swipe_distance = 3
                
                if abs(delta_x) > min_swipe_distance:
                    if delta_x > 0 and self.current_index > 0:
                        print("DEBUG: Swiping right - previous image")
                        self.current_index -= 1
                        self.show_current_image()
                    elif delta_x < 0 and self.current_index < len(self.image_list) - 1:
                        print("DEBUG: Swiping left - next image")
                        self.current_index += 1
                        self.show_current_image()
        except Exception as e:
            print(f"DEBUG: Error in gesture handling: {e}")

    def show_current_image(self):
        """显示当前索引的图片"""
        print("DEBUG: Attempting to show current image")
        if not self.image_list:
            print("DEBUG: No images in list")
            return
            
        if self.img_obj:
            print("DEBUG: Deleting previous image object")
            self.img_obj.delete()
            
        path = self.image_list[self.current_index]
        print(f"DEBUG: Loading image at index {self.current_index}: {path}")
        
        try:
            with open(path, 'rb') as f:
                img_data = f.read()
                print(f"DEBUG: Successfully loaded image, size: {len(img_data)} bytes")
                img_dsc = lv.img_dsc_t({
                    'data_size': len(img_data),
                    'data': img_data
                })
                
                self.img_obj = lv.img(self.content)
                self.img_obj.set_src(img_dsc)
                self.img_obj.center()
                
                # 获取文件名
                filename = path.split('/')[-1]
                # 更新标题显示文件名和索引信息
                total = len(self.image_list)
                self.title_label.set_text(f"{filename}   [{self.current_index + 1}/{total}]")
                print("DEBUG: Image display completed")
        except Exception as e:
            print(f"DEBUG: Error loading/displaying image: {e}")

    def initialize(self):
        """初始化相册界面"""
        print("DEBUG: Starting interface initialization")
        
        # 创建主体内容区
        print("DEBUG: Creating content area")
        self.content = lv.obj(self.screen)
        self.content.set_size(lv.pct(100), 420)
        self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.content.clear_flag(lv.obj.FLAG.SCROLLABLE)
        self.content.set_style_border_width(0,0)
        self.content.set_style_radius(0,0)
        
        
        # 创建标题标签
        print("DEBUG: Creating title label")
        
        # 扫描图片
        self.scan_images()
        
        if self.image_list:
            # 显示第一张图片
            self.show_current_image()
            
            # 添加事件处理
            self.content.add_event(self.handle_gesture, lv.EVENT.RELEASED, None)
            
        else:
            no_image_label = lv.label(self.content)
            no_image_label.set_text(self.text_config.get_section("Gallery")["NoImage"])
            no_image_label.set_style_text_font(lv.font_yb_cn_16, 0)
            no_image_label.center()    
    
    def deinitialize(self):
        """清理资源"""
        print("DEBUG: Starting cleanup")
        self.image_list = []
        if self.img_obj:
            self.img_obj.delete()
            self.img_obj = None
        print("DEBUG: Cleanup completed")