import { apiData, employeeLoginUrl, escapeHtml, jsonRequest } from './script.js';

let csrf = '', catalog = {
    subjects: [], chapters: [], sources: []
},
    activeSubject = null,
    activeSession = null,
    questionIndex = 0,
    timerHandle = null,
    submissionPending = false,
    pendingSave = Promise.resolve();
const $ = selector => document.querySelector(selector), esc = escapeHtml;
const request = (path, options = {}) => apiData(path, options, '題庫服務暫時無法使用');
const writeRequest = (path, payload) => jsonRequest(path, payload, {
    csrf, fallbackMessage: '題庫服務暫時無法使用'
});
const domainTabs = $('#domainTabs'),
    academicPanel = $('#academicPanel'),
    practicalPanel = $('#practicalPanel'),
    academicHome = $('#academicHome'),
    subjectGrid = $('#subjectGrid'),
    setupView = $('#setupView'),
    setupForm = $('#setupForm'),
    setupStatus = $('#setupStatus'),
    chapterChoices = $('#chapterChoices'),
    sourceChoices = $('#sourceChoices'),
    sessionView = $('#sessionView'),
    resultView = $('#resultView'),
    wrongView = $('#wrongView'),
    questionNavigator = $('#questionNavigator'),
    questionContent = $('#questionContent'),
    answerArea = $('#answerArea'),
    answerFeedback = $('#answerFeedback'),
    sessionProgress = $('#sessionProgress');
const floatingTools = $('#examFloatingTools'),
    sessionClock = $('#sessionClock'),
    floatingViewport = matchMedia('(min-width: 680px)'),
    clockHome = document.createComment('計時器原始位置'),
    navigatorHome = document.createComment('題號導覽原始位置');
