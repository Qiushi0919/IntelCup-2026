# Week1

# 0429

## 进度总览

今天新板子到了，买了键鼠套装、外接显示器成功了，烧写了Windows11系统。

### 1 硬件情况

![image-20260429200937968](./Week1.assets/image-20260429200937968.png)

### 2 烧录系统

![image-20260429201118301](./Week1.assets/image-20260429201118301.png)

```
BT：
magnet:?xt=urn:btih:b27644de79e751ff874c2138d4168cef99a5a523&dn=zh-cn_windows_11_consumer_editions_version_25h2_updated_april_2026_x64_dvd_38233bf1.iso&xl=8658569216
```

这个镜像需要一个磁盘软件来下载

![919ed784-791e-4b3b-ae92-f269b330138b](./Week1.assets/919ed784-791e-4b3b-ae92-f269b330138b.png)

![image-20260429201315541](./Week1.assets/image-20260429201315541.png)

在UltraISO中打开Win11的.iso文件



![image-20260429202932292](./Week1.assets/image-20260429202932292.png)

启动(B) → 写入硬盘映像...

要先格式化U盘再写入，这个U盘会作为板卡的系统盘

![image-20260429205318538](./Week1.assets/image-20260429205318538.png)	

后面直接跟着文档做了

### 3 系统安装

1.方法一：

目标主机插上启动盘，然后开机。

开机按F7，然后选择你的U盘为引导项。然后回车

方法二：

也可以开机按Delete，进入BIOS。

在BOOT选项中设置你的U盘为boot option#1

然后按F4保存

![img](./Week1.assets/wps2.png) 

 

 

 

2.进入U盘后，确认系统语言后，点击下一步

![img](./Week1.assets/wps4.png) 

3.选择安装Windows11，同意同款，点击下一步

![img](./Week1.assets/wps8.png) 

 

 

4.点击我没有激活密钥

![img](./Week1.assets/wps10.png) 

 

 

 

1. 选择需要安装的系统

![img](./Week1.assets/wps13.png) 

2. 阅读条款后，点击“Accept”![img](./Week1.assets/wps14.png)

 

 

 

 

 

3. 进入磁盘分区界面。

![磁盘分区界面](./Week1.assets/wps15.png)

把需要安装系统的硬盘分区删除后重新分配。

![删除并重新分配分区](./Week1.assets/wps16.png)

8.删除完成后如下图，点击新建，输入C盘需要的大小，新建C盘容量后，点击应用

![img](./Week1.assets/wps18.png) 

 

 

 

 

9.选择分配的C盘系统盘

![img](./Week1.assets/wps21.png) 

 

 

10.点击“Install”

![img](./Week1.assets/wps23.png)



10. 选择地区，点击“Yes”![img](./Week1.assets/wps25.png) 

 

 

![img](./Week1.assets/wps27.png) 

 

 

 

 

 

 

 

 

11. 键盘布局，选择“跳过”

![img](./Week1.assets/wps29.png) 

 

12. 网络连接，选择I don't have intemet

![img](./Week1.assets/wps31.png) 



13. 输入用户名后，点击下一步

 

![img](./Week1.assets/wps34.png) 

 

 

14.是否需要密码，不需要直接点击“下一步”

![img](./Week1.assets/wps36.png) 

 

 

14. 点击下一步

 

![img](./Week1.assets/wps38.png) 

 

 

16.点击下一步

![img](./Week1.assets/wps40.png)



17.系统安装完成后安装主板驱动

![image-20260429210634024](./Week1.assets/image-20260429210634024.png)
