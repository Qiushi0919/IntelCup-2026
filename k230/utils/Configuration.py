class Configuration:
    def __init__(self, config_dict=None):
        # 默认配置
        self.config = {
            "WLAN": {
                "SSID": "SSID",
                "PASSWORD": "PASSWORD"
            },
            "AP": {
                "default_status": 1,
                "SSID": "YAHBOOM-K230",
                "PASSWORD": "12345678"
            },
            "display": {
                "brightness": 100,
                "LSwallpaper": "/sdcard/resources/LSwallpaper.jpg",
                "wallpaper": "/sdcard/resources/wallpaper.png"
            },
            "sound": {
                "volume": 100
            },
            "safety": {
                "password": "123456",
                "face_recognition": 1,
                "face_recognition_path": "/sdcard/data/face_recognition.bin",
                "kws": 0,
                "kws_path": "/sdcard/data/kws.model"
            },
            "date": {
                "async_time_by_wlan": 0,
                "time_set": "None"
            },
            "language": {
                "text_path": "/sdcard/configs/languages/zh_cn.json"
            }
        }
        
        # 如果提供了配置字典，则使用它覆盖默认配置
        if config_dict:
            self.update_config(config_dict)
    
    def update_config(self, config_dict):
        """更新配置"""
        def update_recursive(target, source):
            for key, value in source.items():
                if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                    update_recursive(target[key], value)
                else:
                    target[key] = value
        
        update_recursive(self.config, config_dict)
    
    def get_config(self):
        """获取整个配置"""
        return self.config
    
    def get_section(self, section):
        """获取指定部分的配置"""
        if section in self.config:
            return self.config[section]
        return None
    
    def set_value(self, section, key, value):
        """设置指定配置的值，如果部分或键不存在，则添加新的项"""
        if section not in self.config:
            # 如果部分不存在，创建新的部分
            self.config[section] = {}
        
        # 设置键的值（如果键不存在，则添加新键）
        self.config[section][key] = value
        return True
    
    def save_to_file(self, filename):
        """保存配置到文件"""
        import json
        try:
            with open(filename, 'w') as f:
                f.write(json.dumps(self.config))
            return True
        except:
            return False
    
    @classmethod
    def load_from_file(cls, filename):
        """从文件加载配置"""
        import json
        try:
            with open(filename, 'r') as f:
                config_dict = json.load(f)
            return cls(config_dict)
        except Exception as e:
            print(e)
            return cls()  # 返回默认配置


if __name__ == "__main__":
    # 从文件加载配置
    config = Configuration.load_from_file('/sdcard/configs/sys_config.json')
    
    # 获取WLAN配置
    wlan_config = config.get_section('WLAN')
    
    print(wlan_config["SSID"])
    
    # 设置音量
    config.set_value('sound', 'volume', 80)
    
    # 设置新项目
    config.set_value('My', 'Love', 520)
    
    # 保存配置到文件
    config.save_to_file('/sdcard/configs/sys_config.json')