> 把「每天手动打开小精灵看任务」变成「跑一条命令」，这是整个过程的一篇探索笔记。
> 记录于 2026-08-27

## 起因

《光·遇》的每日任务每天凌晨刷新，平时要拿「今日任务指南」得打开游戏，点进小精灵翻半天。既然电脑上挂着模拟器、又懂一点抓包，为什么不把这件事自动化？

于是开始了一场从「抓包」到「一条命令搞定」的探索。

## 探索过程

### 第一步：找到问答接口

用 Charles 抓包，发现游戏里的小精灵其实是一个 H5 页面，所有问答都走同一个统一接口：

```text
POST https://<接口域名已脱敏>/sprite/api/ma75/knowledge/get
```

请求体也很直观，带上问题就行：

```json
{
  "ismanual": 0,
  "loginFrom": "sprite",
  "method": "link",
  "question": "今日任务指南"
}
```

接口本身很简单，但请求头里带着一个 `token` —— 没有它，服务器直接拒绝。这引出了核心问题：**token 从哪来？**

### 第二步：识别出 token 是 JWT

把 token 拿出来一看，很有特点：三段、用点号 `.` 分隔。

```text
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3ODc2NTI1OTUsInV1aWQiOiJzZXJ2ZXIubWE3NS4uLiJ9.JD47dD8lxZtg...
```

这是 JWT（JSON Web Token）的典型结构：头 + 载荷 + 签名。把中间那段 Base64 解码，信息一目了然：

| 字段 | 含义 | 示例 |
|---|---|---|
| `exp` | 过期时间（Unix 时间戳） | 1787652595 |
| `uuid` | 会话标识 | server.ma75.xxx |

关键结论：**token 约 2 小时就会过期**。如果每次都要抓包重新拿，自动化就毫无意义。

### 第三步：顺藤摸瓜，找到 token 的签发接口

拿着这个线索，在抓包记录里搜索 token 出现的地方，终于找到了源头——进入小精灵时，客户端会先向另一个接口「要 token」：

```text
POST http://<接口域名已脱敏>:9005/gms_cmd
Content-Type: application/x-www-form-urlencoded
User-Agent: Dalvik/2.1.0 (Linux; U; Android 12; MuMu Build/V417IR)
```

请求体是一段 JSON（账号标识已脱敏）：

```json
{
  "cmd": "kefu_get_token",
  "uid": "aebg**********@ios.netease.win.163.com",
  "game_uid": "65df**********",
  "os": "android",
  "game_server": 8000,
  "login_from": 0,
  "map": "CandleSpace",
  "return_buff": "true"
}
```

返回的 `result` 字段里带着 token —— 和之后向小精灵提问时携带的 token **完全一致**。链路打通了。

### 第四步：写成脚本

于是把整个流程串起来：检测 token 是否过期 → 过期就调 `kefu_get_token` 自动获取 → 带 token 提问 → 解析答案。

```python
# 核心逻辑（简化版）
import base64, json, time, requests

def decode_jwt(token):
    """JWT 第二段就是 payload，Base64 解码即可"""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=="))

def get_token():
    """自动获取 token"""
    resp = requests.post(GM_API, data=json.dumps({
        "cmd": "kefu_get_token", "uid": UID, "game_uid": GAME_UID,
        "os": "android", "game_server": 8000,
        "login_from": 0, "map": "CandleSpace", "return_buff": "true",
    }), headers={"content-type": "application/x-www-form-urlencoded"})
    return json.loads(resp.json()["result"])["token"]

token = get_token()  # 或从本地读取已保存的 token
if decode_jwt(token)["exp"] < time.time():  # 已过期就刷新
    token = get_token()

resp = requests.post(ASK_API, json={
    "ismanual": 0, "loginFrom": "sprite",
    "method": "link", "question": "今日任务指南",
}, headers={"token": token})
print(resp.json()["data"]["answer"])
```

## 最终效果

现在只需要一条命令：

```text
python sky_fetch.py
```

脚本会自动完成：

1. 读取本地配置，检查有没有可用的 token、有没有过期；
2. 没有就调 `kefu_get_token` 接口获取新 token；
3. 带着 token 向问答接口发「今日任务指南」；
4. 解析出当天的任务、攻略链接、配图，并生成带密码门的网页。

实测输出（2026-08-27 的今日任务）：

```text
【今日旅行指南】
1. 向一位玩家鞠躬
2. 点亮一位玩家
3. 收集30点烛火
4. 前往云野重温欢笑追光者的回忆 >>先祖位置
5. 今日季节蜡烛所在地图：云野  >>点击查看
6. 专属客服7x8小时在线
```

## 经验总结

1. **抓包先找「数据源头」**：问答接口要 token，就去抓包里搜 token 第一次出现的地方，顺着链路找签发接口，比瞎猜接口快得多。
2. **识别 JWT 很简单**：三段点号结构 + 开头 `eyJ`（Base64 的 `{"`），一眼就能认出来；中间段可以直接解码看内容。
3. **自包含令牌的好处**：JWT 把过期时间写在自己身上，所以「过期检测」不需要调任何接口，本地解码就算得出来。
4. **客户端接口通常带版本号**：`/api/ma75/...` 的 `ma75` 就是小精灵功能版本号，接口变了先看它。

## 安全提醒

本笔记涉及的请求中，`uid` / `game_uid` 是账号标识，相当于半张登录凭证，**文中均已脱敏**。请勿随意分享原始抓包数据；本页已设置访问密码，仅限朋友间传阅。

---

*以上探索仅供学习交流，请合理使用。*
