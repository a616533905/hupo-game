const http = require('http');
const https = require('https');
const url = require('url');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const MAX_BODY_SIZE = 10 * 1024 * 1024;
const ALLOWED_FORMATS = ['webm', 'mp3', 'wav', 'ogg', 'm4a', 'aac'];

const CONFIG_FILE = path.join(__dirname, 'config.json');
const LOG_DIR = path.join(__dirname, 'logs');

if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
}

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

function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const data = fs.readFileSync(CONFIG_FILE, 'utf-8');
            return JSON.parse(data);
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

function audioToPcm(audioBase64, format) {
    return new Promise((resolve, reject) => {
        const ext = ALLOWED_FORMATS.includes(format) ? format : 'webm';
        const timestamp = Date.now();
        const randomSuffix = Math.random().toString(36).substring(7);
        const tempAudio = path.join(__dirname, `temp_${timestamp}_${randomSuffix}.${ext}`);
        const tempPcm = path.join(__dirname, `temp_${timestamp}_${randomSuffix}.pcm`);

        const audioBuffer = Buffer.from(audioBase64, 'base64');
        fs.writeFileSync(tempAudio, audioBuffer);

        const ffmpeg = spawn('ffmpeg', [
            '-y', '-i', tempAudio,
            '-f', 's16le', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1', tempPcm
        ]);

        let stderr = '';
        ffmpeg.stderr.on('data', (data) => { stderr += data; });

        ffmpeg.on('close', (code) => {
            try {
                fs.unlinkSync(tempAudio);
            } catch (e) {}

            if (code !== 0) {
                try { fs.unlinkSync(tempPcm); } catch (e) {}
                reject(new Error('音频转换失败: ' + stderr));
                return;
            }

            try {
                const pcmBuffer = fs.readFileSync(tempPcm);
                fs.unlinkSync(tempPcm);
                resolve({
                    base64: pcmBuffer.toString('base64'),
                    len: pcmBuffer.length,
                    buffer: pcmBuffer
                });
            } catch (e) {
                reject(e);
            }
        });

        ffmpeg.on('error', (err) => {
            try {
                fs.unlinkSync(tempAudio);
                fs.unlinkSync(tempPcm);
            } catch (e) {}
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
    
    const data = await apiRes.json();
    logInfo('百度API响应: ' + JSON.stringify(data));
    
    if (data.err_no === 0 && data.result && data.result.length > 0) {
        return {
            success: true,
            text: data.result[0],
            provider: 'baidu'
        };
    } else {
        return {
            success: false,
            error: data.err_msg || '识别失败',
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
