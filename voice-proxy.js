const http = require('http');
const https = require('https');
const url = require('url');
const os = require('os');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const MAX_BODY_SIZE = 10 * 1024 * 1024;
const ALLOWED_FORMATS = ['webm', 'mp3', 'wav', 'ogg', 'm4a', 'aac'];
const TEMP_FILE_MAX_AGE = 3600000;

const CONFIG_FILE = path.join(__dirname, 'config.json');
const LOG_DIR = path.join(__dirname, 'logs');
const TEMP_DIR = os.tmpdir();

const activeProcesses = new Set();
const activeConnections = new Set();

if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
}

function cleanupOldTempFiles() {
    try {
        const files = fs.readdirSync(TEMP_DIR);
        const now = Date.now();
        let cleaned = 0;
        
        files.forEach(file => {
            if (file.startsWith('hupo_voice_')) {
                const filePath = path.join(TEMP_DIR, file);
                try {
                    const stats = fs.statSync(filePath);
                    if (now - stats.mtimeMs > TEMP_FILE_MAX_AGE) {
                        fs.unlinkSync(filePath);
                        cleaned++;
                    }
                } catch (e) {
                    // File might be in use or already deleted
                }
            }
        });
        
        if (cleaned > 0) {
            log(`[Cleanup] Removed ${cleaned} old temp files`);
        }
    } catch (e) {
        log(`[Cleanup] Error: ${e.message}`);
    }
}

setInterval(cleanupOldTempFiles, 300000);
cleanupOldTempFiles();

process.on('exit', () => {
    activeProcesses.forEach(proc => {
        try {
            proc.kill('SIGTERM');
        } catch (e) {}
    });
});

function getLogFileName() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `voice_${year}${month}${day}.log`;
}

function formatTimestamp() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

function log(level, message) {
    const timestamp = formatTimestamp();
    const logLine = `${timestamp} [${level}] ${message}`;
    
    console.log(logLine);
    
    const logFile = path.join(LOG_DIR, getLogFileName());
    fs.appendFileSync(logFile, logLine + '\n', 'utf8');
}

function logInfo(message) {
    log('INFO', message);
}

function logError(message) {
    log('ERROR', message);
}

function getDebugLogFileName() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `voice_debug_${year}${month}${day}.log`;
}

function logDebug(message) {
    const timestamp = formatTimestamp();
    const logLine = `${timestamp} [DEBUG] ${message}`;
    const debugLogFile = path.join(LOG_DIR, getDebugLogFileName());
    fs.appendFileSync(debugLogFile, logLine + '\n', 'utf8');
}

function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const data = fs.readFileSync(CONFIG_FILE, 'utf-8');
            const cfg = JSON.parse(data);
            if (cfg.environments) {
                const runtimeMode = cfg.runtime_mode || 'local';
                const envCfg = cfg.environments[runtimeMode] || {};
                ['server', 'access_token', 'token_required', 'active_provider', 'audit', 'voice'].forEach(key => {
                    if (key in envCfg && !(key in cfg)) {
                        cfg[key] = envCfg[key];
                    }
                });
            }
            return cfg;
        }
    } catch (e) {
        logError('配置文件加载失败: ' + e.message);
    }
    return {};
}

const config = loadConfig();

const voiceConfig = config.voice || {};
const VOICE_PROVIDER = voiceConfig.provider || 'browser';

const baidu = config.baidu || {};
const BAIDU_API_KEY = baidu.api_key || '';
const BAIDU_SECRET_KEY = baidu.secret_key || '';

const MAX_AUDIO_SIZE = 10 * 1024 * 1024;
const AUDIO_MAGIC_NUMBERS = {
    webm: [0x1a, 0x45, 0xdf, 0xa3],
    mp4: [0x00, 0x00, 0x00, null, 0x66, 0x74, 0x79, 0x70],
    ogg: [0x4f, 0x67, 0x67, 0x53],
    wav: [0x52, 0x49, 0x46, 0x46]
};

function validateAudioFormat(buffer, format) {
    const magic = AUDIO_MAGIC_NUMBERS[format];
    if (!magic) return true;
    for (let i = 0; i < magic.length; i++) {
        if (magic[i] !== null && buffer[i] !== magic[i]) {
            return false;
        }
    }
    return true;
}

