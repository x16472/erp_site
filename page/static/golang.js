(() => {
    const golang_canvas = document.getElementById('golang_canvas');
    if (!golang_canvas) return;
    const panel = golang_canvas.closest('.panel');
    const editor = document.getElementById('golang-code');
    const stdin = document.getElementById('golang-stdin');
    const output = document.getElementById('golang-output');
    const state = document.getElementById('golang-state');
    const runButton = document.getElementById('golang-run');
    const formatButton = document.getElementById('golang-format');
    const stopButton = document.getElementById('golang-stop');
    const command = document.getElementById('golang-command');
    const sendButton = document.getElementById('golang-send');
    const prompt = document.getElementById('golang-prompt');
    const workerURL = new URL('./golang-worker.js', document.currentScript.src);
    const history = [];
    let historyIndex = 0;
    let commandDraft = '';
    let worker;
    let ready = false;
    let busy = false;
    let multiline = false;
    let currentAction;
    let formatSource;
    let version = '';
    let loadingTimer;

    function appendOutput(text, kind = 'stdout') {
        const follow = output.scrollHeight - output.scrollTop - output.clientHeight < 40;
        const className = kind === 'stderr' ? 'golang-error' : '';
        const last = output.lastChild;
        if (last && last.className === className) last.append(document.createTextNode(text));
        else {
            const span = document.createElement('span');
            span.className = className;
            span.textContent = text;
            output.append(span);
        }
        if (output.textContent.length > 180000) {
            output.textContent = `[較早的輸出已省略]\n${output.textContent.slice(-120000)}`;
        }
        if (follow) output.scrollTop = output.scrollHeight;
    }

    function updateControls(message) {
        state.textContent = message;
        state.classList.toggle('ok', ready && !busy);
        runButton.disabled = !ready || busy;
        formatButton.disabled = !ready || busy;
        command.disabled = !ready || busy;
        sendButton.disabled = !ready || busy;
        stopButton.disabled = !worker;
        golang_canvas.setAttribute('aria-busy', String(busy));
    }

    function disposeWorker() {
        clearTimeout(loadingTimer);
        worker?.terminate();
        worker = undefined;
        ready = false;
        busy = false;
        multiline = false;
        currentAction = undefined;
        prompt.textContent = '>>>';
    }

    function failRuntime(message) {
        disposeWorker();
        appendOutput(`${message}\n請按「重設環境」重試。\n`, 'stderr');
        updateControls('Go 環境無法使用');
    }

    function dispatch(request) {
        busy = true;
        currentAction = request.type;
        updateControls(request.type === 'format' ? '正在格式化…' : '執行中…');
        worker.postMessage(request);
    }

    function initialize(pendingRequest, completionMessage, announce = false) {
        if (worker) return;
        busy = true;
        updateControls('正在載入 Go…');
        try {
            worker = new Worker(workerURL);
            const currentWorker = worker;
            worker.onmessage = ({ data }) => {
                if (worker !== currentWorker) return;
                if (data.type === 'ready') {
                    clearTimeout(loadingTimer);
                    ready = true;
                    busy = false;
                    version = data.version;
                    if (announce) appendOutput(`${version} js/wasm · Yaegi 0.16.1 瀏覽器環境已就緒\n`);
                    if (pendingRequest) dispatch(pendingRequest);
                    else updateControls(completionMessage || `${version} · Yaegi 就緒`);
                } else if (data.type === 'output') {
                    appendOutput(data.text, data.kind);
                } else if (data.type === 'done') {
                    const completedAction = currentAction;
                    const completion = data.ok ? (completedAction === 'format' ? '格式化完成' : '執行完成') : '執行發生錯誤';
                    if (completedAction === 'run') {
                        // main 結束即釋放該 Worker，確保其背景 goroutine 不會流入下一次操作。
                        disposeWorker();
                        initialize(undefined, completion);
                        return;
                    }
                    if (typeof data.formatted === 'string') {
                        if (editor.value === formatSource) editor.value = data.formatted;
                        else appendOutput('格式化期間程式碼已變更，已保留目前內容，請再次格式化。\n');
                    }
                    busy = false;
                    if (completedAction !== 'format') multiline = data.more;
                    prompt.textContent = multiline ? '...' : '>>>';
                    updateControls(multiline ? '等待下一行或結束大括號' : completion);
                    if (completedAction === 'repl' && panel.classList.contains('active')) command.focus();
                } else if (data.type === 'fatal') {
                    failRuntime(data.text);
                }
            };
            worker.onerror = (event) => {
                event.preventDefault();
                if (worker === currentWorker) failRuntime(event.message || '無法啟動 Go Worker。');
            };
            loadingTimer = setTimeout(() => {
                if (worker === currentWorker && !ready) failRuntime('Go 執行環境載入逾時。');
            }, 60000);
            worker.postMessage({ type: 'init' });
            updateControls('正在載入 Go…');
        } catch (error) {
            failRuntime(error.message);
        }
    }

    function runFile() {
        if (!ready || busy) return;
        const request = { type: 'run', code: editor.value, stdin: stdin.value };
        appendOutput('\n$ go run main.go\n');
        disposeWorker();
        initialize(request);
    }

    function formatFile() {
        if (!ready || busy) return;
        formatSource = editor.value;
        dispatch({ type: 'format', code: formatSource, stdin: '' });
    }

    function resetRuntime() {
        disposeWorker();
        appendOutput('\n[Go 環境已重設；互動變數與背景工作已清除]\n');
        initialize(undefined, undefined, true);
    }

    runButton.addEventListener('click', runFile);
    formatButton.addEventListener('click', formatFile);
    stopButton.addEventListener('click', () => {
        disposeWorker();
        appendOutput('\n[已停止；請按「重設環境」重新啟動]\n');
        updateControls('已停止');
    });
    document.getElementById('golang-reset').addEventListener('click', resetRuntime);
    document.getElementById('golang-clear').addEventListener('click', () => { output.textContent = ''; });
    document.getElementById('golang-command-form').addEventListener('submit', (event) => {
        event.preventDefault();
        if (!ready || busy) return;
        const source = command.value;
        command.value = '';
        if (source.trim()) history.push(source);
        historyIndex = history.length;
        commandDraft = '';
        appendOutput(`${prompt.textContent} ${source}\n`);
        if (!multiline) {
            const text = source.trim();
            if (text === 'clear') { output.textContent = ''; return; }
            if (text === 'reset') { resetRuntime(); return; }
            if (text === 'go run main.go') { runFile(); return; }
            if (['go fmt main.go', 'gofmt main.go'].includes(text)) { formatFile(); return; }
            if (text === 'go version') { appendOutput(`${version} js/wasm · Yaegi 0.16.1\n`); return; }
            if (text === 'help') {
                appendOutput('go run main.go：執行上方程式\ngo fmt main.go：格式化上方程式\ngo version：顯示執行環境\nclear：清除輸出；reset：重設環境\n可直接輸入 import "fmt"、變數宣告、運算式或多行 Go 區塊。\n');
                return;
            }
            if (/^go\s+(get|mod|install|build|test|env)(?:\s|$)/.test(text)) {
                appendOutput('此瀏覽器環境提供 Yaegi 與內建標準函式庫，未提供完整 Go 工具鏈或外部 Go modules 安裝。\n', 'stderr');
                return;
            }
        }
        dispatch({ type: 'repl', code: source, stdin: stdin.value });
    });

    command.addEventListener('keydown', (event) => {
        if (event.isComposing || !['ArrowUp', 'ArrowDown'].includes(event.key) || !history.length) return;
        event.preventDefault();
        if (historyIndex === history.length) commandDraft = command.value;
        historyIndex = Math.max(0, Math.min(history.length, historyIndex + (event.key === 'ArrowUp' ? -1 : 1)));
        command.value = historyIndex === history.length ? commandDraft : history[historyIndex];
    });
    editor.addEventListener('keydown', (event) => {
        if (event.isComposing) return;
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            runFile();
        } else if (event.key === 'Tab' && !event.shiftKey) {
            event.preventDefault();
            editor.setRangeText('\t', editor.selectionStart, editor.selectionEnd, 'end');
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const previous = editor.value.slice(0, editor.selectionStart).split('\n').pop();
            const indent = previous.match(/^\s*/)[0] + (previous.trimEnd().endsWith('{') ? '\t' : '');
            editor.setRangeText(`\n${indent}`, editor.selectionStart, editor.selectionEnd, 'end');
        }
    });

    new MutationObserver(() => {
        if (panel.classList.contains('active') && !worker && state.textContent === '尚未載入') initialize(undefined, undefined, true);
    }).observe(panel, { attributes: true, attributeFilter: ['class'] });
    if (panel.classList.contains('active')) initialize(undefined, undefined, true);
    window.addEventListener('pagehide', disposeWorker);
})();
