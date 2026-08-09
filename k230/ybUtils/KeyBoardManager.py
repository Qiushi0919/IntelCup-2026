import lvgl as lv

from media.display import *
from media.media import *
import time, os, sys, gc
import lvgl as lv
import json

DISPLAY_WIDTH = ALIGN_UP(640, 16)
DISPLAY_HEIGHT = 480

# 中文输入法类
class ChineseIME:
    def __init__(self, textarea, temp_input_display):  # 添加temp_input_display参数
        self.textarea = textarea
        self.temp_input_display = temp_input_display  # 保存引用
        self.candidates = []
        self.current_pinyin = ""
        self.page = 0
        self.candidates_per_page = 8  # 增加候选词数量
    
    def process_input(self, key):
        if key.isalpha():  # 处理拼音输入
            self.current_pinyin += key
            self.update_candidates()
        elif key == "<":  # 上一页
            if self.page > 0:
                self.page -= 1
                self.update_candidates_display()
        elif key == ">":  # 下一页
            if (self.page + 1) * self.candidates_per_page < len(self.candidates):
                self.page += 1
                self.update_candidates_display()
        elif key == "⌫":  # 退格键
            if self.current_pinyin:
                self.current_pinyin = self.current_pinyin[:-1]
                self.update_candidates()
                # 更新拼音显示
                return True
            else:
                # 当没有拼音输入时，删除textarea和temp_input_display的内容
                current_text = self.temp_input_display.get_text()
                if current_text:
                    new_text = current_text[:-1]
                    self.temp_input_display.set_text(new_text)
                    self.textarea.set_text(new_text)
                return True
        else:
            return False  # 其他键由键盘处理
        return True

    def update_candidates(self):
        # 这里实现拼音查询逻辑，将匹配的汉字添加到candidates
        # 简化版：使用预定义的拼音映射
        pinyin_map = {
            "a": ["啊", "阿", "呵", "吖", "腌", "锕", "錒", "鸦", "压", "丫"],
            "ai": ["爱", "哎", "哀", "埃", "矮", "碍", "癌", "艾", "挨", "唉", "砹", "隘", "嗳", "嫒", "暧", "瑷", "嗌", "锿", "霭", "懊"],
            "an": ["安", "按", "暗", "岸", "案", "俺", "氨", "胺", "鞍", "谙", "庵", "桉", "鹌", "埯", "铵", "俺", "黯", "唵", "闇"],
            "ang": ["昂", "盎", "肮", "仰", "昻"],
            "ao": ["奥", "澳", "傲", "熬", "敖", "凹", "袄", "嗷", "獒", "拗", "坳", "遨", "骜", "鳌", "翱", "岙", "廒", "懊", "媪", "骜"],
            "ba": ["八", "吧", "把", "巴", "爸", "拔", "霸", "罢", "芭", "跋", "扒", "坝", "笆", "疤", "耙", "靶", "粑", "岜", "钯", "捌"],
            "bai": ["白", "百", "摆", "败", "拜", "柏", "佰", "掰", "呗", "稗", "伯", "捭"],
            "ban": ["办", "半", "班", "板", "版", "伴", "般", "拌", "搬", "扮", "斑", "瓣", "绊", "阪", "坂", "钣", "舨", "湴"],
            "bang": ["帮", "邦", "榜", "棒", "绑", "膀", "傍", "磅", "蚌", "镑", "谤", "梆", "浜"],
            "bao": ["包", "报", "保", "宝", "抱", "爆", "暴", "薄", "饱", "堡", "豹", "胞", "褒", "雹", "苞", "葆", "褓", "鲍", "孢", "煲"],
            "bei": ["北", "被", "背", "杯", "备", "悲", "贝", "倍", "辈", "碑", "卑", "蓓", "悖", "惫", "焙", "褙", "钡", "狈", "孛", "邶"],
            "ben": ["本", "奔", "笨", "苯", "畚", "坌", "锛", "贲", "犇", "夯", "奙", "泵", "逩", "楱"],
            "bi": ["比", "必", "笔", "鼻", "逼", "毕", "避", "闭", "碧", "壁", "臂", "币", "弊", "辟", "蔽", "毙", "庇", "敝", "痹", "泌"],
            "bian": ["边", "变", "便", "编", "遍", "辩", "辨", "贬", "匾", "扁", "卞", "鞭", "辫", "煸", "蝙", "砭", "碥", "窆", "褊", "笾"],
            "biao": ["表", "标", "彪", "飙", "镖", "裱", "膘", "骠", "镳", "杓", "飚", "瘭", "婊", "鳔", "髟", "飑"],
            "bie": ["别", "憋", "瘪", "蹩", "鳖", "别", "徜", "襒", "鞭", "彆"],
            "bing": ["并", "病", "兵", "冰", "丙", "饼", "柄", "秉", "禀", "炳", "摒", "屏", "邴", "槟", "枋", "鞞"],
            "bo": ["波", "博", "播", "伯", "薄", "剥", "拨", "泊", "柏", "铂", "箔", "驳", "勃", "脖", "搏", "膊", "舶", "跛", "渤", "簸"],
            "bu": ["不", "布", "部", "步", "补", "捕", "埠", "簿", "卜", "哺", "怖", "堡", "逋", "晡", "钸", "醭", "瓿", "咘"],
            "ca": ["擦", "嚓", "礤", "拆", "喳", "䃲", "遢"],
            "cai": ["才", "菜", "彩", "财", "裁", "采", "材", "猜", "踩", "睬", "蔡", "彩", "倸", "寀", "跴"],
            "can": ["参", "餐", "残", "灿", "惨", "蚕", "掺", "璨", "粲", "惭", "黪", "骖", "孱", "澹", "谂"],
            "cang": ["仓", "藏", "苍", "舱", "沧", "抢", "臧", "伧", "鸧", "賶", "螥"],
            "cao": ["草", "操", "曹", "槽", "糙", "嘈", "艚", "螬", "漕", "屮", "慅", "肏"],
            "ce": ["策", "测", "侧", "册", "厕", "恻", "栅", "拺", "蓛", "荝"],
            "cha": ["查", "茶", "差", "插", "叉", "察", "茬", "岔", "诧", "刹", "汊", "姹", "杈", "楂", "槎", "檫", "衩", "镲", "猹", "锸"],
            "chai": ["差", "柴", "拆", "钗", "豺", "侪", "虿", "瘥", "茝", "訍"],
            "chan": ["产", "缠", "禅", "颤", "阐", "蝉", "馋", "铲", "搀", "潺", "忏", "谄", "谗", "婵", "骣", "觇", "蒇", "掺", "廛", "澶"],
            "chang": ["长", "场", "常", "唱", "厂", "畅", "昌", "肠", "尝", "偿", "倡", "敞", "猖", "怅", "裳", "琩", "菖", "阊", "鲳", "徜"],
            "chao": ["超", "朝", "吵", "抄", "潮", "炒", "巢", "嘲", "钞", "晁", "绰", "焯", "怊", "耖", "眧", "麨"],
            "che": ["车", "撤", "扯", "彻", "澈", "掣", "坼", "砗", "屮", "尺", "辙"],
            "chen": ["陈", "沉", "尘", "晨", "臣", "衬", "趁", "称", "辰", "谌", "忱", "抻", "琛", "陈", "嗔", "宸", "煁", "掺", "瞋", "榇"],
            "cheng": ["成", "城", "乘", "称", "程", "诚", "承", "呈", "澄", "橙", "盛", "秤", "惩", "逞", "骋", "铛", "枨", "柽", "蛏", "丞"],
            "chi": ["吃", "持", "迟", "赤", "尺", "翅", "齿", "池", "痴", "驰", "耻", "炽", "侈", "弛", "叱", "嗤", "茌", "墀", "蚩", "哧"],
            "chong": ["冲", "虫", "充", "宠", "崇", "重", "涌", "憧", "舂", "忡", "铳", "翀", "茺", "珫", "艟", "虫"],
            "chou": ["抽", "愁", "丑", "臭", "酬", "稠", "筹", "仇", "绸", "畴", "踌", "瞅", "惆", "帱", "俦", "雠", "瘳", "殠", "丑"],
            "chu": ["出", "初", "除", "楚", "触", "厨", "储", "处", "础", "畜", "矗", "橱", "躇", "锄", "雏", "滁", "黜", "褚", "楮", "杵"],
            "chuan": ["传", "船", "穿", "川", "喘", "串", "椽", "氚", "遄", "舛", "巛", "钏", "舡", "荈", "暷", "諯"],
            "chuang": ["窗", "床", "创", "闯", "疮", "幢", "怆", "吹", "闯", "创", "垂", "锤", "炊", "捶", "槌", "陲"],
            "chui": ["吹", "垂", "锤", "捶", "椎", "槌", "炊", "陲", "棰", "箠", "菙", "圌"],
            "chun": ["春", "纯", "唇", "蠢", "醇", "淳", "椿", "蝽", "莼", "鹑", "踔", "輴", "惷", "肫"],
            "ci": ["次", "此", "词", "刺", "慈", "磁", "瓷", "雌", "辞", "祠", "疵", "茨", "糍", "兹", "伺", "赐", "鹚", "呲", "佽", "饎"],
            "cong": ["从", "丛", "匆", "聪", "葱", "囱", "琮", "淙", "骢", "苁", "枞", "璁", "潀", "漗", "悰", "熜"],
            "cu": ["粗", "促", "醋", "簇", "蹙", "蹴", "猝", "蔟", "殂", "徂", "酢", "卒"],
            "cuan": ["窜", "篡", "攒", "蹿", "撺", "汆", "爨", "镩", "殩", "躜"],
            "cui": ["催", "脆", "翠", "崔", "摧", "萃", "淬", "啐", "悴", "璀", "榱", "毳", "瘁", "粹", "衰", "缞"],
            "cun": ["村", "存", "寸", "蹲", "忖", "皴", "浚", "踆", "澊", "拵"],
            "da": ["大", "打", "达", "答", "搭", "塔", "褡", "瘩", "疸", "怛", "妲", "沓", "笪", "靼", "鞑", "炟"],
            "dai": ["带", "代", "待", "戴", "袋", "呆", "贷", "逮", "歹", "殆", "黛", "怠", "傣", "玳", "岱", "迨", "绐", "埭", "甙", "诒"],
            "dan": ["但", "单", "担", "蛋", "弹", "淡", "胆", "丹", "旦", "耽", "诞", "氮", "郸", "萏", "殚", "眈", "赕", "疸", "瘅", "聃"],
            "dang": ["当", "党", "挡", "荡", "档", "裆", "铛", "凼", "菪", "宕", "砀", "谠", "当", "垱", "档", "璫"],
            "dao": ["到", "道", "刀", "导", "岛", "倒", "盗", "稻", "蹈", "捣", "祷", "悼", "刂", "叨", "帱", "忉", "氘", "纛"],
            "dei": ["得", "德", "底"],
            "deng": ["等", "灯", "登", "瞪", "凳", "邓", "锻", "瞠", "凳", "噔"],
            "di": ["第", "地", "低", "敌", "底", "滴", "迪", "抵", "堤", "狄", "涤", "骶", "骐", "嫡"],
            "dian": ["点", "电", "店", "典", "颠", "垫", "滇", "惦", "掂", "腌", "煎", "奠", "钿", "碘"],
            "diao": ["掉", "调", "吊", "雕", "钓", "叼", "凋", "貂", "铫", "吊"],
            "die": ["跌", "叠", "爹", "蝶", "碟", "垫", "谍", "喋", "忉", "啼"],
            "ding": ["定", "顶", "丁", "订", "盯", "锭", "腚", "鼎", "耵", "鼎"],
            "dong": ["东", "动", "冬", "懂", "洞", "冻", "董", "侗", "咚", "恫"],
            "dou": ["都", "斗", "豆", "抖", "陡", "逗", "兜", "蔸", "窦", "陡"],
            "du": ["度", "读", "独", "毒", "堵", "赌", "笃", "睹", "肚", "妒"],
            "duan": ["段", "短", "断", "端", "锻", "煅", "缎", "煅", "奠", "阽"],
            "dui": ["对", "队", "堆", "兑", "对", "怼", "憝", "队", "锻"],
            "dun": ["吨", "顿", "蹲", "盾", "钝", "敦", "遁", "囤", "炖", "吨"],
            "duo": ["多", "夺", "躲", "朵", "堕", "惰", "妥", "舵", "哆", "踱"],
            "e": ["饿", "额", "鹅", "恶", "俄", "厄", "呃", "扼", "愕", "讹"],
            "en": ["恩", "嗯"],
            "er": ["二", "而", "儿", "耳", "尔", "饵", "厄", "尔", "惹"],
            "fa": ["发", "法", "罚", "乏", "伐", "阀", "法", "珐", "发"],
            "fan": ["反", "饭", "范", "犯", "翻", "烦", "泛", "奋", "贩", "繁"],
            "fang": ["方", "房", "放", "防", "访", "仿", "妨", "坊", "芳", "枋"],
            "fei": ["飞", "非", "费", "肥", "废", "肺", "菲", "啡", "霏", "扉"],
            "fen": ["分", "奋", "粉", "份", "氛", "坟", "焚", "焚", "芬", "愤"],
            "feng": ["风", "封", "峰", "疯", "逢", "缝", "凤", "烽", "蜂", "丰"],
            "fo": ["佛"],
            "fou": ["否"],
            "fu": ["夫", "父", "服", "负", "富", "福", "扶", "符", "抚", "幅"],
            "ga": ["嘎", "伽", "盖", "尬", "噶", "嘎", "钆", "尕", "煞"],
            "gai": ["该", "改", "盖", "概", "钙", "溉", "丐", "骸", "嗏"],
            "gan": ["干", "感", "敢", "赶", "肝", "杆", "竿", "戈", "詹"],
            "gang": ["刚", "港", "钢", "岗", "纲", "杠", "肠", "绠", "亘"],
            "gao": ["高", "告", "搞", "稿", "糕", "膏", "皓", "镐", "毫"],
            "ge": ["个", "各", "歌", "哥", "格", "隔", "革", "阁", "戈"],
            "gei": ["给"],
            "gen": ["根", "跟", "艮", "亘", "茛", "艮"],
            "geng": ["更", "耕", "耿", "梗", "埂", "绠"],
            "gong": ["公", "工", "攻", "功", "共", "弓", "龚", "供", "恭"],
            "gou": ["够", "购", "狗", "沟", "勾", "钩", "构", "呱"],
            "gu": ["古", "顾", "故", "姑", "骨", "鼓", "轱", "孤", "估"],
            "gua": ["挂", "瓜", "刮", "寡", "褂", "呱"],
            "guai": ["怪", "拐", "乖", "乖", "乖"],
            "guan": ["关", "观", "官", "管", "惯", "冠", "罐", "莞"],
            "guang": ["光", "广", "逛", "茫", "犷"],
            "gui": ["贵", "归", "鬼", "轨", "跪", "桂"],
            "gun": ["滚", "棍", "衮", "鳏"],
            "guo": ["国", "果", "过", "锅", "郭", "裹", "倭", "蜗"],
            "ha": ["哈", "蛤", "哈", "哈"],
            "hai": ["还", "海", "害", "孩", "亥", "骸"],
            "han": ["汉", "喊", "寒", "含", "汗", "憾", "焊"],
            "hang": ["行", "航", "杭", "巷", "夯"],
            "hao": ["好", "号", "豪", "耗", "毫", "浩", "嗥"],
            "he": ["和", "何", "喝", "河", "核", "合", "赫"],
            "hei": ["黑", "嘿"],
            "hen": ["很", "恨", "痕"],
            "heng": ["横", "恒", "哼"],
            "hong": ["红", "洪", "宏", "轰", "虹", "鸿"],
            "hou": ["后", "候", "厚", "侯", "吼", "喉", "猴", "逅", "堠", "鲎"],
            "hu": ["乎", "呼", "胡", "户", "虎", "护", "湖", "糊", "互", "蝴", "沪", "壶", "葫", "弧", "狐", "忽", "瑚", "戽", "鹄", "鹕"],
            "hua": ["话", "花", "画", "华", "滑", "化", "划", "哗", "猾", "骅", "铧", "桦", "画", "划", "华"],
            "huai": ["坏", "怀", "淮", "徊", "槐", "踝", "蘾", "佪"],
            "huan": ["欢", "换", "环", "缓", "患", "幻", "唤", "还", "涣", "焕", "痪", "寰", "桓", "宦", "豢", "锾", "奂", "洹"],
            "huang": ["黄", "皇", "慌", "晃", "荒", "煌", "谎", "恍", "凰", "惶", "蝗", "磺", "隍", "徨", "簧", "璜", "蟥"],
            "hui": ["会", "回", "灰", "挥", "汇", "悔", "惠", "辉", "毁", "慧", "贿", "徽", "讳", "卉", "徊", "茴", "烩", "诲", "彗", "晦"],
            "hun": ["混", "魂", "昏", "婚", "浑", "荤", "诨", "馄", "珲", "溷", "阍"],
            "huo": ["或", "活", "火", "获", "货", "祸", "豁", "惑", "霍", "伙", "和", "钬", "夥", "锪", "耠", "劐"],
            "ji": ["几", "机", "己", "记", "计", "极", "级", "即", "既", "急", "集", "季", "继", "击", "基", "激", "积", "技", "际", "鸡"],
            "jia": ["家", "加", "假", "价", "甲", "驾", "佳", "夹", "嫁", "嘉", "劫", "迦"],
            "jian": ["见", "间", "件", "建", "剑", "健", "监", "减", "肩", "江", "溅", "奸"],
            "jiang": ["将", "江", "讲", "奖", "降", "疆", "僵", "浆", "姜", "匠", "蒋", "豇"],
            "jiao": ["叫", "教", "交", "角", "脚", "骄", "骄", "浇", "焦", "娇", "搅", "佼"],
            "jie": ["接", "街", "节", "姐", "解", "借", "界", "阶", "洁", "捷", "睫", "胶"],
            "jin": ["进", "今", "金", "斤", "紧", "禁", "锦", "巾", "谨", "尽", "筋", "靳"],
            "jing": ["经", "京", "静", "精", "境", "惊", "井", "警", "景", "镜", "腥", "煎"],
            "jiu": ["就", "九", "酒", "久", "救", "旧", "舅", "纠", "揪", "灸", "咀", "阍"],
            "ju": ["局", "据", "举", "具", "剧", "距", "瞿", "菊", "炬", "巨", "锯", "举"],
            "juan": ["卷", "捐", "娟", "倦", "圈", "涓", "眷", "鹃", "锩"],
            "jue": ["觉", "决", "绝", "掘", "爵", "抉", "劂", "焚", "阕"],
            "jun": ["军", "均", "君", "俊", "菌", "骏", "峻", "捃", "钧"],
            "ka": ["卡", "咖", "咯", "咖", "喀", "卡"],
            "kai": ["开", "凯", "慨", "楷", "揩", "恺", "剀"],
            "kan": ["看", "刊", "砍", "坎", "侃", "阚", "瞿"],
            "kang": ["抗", "康", "扛", "炕", "慷", "糠", "亢"],
            "kao": ["考", "靠", "烤", "尻", "犒", "拷"],
            "ke": ["可", "科", "克", "客", "课", "渴", "克", "刻", "恪"],
            "ken": ["肯", "啃", "恳"],
            "kong": ["空", "控", "恐", "孔", "箜", "崆"],
            "kou": ["口", "扣", "寇", "抠", "蔻"],
            "ku": ["苦", "库", "哭", "酷", "裤", "枯", "骷"],
            "kua": ["夸", "跨", "垮", "挎"],
            "kuai": ["快", "块", "筷", "会", "快", "侩"],
            "kuan": ["宽", "款", "圈", "髋"],
            "kuang": ["狂", "框", "矿", "旷", "狂", "邝"],
            "kui": ["亏", "愧", "奎", "窥", "葵", "魁"],
            "kun": ["困", "昆", "捆", "坤", "阔"],
            "kuo": ["扩", "阔", "括", "廓"],
            "la": ["拉", "啦", "辣", "蜡", "腊", "喇"],
            "lai": ["来", "赖", "莱", "睐"],
            "lan": ["兰", "蓝", "拦", "懒", "烂", "阑"],
            "lang": ["浪", "朗", "郎", "廊", "琅", "榔"],
            "lao": ["老", "劳", "捞", "牢", "佬", "烙"],
            "le": ["了", "乐", "勒"],
            "lei": ["类", "泪", "雷", "累", "垒", "镭"],
            "leng": ["冷", "愣", "冷", "楞"],
            "li": ["力", "里", "立", "李", "利", "礼", "璃", "狸"],
            "lian": ["连", "脸", "恋", "联", "廉", "怜", "炼", "涟"],
            "liang": ["两", "亮", "量", "良", "凉", "梁"],
            "liao": ["了", "料", "聊", "辽", "疗", "燎"],
            "lie": ["列", "烈", "裂", "猎", "劣"],
            "lin": ["林", "临", "邻", "淋", "琳", "鳞"],
            "ling": ["另", "领", "零", "灵", "令", "铃", "岭"],
            "liu": ["六", "刘", "流", "留", "柳", "溜", "熘"],
            "long": ["龙", "隆", "笼", "聋", "拢", "垄"],
            "lou": ["楼", "漏", "搂", "陋", "娄"],
            "lu": ["路", "录", "露", "卢", "炉", "鲁", "绿"],
            "luan": ["乱", "卵", "峦", "滦"],
            "lue": ["略", "掠"],
            "lun": ["论", "轮", "伦", "仑"],
            "luo": ["落", "罗", "洛", "裸", "螺", "骡"],
            "ma": ["吗", "妈", "马", "码", "麻", "骂", "马", "玛"],
            "mai": ["买", "卖", "麦", "迈"],
            "man": ["满", "慢", "漫", "曼", "瞒"],
            "mang": ["忙", "芒", "盲", "茫"],
            "mao": ["毛", "猫", "冒", "帽", "矛", "茂"],
            "me": ["么"],
            "mei": ["没", "每", "美", "妹", "眉", "煤"],
            "men": ["们", "门", "闷", "蒙"],
            "meng": ["梦", "猛", "蒙", "盟", "萌"],
            "mi": ["米", "迷", "密", "秘", "蜜", "眯"],
            "mian": ["面", "免", "棉", "眠", "缅"],
            "miao": ["妙", "庙", "描", "秒", "苗"],
            "mie": ["灭", "蔑"],
            "min": ["民", "敏", "闽", "悯"],
            "ming": ["明", "名", "命", "鸣", "铭"],
            "mo": ["末", "莫", "摸", "模", "墨", "魔"],
            "mou": ["某", "谋", "牟"],
            "mu": ["目", "木", "母", "亩", "幕", "慕"],
            "na": ["那", "拿", "哪", "纳", "娜"],
            "nai": ["乃", "奶", "耐", "奈"],
            "nan": ["南", "难", "男", "楠"],
            "nao": ["闹", "脑", "挠", "恼"],
            "ne": ["呢", "哪"],
            "nei": ["内", "那"],
            "nen": ["嫩", "能"],
            "neng": ["能"],
            "ni": ["你", "呢", "妮", "尼", "拟", "逆"],
            "nian": ["年", "念", "黏", "碾"],
            "niang": ["娘", "酿"],
            "niao": ["鸟", "尿"],
            "nie": ["捏", "聂", "孽"],
            "nin": ["您"],
            "ning": ["宁", "凝", "拧", "柠"],
            "niu": ["牛", "扭", "纽"],
            "nong": ["农", "浓", "弄"],
            "nu": ["女", "努", "奴", "怒"],
            "nuan": ["暖", "暧", "煖"],
            "nue": ["虐", "疟", "谑"],
            "nuo": ["诺", "挪", "懦", "糯", "娜", "锘"],
            "ou": ["欧", "偶", "呕", "藕", "鸥", "殴", "区"],
            "pa": ["怕", "爬", "啪", "趴", "帕", "扒", "葩"],
            "pai": ["派", "排", "牌", "拍", "徘", "湃", "迫"],
            "pan": ["盘", "判", "盼", "叛", "攀", "畔", "潘", "磐"],
            "pang": ["旁", "胖", "庞", "膀", "乓", "耪", "磅"],
            "pao": ["跑", "泡", "抛", "炮", "袍", "刨", "咆"],
            "pei": ["配", "培", "陪", "佩", "赔", "沛", "裴", "胚"],
            "pen": ["喷", "盆", "喯", "湓"],
            "peng": ["朋", "碰", "棚", "蓬", "鹏", "捧", "膨", "烹"],
            "pi": ["皮", "批", "屁", "啤", "脾", "疲", "匹", "披", "劈", "辟"],
            "pian": ["片", "偏", "骗", "篇", "便", "扁", "翩"],
            "piao": ["票", "飘", "漂", "瓢", "嫖", "剽", "缥"],
            "pie": ["撇", "瞥", "氕", "苤"],
            "pin": ["品", "贫", "拼", "聘", "频", "苹", "娉", "牝"],
            "ping": ["平", "评", "瓶", "凭", "萍", "坪", "屏", "苹"],
            "po": ["破", "坡", "泼", "婆", "迫", "魄", "颇", "珀"],
            "pou": ["剖", "裒", "掊", "抔"],
            "pu": ["普", "扑", "铺", "葡", "仆", "谱", "浦", "蒲", "曝", "瀑"],
            "qi": ["其", "起", "七", "气", "齐", "奇", "期", "旗", "汽", "骑", "妻", "棋", "欺", "岂", "企", "启", "器", "弃", "契"],
            "qia": ["卡", "恰", "掐", "洽", "髂", "袷"],
            "qian": ["前", "钱", "千", "签", "潜", "浅", "遣", "欠", "牵", "谦", "黔", "迁", "歉", "纤", "嵌", "乾"],
            "qiang": ["强", "抢", "枪", "墙", "腔", "呛", "羌", "蔷", "锵", "跄"],
            "qiao": ["桥", "敲", "巧", "乔", "翘", "俏", "悄", "瞧", "鞘", "橇", "锹", "壳"],
            "qie": ["且", "切", "窃", "茄", "怯", "锲", "妾", "趄"],
            "qin": ["亲", "琴", "勤", "侵", "秦", "芹", "禽", "寝", "擒", "沁"],
            "qing": ["请", "情", "清", "轻", "庆", "倾", "青", "氢", "卿", "晴", "擎", "顷", "氰"],
            "qiong": ["穷", "琼", "穹", "茕"],
            "qiu": ["求", "球", "秋", "邱", "囚", "丘", "仇", "酋", "裘", "糗"],
            "qu": ["去", "区", "取", "曲", "趣", "驱", "渠", "屈", "躯", "娶", "蛆", "趋", "氍"],
            "quan": ["全", "权", "圈", "劝", "拳", "犬", "泉", "诠", "痊", "券", "筌"],
            "que": ["却", "确", "缺", "雀", "阙", "瘸", "鹊", "炔"],
            "qun": ["群", "裙", "逡", "麇"],
            "ran": ["然", "染", "燃", "冉", "髯", "苒"],
            "rang": ["让", "嚷", "壤", "攘", "瓤"],
            "rao": ["饶", "绕", "扰", "桡", "娆"],
            "re": ["热", "若", "惹", "喏"],
            "ren": ["人", "任", "认", "忍", "刃", "韧", "仁", "妊", "轫", "纫"],
            "reng": ["仍", "扔", "礽"],
            "ri": ["日", "鈤"],
            "rong": ["容", "荣", "融", "绒", "蓉", "熔", "溶", "榕", "戎", "茸"],
            "rou": ["肉", "柔", "揉", "蹂", "糅"],
            "ru": ["如", "入", "乳", "辱", "儒", "汝", "茹", "褥", "蠕"],
            "ruan": ["软", "阮", "朊"],
            "rui": ["瑞", "锐", "蕊", "芮", "睿"],
            "run": ["润", "闰"],
            "ruo": ["若", "弱", "偌"],
            "sa": ["撒", "萨", "洒", "飒", "卅"],
            "sai": ["赛", "塞", "腮", "噻"],
            "san": ["三", "散", "伞", "叁", "馓", "糁"],
            "sang": ["丧", "桑", "嗓", "搡", "磉"],
            "sao": ["扫", "骚", "嫂", "臊", "搔", "缫"],
            "se": ["色", "涩", "瑟", "塞", "啬"],
            "sen": ["森"],
            "seng": ["僧"],
            "sha": ["杀", "沙", "傻", "纱", "刹", "砂", "啥", "煞", "莎", "杉"],
            "shai": ["晒", "筛", "色"],
            "shan": ["山", "善", "闪", "衫", "扇", "删", "陕", "珊", "杉", "煽", "擅", "膳", "赡"],
            "shang": ["上", "商", "伤", "尚", "赏", "晌", "墒", "裳", "觞"],
            "shao": ["少", "烧", "稍", "绍", "哨", "邵", "劭", "韶", "捎"],
            "she": ["社", "设", "射", "舍", "蛇", "涉", "摄", "赦", "慑", "奢", "赊"],
            "shei": ["谁"],
            "shen": ["深", "身", "神", "审", "沈", "伸", "绅", "呻", "娠"],
            "sheng": ["生", "声", "胜", "省", "升", "盛", "绳", "腥"],
            "shi": ["是", "时", "事", "市", "十", "师", "使", "石", "识", "诗", "狮", "尸", "施"],
            "shou": ["手", "受", "收", "守", "首", "寿", "狩", "绶"],
            "shu": ["书", "数", "树", "属", "输", "熟", "煮", "数", "舒", "蜀"],
            "shua": ["刷", "耍", "唰"],
            "shuai": ["帅", "摔", "衰"],
            "shuan": ["栓", "拴"],
            "shuang": ["双", "爽", "霜", "妆"],
            "shui": ["水", "谁", "睡", "税", "穗", "氵"],
            "shun": ["顺", "瞬", "舜"],
            "shuo": ["说", "硕", "朔", "搠"],
            "si": ["四", "死", "思", "司", "丝", "似", "饲", "祀"],
            "song": ["送", "宋", "松", "颂", "耸", "悚", "怂"],
            "sou": ["搜", "艘", "嗽"],
            "su": ["苏", "素", "速", "诉", "宿", "俗", "塑"],
            "suan": ["算", "酸", "蒜"],
            "sui": ["随", "岁", "虽", "碎", "隋"],
            "sun": ["孙", "损", "笋"],
            "suo": ["所", "锁", "缩", "索", "琐"],
            "ta": ["他", "她", "它", "塔", "踏", "塌"],
            "tai": ["太", "台", "态", "抬", "泰", "胎"],
            "tan": ["谈", "坦", "探", "贪", "摊", "叹"],
            "tang": ["堂", "汤", "唐", "糖", "烫", "躺", "塘"],
            "tao": ["套", "讨", "逃", "桃", "陶", "淘"],
            "te": ["特"],
            "teng": ["疼", "腾", "藤"],
            "ti": ["体", "提", "题", "替", "梯", "踢"],
            "tian": ["天", "田", "填", "甜", "添"],
            "tiao": ["条", "调", "跳", "挑", "眺"],
            "tie": ["铁", "贴", "帖"],
            "ting": ["听", "停", "庭", "挺", "亭"],
            "tong": ["同", "通", "统", "桐", "痛", "铜"],
            "tou": ["头", "投", "偷", "透"],
            "tu": ["土", "图", "突", "徒", "涂", "兔"],
            "tuan": ["团", "抟"],
            "tui": ["推", "退", "腿", "颓"],
            "tun": ["吞", "屯", "臀"],
            "tuo": ["托", "脱", "拖", "妥", "驼"],
            "wa": ["哇", "娃", "挖", "瓦", "蛙"],
            "wai": ["外", "歪"],
            "wan": ["万", "完", "晚", "玩", "碗", "弯"],
            "wang": ["王", "望", "网", "往", "忘", "亡"],
            "wei": ["为", "位", "伟", "味", "尾", "微"],
            "wen": ["问", "文", "闻", "温", "稳", "吻"],
            "weng": ["翁", "嗡"],
            "wo": ["我", "握", "沃", "卧", "窝", "蜗"],
            "wu": ["五", "无", "物", "务", "武", "舞"],
            "xi": ["系", "西", "息", "希", "喜", "惜"],
            "xia": ["下", "夏", "吓", "侠", "虾", "瞎"],
            "xian": ["先", "现", "线", "显", "闲", "献", "限", "掀", "嫌", "县", "宪", "陷", "贤", "弦", "咸", "衔", "舷"],
            "xiang": ["想", "向", "相", "香", "箱", "乡"],
            "xiao": ["小", "笑", "校", "消", "晓", "肖"],
            "xie": ["些", "写", "谢", "鞋", "斜", "卸"],
            "xin": ["心", "新", "信", "欣", "辛", "薪"],
            "xing": ["行", "星", "形", "性", "醒", "兴"],
            "xiong": ["兄", "熊", "胸", "凶"],
            "xiu": ["修", "秀", "袖", "休", "羞"],
            "xu": ["需", "许", "续", "序", "虚", "徐"],
            "xuan": ["选", "宣", "悬", "旋", "炫"],
            "xue": ["学", "雪", "血", "穴"],
            "xun": ["寻", "训", "讯", "迅", "巡", "询"],
            "ya": ["呀", "亚", "压", "牙", "鸭", "崖"],
            "yan": ["眼", "言", "严", "烟", "研", "演"],
            "yang": ["阳", "养", "样", "羊", "洋", "仰"],
            "yao": ["要", "药", "摇", "咬", "腰", "邀"],
            "ye": ["也", "夜", "业", "叶", "野", "爷"],
            "yi": ["一", "以", "已", "亿", "义", "易"],
            "yin": ["因", "音", "引", "银", "印", "阴"],
            "ying": ["应", "英", "影", "迎", "营", "硬"],
            "yo": ["哟"],
            "yong": ["用", "永", "勇", "泳", "拥", "咏"],
            "you": ["有", "又", "由", "油", "友", "右"],
            "yu": ["于", "与", "语", "育", "遇", "玉"],
            "yuan": ["远", "员", "元", "原", "院", "缘"],
            "yue": ["月", "约", "越", "阅", "悦", "跃"],
            "yun": ["运", "云", "允", "韵", "孕", "匀"],
            "za": ["杂", "砸", "咋"],
            "zai": ["在", "再", "灾", "载", "栽"],
            "zan": ["咱", "暂", "赞", "攒"],
            "zang": ["脏", "藏", "葬", "赃"],
            "zao": ["早", "造", "糟", "燥", "躁", "噪"],
            "ze": ["则", "责", "择", "泽"],
            "zei": ["贼"],
            "zen": ["怎"],
            "zeng": ["增", "赠", "曾", "憎"],
            "zha": ["查", "炸", "扎", "诈", "闸", "渣"],
            "zhai": ["摘", "宅", "窄", "债"],
            "zhan": ["战", "展", "站", "占", "沾", "斩"],
            "zhang": ["长", "张", "章", "掌", "涨", "帐"],
            "zhao": ["找", "照", "招", "赵", "召", "兆"],
            "zhe": ["这", "者", "着", "折", "哲", "浙"],
            "zhei": ["这"],
            "zhen": ["真", "针", "诊", "震", "镇", "阵"],
            "zheng": ["正", "政", "证", "争", "整", "郑"],
            "zhi": ["之", "只", "知", "至", "直", "制", "智", "值", "纸"],
            "zhong": ["中", "重", "众", "钟", "终", "忠"],
            "zhou": ["周", "州", "轴", "舟", "皱", "宙", "洲", "昼", "骤", "咒", "肘", "帚", "绉"],
            "zhu": ["主", "住", "注", "助", "著", "竹", "珠", "猪", "诸", "朱", "铸", "嘱", "柱", "烛", "逐", "筑", "祝", "驻", "蛛", "贮", "煮"],
            "zhua": ["抓", "爪", "挝", "髽"],
            "zhuai": ["拽", "跩"],
            "zhuan": ["转", "专", "传", "赚", "砖", "撰", "篆", "馔", "啭", "颛"],
            "zhuang": ["装", "壮", "庄", "撞", "妆", "桩", "幢", "奘", "戆"],
            "zhui": ["追", "坠", "锥", "椎", "赘", "惴", "缀", "骓"], 
            "zhun": ["准", "谆", "窀", "肫", "准"],
            "zhuo": ["桌", "捉", "卓", "着", "浊", "酌", "拙", "啄", "灼", "茁", "斫", "镯"],
            "zi": ["子", "自", "字", "资", "仔", "紫", "姿", "咨", "籽", "滋", "孜", "梓", "渍", "姊", "吱", "秭", "恣"],
            "zong": ["总", "宗", "纵", "踪", "综", "棕", "粽", "鬃", "腙", "踵", "偬"],
            "zou": ["走", "奏", "邹", "揍", "诹", "鲰", "鄹", "陬"],
            "zu": ["组", "族", "足", "祖", "阻", "租", "卒", "诅", "镞", "俎", "菹"],
            "zuan": ["钻", "赚", "钻", "攥", "纂", "缵"],
            "zui": ["最", "嘴", "醉", "罪", "蕞", "觜", "枠", "咀"],
            "zun": ["尊", "遵", "樽", "鳟", "撙", "噂"],
            "zuo": ["做", "作", "坐", "左", "座", "昨", "佐", "琢", "撮", "祚", "怍", "笮", "阼"],
            "nihao": ["你好", "拟好", "逆号", "泥耗"],
            "zaijian": ["再见", "在间", "再检", "载舰", "宰间"],
            "nihao": ["你好"],
            "zaijian": ["再见"],
            "xiexie": ["谢谢"],
            "bukeqi": ["不客气"],
            "duibuqi": ["对不起"],
            "meiguanxi": ["没关系"],
            "zongjie": ["总结"],
            "gongzuo": ["工作"],
            "xuexi": ["学习"],
            "laoshi": ["老师"],
            "xuesheng": ["学生"],
            "pengyou": ["朋友"],
            "jiating": ["家庭"],
            "shehui": ["社会"],
            "zhengfu": ["政府"],
            "jingji": ["经济"],
            "wenhua": ["文化"],
            "jiaoyu": ["教育"],
            "keji": ["科技"],
            "huanjing": ["环境"],
            "zhineng": ["智能"],
            "gongsi": ["公司"],
            "minzu": ["民族"],
            "guojia": ["国家"],
            "renmin": ["人民"],
            "zhongguo": ["中国"],
            "beijing": ["北京"],
            "shanghai": ["上海"],
            "guangzhou": ["广州"],
            "shenzhen": ["深圳"],
            "daolu": ["道路"],
            "chengshi": ["城市", "诚实"],
            "qiche": ["汽车"],
            "dianhua": ["电话"],
            "diannao": ["电脑"],
            "shouji": ["手机"],
            "yinhang": ["银行"],
            "yiyuan": ["医院"],
            "xuexiao": ["学校"],
            "tushuguan": ["图书馆"],
            "shangye": ["商业"],
            "shenghuo": ["生活"],
            "yundong": ["运动"],
            "yinshi": ["饮食"],
            "jiankang": ["健康"],
            "shangchang": ["商场"],
            "chaoshi": ["超市"],
            "canting": ["餐厅"],
            "ditie": ["地铁"],
            "gongjiao": ["公交"],
            "kongtiao": ["空调"],
            "bingxiang": ["冰箱"],
            "dianshi": ["电视"],
            "wangluo": ["网络"],
            "hulianwang": ["互联网"],
            "youxi": ["游戏"],
            "yinyue": ["音乐"],
            "dianying": ["电影"],
            "xiaoshuo": ["小说"],
            "tiyu": ["体育"],
            "zuqiu": ["足球"],
            "lanqiu": ["篮球"],
            "wangqiu": ["网球"],
            "youyong": ["游泳"],
            "shenghuo": ["生活"],
            "yundong": ["运动"],
            "yinshi": ["饮食"],
            "jiankang": ["健康"],
            "shangchang": ["商场"],
            "chaoshi": ["超市"],
            "canting": ["餐厅"],
            "ditie": ["地铁"],
            "gongjiao": ["公交"],
            "kongtiao": ["空调"],
            "bingxiang": ["冰箱"],
            "dianshi": ["电视"],
            "wangluo": ["网络"],
            "hulianwang": ["互联网"],
            "youxi": ["游戏"],
            "yinyue": ["音乐"],
            "dianying": ["电影"],
            "xiaoshuo": ["小说"],
            "tiyu": ["体育"],
            "zuqiu": ["足球"],
            "lanqiu": ["篮球"],
            "wangqiu": ["网球"],
            "youyong": ["游泳"],
            "dengji": ["登记"],
            "xinzhi": ["新知"],
            "zhaopin": ["招聘"],
            "jiaochen": ["交陈"],
            "shijian": ["时间"],
            "jichu": ["基础"],
            "chukou": ["出口"],
            "ruanjian": ["软件"],
            "gongju": ["工具"],
            "daihao": ["代号"],
            "xingqi": ["星期"],
            "yuefen": ["月份"],
            "tianqi": ["天气"],
            "zhuangtai": ["状态"],
            "shouce": ["手册"],
            "shijie": ["世界"],
            "quyu": ["区域"],
            "yuyue": ["预约"],
            "zhengjian": ["证件"],
            "xingcheng": ["行程"],
            "shoufei": ["收费"],
            "huodong": ["活动"],
            "xuqiu": ["需求"]
        }
        
        self.candidates = []
        exact_matches = []
        prefix_matches = []
        
        # 先查找完全匹配的拼音
        if self.current_pinyin in pinyin_map:
            exact_matches.extend(pinyin_map[self.current_pinyin])
        
        # 再查找前缀匹配的拼音
        for key, values in pinyin_map.items():
            if key.startswith(self.current_pinyin) and key != self.current_pinyin:
                prefix_matches.extend(values)
        
        # 完全匹配的放在前面，前缀匹配的放在后面
        self.candidates = exact_matches + prefix_matches
        
        self.page = 0
        self.update_candidates_display()

    def update_candidates_display(self):
        # 返回当前页的候选词，用于显示
        start = self.page * self.candidates_per_page
        end = min(start + self.candidates_per_page, len(self.candidates))
        return self.candidates[start:end]

    def select_candidate(self, index):
        if not self.candidates:
            return
        
        page_start = self.page * self.candidates_per_page
        if page_start + index < len(self.candidates):
            selected = self.candidates[page_start + index]
            
            # 获取当前文本并找到拼音在文本中的位置
            current_text = self.temp_input_display.get_text()
            
            # 如果有拼音输入，先删除拼音部分
            if self.current_pinyin:
                # 查找当前拼音在文本末尾的位置并移除
                if current_text.endswith(self.current_pinyin):
                    current_text = current_text[:-len(self.current_pinyin)]
                
            # 添加选中的汉字
            new_text = current_text + selected
            self.temp_input_display.set_text(new_text)
            self.textarea.set_text(new_text)
            
            # 清空当前状态
            self.current_pinyin = ""
            self.candidates = []
            self.update_candidates_display()

    def get_current_state(self):
        return {
            "pinyin": self.current_pinyin,
            "candidates": self.update_candidates_display(),
            "has_prev": self.page > 0,
            "has_next": (self.page + 1) * self.candidates_per_page < len(self.candidates)
        }

    def clear(self):
        self.current_pinyin = ""
        self.candidates = []
        self.page = 0

