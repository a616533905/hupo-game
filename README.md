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

### 安全特性
- **Token 认证**: 所有 API 端点支持 Token 验证
- **请求频率限制**: 防止单IP滥用API（默认100次/分钟）
- **请求体大小限制**: 最大 10MB，防止内存耗尽攻击
- **本地端点保护**: `/health`、`/metrics`、`/model` 仅允许本地访问
- **格式白名单**: 音频格式验证，防止文件扩展名注入

### 稳定性特性
- **线程安全**: Prometheus 指标和频率限制数据使用锁保护
- **HTTP 超时**: 所有外部 API 调用设置 30 秒超时
- **日志记录**: 详细的请求日志，按日期轮转
- **配置验证**: 启动时自动验证配置文件格式
- **优雅关闭**: 支持平滑重启，不中断当前请求

### 监控特性
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
├── status.bat            # Windows 状态查看脚本
├── status.sh             # Linux 状态查看脚本
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
        "host": "localhost",
        "http_port": 80,
        "https_port": 443,
        "voice_port": 85,
        "remote_host": "http://你的服务器IP/",
        "ssl_cert_file": "cert.pem",
        "ssl_key_file": "key.pem"
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

### Token 认证

启用 Token 认证保护 API：

```json
{
    "access_token": "your_secure_token",
    "token_required": "yes"
}
```

启用后，所有 API 请求需要携带 Token：
- URL 参数: `?token=your_secure_token`
- Cookie: `hupo_token=your_secure_token`
- 请求体: `{"token": "your_secure_token", ...}`
- Authorization 头: `Bearer your_secure_token`

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

### 主服务 (端口 80)

| 端点 | 方法 | 认证 | 访问限制 | 说明 |
|------|------|------|----------|------|
| `/health` | GET | - | 仅本地 | 健康检查（含CPU/内存/磁盘状态） |
| `/metrics` | GET | - | 仅本地 | Prometheus 监控指标 |
| `/model` | GET | - | 仅本地 | 获取当前模型信息 |
| `/chat` | POST | Token | - | AI 对话接口 |
| `/tts` | POST | Token | - | 语音合成接口 |
| `/asr` | POST | Bearer | - | 语音识别接口 |
| `/*` | GET | Token/Cookie | - | 静态文件服务 |

### 语音服务 (端口 85)

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/voice/config` | GET | Token | 获取语音配置 |
| `/voice/token` | GET | Token | 获取百度语音 Token |
| `/voice/recognize` | POST | Token | 语音识别接口 |

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
# 使用状态脚本
./status.sh

# 或使用 systemctl
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

## 配置参数

### 请求限制

修改 `nanobot_bridge.py` 中的配置：
```python
RATE_LIMIT_WINDOW = 60        # 频率限制时间窗口（秒）
RATE_LIMIT_MAX_REQUESTS = 100 # 每IP每窗口最大请求数
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 请求体最大大小（字节）
HTTP_TIMEOUT = 30             # HTTP 请求超时（秒）
MAX_HISTORY_LENGTH = 20       # 对话历史最大长度
```

### 语音服务配置

修改 `voice-proxy.js` 中的配置：
```javascript
const MAX_BODY_SIZE = 10 * 1024 * 1024;  // 请求体最大大小
const ALLOWED_FORMATS = ['webm', 'mp3', 'wav', 'ogg', 'm4a', 'aac'];  // 允许的音频格式
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
A: 
- Linux: 运行 `./status.sh`
- Windows: 运行 `status.bat`
- 或访问 `http://localhost/health`（仅本地）

**Q: Token 认证失败？**
A: 确保 `config.json` 中 `token_required` 设置为 `yes`，且请求携带正确的 `access_token`

**Q: 请求体过大错误？**
A: 默认限制 10MB，如需调整请修改 `MAX_CONTENT_LENGTH`

## 更新日志

### v1.1.0 (最新)
- 添加线程安全保护（Prometheus 指标、频率限制数据）
- 添加 HTTP 请求超时设置（30秒）
- 添加请求体大小限制（10MB）
- 添加音频格式白名单验证
- 添加 `/voice/config` 端点认证
- 添加 `/model` 端点本地访问限制
- 改进 JSON 解析错误处理
- 改进环境变量解析异常处理
- 修复命令注入漏洞（使用 spawn 替代 exec）
- 修复内存泄漏（频率限制数据定期清理）

### v1.0.0
- 初始版本发布
- 支持 MiniMax、OpenRouter、Ollama AI 提供商
- 支持百度语音识别
- 支持请求频率限制
- 支持 Prometheus 监控
- 支持 Systemd 服务管理

## License

MIT License
