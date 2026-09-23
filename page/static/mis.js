import { apiData, bindAdminAccess, bindImageFallbacks, bindTabs, escapeHtml, formatNumber } from './script.js';

let csrf = '', tables = [], staffItems = [], submissions = [], selectedEmployee = '', selectedCategory = '', selectedTable = '', currentPage = 1, totalRows = 0, pageSize = 20;
const loginShell = document.querySelector('#loginShell'),
    adminConsole = document.querySelector('#adminConsole'),
    apiState = document.querySelector('#apiState'),
    adminName = document.querySelector('#adminName'),
    settingsForm = document.querySelector('#settingsForm'),
    settingsPreview = document.querySelector('#settingsPreview'),
    toast = document.querySelector('#toast'),
    loginForm = document.querySelector('#loginForm'),
    loginStatus = document.querySelector('#loginStatus'),
    logoutButton = document.querySelector('#logoutButton'),
    adminTabs = document.querySelector('#adminTabs'),
    previewTitle = document.querySelector('#previewTitle'),
    previewSubtitle = document.querySelector('#previewSubtitle'),
    settingsStatus = document.querySelector('#settingsStatus'),
    catalogSearch = document.querySelector('#catalogSearch'),
    catalog = document.querySelector('#catalog'),
    dataTitle = document.querySelector('#dataTitle'),
    dataBody = document.querySelector('#dataBody'),
    dataMeta = document.querySelector('#dataMeta'),
    dataHead = document.querySelector('#dataHead'),
    pageInfo = document.querySelector('#pageInfo'),
    prevPage = document.querySelector('#prevPage'),
    nextPage = document.querySelector('#nextPage'),
    submissionList = document.querySelector('#submissionList'),
    staffList = document.querySelector('#staffList'),
    queueFilters = document.querySelector('#queueFilters'),
    queueTitle = document.querySelector('#queueTitle'),
    queueCount = document.querySelector('#queueCount'),
    syncTraining = document.querySelector('#syncTraining'),
    syncStatus = document.querySelector('#syncStatus');
const esc = escapeHtml;
const number = formatNumber;
let operationsManuals = [], complianceQuestions = [], essayAnswers = [], trainingTaxonomy = { subjects: [], chapters: [] };
const trainingDocumentList = document.querySelector('#trainingDocumentList'),
    subjectForm = document.querySelector('#subjectForm'),
    chapterForm = document.querySelector('#chapterForm'),
    chapterSubject = document.querySelector('#chapterSubject'),
    taxonomyList = document.querySelector('#taxonomyList'),
    questionForm = document.querySelector('#questionForm'),
    questionDocument = document.querySelector('#questionDocument'),
    questionDomain = document.querySelector('#questionDomain'),
    questionSubject = document.querySelector('#questionSubject'),
    questionChapter = document.querySelector('#questionChapter'),
    bulkSubject = document.querySelector('#bulkSubject'),
    bulkChapter = document.querySelector('#bulkChapter'),
    bulkStatus = document.querySelector('#bulkStatus'),
    questionSearch = document.querySelector('#questionSearch'),
    questionStatusFilter = document.querySelector('#questionStatusFilter'),
    questionList = document.querySelector('#questionList'),
    questionStatus = document.querySelector('#questionStatus'),
    resetQuestion = document.querySelector('#resetQuestion'),
    questionTypeTabs = document.querySelector('#questionTypeTabs'),
    passageField = document.querySelector('#passageField'),
    optionsField = document.querySelector('#optionsField'),
    answersField = document.querySelector('#answersField'),
    structureField = document.querySelector('#structureField'),
    explanationField = document.querySelector('#explanationField'),
    essayHint = document.querySelector('#essayHint'),
    essayAnswerList = document.querySelector('#essayAnswerList');
