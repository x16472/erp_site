(() => {
    const python_canvas = document.getElementById('python_canvas');
    if (!python_canvas) return;
    const panel = python_canvas.closest('.panel');
    const editor = document.getElementById('python-code');
    const stdin = document.getElementById('python-stdin');
    const output = document.getElementById('python-output');
    const state = document.getElementById('python-state');
    const runButton = document.getElementById('python-run');
    const stopButton = document.getElementById('python-stop');
    const command = document.getElementById('python-command');
    const sendButton = document.getElementById('python-send');
    const prompt = document.getElementById('python-prompt');
    const workerURL = new URL('./python-worker.js', document.currentScript.src);
    const history = [];
    let historyIndex = 0;
    let commandDraft = '';
    let worker;
    let ready = false;
    let busy = false;
    let multiline = false;
    let loadingTimer;
    const packageCookie = 'python_playground_packages';

    function readPackages() {
        try {
            const value = document.cookie.split('; ').find(item => item.startsWith(`${packageCookie}=`));
            const packages = value ? JSON.parse(decodeURIComponent(value.slice(packageCookie.length + 1))) : [];
            return Array.isArray(packages) ? packages.filter(name => typeof name === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]*(?:==[A-Za-z0-9][A-Za-z0-9._+-]*)?$/.test(name)) : [];
        } catch {
            return [];
        }
    }

    function rememberPackages(packages) {
        if (!packages.length) return;
        const saved = new Map(readPackages().map(name => [name.split('==')[0].toLowerCase().replace(/[-_.]+/g, '-'), name]));
        packages.forEach(name => saved.set(name.split('==')[0].toLowerCase().replace(/[-_.]+/g, '-'), name));
        const value = encodeURIComponent(JSON.stringify([...saved.values()]));
        if (value.length > 3000) {
            appendOutput('套件已安裝，但清單超過 Cookie 容量，本次清單無法保存。\n', 'stderr');
            return;
        }
        try {
            document.cookie = `${packageCookie}=${value}; Path=${location.pathname}; Max-Age=2592000; SameSite=Strict${location.protocol === 'https:' ? '; Secure' : ''}`;
            if (!document.cookie.split('; ').includes(`${packageCookie}=${value}`)) throw new Error('Cookie 已停用');
        } catch {
            appendOutput('套件已安裝，但瀏覽器未允許保存 Cookie；本次環境仍可使用。\n', 'stderr');
        }
    }

    function appendOutput(text, kind = 'stdout') {
        const followOutput = output.scrollHeight - output.scrollTop - output.clientHeight < 40;
        const last = output.lastChild;
        const className = kind === 'stderr' ? 'python-error' : '';
        if (last && last.className === className) last.append(document.createTextNode(text));
        else {
            const span = document.createElement('span');
            span.className = className;
            span.textContent = text;
            output.append(span);
        }
        // 限制命令列保留量，避免大量 print 讓整頁越來越慢。
        if (output.textContent.length > 180000) {
            output.textContent = `[較早的輸出已省略]\n${output.textContent.slice(-120000)}`;
        }
        if (followOutput) output.scrollTop = output.scrollHeight;
    }

    function updateControls(message) {
        state.textContent = message;
        state.classList.toggle('ok', ready && !busy);
        runButton.disabled = !ready || busy;
        command.disabled = !ready || busy;
        sendButton.disabled = !ready || busy;
        stopButton.disabled = !worker;
        python_canvas.setAttribute('aria-busy', String(busy));
    }

    function disposeWorker() {
        clearTimeout(loadingTimer);
        worker?.terminate();
        worker = undefined;
        ready = false;
        busy = false;
        multiline = false;
        prompt.textContent = '>>>';
    }

    function failRuntime(message) {
        disposeWorker();
        appendOutput(`${message}\n請確認網路連線，再按「重設環境」重試。\n`, 'stderr');
        updateControls('載入失敗');
    }

    function initialize() {
        if (worker) return;
        busy = true;
        updateControls('正在載入 Python 3.11…');
        try {
            worker = new Worker(workerURL);
            const currentWorker = worker;
            worker.onmessage = ({ data }) => {
                if (worker !== currentWorker) return;
                if (data.type === 'ready') {
                    clearTimeout(loadingTimer);
                    ready = true;
                    busy = false;
                    appendOutput(`Python ${data.version} · 瀏覽器執行環境已就緒\n`);
                    updateControls(`Python ${data.version} 就緒`);
                } else if (data.type === 'output') {
                    appendOutput(data.text, data.kind);
                } else if (data.type === 'done') {
                    busy = false;
                    multiline = data.more;
                    prompt.textContent = multiline ? '...' : '>>>';
                    rememberPackages(data.packages || []);
                    updateControls(multiline ? '等待下一行（空白行結束）' : (data.ok ? '執行完成' : '執行發生錯誤'));
                    if (panel.classList.contains('active')) command.focus();
                } else if (data.type === 'fatal') {
                    failRuntime(data.text);
                } else if (data.type === 'restoring') {
                    clearTimeout(loadingTimer);
                    updateControls('正在還原瀏覽器套件…');
                }
            };
            worker.onerror = (event) => {
                event.preventDefault();
                if (worker === currentWorker) failRuntime(event.message || '無法啟動 Python Worker。');
            };
            loadingTimer = setTimeout(() => {
                if (worker === currentWorker && !ready) failRuntime('Python 載入逾時。');
            }, 90000);
            worker.postMessage({ type: 'init', packages: readPackages() });
            updateControls('正在載入 Python 3.11…');
        } catch (error) {
            failRuntime(error.message);
        }
    }

    function execute(type, code, packages) {
        if (!ready || busy) return;
        busy = true;
        updateControls(type === 'install' ? '正在安裝套件…' : '執行中…');
        worker.postMessage({ type, code, packages, stdin: stdin.value });
    }

    function runFile() {
        if (!ready || busy) return;
        appendOutput('\n$ python main.py\n');
        execute('run', editor.value);
    }

    function resetRuntime() {
        disposeWorker();
        appendOutput('\n[環境已重設；變數與暫存檔案已清除，將依 Cookie 還原套件]\n');
        initialize();
    }

    runButton.addEventListener('click', runFile);
    stopButton.addEventListener('click', () => {
        disposeWorker();
        appendOutput('\n[已停止；執行環境已釋放，請按「重設環境」重新啟動]\n');
        updateControls('已停止');
    });
    document.getElementById('python-reset').addEventListener('click', resetRuntime);
    document.getElementById('python-clear').addEventListener('click', () => { output.textContent = ''; });
    document.getElementById('python-command-form').addEventListener('submit', (event) => {
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
            if (text === 'python main.py') { runFile(); return; }
            if (/^pip\s+install(?:\s|$)/.test(text)) {
                const packages = text.split(/\s+/).slice(2);
                if (!packages.length || packages.some(name => !/^[A-Za-z0-9][A-Za-z0-9._-]*(?:==[A-Za-z0-9][A-Za-z0-9._+-]*)?$/.test(name))) {
                    appendOutput('用法：pip install 套件名稱 [套件名稱==版本]\n', 'stderr');
                    return;
                }
                execute('install', '', packages);
                return;
            }
        }
        execute('repl', source);
    });

    command.addEventListener('keydown', (event) => {
        if (!['ArrowUp', 'ArrowDown'].includes(event.key) || !history.length || event.isComposing) return;
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
            editor.setRangeText('    ', editor.selectionStart, editor.selectionEnd, 'end');
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const previous = editor.value.slice(0, editor.selectionStart).split('\n').pop();
            const indent = previous.match(/^\s*/)[0] + (previous.trimEnd().endsWith(':') ? '    ' : '');
            editor.setRangeText(`\n${indent}`, editor.selectionStart, editor.selectionEnd, 'end');
        }
    });

    // 第三分頁開啟時才下載 Python，避免增加其他工作面板的啟動負擔。
    new MutationObserver(() => {
        if (panel.classList.contains('active') && !worker && state.textContent === '尚未載入') initialize();
    }).observe(panel, { attributes: true, attributeFilter: ['class'] });
    if (panel.classList.contains('active')) initialize();
    window.addEventListener('pagehide', disposeWorker);
})();
