/* Pyodide 0.25.1 固定使用 CPython 3.11，避免 CDN 升版改變練習環境。 */
const PYTHON_INDEX_URL = 'https://cdn.jsdelivr.net/pyodide/v0.25.1/full/';
const OUTPUT_LIMIT = 120000;
let runtime;
let namespace;
let compiler;
let evaluate;
let pendingLines = [];
let busy = false;
let outputSize = 0;
let outputLimited = false;
let outputBuffer = '';
let outputKind = 'stdout';
let outputTimer;
let lastFlushTime = 0;

// 僅快取公開的執行環境與 wheel；不攔截網站 API 或任何後端請求。
const networkFetch = self.fetch.bind(self);
self.fetch = async (input, options) => {
    const request = new Request(input, options);
    const url = new URL(request.url);
    const cacheable = request.method === 'GET' && (
        request.url.startsWith(PYTHON_INDEX_URL) ||
        (url.hostname === 'files.pythonhosted.org' && url.pathname.endsWith('.whl'))
    );
    if (!cacheable || !self.caches) return networkFetch(request);
    let cache;
    try {
        cache = await caches.open('python-playground-pyodide-0.25.1');
        const cached = await cache.match(request);
        if (cached) return cached;
    } catch {
        // 私密瀏覽或儲存空間限制時，仍可直接下載執行。
    }
    const response = await networkFetch(request);
    if (cache && response.ok) {
        try { await cache.put(request, response.clone()); } catch { /* 快取失敗不影響執行。 */ }
    }
    return response;
};

function flushOutput() {
    clearTimeout(outputTimer);
    outputTimer = undefined;
    if (!outputBuffer) return;
    self.postMessage({ type: 'output', kind: outputKind, text: outputBuffer });
    outputBuffer = '';
    lastFlushTime = performance.now();
}

function writeOutput(text, kind = 'stdout') {
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
}

function makeStream(kind) {
    const decoder = new TextDecoder();
    return {
        write(buffer) {
            writeOutput(decoder.decode(buffer, { stream: true }), kind);
            return buffer.length;
        }
    };
}

async function initialize(savedPackages) {
    importScripts(`${PYTHON_INDEX_URL}pyodide.js`);
    runtime = await loadPyodide({ indexURL: PYTHON_INDEX_URL });
    const version = runtime.runPython('import sys; sys.version.split()[0]');
    if (!version.startsWith('3.11.')) throw new Error(`Python 版本不符：${version}`);
    runtime.setStdout(makeStream('stdout'));
    runtime.setStderr(makeStream('stderr'));
    namespace = runtime.runPython("dict(__name__='__main__', __file__='main.py')");
    runtime.runPython("sys.argv = ['main.py']");
    compiler = runtime.runPython("__import__('codeop').CommandCompiler()");
    evaluate = runtime.runPython('eval');
    if (savedPackages.length) {
        self.postMessage({ type: 'restoring' });
        await runtime.loadPackage('micropip');
        const micropip = runtime.pyimport('micropip');
        try {
            await micropip.install(savedPackages);
            writeOutput(`已從瀏覽器紀錄還原套件：${savedPackages.join(' ')}\n`);
        } catch (error) {
            writeOutput(`套件還原失敗，可用 pip install 重試：${error.message}\n`, 'stderr');
        } finally {
            micropip.destroy();
            flushOutput();
        }
    }
    self.postMessage({ type: 'ready', version });
}

async function execute(message) {
    let result;
    let compiled;
    let packages;
    let more = false;
    let ok = true;
    outputSize = 0;
    outputLimited = false;
    lastFlushTime = 0;
    // 每次請求重新開啟 stdin，避免上一次的 EOF 狀態影響下一次 input()。
    const input = message.stdin.replace(/\r\n?/g, '\n');
    const inputLines = input === '' ? [] : input.split('\n');
    if (input.endsWith('\n')) inputLines.pop();
    let inputIndex = 0;
    runtime.setStdin({ stdin: () => inputLines[inputIndex++] });
    try {
        if (message.type === 'install') {
            await runtime.loadPackage('micropip');
            packages = runtime.pyimport('micropip');
            await packages.install(message.packages);
            writeOutput(`已安裝：${message.packages.join(' ')}\n`);
        } else if (message.type === 'run') {
            pendingLines = [];
            runtime.FS.writeFile('main.py', message.code);
            await runtime.loadPackagesFromImports(message.code);
            result = await runtime.runPythonAsync(message.code, {
                globals: namespace,
                filename: 'main.py'
            });
        } else {
            pendingLines.push(message.code);
            const source = pendingLines.join('\n');
            compiled = compiler(source, '<console>', 'single');
            if (compiled == null) {
                more = true;
            } else {
                await runtime.loadPackagesFromImports(source);
                result = evaluate(compiled, namespace);
                pendingLines = [];
            }
        }
    } catch (error) {
        ok = false;
        pendingLines = [];
        writeOutput(`${error.message || error}\n`, 'stderr');
    } finally {
        result?.destroy?.();
        compiled?.destroy?.();
        packages?.destroy?.();
        flushOutput();
        self.postMessage({ type: 'done', ok, more, packages: ok && message.type === 'install' ? message.packages : [] });
    }
}

self.onmessage = async ({ data }) => {
    if (busy) return;
    busy = true;
    try {
        if (data.type === 'init') await initialize(data.packages || []);
        else if (runtime) await execute(data);
    } catch (error) {
        self.postMessage({ type: 'fatal', text: error.message || String(error) });
    } finally {
        busy = false;
    }
};