function audioToPcm(audioBase64, format) {
    return new Promise((resolve, reject) => {
        if (!ALLOWED_FORMATS.includes(format)) {
            return reject(new Error('Invalid audio format'));
        }
        
        const ext = format;
        const timestamp = Date.now();
        const randomSuffix = Math.random().toString(36).substring(7);
        const tempAudio = path.join(TEMP_DIR, `hupo_voice_${timestamp}_${randomSuffix}.${ext}`);
        const tempPcm = path.join(TEMP_DIR, `hupo_voice_${timestamp}_${randomSuffix}.pcm`);

        let audioBuffer;
        try {
            audioBuffer = Buffer.from(audioBase64, 'base64');
        } catch (e) {
            return reject(new Error('Invalid base64 audio data'));
        }
        
        if (audioBuffer.length > MAX_AUDIO_SIZE) {
            return reject(new Error('Audio file too large (max 10MB)'));
        }
        
        if (!validateAudioFormat(audioBuffer, format)) {
            return reject(new Error('Audio format verification failed'));
        }

        fs.writeFileSync(tempAudio, audioBuffer);

        const cleanup = () => {
            try { fs.unlinkSync(tempAudio); } catch (e) {}
            try { fs.unlinkSync(tempPcm); } catch (e) {}
        };

        const ffmpeg = spawn('ffmpeg', [
            '-y', '-i', tempAudio,
            '-f', 's16le', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1', tempPcm
        ], { 
            timeout: 30000,
            maxBuffer: MAX_AUDIO_SIZE
        });

        activeProcesses.add(ffmpeg);
        
        let stderr = '';
        ffmpeg.stderr.on('data', (data) => { stderr += data; });

        ffmpeg.on('close', (code) => {
            activeProcesses.delete(ffmpeg);
            if (code !== 0) {
                cleanup();
                reject(new Error('音频转换失败: ' + stderr));
                return;
            }

            try {
                const pcmBuffer = fs.readFileSync(tempPcm);
                cleanup();
                resolve({
                    base64: pcmBuffer.toString('base64'),
                    len: pcmBuffer.length,
                    buffer: pcmBuffer
                });
            } catch (e) {
                cleanup();
                reject(e);
            }
        });

        ffmpeg.on('error', (err) => {
            activeProcesses.delete(ffmpeg);
            cleanup();
            reject(new Error('ffmpeg启动失败: ' + err.message));
        });
    });
}

function webmToPcm(webmBase64) {
    return audioToPcm(webmBase64, 'webm');
}

async function recognizeBaidu(speech, token, format) {
    let pcmData;
    try {
        pcmData = await audioToPcm(speech, format || 'webm');
        logInfo('百度PCM转换成功, 长度: ' + pcmData.len + ' bytes');
    } catch (convertError) {
        logError('PCM转换失败: ' + convertError.message);
        pcmData = { base64: speech, len: Buffer.from(speech, 'base64').length };
    }

    const requestBody = {
        format: 'pcm',
        rate: 16000,
        dev_pid: 1537,
        channel: 1,
        cuid: 'hupo_cat_game',
        token: token,
        speech: pcmData.base64,
        len: pcmData.len
    };

    logInfo('发送到百度API, len: ' + pcmData.len);

    const apiRes = await fetch('https://vop.baidu.com/server_api', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    });

    const BAIDU_ERROR_MAP = {
        '3300': '输入参数不正确，请检查请求参数',
        '3301': '音频质量过差，请上传清晰的音频',
        '3302': '鉴权失败，请检查API_KEY和SECRET_KEY是否正确，或QPS/调用量是否超限',
        '3303': '百度服务器繁忙，请稍后重试',
        '3304': '请求并发超限，请降低识别频率',
        '3305': '日请求量超限，请开通付费购买调用量',
        '3307': '语音服务器识别出错，请重试',
        '3308': '音频时长超过60秒，请截取后重试',
        '3309': '音频数据无法转为pcm格式，请检查音频编码和采样率',
        '3310': '音频文件过大，请确保音频时长不超过60秒',
        '3311': '采样率不支持，目前仅支持16000和8000',
        '3312': '音频格式不支持，目前仅支持pcm、wav、amr',
        '3313': '语音服务器解析超时，请重试',
        '3314': '音频长度过短，请录制更长的音频',
        '3315': '语音服务器处理超时，请重试',
        '3316': '音频转为pcm失败，请确认音频格式和采样率正确',
    };

    const getBaiduErrorMsg = (err_no) => {
        const key = String(err_no);
        return BAIDU_ERROR_MAP[key] || '识别失败，请重试';
    };

    const httpStatus = apiRes.status;
    const data = await apiRes.json();
    logInfo('百度API响应: HTTP ' + httpStatus + ', err_no=' + data.err_no + ', err_msg=' + data.err_msg);

    if (data.err_no === 0 && data.result && data.result.length > 0) {
        logDebug('[百度识别] 识别结果: ' + data.result[0]);
        return {
            success: true,
            text: data.result[0],
            provider: 'baidu'
        };
    } else {
        const userMsg = getBaiduErrorMsg(data.err_no);
        logError('百度识别失败: HTTP ' + httpStatus + ', err_no=' + data.err_no + ', err_msg=' + data.err_msg);
        return {
            success: false,
            error: userMsg,
            err_no: data.err_no,
            http_status: httpStatus,
            provider: 'baidu'
        };
    }
}