# 修改后的键盘管理类
class KeyboardManager:
    def __init__(self, screen, textarea):
        self.screen = screen
        self.target_textarea = textarea
        self.keyboard_visible = False
        # 将ime的初始化移到create_keyboard之后
        self.ime = None
        self.ime_active = False
        self.create_keyboard()
        # 创建完键盘后初始化ime
        self.ime = ChineseIME(textarea, self.temp_input_display)

    def create_keyboard(self):
        # 创建键盘容器，覆盖整个屏幕，使用固定分辨率
        self.keyboard_container = lv.obj(self.screen)
        self.keyboard_container.set_size(DISPLAY_WIDTH, DISPLAY_HEIGHT)  # 使用固定分辨率
        self.keyboard_container.align(lv.ALIGN.TOP_LEFT, 0, 0)
        self.keyboard_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        self.keyboard_container.set_style_pad_all(0, 0)  # 移除所有填充
        self.keyboard_container.set_style_border_width(0, 0)  # 移除边框
        self.keyboard_container.add_flag(lv.obj.FLAG.HIDDEN)

        # 创建半透明遮罩层
        self.overlay = lv.obj(self.keyboard_container)
        self.overlay.set_size(DISPLAY_WIDTH, DISPLAY_HEIGHT)  # 同样使用固定分辨率
        self.overlay.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.overlay.set_style_bg_opa(lv.OPA._50, 0)  # 半透明
        self.overlay.set_style_pad_all(0, 0)  # 移除填充
        self.overlay.set_style_border_width(0, 0)  # 移除边框
        self.overlay.set_style_radius(0,0)
        self.overlay.add_event(self.overlay_click_cb, lv.EVENT.CLICKED, None)

        # 创建键盘
        self.keyboard = lv.keyboard(self.keyboard_container)
        self.keyboard.set_size(DISPLAY_WIDTH, int(DISPLAY_HEIGHT * 0.4))  # 保持原有比例
        self.keyboard.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.keyboard.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)
        self.keyboard.set_style_radius(0, 0)
        self.keyboard.set_style_shadow_width(5, 0)
        self.keyboard.set_style_shadow_opa(lv.OPA._20, 0)
        self.keyboard.set_style_pad_all(0, 0)  # 移除填充

        # 创建临时输入显示区域
        self.temp_input_display = lv.textarea(self.keyboard_container)
        self.keyboard.set_textarea(self.temp_input_display)
        self.temp_input_display.set_size(DISPLAY_WIDTH, 60)
        self.temp_input_display.align_to(self.keyboard, lv.ALIGN.OUT_TOP_MID, 0, 0)
        self.temp_input_display.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.temp_input_display.set_style_radius(0, 0)
        self.temp_input_display.set_style_border_width(1, 0)
        self.temp_input_display.set_style_border_color(lv.color_hex(0xDDDDDD), 0)
        self.temp_input_display.set_style_pad_all(10, 0)
        self.temp_input_display.set_one_line(False)
        self.temp_input_display.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
        self.temp_input_display.set_text("")

        # 创建中文输入法候选区 - 增加高度
        self.ime_container = lv.obj(self.keyboard_container)
        self.ime_container.set_size(DISPLAY_WIDTH, 80)  # 增加高度从50到80
        self.ime_container.align_to(self.temp_input_display, lv.ALIGN.OUT_TOP_MID, 0, 0)
        self.ime_container.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)  # 改为浅灰色背景与键盘一致
        self.ime_container.set_style_border_width(0, 0)  # 移除边框
        self.ime_container.set_style_pad_all(10, 0)  # 增加内边距
        self.ime_container.set_style_radius(0, 0)
        self.ime_container.add_flag(lv.obj.FLAG.HIDDEN)
        
        # 拼音显示
        self.pinyin_label = lv.label(self.ime_container)
        self.pinyin_label.set_text("")
        self.pinyin_label.align(lv.ALIGN.LEFT_MID, 5, 0)
        self.pinyin_label.set_style_text_color(lv.color_hex(0x007AFF), 0)
        self.pinyin_label.set_style_text_font(lv.font_yb_cn_16, 0)  # 增大字体
        
        # 修改候选词按钮容器的设置
        self.candidates_container = lv.obj(self.ime_container)
        self.candidates_container.set_size(DISPLAY_WIDTH - 100, 60)
        self.candidates_container.align(lv.ALIGN.RIGHT_MID, -60, 0)
        self.candidates_container.set_flex_flow(lv.FLEX_FLOW.ROW)
        self.candidates_container.set_flex_align(lv.FLEX_ALIGN.SPACE_EVENLY, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
        self.candidates_container.set_style_pad_all(0, 0)
        self.candidates_container.set_style_bg_opa(lv.OPA.TRANSP, 0)
        self.candidates_container.set_style_border_width(0, 0)
        
        # 禁用滚动
        self.candidates_container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.candidates_container.clear_flag(lv.obj.FLAG.SCROLLABLE)
        
        # 创建翻页按钮 - iOS风格
        self.prev_btn = lv.btn(self.ime_container)
        self.prev_btn.set_size(40, 40)  # 增大按钮
        self.prev_btn.align(lv.ALIGN.RIGHT_MID, -40, 0)  # 修改对齐位置
        self.prev_btn.add_event(self.prev_page_cb, lv.EVENT.CLICKED, None)
        self.prev_btn.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)  # 与背景同色
        self.prev_btn.set_style_bg_color(lv.color_hex(0xE5E5E7), lv.STATE.PRESSED)  # 按下时的颜色
        self.prev_btn.set_style_shadow_width(0, 0)  # 无阴影
        self.prev_btn.set_style_border_width(0, 0)  # 无边框
        prev_label = lv.label(self.prev_btn)
        prev_label.set_text("<")
        prev_label.set_style_text_color(lv.color_hex(0x007AFF), 0)  # iOS蓝色
        prev_label.center()
        
        self.next_btn = lv.btn(self.ime_container)
        self.next_btn.set_size(40, 40)  # 增大按钮
        self.next_btn.align(lv.ALIGN.RIGHT_MID, 5, 0)  # 修改对齐位置
        self.next_btn.add_event(self.next_page_cb, lv.EVENT.CLICKED, None)
        self.next_btn.set_style_bg_color(lv.color_hex(0xF5F5F7), 0)  # 与背景同色
        self.next_btn.set_style_bg_color(lv.color_hex(0xE5E5E7), lv.STATE.PRESSED)  # 按下时的颜色
        self.next_btn.set_style_shadow_width(0, 0)  # 无阴影
        self.next_btn.set_style_border_width(0, 0)  # 无边框
        next_label = lv.label(self.next_btn)
        next_label.set_text(">")
        next_label.set_style_text_color(lv.color_hex(0x007AFF), 0)  # iOS蓝色
        next_label.center()
        
        # 创建中英文切换按钮 - iOS风格
        self.toggle_lang_btn = lv.btn(self.keyboard)
        self.toggle_lang_btn.set_size(70, 40)
        self.toggle_lang_btn.align(lv.ALIGN.BOTTOM_LEFT, 5, 5)
        self.toggle_lang_btn.add_event(self.toggle_lang_cb, lv.EVENT.CLICKED, None)
        self.toggle_lang_btn.set_style_bg_color(lv.color_hex(0xD1D1D6), 0)  # iOS灰色按钮
        self.toggle_lang_btn.set_style_radius(5, 0)  # 轻微圆角
        self.toggle_lang_label = lv.label(self.toggle_lang_btn)
        self.toggle_lang_label.set_text("中")
        self.toggle_lang_label.center()
        
        # 设置键盘事件回调
        self.keyboard.add_event(self.custom_keyboard_event_cb, lv.EVENT.VALUE_CHANGED, None)
        self.keyboard.set_mode(lv.keyboard.MODE.TEXT_LOWER)

    def overlay_click_cb(self, evt):
        self.hide()

    def show(self):
        self.keyboard_container.clear_flag(lv.obj.FLAG.HIDDEN)
        self.keyboard_visible = True
        current_text = self.target_textarea.get_text()
        self.temp_input_display.set_text(current_text)
        self.temp_input_display.set_cursor_pos(len(current_text))
        self.temp_input_display.add_state(lv.STATE.FOCUSED)

    def hide(self):
        self.keyboard_container.add_flag(lv.obj.FLAG.HIDDEN)
        self.keyboard_visible = False
        self.target_textarea.set_text(self.temp_input_display.get_text())
        lv.group_focus_obj(None)
        self.ime.clear()
        self.update_ime_display()

    def custom_keyboard_event_cb(self, e):
        kb = lv.keyboard.__cast__(e.get_target())
        code = e.get_code()
        if code == lv.EVENT.VALUE_CHANGED:
            btn_id = kb.get_selected_btn()
            key = kb.get_btn_text(btn_id)
            pass
            if key == "":  # 处理删除键
                # 完全自己处理删除逻辑，不依赖键盘默认行为
                if self.ime_active and self.ime.current_pinyin:
                    self.ime.process_input("⌫")
                    self.update_ime_display()
                return
                
            if key and self.ime_active:
                processed = self.ime.process_input(key)
                if processed:
                    self.update_ime_display()
                    return
    
    def update_ime_display(self):
        ime_state = self.ime.get_current_state()
        
        # 更新拼音显示
        self.pinyin_label.set_text(ime_state["pinyin"])
        
        # 更新候选词按钮
        self.candidates_container.clean()
        
        candidates_count = len(ime_state["candidates"])
        if candidates_count > 0:
            btn_width = ((self.candidates_container.get_width() - 20) // 10)
            btn_width = max(btn_width, 20)  # 确保最小宽度
            
            for i, candidate in enumerate(ime_state["candidates"]):
                btn = lv.btn(self.candidates_container)
                btn.set_size(btn_width, 45)
                
                # iOS风格的按钮样式
                btn.set_style_radius(0, 0)
                btn.set_style_bg_opa(lv.OPA.TRANSP, 0)
                btn.set_style_border_width(0, 0)
                btn.set_style_shadow_width(0, 0)
                
                # 按下状态的样式
                btn.set_style_bg_opa(lv.OPA._20, lv.STATE.PRESSED)
                btn.set_style_bg_color(lv.color_hex(0x000000), lv.STATE.PRESSED)
                
                def make_cb(idx):
                    def cb(e):
                        self.ime.select_candidate(idx)
                        self.update_ime_display()
                    return cb
                
                btn.add_event(make_cb(i), lv.EVENT.CLICKED, None)
                
                label = lv.label(btn)
                label.set_text(candidate)
                label.set_style_text_color(lv.color_hex(0x232324), 0) 
                label.set_style_text_font(lv.font_yb_cn_16, 0)
                label.center()
        
        # 更新翻页按钮状态
        if ime_state["has_prev"]:
            self.prev_btn.clear_state(lv.STATE.DISABLED)
        else:
            self.prev_btn.add_state(lv.STATE.DISABLED)
            
        if ime_state["has_next"]:
            self.next_btn.clear_state(lv.STATE.DISABLED)
        else:
            self.next_btn.add_state(lv.STATE.DISABLED)
        
        # 显示或隐藏输入法面板
        if ime_state["pinyin"] or ime_state["candidates"]:
            self.ime_container.clear_flag(lv.obj.FLAG.HIDDEN)
        else:
            self.ime_container.add_flag(lv.obj.FLAG.HIDDEN)    
        
    def candidate_click_cb(self, e, index):
        self.ime.select_candidate(index)
        self.update_ime_display()

    def prev_page_cb(self, e):
        self.ime.process_input("<")
        self.update_ime_display()

    def next_page_cb(self, e):
        self.ime.process_input(">")
        self.update_ime_display()

    def toggle_lang_cb(self, e):
        self.ime_active = not self.ime_active
        
        if self.ime_active:
            self.toggle_lang_label.set_text("英")
            # 切换到拼音输入模式
            self.ime.clear()
            self.update_ime_display()
        else:
            self.toggle_lang_label.set_text("中")
            # 切换到英文输入模式
            self.ime_container.add_flag(lv.obj.FLAG.HIDDEN)