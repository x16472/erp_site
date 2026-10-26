const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const resultSection = document.getElementById('result');
const imgPreview = document.getElementById('img-preview');
const errorMsg = document.getElementById('error-msg');
// 點擊觸發上傳
dropZone.addEventListener('click', () => fileInput.click());
// 拖曳視覺效果
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
    }
});
// 檔案選擇變更
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});
// 處理圖片檔案
function handleFile(file) {
    errorMsg.style.display = 'none';
    resultSection.style.display = 'none';
    if (file.type !== 'image/png') {
        showError('目前僅支援原始的 PNG 格式圖片。');
        return;
    }
    // 顯示預覽圖
    const url = URL.createObjectURL(file);
    imgPreview.src = url;
    const reader = new FileReader();
    reader.onload = function (e) {
        const buffer = e.target.result;
        const view = new DataView(buffer);
        // 驗證 PNG 標頭
        if (view.getUint32(0) !== 0x89504E47) {
            showError('無效的 PNG 檔案。');
            return;
        }
        let pos = 8;
        let metadataText = "";
        // 尋找 PNG 區塊 (Chunks)
        while (pos < buffer.byteLength) {
            if (pos + 8 > buffer.byteLength) break;

            const length = view.getUint32(pos);
            const type = view.getUint32(pos + 4);

            // 0x74455874 是 "tEXt" 區塊的 ASCII 碼
            if (type === 0x74455874) {
                const dataPos = pos + 8;
                const textBytes = new Uint8Array(buffer, dataPos, length);
                const decoder = new TextDecoder('utf-8');
                const fullText = decoder.decode(textBytes);

                // WebUI 通常會把關鍵字寫在 'parameters\0' 後面
                if (fullText.startsWith('parameters\0')) {
                    metadataText = fullText.substring(11); // 扣除 'parameters\0'
                    break;
                }
            }
            pos += 12 + length; // 4位長度 + 4位類型 + 資料長度 + 4位CRC
        }

        if (metadataText) {
            parseSDParameters(metadataText);
            resultSection.style.display = 'block';
        } else {
            showError('這張圖片中找不到 WebUI 參數（可能被社群軟體壓縮抹除了）。');
        }
    };
    reader.readAsArrayBuffer(file);
}
// 解析 Stable Diffusion 的文字格式
function parseSDParameters(text) {
    let prompt = "";
    let negPrompt = "";
    let otherParams = "";
    // WebUI 格式通常是:
    // [Prompt]
    // Negative prompt: [Neg Prompt]
    // Steps: 20, Sampler: DPM++...
    const negMarker = "Negative prompt:";
    const stepsMarker = "Steps:";

    let negIdx = text.indexOf(negMarker);
    let stepsIdx = text.indexOf(stepsMarker);

    if (negIdx !== -1) {
        prompt = text.substring(0, negIdx).trim();
        if (stepsIdx !== -1) {
            negPrompt = text.substring(negIdx + negMarker.length, stepsIdx).trim();
            otherParams = text.substring(stepsIdx).trim();
        } else {
            negPrompt = text.substring(negIdx + negMarker.length).trim();
        }
    } else if (stepsIdx !== -1) {
        prompt = text.substring(0, stepsIdx).trim();
        otherParams = text.substring(stepsIdx).trim();
    } else {
        prompt = text.trim();
    }
    document.getElementById('prompt').value = prompt || "(無)";
    document.getElementById('neg-prompt').value = negPrompt || "(無)";
    document.getElementById('raw-params').value = otherParams || "(無)";
}
function showError(msg) {
    errorMsg.innerText = msg;
    errorMsg.style.display = 'block';
}