sessionClock.before(clockHome);
questionNavigator.before(navigatorHome);
function syncFloatingTools() {
    const floating = floatingViewport.matches && !sessionView.hidden && !academicPanel.hidden;
    floatingTools.hidden = !floating;
    document.body.classList.toggle('exam-has-floating-tools', floating);
    if (floating) {
        floatingTools.append(sessionClock, questionNavigator);
    } else {
        clockHome.after(sessionClock);
        navigatorHome.after(questionNavigator);
    }
}
floatingViewport.addEventListener('change', syncFloatingTools);
syncFloatingTools();
function showAcademic(view) {
    [academicHome, setupView, sessionView, resultView, wrongView].forEach(item => item.hidden = item !== view);
    syncFloatingTools();
}
function renderBlocks(blocks) {
    return (blocks || []).map(block => {
        if (block.type === 'image') return `<img class="question-image" src="/api/training/image?name=${encodeURIComponent(block.content)}" alt="題目附圖" loading="lazy">`;
        if (block.type === 'code') return `<pre class="question-code"><code>${esc(block.content)}</code></pre>`;
        return `<div class="question-text">${esc(block.content).replace(/\n/g, '<br>')}</div>`;
    }).join('');
}
function renderCatalog() {
    const subjects = catalog.subjects.filter(item => item.domain === 'academic');
    subjectGrid.innerHTML = subjects.length ? subjects.map(subject => {
        const chapters = catalog.chapters.filter(item => item.subject_id === subject.id);
        return `<article class="subject-card"><span class="eyebrow">ACADEMIC</span><h3>${esc(subject.name)}</h3><p>${subject.question_count} 題已發布 · ${subject.mock_question_count} 題模擬考</p><div class="subject-progress">${chapters.map(chapter => `<div><span>${esc(chapter.name)}
    <small>${chapter.attempted_count}/${chapter.question_count} 題</small></span><progress class="progress-track" max="100" value="${Number(chapter.progress_percent) || 0}" aria-label="${esc(chapter.name)}練習進度"></progress></div>`).join('') || '<small>尚未建立章節</small>'}</div><button class="btn" data-subject="${subject.id}">選擇科目</button></article>`
    }).join('') : '<div class="empty">目前沒有已啟用的學科科目。</div>';

}
function openSetup(subjectId) {
    activeSubject = catalog.subjects.find(item => item.id === Number(subjectId));
    if (!activeSubject) return;
    setupForm.reset();
    setupForm.elements.subject_id.value = activeSubject.id;
    $('#setupTitle').textContent = activeSubject.name;
    $('#setupMeta').textContent = `模擬考規則：${activeSubject.mock_question_count} 題／${activeSubject.mock_duration_minutes} 分鐘／${activeSubject.mock_pass_score} 分及格`;
    $('#mockRule').textContent = $('#setupMeta').textContent.replace('模擬考規則：', '');
    const chapters = catalog.chapters.filter(item => item.subject_id === activeSubject.id);
    chapterChoices.innerHTML = chapters.map(item => `<label><input type="checkbox" name="chapter_id" value="${item.id}">${esc(item.code)} ${esc(item.name)}（${item.question_count}）</label>`).join('') || '<span class="hint">目前沒有章節</span>'; const sources = catalog.sources.filter(item => item.subject_id === activeSubject.id);
    sourceChoices.innerHTML = sources.map(item => `<label><input type="checkbox" name="source_id" value="${item.id}">${esc(item.title)}</label>`).join('') || '<span class="hint">目前沒有來源篩選</span>';
    setupStatus.textContent = '';
    showAcademic(setupView)
}
function sessionQuestion() { return activeSession.questions[questionIndex] }
function answerValues(question) {
    return [...answerArea.querySelectorAll('[name="answer"]:checked')].map(input => Number(input.value))
}
function renderAnswerArea(question) {
    const saved = question.response?.answers || [];
    const multiple = question.question_type === 'multiple_choice';
    answerArea.innerHTML = (question.options || []).map((option, index) => `<label class="quiz-option answer-label"><input name="answer" type="${multiple ? 'checkbox' : 'radio'}" value="${index}" ${saved.includes(index) ? 'checked' : ''}><span>${String.fromCharCode(65 + index)}. ${esc(option)}</span></label>`).join('')
}
function renderNavigator() { questionNavigator.innerHTML = activeSession.questions.map((question, index) => `<button class="${index === questionIndex ? 'active' : ''} ${question.response?.answers?.length ? 'answered' : ''} ${question.flagged ? 'flagged' : ''}" data-question-index="${index}">${index + 1}</button>`).join('') }
function renderQuestion() {
    const question = sessionQuestion();
    if (!question) return;
    $('#sessionMode').textContent = activeSession.mode === 'mock' ? '模擬考' : '分類練習';
    $('#sessionTitle').textContent = `${question.subject}｜${question.chapter}`;
    sessionProgress.value = (questionIndex + 1) / activeSession.questions.length * 100;
    questionContent.innerHTML = `<p class="hint">第 ${questionIndex + 1} 題，共 ${activeSession.questions.length} 題 · ${esc(question.source || '人工建立')} ${esc(question.source_locator || '')}</p>${question.passage ? `<article class="reading-passage">${esc(question.passage).replace(/\n/g, '<br>')}</article>` : ''}${renderBlocks(question.content_blocks)}`;
    renderAnswerArea(question); answerFeedback.textContent = '';
    $('#previousQuestion').disabled = questionIndex === 0;
    $('#nextQuestion').disabled = questionIndex === activeSession.questions.length - 1;
    $('#flagQuestion').classList.toggle('active', Boolean(question.flagged));
    $('#submitSession').textContent = activeSession.mode === 'mock' ? '交卷' : '完成練習';
    renderNavigator()
}
function utcMilliseconds(value) {
    if (!value) return NaN;
    const text = String(value);
    return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(text) ? text : `${text}Z`);
}
async function startTimer(requestStarted = performance.now()) {
    clearInterval(timerHandle);
    timerHandle = null;
    const session = activeSession;
    $('#sessionClock').hidden = session.mode !== 'mock';
    if (session.mode !== 'mock') return;
    $('#countdown').textContent = '校時中…';
    const expiresAt = utcMilliseconds(session.expires_at);
    if (!Number.isFinite(expiresAt)) throw new Error('模擬考缺少有效的到期時間，請重新讀取題組。');
    let deadline, lastSync = performance.now(), syncing = false;
    const initialTime = utcMilliseconds(session.server_time);
    if (Number.isFinite(initialTime)) {
        deadline = performance.now() + expiresAt - initialTime - (performance.now() - requestStarted) / 2;
    } else {
        const started = performance.now();
        const time = await request('/api/time', { cache: 'no-store' });
        if (!Number.isFinite(Number(time.unix_ms))) throw new Error('無法取得模擬考計時資料。');
        deadline = performance.now() + expiresAt - Number(time.unix_ms) - (performance.now() - started) / 2;
    }
    if (activeSession !== session) return;
    const tick = () => {
        if (activeSession !== session || session.status === 'submitted') return;
        const remaining = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
        $('#countdown').textContent = `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`;
        if (remaining === 0) {
            clearInterval(timerHandle);
            timerHandle = null;
            session.expired = true;
            answerArea.querySelectorAll("input").forEach(input => { input.disabled = true; });
            $("#saveAnswer").disabled = true;
            $("#flagQuestion").disabled = true;
            submitSession(true);
            return;
        }
        if (!syncing && performance.now() - lastSync >= 60000) {
            syncing = true;
            const started = performance.now();
            request('/api/time', { cache: 'no-store' }).then(time => {
                if (activeSession === session && Number.isFinite(Number(time.unix_ms))) {
                    deadline = performance.now() + expiresAt - Number(time.unix_ms) - (performance.now() - started) / 2;
                }
            }).catch(() => {
                answerFeedback.textContent = '暫時無法校時，持續依前次伺服器時間倒數。';
            }).finally(() => { syncing = false; lastSync = performance.now(); });
        }
    };
    timerHandle = setInterval(tick, 1000);
    tick();
}
async function openSession(session, requestStarted = performance.now()) {
    clearInterval(timerHandle);
    activeSession = session;
    questionIndex = 0;
    submissionPending = false;
    pendingSave = Promise.resolve();
    if (session.status === 'submitted') return renderResult(session);
    if (!session.questions?.length) throw new Error('此題組沒有可作答的題目。');
    showAcademic(sessionView);
    renderQuestion();
    $('#submitSession').disabled = false;
    $('#saveAnswer').disabled = false;
    $('#flagQuestion').disabled = false;
    try { await startTimer(requestStarted); } catch (error) {
        $('#countdown').textContent = '計時失敗';
        answerFeedback.textContent = error.message;
        answerFeedback.className = 'quiz-feedback error-note';
    }
}
async function saveCurrent(showMessage = true) {
    const session = activeSession, question = sessionQuestion(), answers = answerValues(question);
    const payload = { session_id: session.id, order: question.order, response: { answers }, flagged: Boolean(question.flagged) };
    question.response = { answers };
    const task = pendingSave.catch(() => {}).then(() => writeRequest('/api/training/session/answer', payload));
    pendingSave = task;
    const result = await task;
    if (activeSession !== session || session.status === 'submitted') return result;
    if (session.mode === 'practice') {
        answerFeedback.textContent = `${result.correct ? '答對了。' : '答案不正確。'} ${result.explanation || '此題尚無解析。'}`;
        answerFeedback.className = `quiz-feedback ${result.correct ? 'success-note' : 'error-note'}`;
    } else if (showMessage) answerFeedback.textContent = '答案已儲存。';
    renderNavigator();
    return result;
}
answerArea.addEventListener('change', () => {
    if (activeSession?.mode === 'mock' && !activeSession.expired) {
        saveCurrent(false).catch(error => { answerFeedback.textContent = error.message; });
    }
});
async function navigateQuestion(index) {
    if (activeSession.expired || submissionPending) return;
    if (activeSession.mode === 'mock') {
        try { await saveCurrent(false) } catch (error) {
            answerFeedback.textContent = error.message;
            return
        }
    } questionIndex = index; renderQuestion()
}
async function submitSession(timeout = false) {
    if (submissionPending || !activeSession || activeSession.status === 'submitted') return;
    timeout = timeout || Boolean(activeSession.expired);
    if (!timeout && activeSession.mode === 'mock') {
        const unanswered = activeSession.questions.filter((question, index) => {
            const answers = index === questionIndex ? answerValues(question) : (question.response?.answers || []);
            return !answers.length;
        }).length;
        if (!confirm(`確定要交卷嗎？目前尚有 ${unanswered} 題未作答，仍會一併送出。`)) return;
    }
    submissionPending = true;
    $('#submitSession').disabled = true;
    try {
        if (timeout) await pendingSave.catch(() => {});
        else await saveCurrent(false);
        const result = await writeRequest('/api/training/session/submit', { session_id: activeSession.id });
        renderResult(result);
    } catch (error) {
        answerFeedback.textContent = `${error.message}${timeout ? ' 時間已到，請按交卷重試。' : ''}`;
        answerFeedback.className = 'quiz-feedback error-note';
    } finally {
        submissionPending = false;
        $('#submitSession').disabled = false;
    }
}
function renderReviewQuestion(question) { const answerText = (question.answers || []).map(value => typeof value === 'number' ? String.fromCharCode(65 + value) : value).join('、') || '由人工審核'; return `<details class="review-question ${question.correct ? 'correct' : 'wrong'}"><summary>第 ${question.order} 題｜${question.correct ? '答對' : '答錯或未作答'}</summary>${renderBlocks(question.content_blocks)}<p>正確答案：${esc(answerText)}</p><p>${esc(question.explanation || '此題尚無解析。')}</p></details>` }
function renderResult(session) {
    clearInterval(timerHandle);
    activeSession = session;
    showAcademic(resultView);
    const passScore = session.config?.pass_score,
        passed = passScore == null || Number(session.score) >= Number(passScore),
        chapterMap = {};
    session.questions.forEach(question => {
        const name = question.chapter || '未分類';
        chapterMap[name] ??= { total: 0, correct: 0 };
        chapterMap[name].total++;
        chapterMap[name].correct += question.correct ? 1 : 0
    });
    const chapterStats = Object.entries(chapterMap).map(([name, value]) =>
        `<article class="metric-card"><p>${esc(name)}</p><strong>${Math.round(value.correct * 100 / value.total)}%&nbsp;</strong><small>${value.correct} / ${value.total} 題</small></article>`).join('');
    resultView.innerHTML = `<div class="result-hero"><span class="eyebrow">RESULT</span><h2>${passed ? '已完成本次題組' : '本次尚未達及格標準'}</h2><strong>${Number(session.score || 0).toFixed(1)} 分</strong>${passScore != null ? `<p>及格標準 ${passScore} 分</p>` : ''}</div><div class="metric-grid">${chapterStats}</div><div class="review-list">${session.questions.map(renderReviewQuestion).join('')}</div><div class="actions"><button class="btn" id="backToSubjects">返回題庫首頁</button></div>`;
    resultView.querySelector('#backToSubjects').onclick = async () => {
        await loadCatalog();
        showAcademic(academicHome)
    }
}
async function loadWrong() {
    showAcademic(wrongView);
    const items = await request('/api/training/wrong');
    $('#wrongList').innerHTML = items.length ? items.map(item => `<article class="wrong-card" data-wrong-card="${item.id}"><div><span class="tag">${esc(item.subject)}｜${esc(item.chapter)}</span>${renderBlocks(item.content_blocks)}<p class="hint">正確答案：${esc((item.answers || []).map(value => typeof value === 'number' ? String.fromCharCode(65 + value) : value).join('、'))}</p><p>${esc(item.explanation || '此題尚無解析。')}</p></div><button class="btn second" data-remove-wrong="${item.id}">從錯題本移除</button></article>`).join('') : '<div class="empty">目前沒有待複習錯題。</div>'
}
async function loadPractical() {
    const items = await request('/api/training/practical');
    $('#practicalList').innerHTML = items.length ? items.map(item => `<article class="portal-card practical-card"><header><span class="tag">${esc(item.subject)}｜${esc(item.chapter || '未分類')}</span><span class="tag">${esc(item.answer_status || '尚未作答')}</span></header>${renderBlocks(item.content_blocks)}${item.feedback ? `<p class="error-note">審核回饋：${esc(item.feedback)}</p>` : ''}<form data-practical="${item.id}"><label class="field"><span>申論答案</span><textarea name="answer_text" rows="10" maxlength="5000" required></textarea></label><button class="btn" type="submit">送交人工審核</button><p aria-live="polite"></p></form></article>`).join('') : '<div class="empty">目前沒有已發布的術科題目。</div>'
}
async function loadCatalog() {
    catalog = await request('/api/training/catalog');
    $('#resumeSession').hidden = !catalog.resumable;
    $('#wrongCount').textContent = String(catalog.wrong_count || 0);
    renderCatalog()
}
domainTabs.onclick = event => {
    const button = event.target.closest('[data-domain]');
    if (!button) return;
    domainTabs.querySelectorAll('button').forEach(item => item.classList.toggle('active', item === button));
    const academic = button.dataset.domain === 'academic';
    academicPanel.hidden = !academic;
    practicalPanel.hidden = academic;
    syncFloatingTools();
    if (!academic) loadPractical().catch(error => $('#practicalList').innerHTML = `<div class="error-note">${esc(error.message)}</div>`)
};
subjectGrid.onclick = event => {
    const button = event.target.closest('[data-subject]');
    if (button) openSetup(button.dataset.subject)
};
$('#cancelSetup').onclick = () => showAcademic(academicHome);
setupForm.onchange = event => {
    if (event.target.name === 'mode') setupForm.elements.question_count.disabled = event.target.value === 'mock'
};
setupForm.onsubmit = async event => {
    event.preventDefault();
    const values = new FormData(setupForm);
    setupStatus.textContent = '正在建立題組…';
    const startButton = setupForm.querySelector('[type="submit"]');
    if (startButton.disabled) return;
    startButton.disabled = true;
    try {
        const requestStarted = performance.now();
        const session = await writeRequest('/api/training/session/start', {
            subject_id: Number(values.get('subject_id')),
            mode: values.get('mode'),
            question_count: Number(values.get('question_count')),
            chapter_ids: values.getAll('chapter_id').map(Number),
            source_ids: values.getAll('source_id').map(Number),
            question_types: values.getAll('question_type')
        }); await openSession(session, requestStarted)
    } catch (error) {
        setupStatus.className = 'error-note';
        setupStatus.textContent = error.message
    } finally { startButton.disabled = false; }
};
questionNavigator.onclick = event => {
    const button = event.target.closest('[data-question-index]');
    if (button) navigateQuestion(Number(button.dataset.questionIndex))
}; $('#previousQuestion').onclick = () => {
    if (questionIndex > 0) navigateQuestion(questionIndex - 1)
};
$('#nextQuestion').onclick = () => {
    if (questionIndex < activeSession.questions.length - 1) navigateQuestion(questionIndex + 1)
};
$('#flagQuestion').onclick = async () => {
    if (activeSession.expired || submissionPending) return;
    const question = sessionQuestion();
    question.flagged = !question.flagged;
    await saveCurrent(false);
    renderQuestion()
}; $('#saveAnswer').onclick = () => saveCurrent().catch(error => answerFeedback.textContent = error.message);
$('#submitSession').onclick = () => submitSession(false);
$('#resumeSession').onclick = async () => {
    const started = performance.now();
    try { await openSession(await request(`/api/training/session?id=${encodeURIComponent(catalog.resumable.id)}`), started); }
    catch (error) { $('#apiState').textContent = error.message; }
};
$('#openWrong').onclick = () => loadWrong().catch(error => $('#wrongList').innerHTML = `<div class="error-note">${esc(error.message)}</div>`);
$('#closeWrong').onclick = () => showAcademic(academicHome);
$('#wrongList').onclick = async event => {
    const button = event.target.closest('[data-remove-wrong]');
    if (!button) return; await writeRequest('/api/training/wrong/remove',
        { question_id: Number(button.dataset.removeWrong) });
    button.closest('[data-wrong-card]').remove();
    await loadCatalog()
};
$('#practicalList').onsubmit = async event => {
    const form = event.target.closest('[data-practical]');
    if (!form) return; event.preventDefault();
    const status = form.querySelector('p');
    status.textContent = '送出中…';
    try {
        await writeRequest('/api/training/practical/answer',
            {
                question_id: Number(form.dataset.practical),
                answers: [],
                answer_text: form.elements.answer_text.value
            }); status.className = 'success-note';
        status.textContent = '已送交人工審核。';
        form.elements.answer_text.disabled = true
    } catch (error) {
        status.className = 'error-note';
        status.textContent = error.message
    }
};
request('/api/employee/session').then(session => {
    if (!session.authenticated) return location.replace(employeeLoginUrl);
    csrf = session.csrf;
    return loadCatalog()
}).then(() => {
    $('#apiState').textContent = '題庫資料已同步';
    $('#apiState').classList.add('ok')
}).catch(error => {
    $('#apiState').textContent = '題庫服務未連線';
    subjectGrid.innerHTML = `<div class="error-note">${esc(error.message)}</div>`
});
