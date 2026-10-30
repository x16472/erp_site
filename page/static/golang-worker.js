const GOLANG_RUNTIME = './golang-runtime/';
const GOLANG_BUILD = 'yaegi-0.16.1-go1.22.12-2';
const OUTPUT_LIMIT = 120000;
let busy = false;
let outputSize = 0;
let outputLimited = false;
let outputBuffer = '';
let outputKind = 'stdout';
let outputTimer;
let lastFlushTime = 0;

function flushOutput() {
    clearTimeout(outputTimer);
    outputTimer = undefined;
    if (!outputBuffer) return;
    self.postMessage({ type: 'output', kind: outputKind, text: outputBuffer });
    outputBuffer = '';
    lastFlushTime = performance.now();
}

self.golangEmit = (kind, text) => {
    if (outputLimited) return;
    if (kind !== outputKind) flushOutput();
    outputKind = kind;
    const remaining = OUTPUT_LIMIT - outputSize;
    outputBuffer += text.slice(0, remaining);
    outputSize += Math.min(text.length, remaining);
    if (text.length > remaining) {
        outputBuffer += '\n[本次輸出已達上限，後續輸出省略；可按停止中止程式。]\n';
        outputLimited = true;
    }
    if (outputBuffer.length >= 4096 || performance.now() - lastFlushTime >= 32) flushOutput();
    else if (!outputTimer) outputTimer = setTimeout(flushOutput, 32);
};

self.golangComplete = (result) => {
    flushOutput();
    busy = false;
    self.postMessage({ type: 'done', ...result });
};
self.golangReady = (version) => {
    busy = false;
    self.postMessage({ type: 'ready', version });
};
self.golangFatal = (text) => {
    flushOutput();
    self.postMessage({ type: 'fatal', text });
};

async function fetchRuntime() {
    const url = new URL(`${GOLANG_RUNTIME}golang.wasm.gz?v=${GOLANG_BUILD}`, self.location.href);
    let cache;
    try {
        if (self.caches) {
            cache = await caches.open(`golang-playground-${GOLANG_BUILD}`);
            const cached = await cache.match(url);
            if (cached) return cached;
        }
    } catch { /* 私密瀏覽或儲存空間不足時，仍可使用正常下載。 */ }
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Go 執行環境下載失敗（HTTP ${response.status}）。`);
    if (cache) {
        try { await cache.put(url, response.clone()); } catch { /* 快取失敗不影響執行。 */ }
    }
    return response;
}

async function initialize() {
    importScripts(`${GOLANG_RUNTIME}wasm_exec.js?v=${GOLANG_BUILD}`);
    const stdout = new TextDecoder();
    const stderr = new TextDecoder();
    self.fs.writeSync = (descriptor, bytes) => {
        const kind = descriptor === 2 ? 'stderr' : 'stdout';
        self.golangEmit(kind, (descriptor === 2 ? stderr : stdout).decode(bytes, { stream: true }));
        return bytes.length;
    };
    const go = new Go();
    go.env = { YAEGI_SPECIAL_STDIO: 'true' };
    const response = await fetchRuntime();
    if (!self.DecompressionStream) throw new Error('請使用支援 DecompressionStream 的新版瀏覽器。');
    const wasm = new Response(response.body.pipeThrough(new DecompressionStream('gzip')));
    const { instance } = await WebAssembly.instantiate(await wasm.arrayBuffer(), go.importObject);
    go.run(instance).then(() => {
        self.golangFatal('Go 執行環境已結束，請重設環境。');
    }).catch(error => self.golangFatal(error.message || String(error)));
}

self.onmessage = async ({ data }) => {
    if (busy) return;
    busy = true;
    try {
        if (data.type === 'init') {
            await initialize();
        } else {
            outputSize = 0;
            outputLimited = false;
            lastFlushTime = 0;
            self.golangExecute(data);
        }
    } catch (error) {
        self.golangFatal(error.message || String(error));
    }
};
