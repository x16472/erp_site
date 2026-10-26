const $ = id => document.getElementById(id);
const dz = $('drop-zone'), fi = $('file');
const showErr = msg => { $('err').textContent = msg; $('err').hidden = !msg; }

dz.onclick = () => fi.click();
dz.ondragover = e => e.preventDefault();
dz.ondrop = e => { e.preventDefault(); load(e.dataTransfer.files[0]); };
fi.onchange = e => load(e.target.files[0]);
async function load(f) {
    showErr('');
    $('result').hidden = true;
    if (!f || f.type !== 'image/png') return showErr('僅支援 PNG 格式');
    $('img-prev').src = URL.createObjectURL(f);
    const buf = await f.arrayBuffer(), v = new DataView(buf), dec = new TextDecoder('utf-8');
    if (v.getUint32(0) !== 0x89504E47) return showErr('無效的 PNG');
    // 逐一走訪 PNG chunk，找出 tEXt 內以 "parameters" 開頭的內容
    for (let pos = 8; pos + 8 <= buf.byteLength;) {
        const len = v.getUint32(pos);
        if (v.getUint32(pos + 4) === 0x74455874) {
            const s = dec.decode(new Uint8Array(buf, pos + 8, len));
            if (s.startsWith('parameters\0')) {
                convert(s.slice(11));
                $('result').hidden = false;
                return;
            }
        }
        pos += 12 + len;
    }
    showErr('找不到 SD 參數');
}
function convert(t) {
    const n = t.indexOf('Negative prompt:'), s = t.indexOf('Steps:');
    const end = s < 0 ? t.length : s;
    const p = t.slice(0, n < 0 ? end : n);
    const np = n < 0 ? '' : t.slice(n + 16, end);
    const op = s < 0 ? '' : t.slice(s);
    // 擷取 LoRA 並從提示詞中移除
    const lo = $('loras');
    lo.textContent = '';
    const cleanP = p
        .replace(/<lora:([^:]+):([^>]+)>/g, (_, name, w) => { lo.append(`【${name}:${w}】`); return ''; })
        .replace(/,\s*,/g, ',')
        .replace(/^\s*,|,\s*$/g, '')
        .trim();
    $('cp').value = cleanP || '(無)';
    $('cn').value = np.trim() || '(無)';
    // 解析 Steps、Seed 等參數
    const m = {};
    op.split(',').forEach(i => {
        const [k, ...v] = i.split(':');
        if (v.length) m[k.trim().toLowerCase()] = v.join(':').trim();
    });
    // 從 Sampler 名稱分離出 Scheduler
    const ws = m.sampler || '';
    const sch = (ws.match(/karras|exponential/i) || ['normal'])[0].toLowerCase();
    const samp = ws.replace(/karras|exponential/i, '').trim();
    const info = { seed: m.seed, steps: m.steps, cfg: m['cfg scale'], size: m.size, samp, sch };
    for (const k in info) $('m-' + k).textContent = info[k] || '-';
};