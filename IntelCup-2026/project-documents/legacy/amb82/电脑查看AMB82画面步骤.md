# 电脑查看 AMB82-Mini 摄像头画面

## 最推荐方式：RTSP

AMB82-Mini 官方摄像头示例是 RTSP 推流。流程是：

1. 让 AMB82-Mini 跑官方 RTSP 示例。
   - Arduino IDE 中打开：`File > Examples > AmebaMultimedia > StreamRTSP > StreamRTSPVideoOnly`
   - 在代码里填你的 Wi-Fi 名称和密码：`ssid`、`pass`
   - 上传到 AMB82-Mini，按 Reset

2. 在串口监视器里找 IP 和端口。
   - 串口监视器会显示板子的 IP 和 RTSP 端口
   - 单路视频示例默认端口通常是 `554`
   - 地址一般长这样：`rtsp://192.168.1.154:554`

3. 电脑必须和 AMB82-Mini 连同一个 Wi-Fi。
   - 如果电脑是 `10.16.x.x`，AMB82 也应该在同一个可互通网络里
   - 如果学校/公司 Wi-Fi 隔离设备，建议先用手机热点或小路由器测试

4. 用 VLC 或 Python 打开画面。

## 用 VLC 看

1. 安装 VLC。
2. 打开 VLC。
3. macOS：`File > Open Network...`
4. 输入串口里打印出来的地址，例如：

```text
rtsp://192.168.1.154:554
```

5. 点播放。

## 用 Python 看

第一次先装 OpenCV：

```bash
python3 -m pip install opencv-python
```

进入这个文件夹后运行：

```bash
python3 view_rtsp.py 192.168.1.154
```

或者直接给完整地址：

```bash
python3 view_rtsp.py --url rtsp://192.168.1.154:554
```

窗口出现后，按 `q` 或 `Esc` 退出。

## 如果看不到画面

- 先确认串口已经打印出了 AMB82 的 IP。
- 确认电脑和 AMB82 在同一个 Wi-Fi/局域网。
- 如果 VLC/Python 都打不开，换手机热点或独立路由器测试，很多校园网会阻止设备互相访问。
- 如果画面卡顿，降低 RTSP 示例里的码率或分辨率。
- 如果电脑没有出现 AMB82 的串口设备，重新插 USB 线，确认线支持数据传输，不只是充电线。

官方参考：Realtek AmebaPro2 `Multimedia - RTSP Streaming`
https://www.amebaiot.com.cn/en/amebapro2-arduino-video-rtsp/
