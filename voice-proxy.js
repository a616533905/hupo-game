const http = require('http');
const https = require('https');
const url = require('url');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const MAX_BODY_SIZE = 10 * 1024 * 1024;
const ALLOWED_FORMATS = ['webm', 'mp3', 'wav', 'ogg', 'm4a', 'aac'];

const CONFIG_FILE = path.join(__dirname, 'config.json');

function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const data = fs.readFileSync(CONFIG_FILE, 'utf-8');
            return JSON.parse(data);
        }
    } catch (e) {
        console.error('配置文件加载失败:', e.message);
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
        console.log('百度PCM转换成功, 长度:', pcmData.len, 'bytes');
    } catch (convertError) {
        console.error('PCM转换失败:', convertError.message);
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

    console.log('发送到百度API, len:', pcmData.len);

    const apiRes = await fetch('https://vop.baidu.com/server_api', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    });
    
    const data = await apiRes.json();
    console.log('百度API响应:', JSON.stringify(data));
    
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

const server = http.createServer(async (req, res) => {
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
            console.log('Token验证失败: /voice/token');
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
            console.log('Token响应:', JSON.stringify(data));
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
        } catch (e) {
            console.error('Token错误:', e);
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
                const { speech, token, provider, format, access_token } = JSON.parse(body);
                
                if (!verifyToken(access_token)) {
                    console.log('Token验证失败: /voice/recognize');
                    res.writeHead(401, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ 
                        success: false,
                        error: 'Unauthorized: invalid token'
                    }));
                    return;
                }
                
                const useProvider = provider || VOICE_PROVIDER;
                const audioFormat = format || 'webm';
                console.log('收到识别请求, 提供商:', useProvider, '格式:', audioFormat, '音频base64长度:', speech.length);

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
                console.error('识别错误:', e);
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
});

console.log('语音代理服务器配置加载完成');
console.log('配置文件:', CONFIG_FILE);
console.log('当前语音提供商:', VOICE_PROVIDER);
console.log('');
console.log('语音提供商状态:');

if (BAIDU_API_KEY && BAIDU_SECRET_KEY) {
    console.log('  百度API: ✓ 已配置');
} else {
    console.log('  百度API: ✗ 未配置（请在config.json中设置baidu.api_key和baidu.secret_key）');
}

console.log('');
const PORT = parseInt(process.env.VOICE_PORT) || config.server?.voice_port || 85;
server.listen(PORT, '0.0.0.0', () => {
    console.log('语音代理服务器运行在 http://0.0.0.0:' + PORT);
    console.log('局域网访问: http://<你的IP>:' + PORT);
});
