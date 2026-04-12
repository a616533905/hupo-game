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

## 生产环境特性

- **日志记录**: 详细的请求日志，按日期轮转
- **配置验证**: 启动时自动验证配置文件格式
- **优雅关闭**: 支持平滑重启，不中断当前请求
- **请求频率限制**: 防止单IP滥用API（默认100次/分钟）
- **健康检查**: CPU/内存/磁盘监控
- **Prometheus监控**: 标准指标导出，支持Grafana可视化
- **Systemd服务**: 开机自启，崩溃自动重启

## 快速开始

### Windows 用户

```batch
# 方式1: 运行安装脚本（推荐首次安装）
install.bat

# 方式2: 直接启动
start.bat
```

浏览器访问: http://localhost

### Linux 服务器部署

```bash
# 方式1: 使用安装脚本（推荐）
chmod +x install.sh
sudo ./install.sh

# 方式2: 手动部署
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
├── index.html            # 游戏主程序（HTML + CSS + JS）
├── config.json           # 配置文件（AI、语音、服务器）
├── nanobot_bridge.py     # AI 桥接服务 + Web 服务器
├── voice-proxy.js        # 语音代理服务
├── start.bat             # Windows 启动脚本
├── start.sh              # Linux 启动脚本
├── install.bat           # Windows 安装脚本
├── install.sh            # Linux 安装脚本
├── hupo-bridge.service   # Systemd 服务配置
├── hupo-voice.service    # 语音服务 Systemd 配置
├── logrotate.conf        # 日志轮转配置
├── favicon.ico           # 网站图标
├── README.md             # 说明文档
└── logs/                 # 日志目录（自动创建）
```

## 环境要求

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.8+ | AI 桥接服务 |
| Node.js | 14+ | 语音代理服务 |
| ffmpeg | 任意版本 | 音频格式转换（语音识别必需） |
| psutil | 最新版 | 系统监控（自动安装） |

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

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（含CPU/内存/磁盘状态） |
| `/metrics` | GET | Prometheus 监控指标 |
| `/chat` | POST | AI 对话接口 |
| `/tts` | POST | 语音合成接口 |
| `/model` | GET | 获取当前模型信息 |

### 健康检查示例

```bash
curl http://localhost:80/health
```

响应：
```json
{
    "status": "ok",
    "uptime": 3600.5,
    "cpu_percent": 15.2,
    "memory_percent": 42.8,
    "disk_percent": 55.0,
    "requests_total": 1234
}
```

### Prometheus 监控

```bash
curl http://localhost:80/metrics
```

可用指标：
- `hupo_requests_total` - 总请求数
- `hupo_requests_success` - 成功请求数
- `hupo_requests_error` - 失败请求数
- `hupo_chat_requests` - Chat API 请求数
- `hupo_tts_requests` - TTS API 请求数
- `hupo_cpu_percent` - CPU 使用率
- `hupo_memory_percent` - 内存使用率
- `hupo_uptime_seconds` - 运行时间

## 服务管理

### 启动服务

```bash
systemctl start hupo-bridge
systemctl start hupo-voice
```

### 停止服务

```bash
systemctl stop hupo-bridge
systemctl stop hupo-voice
```

### 重启服务

```bash
systemctl restart hupo-bridge
systemctl restart hupo-voice
```

### 查看状态

```bash
systemctl status hupo-bridge
systemctl status hupo-voice
```

### 查看日志

```bash
# Systemd 日志
journalctl -u hupo-bridge -f

# 应用日志
tail -f /root/hupo-game/logs/bridge_*.log
```

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

## 请求频率限制

默认限制：每个IP每分钟最多100次请求

修改 `nanobot_bridge.py` 中的配置：
```python
RATE_LIMIT_WINDOW = 60        # 时间窗口（秒）
RATE_LIMIT_MAX_REQUESTS = 100 # 最大请求数
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

**Q: 请求频率超限？**
A: 默认每IP每分钟100次请求，可在代码中调整限制

**Q: 如何查看系统状态？**
A: 访问 http://服务器IP/health 查看CPU/内存状态

## License

MIT License
