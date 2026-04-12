# 琥珀猫冒险

一个可爱的猫咪养成冒险游戏，支持 AI 对话、语音识别、战斗系统、探索冒险等功能。

## 功能特性

- **AI 对话**: 支持多种 AI 提供商（MiniMax、OpenRouter、Ollama）
- **语音识别**: 百度语音识别，支持多种音频格式
- **语音合成**: Edge TTS / 浏览器原生 TTS
- **战斗系统**: 回合制战斗，技能系统，伙伴系统
- **探索冒险**: 多地图探索，随机事件，NPC 互动
- **养成系统**: 等级、装备、皮肤、成就
- **竞技场**: PVP 对战，排名系统

## 快速开始

### Windows 用户

```batch
# 双击运行 start.bat
# 或命令行执行：
start.bat
```

浏览器访问: http://localhost

### Linux 服务器部署

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3 nodejs npm ffmpeg

# 2. 上传文件到服务器
scp -r hupo-game root@你的服务器IP:/root/

# 3. 启动服务
cd /root/hupo-game
chmod +x start.sh
./start.sh
```

### 手机访问

1. 电脑/服务器运行启动脚本
2. 手机连接同一局域网
3. 手机浏览器访问显示的局域网地址

## 文件说明

```
hupo-game/
├── index.html          # 游戏主程序（HTML + CSS + JS）
├── config.json         # 配置文件（AI、语音、服务器）
├── nanobot_bridge.py   # AI 桥接服务 + Web 服务器
├── voice-proxy.js      # 语音代理服务
├── start.bat           # Windows 启动脚本
├── start.sh            # Linux 启动脚本
├── favicon.ico         # 网站图标
├── README.md           # 说明文档
└── requirements.txt    # 依赖说明
```

## 环境要求

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.6+ | AI 桥接服务 |
| Node.js | 14+ | 语音代理服务 |
| ffmpeg | 任意版本 | 音频格式转换（语音识别必需） |

## 配置说明

编辑 `config.json` 配置各项服务：

```json
{
    "runtime_mode": "server",
    "server": {
        "api_port": 80,
        "voice_port": 85,
        "remote_host": "http://你的服务器IP/"
    },
    "access_token": "your_token",
    "token_required": "no",
    "minimax": {
        "api_key": "你的API密钥",
        "group_id": "你的GroupID"
    },
    "baidu": {
        "api_key": "百度API Key",
        "secret_key": "百度Secret Key"
    },
    "voice": {
        "provider": "baidu"
    },
    "active_provider": "minimax"
}
```

### 支持的 AI 提供商

| 提供商 | 说明 |
|--------|------|
| minimax | MiniMax AI（推荐） |
| openrouter | OpenRouter API |
| ollama | 本地 Ollama |

### 支持的语音提供商

| 提供商 | 说明 |
|--------|------|
| baidu | 百度语音识别（推荐） |
| browser | 浏览器原生语音识别 |

## 防火墙配置

```bash
# Ubuntu/Debian
sudo ufw allow 80/tcp
sudo ufw allow 85/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=80/tcp --permanent
sudo firewall-cmd --add-port=85/tcp --permanent
sudo firewall-cmd --reload
```

## 后台运行（systemd）

创建服务文件 `/etc/systemd/system/hupo-game.service`：

```ini
[Unit]
Description=Hupo Cat Game Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/hupo-game
ExecStart=/root/hupo-game/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable hupo-game
sudo systemctl start hupo-game
```

## 可选：本地 AI（Ollama）

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:270m
```

修改 `config.json`：
```json
{
    "active_provider": "ollama",
    "ollama": {
        "api_base": "http://localhost:11434/v1",
        "model": "gemma3:270m"
    }
}
```

## 浏览器兼容性

| 浏览器 | 支持程度 |
|--------|----------|
| Chrome | 完全支持 |
| Edge | 完全支持 |
| Firefox | 基本支持 |
| Safari | 基本支持 |
| 手机浏览器 | 需要HTTPS才能使用语音 |

## 常见问题

**Q: 语音识别不工作？**
A: 确保已安装 ffmpeg，并且语音代理服务已启动

**Q: 手机无法访问？**
A: 检查防火墙是否开放端口，确保手机和服务器在同一网络

**Q: AI 不回复？**
A: 检查 API Key 是否正确，查看控制台错误日志

## License

MIT License
