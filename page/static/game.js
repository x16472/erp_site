import { apiData, requireEmployee } from './script.js';

const DEFAULT_URL = 'https://www.youtube.com/watch?v=BsvIwqyiaJw';
const youtubeForm = document.querySelector('#youtubeForm'),
    youtubeUrl = document.querySelector('#youtubeUrl'),
    youtubePlayer = document.querySelector('#youtubePlayer'),
    youtubeStatus = document.querySelector('#youtubeStatus'),
    playerState = document.querySelector('#playerState'),
    videoTitle = document.querySelector('#videoTitle'),
    openYoutube = document.querySelector('#openYoutube'),
    submitButton = youtubeForm.querySelector('button[type="submit"]');
const employeeAccess = requireEmployee();
async function resolveVideo(url, remember = true) {
    const controller = new AbortController(),
        timer = setTimeout(() => controller.abort(), 10000);
    submitButton.disabled = true;
    playerState.textContent = '後端驗證中';
    youtubeStatus.className = 'hint';
    youtubeStatus.textContent = '正在確認影片並取得標題…';
    try {
        await employeeAccess;
        const video = await apiData('/api/youtube/resolve', {
            method: 'POST', credentials: 'include', headers: {
                'Content-Type': 'application/json'
            }, body: JSON.stringify({ url }),
            signal: controller.signal
        }, '影片資訊取得失敗');
        youtubePlayer.src = video.embed_url;
        videoTitle.textContent = video.title;
        openYoutube.href = video.watch_url;
        youtubeUrl.value = video.watch_url;
        if (remember) localStorage.setItem('YoutubeVideo', video.watch_url);
        youtubeStatus.className = 'hint success-note';
        youtubeStatus.textContent = '後端已驗證網址並取得 YouTube 影片標題。';
        playerState.textContent = '播放器已更新';
    } catch (error) {
        const message = error.name === 'AbortError' ? '影片資訊讀取逾時，請稍後重試。' : error.message;
        youtubeStatus.className = 'error-note';
        youtubeStatus.textContent = message; playerState.textContent = '影片載入失敗';
    } finally {
        clearTimeout(timer);
        submitButton.disabled = false
    }
}
youtubeForm.addEventListener('submit', event => {
    event.preventDefault();
    resolveVideo(youtubeUrl.value);
});
const savedUrl = localStorage.getItem('YoutubeVideo');
resolveVideo(savedUrl || DEFAULT_URL, false);