const request = (url, options = {}) => apiData(url, options, '操作失敗');
function showLogin() {
    loginShell.hidden = false;
    adminConsole.hidden = true;
    apiState.textContent = '需要管理員登入'
}
function showAdmin(session) {
    loginShell.hidden = true;
    adminConsole.hidden = false;
    adminName.textContent = session.username;
    csrf = session.csrf;
    apiState.textContent = '管理員已登入';
    apiState.classList.add('ok');
    loadAdmin()
}
async function loadAdmin() {
    try {
        const [settings, catalogData, submissionData, staff, documents, questionItems, answerItems, taxonomy] =
            await Promise.all([request('/api/admin/settings'), request('/api/admin/catalog'),
            request('/api/admin/submissions'),
            request('/api/admin/staff'),
            request('/api/admin/manuals/documents'),
            request('/api/admin/compliance/questions'),
            request('/api/admin/compliance/answers'),
            request('/api/admin/training/taxonomy')]);
        settingsForm.theme.value = settings.theme;
        settingsForm.hero_title.value = settings.hero_title;
        settingsForm.hero_subtitle.value = settings.hero_subtitle;
        settingsForm.announcement.value = settings.announcement || '';
        updatePreview(); tables = catalogData; staffItems = staff;
        submissions = submissionData; operationsManuals = documents;
        complianceQuestions = questionItems;
        essayAnswers = answerItems;
        trainingTaxonomy = taxonomy;
        renderCatalog();
        renderQueue();
        renderTrainingDocuments();
        renderTrainingTaxonomy();
        renderQuestions();
        renderEssayAnswers()
    } catch (error) { toast.textContent = error.message; toast.classList.add('show') }
}
bindTabs(adminTabs);
function updatePreview() {
    settingsPreview.className = `settings-preview ${settingsForm.theme.value}`;
    previewTitle.textContent = settingsForm.hero_title.value || '首頁標題';
    previewSubtitle.textContent = settingsForm.hero_subtitle.value || '首頁說明'
}
settingsForm.addEventListener('input', updatePreview);
settingsForm.onsubmit = async event => {
    event.preventDefault(); settingsStatus.className = '';
    settingsStatus.textContent = '儲存中…'; try {
        await request('/api/admin/settings', {
            method: 'POST', headers: {
                'Content-Type': 'application/json', 'X-CSRF-Token': csrf
            },
            body: JSON.stringify(Object.fromEntries(new FormData(settingsForm)))
        });
        settingsStatus.className = 'success-note';
        settingsStatus.textContent = '設定已寫入 SQL Server 並發布。'
    } catch (error) {
        settingsStatus.className = 'error-note';
        settingsStatus.textContent = error.message
    }
};
function renderCatalog() {
    //20260816第379行「<small>${esc(item.name)} ·」的這個刪掉，顯示上就不擁擠，也更美觀
    const q = catalogSearch.value.trim().toLowerCase(),
        items = tables.filter(item => `${item.name} ${item.display_name || ''}`.toLowerCase().includes(q));
    catalog.innerHTML = items.map(item =>
        `<button class="catalog-item ${item.name === selectedTable ? 'active' : ''}" data-table="${esc(item.name)}">
        <span>${esc(item.display_name || item.name)}</span>
        <small>${number(item.row_count)} 筆</small>
        </button>`).join('') || '<div class="empty">找不到資料表</div>'
} catalogSearch.oninput = renderCatalog; catalog.onclick = event => {
    const button = event.target.closest('[data-table]'); if (button) loadTable(button.dataset.table, 1)
};
async function loadTable(name, page) {
    selectedTable = name; currentPage = page; renderCatalog();
    const catalogItem = tables.find(item => item.name === name);
    dataTitle.textContent = catalogItem?.display_name || name;//維持現狀的三元判斷式
    dataBody.innerHTML = '<tr><td>查詢中…</td></tr>';
    try {
        const result = await request(`/api/admin/table?name=${encodeURIComponent(name)}&page=${page}&page_size=${pageSize}`);
        totalRows = result.total;
        dataMeta.textContent = `${result.columns.length} 欄 · ${number(result.total)} 筆 · 唯讀遮罩`;
        dataHead.innerHTML = `<tr>${result.columns.map(column => `<th>${esc(column.name)}<br><small>${esc(column.type)}</small></th>`).join('')}</tr>`;
        dataBody.innerHTML = result.rows.length ? result.rows.map(row => `<tr>${result.columns.map(column =>
            `<td class="${column.classification}">${row[column.name] === null ? 'NULL' : esc(row[column.name])}</td>`).join('')}</tr>`).join('') :
            `<tr><td colspan="${result.columns.length}">目前沒有資料。</td></tr>`;
        const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
        pageInfo.textContent = `第 ${page} / ${totalPages} 頁`;
        prevPage.disabled = page <= 1;
        nextPage.disabled = page >= totalPages
    } catch (error) { dataBody.innerHTML = `<tr><td>${esc(error.message)}</td></tr>` }
}
prevPage.onclick = () => currentPage > 1 && loadTable(selectedTable, currentPage - 1);
nextPage.onclick = () => currentPage * pageSize < totalRows && loadTable(selectedTable, currentPage + 1);
function renderQueue() {
    const counts = new Map(); submissions.forEach(item => {
        if (item.submitted_by) counts.set(item.submitted_by,
            (counts.get(item.submitted_by) || 0) + 1)
    });
    staffList.innerHTML = `<button class="review-person ${selectedEmployee === '' ? 'active' : ''}" data-employee=""><span class="review-avatar">ALL</span><div><b>全部員工</b><small>顯示所有待審事件</small></div><em>${number(submissions.length)}</em></button>` + staffItems.map(item => `<button class="review-person ${selectedEmployee === item.employee_id ? 'active' : ''}" data-employee="${esc(item.employee_id)}"><img src="${item.photo_file ? `static/staff/${encodeURIComponent(item.photo_file)}` : 'static/appicon.png'}" alt=""><div><b>${esc(item.employee_id)}｜${esc(item.display_name)}</b><small>${esc(item.department)} · ${esc(item.position)}</small></div><em>${number(counts.get(item.employee_id) || 0)}</em></button>`).join('');
    bindImageFallbacks(staffList);
    const categories = [...new Set(submissions.map(item => item.category))];
    queueFilters.innerHTML = `<button class="${selectedCategory === '' ? 'active' : ''}" data-category="">全部事件</button>` + categories.map(category => `<button class="${selectedCategory === category ? 'active' : ''}" data-category="${esc(category)}">${esc(category)}</button>`).join('');
    const employee = staffItems.find(item => item.employee_id === selectedEmployee);
    const items = submissions.filter(item => (!selectedEmployee || item.submitted_by === selectedEmployee) && (!selectedCategory || item.category === selectedCategory));
    queueTitle.textContent = `${employee ? `${employee.display_name}的` : ''}${selectedCategory || '全部'}申請事件`;
    queueCount.textContent = `${number(items.length)} 筆`;
    submissionList.innerHTML = items.length ? items.map(item => `<article class="review-event-card submission-card">
        <header><b>${esc(item.category)} · ${esc(item.campus)}</b><span class="tag">${esc(item.status)}</span></header>
        <p>${esc(item.date)} · ${number(item.count)} 筆 · ${esc(item.note || '無備註')}</p>
        <footer><span>${esc(item.submitted_by || '未記錄')}｜${esc(item.submitted_by_name || '未記錄建立者')}</span><small>${esc(item.submitted_at)}</small></footer>
        <div class="activity-list">${item.activities.map(activity => `<div class="activity-item"><b>${esc(activity.actor_role === 'admin' ? '管理員' : '員工')}</b>${activity.message ? `<p>${esc(activity.message)}</p>` : ''}<small>${esc(activity.created_at)}</small></div>`).join('')}</div>
        <form class="review-form" data-review-id="${esc(item.id)}">
            <label class="field"><span>審閱意見</span><textarea name="message" maxlength="1000" placeholder="要求補件時必填"></textarea></label>
            <div class="actions"><button class="btn secondary" name="status" value="要求補件">要求補件</button><button class="btn" name="status" value="審核通過">審核通過</button><button class="btn secondary" name="status" value="已退回">退回</button></div>
        </form>
    </article>`).join('') : '<div class="empty">目前沒有符合條件的待審事項。</div>'
}
staffList.onclick = event => {
    const button = event.target.closest('[data-employee]');
    if (!button) return;
    selectedEmployee = button.dataset.employee;
    selectedCategory = '';
    renderQueue()
};
queueFilters.onclick = event => {
    const button = event.target.closest('[data-category]');
    if (!button) return;
    selectedCategory = button.dataset.category;
    renderQueue()
};
submissionList.onsubmit = async event => {
    const form = event.target.closest('[data-review-id]');
    if (!form) return;
    event.preventDefault();
    const submitter = event.submitter;
    try {
        await request('/api/admin/submission/review', {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
            body: JSON.stringify({id: form.dataset.reviewId, status: submitter.value, message: form.elements.message.value})
        });
        submissions = await request('/api/admin/submissions');
        renderQueue()
    } catch (error) {
        alert(error.message)
    }
};
/* 渲染SOP文件，並同步更新題目表單的文件選單。 */
function renderTrainingTaxonomy() {
    const subjectOptions = trainingTaxonomy.subjects.map(item =>
        `<option value="${item.id}" data-domain="${item.domain}">${item.domain === 'academic' ? '學科' : '術科'}｜${esc(item.name)}</option>`).join('');
    chapterSubject.innerHTML = subjectOptions;
    questionSubject.innerHTML = subjectOptions;
    bulkSubject.innerHTML = '<option value="">不變更科目</option>' + subjectOptions;
    renderQuestionChapters();
    renderBulkChapters();
    taxonomyList.innerHTML = trainingTaxonomy.subjects.map(subject => {
        const chapters = trainingTaxonomy.chapters.filter(item => item.subject_id === subject.id);
        return `<article class="staff-admin-card"><div><b>${subject.domain === 'academic' ? '學科' : '術科'}｜${esc(subject.name)}</b>
            <small>${subject.domain === 'academic' ? `${subject.mock_question_count} 題／${subject.mock_duration_minutes} 分鐘／${subject.mock_pass_score} 分及格` : '人工審核'} · ${subject.is_active ? '啟用' : '停用'}</small>
            <small>${chapters.map(item => `<button class="text-action" data-chapter-edit="${item.id}" type="button">${esc(item.code)} ${esc(item.name)}</button>`).join(' ') || '尚無章節'}</small></div>
            <button class="btn secondary" data-subject-edit="${subject.id}">編輯</button></article>`
    }).join('') || '<div class="empty">尚未建立科目。</div>'
}
function renderQuestionChapters() {
    const subjectId = Number(questionSubject.value || trainingTaxonomy.subjects[0]?.id || 0);
    const chapters = trainingTaxonomy.chapters.filter(item => item.subject_id === subjectId);
    questionChapter.innerHTML = chapters.map(item => `<option value="${item.id}">${esc(item.code)}｜${esc(item.name)}</option>`).join('');
    const subject = trainingTaxonomy.subjects.find(item => item.id === subjectId);
    if (subject) questionDomain.value = subject.domain
}
questionSubject.onchange = renderQuestionChapters;
function renderBulkChapters() {
    const subjectId = Number(bulkSubject.value || 0);
    bulkChapter.innerHTML = '<option value="">不變更章節</option>' + trainingTaxonomy.chapters.filter(item => item.subject_id === subjectId)
        .map(item => `<option value="${item.id}">${esc(item.code)}｜${esc(item.name)}</option>`).join('')
}
bulkSubject.onchange = renderBulkChapters;
subjectForm.onsubmit = async event => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(subjectForm));
    await request('/api/admin/training/subject', { method: 'POST', headers: {'Content-Type':'application/json','X-CSRF-Token':csrf},
        body: JSON.stringify({...values,id:Number(values.id||0),mock_question_count:Number(values.mock_question_count),mock_duration_minutes:Number(values.mock_duration_minutes),mock_pass_score:Number(values.mock_pass_score),is_active:subjectForm.elements.is_active.checked}) });
    trainingTaxonomy = await request('/api/admin/training/taxonomy'); renderTrainingTaxonomy(); subjectForm.reset()
};
chapterForm.onsubmit = async event => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(chapterForm));
    await request('/api/admin/training/chapter', { method: 'POST', headers: {'Content-Type':'application/json','X-CSRF-Token':csrf},
        body: JSON.stringify({...values,id:Number(values.id||0),subject_id:Number(values.subject_id),display_order:Number(values.display_order||0),is_active:chapterForm.elements.is_active.checked}) });
    trainingTaxonomy = await request('/api/admin/training/taxonomy'); renderTrainingTaxonomy(); chapterForm.reset()
};
document.querySelector('#resetSubject').onclick = () => subjectForm.reset();
document.querySelector('#resetChapter').onclick = () => chapterForm.reset();
taxonomyList.onclick = event => {
    const button = event.target.closest('[data-subject-edit]'), chapterButton = event.target.closest('[data-chapter-edit]');
    if (button) {
        const item = trainingTaxonomy.subjects.find(row => row.id === Number(button.dataset.subjectEdit)); if (!item) return;
        Object.entries({id:item.id,domain:item.domain,name:item.name,mock_question_count:item.mock_question_count,mock_duration_minutes:item.mock_duration_minutes,mock_pass_score:item.mock_pass_score}).forEach(([name,value]) => subjectForm.elements[name].value = value);
        subjectForm.elements.is_active.checked = item.is_active
    }
    if (chapterButton) {
        const item = trainingTaxonomy.chapters.find(row => row.id === Number(chapterButton.dataset.chapterEdit)); if (!item) return;
        Object.entries({id:item.id,subject_id:item.subject_id,code:item.code,name:item.name,display_order:item.display_order}).forEach(([name,value]) => chapterForm.elements[name].value = value);
        chapterForm.elements.is_active.checked = item.is_active
    }
};
function renderTrainingDocuments() {
    //將每筆文件轉成一張卡片（article）
    //is_active 為 false 時，卡片加上 inactive class（樣式變灰/降低顯示優先度）
    //顯示標題、分類、段落數、原始檔名，並在停用時附加「已停用」文字
    //按鈕依目前啟用狀態顯示「停用」或「啟用」，並透過 data-* 屬性
    //傳遞文件id與「點擊後應該切換成的目標狀態」(data-active)
    trainingDocumentList.innerHTML = operationsManuals.map(item => `<article class="staff-admin-card training-document-card ${item.is_active ? '' : 'inactive'}">
    <div>
        <b>${esc(item.title)}</b>
        <small>${esc(item.category)} · ${item.section_count} 段 · ${esc(item.file_name)} · ${esc(item.source_kind || 'manual')}${item.parse_status ? ` · ${esc(item.parse_status)}` : ''}${item.is_active ? '' : ' · 已停用'}</small>
        ${item.parse_message ? `<small class="error-note">${esc(item.parse_message)}</small>` : ''}
    </div>
    <button class="btn secondary compact-action" data-document-state="${item.id}" data-active="${item.is_active ? 'false' : 'true'}">
        ${item.is_active ? '停用' : '啟用'}
    </button>
</article>`).join('') || '<div class="empty">目前沒有SOP文件。</div>';
    questionDocument.innerHTML = '<option value="">不指定文件</option>' +
        operationsManuals.map(item =>
            `<option value="${item.id}">${esc(item.title)}</option>`
        ).join('');
}
/* 渲染商業規範與工安檢核題目。 */
const questionTypeNames = {
    single_choice: '單選題', multiple_choice: '多選題', reading: '閱讀測驗',
    fill_blank: '程式碼填空', matching: '配對題', essay: '申論題'
};
function setQuestionType(type) {
    questionForm.elements.question_type.value = type;
    questionTypeTabs.querySelectorAll('[data-question-type]').forEach(button =>
        button.classList.toggle('active', button.dataset.questionType === type));
    const essay = type === 'essay', reading = type === 'reading', structured = ['fill_blank', 'matching'].includes(type);
    passageField.hidden = !reading;
    optionsField.hidden = essay || structured;
    answersField.hidden = essay;
    structureField.hidden = !structured;
    explanationField.hidden = essay;
    essayHint.hidden = !essay;
    questionDomain.value = essay ? 'practical' : 'academic';
    questionForm.elements.passage.required = reading;
    questionForm.elements.options.required = !essay && !structured;
    questionForm.elements.answers.required = !essay;
    questionForm.elements.explanation.required = !essay && questionForm.elements.status.value === 'published'
}
questionTypeTabs.onclick = event => {
    const button = event.target.closest('[data-question-type]');
    if (button) setQuestionType(button.dataset.questionType)
};
function renderQuestions() {
    const keyword = questionSearch.value.trim().toLowerCase(), statusFilter = questionStatusFilter.value,
        visibleQuestions = complianceQuestions.filter(item => (!statusFilter || item.status === statusFilter) &&
            (!keyword || `${item.subject} ${item.chapter} ${item.question}`.toLowerCase().includes(keyword)));
    questionList.innerHTML = visibleQuestions.map(item => `<article class="staff-admin-card question-card ${item.status === 'published' ? '' : 'inactive'}">
    <input type="checkbox" data-question-select="${item.id}" aria-label="選取題目 ${item.id}">
    <div>
        <b class="question-title" title="${esc(item.subject)}｜${esc(item.chapter)}｜${esc(item.question)}">${esc(item.subject || '未分類')}｜${esc(item.chapter || item.category)}｜${esc(item.question)}</b>
        <small>${item.domain === 'practical' ? '術科' : '學科'} · ${esc(questionTypeNames[item.question_type] || item.question_type)} · ${esc(item.status)}${item.admin_locked ? ' · 管理員保護' : ''}${item.parse_warnings?.length ? ` · ${item.parse_warnings.length} 項解析警告` : ''}</small>
    </div>
    <div class="btn-group">
        <button class="btn secondary" data-question-edit="${item.id}">編輯</button>
        ${item.source ? `<button class="btn secondary" data-question-reimport="${item.id}">以來源重新匯入</button>` : ''}
        ${item.status !== 'published' ? `<button class="btn" data-question-status="${item.id}" data-status="published">發布</button>` : `<button class="btn secondary" data-question-status="${item.id}" data-status="draft">退回草稿</button>`}
        ${item.status !== 'disabled' ? `<button class="btn secondary" data-question-disable="${item.id}">停用</button>` : ''}
    </div>
    </article>`).join('') || '<div class="empty">目前沒有題目。</div>'
}
questionSearch.oninput = renderQuestions;
questionStatusFilter.onchange = renderQuestions;
trainingDocumentList.onclick = async event => {
    const button = event.target.closest('[data-document-state]');
    if (!button) return; await request('/api/admin/manuals/document', {
        method: 'POST', headers: {
            'Content-Type': 'application/json', 'X-CSRF-Token': csrf
        }, body: JSON.stringify({
            id: Number(button.dataset.documentState),
            is_active: button.dataset.active === 'true'
        })
    });
    //重新載入並渲染文件
    operationsManuals = await request('/api/admin/manuals/documents');
    renderTrainingDocuments()
};
questionList.onclick = async event => {
    const edit = event.target.closest('[data-question-edit]'),
        disable = event.target.closest('[data-question-disable]'),
        reimport = event.target.closest('[data-question-reimport]');
    if (edit) {
        const item = complianceQuestions.find(row => row.id === Number(edit.dataset.questionEdit));
        if (item) {
            questionForm.elements.id.value = item.id;
            questionForm.elements.document_id.value = item.document_id || '';
            questionForm.elements.subject_id.value = item.subject_id || '';
            renderQuestionChapters();
            questionForm.elements.chapter_id.value = item.chapter_id || '';
            questionForm.elements.domain.value = item.domain;
            questionForm.elements.status.value = item.status;
            setQuestionType(item.question_type);
            questionForm.elements.question.value = item.question;
            questionForm.elements.passage.value = item.passage || '';
            questionForm.elements.options.value = item.options.join('\n');
            questionForm.elements.answers.value = item.answers.map(value => value + 1).join(',');
            if (['fill_blank','matching'].includes(item.question_type)) questionForm.elements.answers.value = item.answers.join('\n');
            questionForm.elements.structure.value = JSON.stringify(item.structure || {}, null, 2);
            questionForm.elements.explanation.value = item.explanation;
            questionForm.elements.question.focus()
        }
    }
    const statusButton = event.target.closest('[data-question-status]');
    if (statusButton) {
        await request('/api/admin/training/question/status', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
            body:JSON.stringify({id:Number(statusButton.dataset.questionStatus),status:statusButton.dataset.status})});
        complianceQuestions = await request('/api/admin/compliance/questions'); renderQuestions()
    }
    if (reimport && confirm('此操作會解除管理員保護，並重新解析來源。\n\n將覆寫：題幹、選項或配對資料、正解、解析、分類、來源位置與解析警告。\n\n確定繼續？')) {
        await request('/api/admin/training/question/reimport', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
            body:JSON.stringify({question_id:Number(reimport.dataset.questionReimport)})});
        complianceQuestions = await request('/api/admin/compliance/questions'); renderQuestions()
    }
    if (disable && confirm('確定停用此題目？')) {
        await request('/api/admin/compliance/question', {
            method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
            body: JSON.stringify({ id: Number(disable.dataset.questionDisable) })
        });
        complianceQuestions = await request('/api/admin/compliance/questions');
        renderQuestions()
    }
};
questionForm.onsubmit = async event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(questionForm));
    const essay = values.question_type === 'essay';
    const structured = ['fill_blank','matching'].includes(values.question_type);
    let structure = {};
    try { structure = values.structure ? JSON.parse(values.structure) : {} } catch (_) { questionStatus.className='error-note'; questionStatus.textContent='題型結構必須是有效 JSON。'; return }
    const payload = {
        ...values, id: Number(values.id || 0),
        document_id: Number(values.document_id || 0) || null,
        subject_id: Number(values.subject_id), chapter_id: Number(values.chapter_id),
        chapter_name: questionChapter.selectedOptions[0]?.textContent || '',
        options: essay || structured ? [] : values.options.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
        answers: essay ? [] : structured ? values.answers.split(/\r?\n/).map(value => value.trim()).filter(Boolean) : values.answers.split(/[,，、\s]+/).filter(Boolean).map(value => Number(value) - 1),
        content_blocks: [{type:'text',content:values.question}], structure,
        passage: values.passage || '',
        explanation: essay ? '' : values.explanation
    };
    questionStatus.textContent = '儲存中…';
    try {
        await request('/api/admin/compliance/question', {
            method: 'POST', headers: {
                'Content-Type': 'application/json', 'X-CSRF-Token': csrf
            },
            body: JSON.stringify(payload)
        });
        questionForm.reset();
        setQuestionType('single_choice');
        complianceQuestions = await request('/api/admin/compliance/questions');
        renderQuestions();
        questionStatus.className = 'success-note';
        questionStatus.textContent = '題目已儲存。'
    } catch (error) {
        questionStatus.className = 'error-note';
        questionStatus.textContent = error.message
    }
};
resetQuestion.onclick = () => {
    questionForm.reset();
    setQuestionType('single_choice');
    questionStatus.textContent = '';
    questionForm.elements.question.focus()
};
document.querySelector('#applyQuestionBulk').onclick = async () => {
    const ids = [...questionList.querySelectorAll('[data-question-select]:checked')].map(item => Number(item.dataset.questionSelect));
    if (!ids.length) return alert('請先勾選題目。');
    if (bulkSubject.value && !bulkChapter.value) return alert('變更分類時請同時選擇章節。');
    await request('/api/admin/training/questions/bulk', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({
        ids,subject_id:Number(bulkSubject.value||0)||null,chapter_id:Number(bulkChapter.value||0)||null,status:bulkStatus.value
    })});
    complianceQuestions = await request('/api/admin/compliance/questions'); renderQuestions()
};
function renderEssayAnswers() {
    essayAnswerList.innerHTML = essayAnswers.length ? essayAnswers.map(item => `<article class="submission-card essay-answer-card">
        <header><b>${esc(item.category)}｜${esc(item.question)}</b><span class="tag">${esc(item.status)}</span></header>
        <p><b>${esc(item.employee_id)}｜${esc(item.employee_name)}</b></p>
        <div class="essay-answer-text">${esc(item.answer_text).replace(/\n/g, '<br>')}</div>
        ${item.feedback ? `<p class="hint">審核回饋：${esc(item.feedback)}</p>` : ''}
        <form data-essay-review="${item.id}"><label class="field"><span>審核回饋</span><textarea name="feedback" maxlength="1000" placeholder="要求修正時必填">${esc(item.feedback || '')}</textarea></label>
            <div class="actions"><button class="btn" name="status" value="審核通過">審核通過</button><button class="btn secondary" name="status" value="需修正">需修正</button></div>
        </form>
    </article>`).join('') : '<div class="empty">目前沒有申論答案。</div>'
}
essayAnswerList.onsubmit = async event => {
    const form = event.target.closest('[data-essay-review]');
    if (!form) return;
    event.preventDefault();
    try {
        await request('/api/admin/compliance/answer/review', {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
            body: JSON.stringify({id: Number(form.dataset.essayReview), status: event.submitter.value, feedback: form.elements.feedback.value})
        });
        essayAnswers = await request('/api/admin/compliance/answers');
        renderEssayAnswers()
    } catch (error) {
        alert(error.message)
    }
};
setQuestionType('single_choice');
syncTraining.onclick = async () => {
    syncTraining.disabled = true;
    syncStatus.textContent = '正在解析並同步 Word、Excel 與 PDF 文件…';
    try {
        const result = await request('/api/admin/manuals/sync', {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: '{}'
        });
        operationsManuals = await request('/api/admin/manuals/documents');
        renderTrainingDocuments();
        syncStatus.className = 'success-note';
        complianceQuestions = await request('/api/admin/compliance/questions');
        trainingTaxonomy = await request('/api/admin/training/taxonomy');
        renderTrainingTaxonomy(); renderQuestions();
        const failures = result.failures || [], warnings = result.warnings || [];
        syncStatus.textContent = `已同步 ${result.documents} 份文件；解析 ${result.parsed} 題、待校對 ${result.pending_review}、警告 ${warnings.length}、重複 ${result.duplicates}、失敗 ${failures.length}、管理員保護 ${result.locked}。` +
            (failures.length ? ` 失敗明細：${failures.map(item => `${item.source}：${item.message}`).join('；')}` : '');
    } catch (error) {
        syncStatus.className = 'error-note';
        syncStatus.textContent = error.message
    } finally {
        syncTraining.disabled = false
    }
};
bindAdminAccess({
    loginForm,
    loginStatus,
    logoutButton,
    onAuthenticated: showAdmin,
    onUnauthenticated: () => {
        csrf = '';
        showLogin();
    },
});