const sslCertFile = config.server?.ssl_cert_file || config.ssl_cert_file || config.ssl?.cert || '';
const sslKeyFile = config.server?.ssl_key_file || config.ssl_key_file || config.ssl?.key || '';

logInfo('SSL配置检查:');
logInfo('  ssl_cert_file: ' + (config.server?.ssl_cert_file || config.ssl_cert_file || '未配置'));
logInfo('  ssl_key_file: ' + (config.server?.ssl_key_file || config.ssl_key_file || '未配置'));
logInfo('  cert文件存在: ' + (sslCertFile && fs.existsSync(sslCertFile) ? '是' : '否'));
logInfo('  key文件存在: ' + (sslKeyFile && fs.existsSync(sslKeyFile) ? '是' : '否'));

const requestHandler = async (req, res) => {
    activeConnections.add(req.socket);
    req.socket.on('close', () => {
        activeConnections.delete(req.socket);
    });
    
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    const parsedUrl = url.parse(req.url, true);
    const ACCESS_TOKEN = config.access_token || '';
    const TOKEN_REQUIRED = config.token_required || 'no';

    function verifyToken(reqToken) {
        if (TOKEN_REQUIRED !== 'yes' || !ACCESS_TOKEN) {
            return true;
        }
        return reqToken === ACCESS_TOKEN;
    }

    if (parsedUrl.pathname === '/voice/config') {
        const queryToken = parsedUrl.query.token || '';
        if (!verifyToken(queryToken)) {
            logInfo('Token验证失败: /voice/config');
            res.writeHead(401, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Unauthorized: invalid token' }));
            return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            provider: VOICE_PROVIDER,
            baidu: !!(BAIDU_API_KEY && BAIDU_SECRET_KEY),
            browser: true
        }));
        return;
    }

    if (parsedUrl.pathname === '/voice/token') {
        const queryToken = parsedUrl.query.token || '';
        if (!verifyToken(queryToken)) {
            logInfo('Token验证失败: /voice/token');
            res.writeHead(401, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Unauthorized: invalid token' }));
            return;
        }
        
        if (VOICE_PROVIDER !== 'baidu') {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: '当前语音提供商不是百度' }));
            return;
        }
        
        if (!BAIDU_API_KEY || !BAIDU_SECRET_KEY) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: '百度API未配置，请在config.json中设置baidu.api_key和baidu.secret_key' }));
            return;
        }

        try {
            const tokenRes = await fetch('https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=' + BAIDU_API_KEY + '&client_secret=' + BAIDU_SECRET_KEY, {
                method: 'POST'
            });
            const data = await tokenRes.json();
            logInfo('Token响应: ' + JSON.stringify(data));
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
        } catch (e) {
            logError('Token错误: ' + e);
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: e.message }));
        }
        return;
    }

    if (parsedUrl.pathname === '/voice/recognize') {
        let body = '';
        let bodySize = 0;
        req.on('data', chunk => {
            bodySize += chunk.length;
            if (bodySize > MAX_BODY_SIZE) {
                res.writeHead(413, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: false, error: '请求体过大，最大10MB' }));
                req.destroy();
                return;
            }
            body += chunk;
        });
        req.on('end', async () => {
            try {
                let parsedBody;
                try {
                    parsedBody = JSON.parse(body);
                } catch (parseError) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ success: false, error: '无效的JSON格式' }));
                    return;
                }
                const { speech, token, provider, format, access_token } = parsedBody;
                
                if (!speech) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ success: false, error: '缺少speech参数' }));
                    return;
                }
                
                if (!verifyToken(access_token)) {
                    logInfo('Token验证失败: /voice/recognize');
                    res.writeHead(401, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ 
                        success: false,
                        error: 'Unauthorized: invalid token'
                    }));
                    return;
                }
                
                const useProvider = provider || VOICE_PROVIDER;
                const audioFormat = format || 'webm';
                
                if (format && !ALLOWED_FORMATS.includes(format)) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ 
                        success: false,
                        error: '不支持的音频格式: ' + format + '，支持: ' + ALLOWED_FORMATS.join(', ')
                    }));
                    return;
                }
                
                logInfo('收到识别请求, 提供商: ' + useProvider + ' 格式: ' + audioFormat + ' 音频base64长度: ' + speech.length);

                if (useProvider === 'baidu') {
                    if (!BAIDU_API_KEY || !BAIDU_SECRET_KEY) {
                        res.writeHead(500, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify({ 
                            success: false,
                            error: '百度API未配置，请在config.json中设置baidu.api_key和baidu.secret_key',
                            provider: 'baidu'
                        }));
                        return;
                    }
                    const result = await recognizeBaidu(speech, token, audioFormat);
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify(result));
                } else {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ 
                        success: false,
                        error: '不支持的语音提供商: ' + useProvider,
                        provider: useProvider
                    }));
                }
            } catch (e) {
                logError('识别错误: ' + e);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ 
                    success: false,
                    error: e.message,
                    provider: VOICE_PROVIDER
                }));
            }
        });
        return;
    }

    res.writeHead(404);
    res.end('Not Found');
};

