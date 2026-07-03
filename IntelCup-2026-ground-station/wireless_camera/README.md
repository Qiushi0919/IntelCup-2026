# AMB82-Mini 720p RTSP 图传固件

当前采用方案 C：

- 分辨率：1280×720；
- 帧率：15 FPS；
- 编码：H.264；
- 码率：约 2 Mbps；
- 主图传：`rtsp://设备IP:554`；
- 兼容回退：`http://设备IP/snapshot.jpg`。

## 烧录

1. 复制 `network_config.example.h` 为 `network_config.h`，再填写比赛现场
   Wi-Fi 名称和密码；真实配置文件已被 Git 忽略；
2. 使用 USB 连接 AMB82-Mini；
3. 在 Arduino IDE 中选择 `AMB82-MINI`，打开 `wireless_camera.ino` 后上传；
4. 串口监视器设为 115200，可查看设备 IP 和两个图传地址。

已验证源码可在 Realtek AmebaPro2 4.1.0 下编译。`firmware/amb82_720p_rtsp_15fps.bin`
是本次编译生成的固件文件。

地面站的设备地址保持为 `auto` 即可：它会优先连接 RTSP，检测到旧固件时自动使用快照模式。
