const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('快速切換資料表時，只顯示最後一次選取的結果', async () => {
    const source = fs.readFileSync(path.join(__dirname, '../static/js/mis.js'), 'utf8');
    const pending = new Map();
    const context = vm.createContext({
        tableRequestVersion: 0, tables: [], pageSize: 20,
        renderCatalog() {}, esc: value => String(value), number: value => value,
        request: url => new Promise((resolve, reject) => pending.set(url, { resolve, reject })),
        ...Object.fromEntries(['dataTitle', 'dataBody', 'dataHead', 'dataMeta', 'pageInfo', 'prevPage', 'nextPage']
            .map(name => [name, { innerHTML: '', textContent: '', disabled: false }])),
    });
    vm.runInContext(source.slice(source.indexOf('async function loadTable('), source.indexOf('prevPage.onclick =')), context);
    const first = context.loadTable('Company_TrainingDocument', 1);
    const second = context.loadTable('Company_TrainingQuestion', 1);
    const requests = [...pending.values()];
    requests[1].resolve({ total: 12, page_size: 20, columns: [{ name: 'question_id', type: 'nvarchar' }], rows: [{ question_id: 12 }] });
    await second;
    const latestContent = context.dataBody.innerHTML;
    requests[0].resolve({ total: 4, page_size: 20, columns: [{ name: 'document_id', type: 'nvarchar' }], rows: [{ document_id: 1 }] });
    await first;
    assert.equal(context.dataTitle.textContent, 'Company_TrainingQuestion');
    assert.equal(context.dataBody.innerHTML, latestContent);
    assert.match(context.dataHead.innerHTML, /question_id/);
    assert.doesNotMatch(context.dataHead.innerHTML, /document_id/);

    const stale = context.loadTable('Company_TrainingDocument', 1);
    const latest = context.loadTable('Company_TrainingQuestion', 1);
    const retryRequests = [...pending.values()];
    retryRequests[1].resolve({ total: 0, page_size: 20, columns: [], rows: [] });
    await latest;
    retryRequests[0].reject(new Error('過期查詢失敗'));
    await stale;
    assert.doesNotMatch(context.dataBody.innerHTML, /過期查詢失敗/);
});

test('題庫編號依數值排序，文字型別的 10 與 11 不會排在 2 前面', () => {
    const source = fs.readFileSync(path.join(__dirname, '../static/js/mis.js'), 'utf8');
    const context = vm.createContext({
        questionSearch: { value: '' }, questionStatusFilter: { value: '' },
        complianceQuestions: ['1', '10', '11', '2', '51'].map(id => ({
            id, question: `題目 ${id}`, status: 'published', question_type: 'single_choice',
        })),
        selectedQuestionIds: new Set(), questionForm: { elements: { id: { value: '' } } },
        questionList: { innerHTML: '' },
        questionTypeNames: { single_choice: '單選題' }, questionStatusNames: { published: '已發布' },
        esc: value => String(value ?? ''), updateQuestionControls() {},
        document: { querySelector: () => ({ textContent: '' }) },
    });
    vm.runInContext(source.slice(source.indexOf('function renderQuestions()'), source.indexOf('questionSearch.oninput =')), context);
    context.renderQuestions();
    const ids = [...context.questionList.innerHTML.matchAll(/data-question-row="(\d+)"/g)].map(match => match[1]);
    assert.deepEqual(ids, ['1', '2', '10', '11', '51']);
});