let server;
let protocol = 'http';

if (sslCertFile && sslKeyFile && fs.existsSync(sslCertFile) && fs.existsSync(sslKeyFile)) {
    try {
        const sslOptions = {
            cert: fs.readFileSync(sslCertFile),
            key: fs.readFileSync(sslKeyFile)
        };
        server = https.createServer(sslOptions, requestHandler);
        protocol = 'https';
        logInfo('HTTPS 已启用');
    } catch (e) {
        logError('SSL证书加载失败: ' + e.message + ', 使用HTTP');
        server = http.createServer(requestHandler);
    }
} else {
    server = http.createServer(requestHandler);
}

logInfo('语音代理服务器配置加载完成');
logInfo('配置文件: ' + CONFIG_FILE);
logInfo('当前语音提供商: ' + VOICE_PROVIDER);
logInfo('');
logInfo('语音提供商状态:');

if (BAIDU_API_KEY && BAIDU_SECRET_KEY) {
    logInfo('  百度API: ✓ 已配置');
} else {
    logInfo('  百度API: ✗ 未配置（请在config.json中设置baidu.api_key和baidu.secret_key）');
}

logInfo('');
const PORT = parseInt(process.env.VOICE_PORT) || config.server?.voice_port || 85;
server.listen(PORT, '0.0.0.0', () => {
    logInfo('语音代理服务器运行在 ' + protocol + '://0.0.0.0:' + PORT);
    logInfo('局域网访问: ' + protocol + '://<你的IP>:' + PORT);
});

let isShuttingDown = false;

function gracefulShutdown(signal) {
    if (isShuttingDown) return;
    isShuttingDown = true;
    
    logInfo('收到 ' + signal + ' 信号，正在关闭服务器...');
    
    if (activeProcesses.size > 0) {
        logInfo('终止 ' + activeProcesses.size + ' 个活跃的 ffmpeg 进程...');
        for (const proc of activeProcesses) {
            try {
                proc.kill('SIGTERM');
            } catch (e) {}
        }
        activeProcesses.clear();
    }
    
    if (activeConnections.size > 0) {
        logInfo('关闭 ' + activeConnections.size + ' 个活跃连接...');
        for (const conn of activeConnections) {
            try {
                conn.destroy();
            } catch (e) {}
        }
        activeConnections.clear();
    }
    
    server.close(() => {
        logInfo('服务器已关闭');
        process.exit(0);
    });
    
    setTimeout(() => {
        logError('强制退出');
        process.exit(1);
    }, 5000);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

process.on('exit', (code) => {
    logInfo('进程退出，代码: ' + code);
});
