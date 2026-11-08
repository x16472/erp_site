// 1. 全域設定與核心邏輯分類 (Config)
const YoutubeThumbnailApp = {
    STORAGE_KEY: "youtube_thumbnails_v2",
    MAX_ITEMS: 8,
    ID_RE: /^[A-Za-z0-9_-]{11}$/,
    SIZES: [
        ["maxresdefault", 1280, 720, "HD"],
        ["sddefault", 640, 480, "SD"],
        ["hqdefault", 480, 360, "HQ"],
        ["mqdefault", 320, 180, "MQ"],
    ],
    $: (id) => document.getElementById(`thumbnail-${id}`),
    thumbUrl: (id, name) => `https://i.ytimg.com/vi/${id}/${name}.jpg`,
    // 網址與 ID 解析
    parseVideoId(input) {
        const text = input.trim();
        if (this.ID_RE.test(text)) return text;
        let url;
        try {
            url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
        } catch {
            return null;
        }
        if (!['http:', 'https:'].includes(url.protocol)) return null;
        const host = url.hostname.replace(/^(www|m|music)\./, "");
        let id = null;
        if (host === "youtu.be") {
            id = url.pathname.split("/")[1];
        } else if (host === "youtube.com" || host === "youtube-nocookie.com") {
            id = url.searchParams.get("v") || (url.pathname.match(/^\/(?:shorts|live|embed|v)\/([^/]+)/) || [])[1];
        }
        return this.ID_RE.test(id || "") ? id : null;
    },
    // 2. 本地儲存資料分類 (Storage)
    Storage: {
        read() {
            try {
                const list = JSON.parse(localStorage.getItem(YoutubeThumbnailApp.STORAGE_KEY) || "[]");
                return Array.isArray(list) ? list.filter((id) => YoutubeThumbnailApp.ID_RE.test(id)).slice(0, YoutubeThumbnailApp.MAX_ITEMS) : [];
            } catch {
                return [];
            }
        },
        save(ids) {
            try {
                if (ids.length) localStorage.setItem(YoutubeThumbnailApp.STORAGE_KEY, JSON.stringify(ids.slice(0, YoutubeThumbnailApp.MAX_ITEMS)));
                else localStorage.removeItem(YoutubeThumbnailApp.STORAGE_KEY);
            } catch { }
        }
    },
    // 3. 畫面顯示與互動分類 (UI)
    UI: {
        renderRecent(ids) {
            const App = YoutubeThumbnailApp;
            App.$("recent").hidden = ids.length === 0;
            App.$("recent-list").innerHTML = ids
                .map((id) => `<button type="button" data-video-id="${id}" aria-label="重新查詢影片 ${id}"><img src="${App.thumbUrl(id, "mqdefault")}" alt="" width="320" height="180" loading="lazy"><span>${id}</span></button>`)
                .join("");
        },
        finish(id) {
            const App = YoutubeThumbnailApp;
            const found = App.$("grid").children.length > 0;
            App.$("empty").hidden = found;
            App.$("msg").textContent = found ? '已載入可用縮圖，請選擇尺寸下載。' : '無法取得縮圖。';
            if (!found) return;
            const ids = [id, ...App.Storage.read().filter((item) => item !== id)].slice(0, App.MAX_ITEMS);
            App.Storage.save(ids);
            this.renderRecent(ids);
        },
        showThumbnails(id) {
            const App = YoutubeThumbnailApp;
            const request = this.request = (this.request || 0) + 1;
            App.$("grid").replaceChildren();
            App.$("empty").hidden = true;
            App.$("msg").textContent = '正在載入縮圖…';
            App.$("video-id").textContent = id;
            App.$("result").hidden = false;
            let pending = App.SIZES.length;

            App.SIZES.forEach(([name, width, height, tag]) => {
                const card = document.createElement("article");
                card.className = "thumbnail-card";
                card.innerHTML = `
          <img alt="${tag} 縮圖" width="${width}" height="${height}">
          <div class="thumbnail-card-body">
            <div><span class="tag">${tag}</span> <span class="size">${width} × ${height}</span></div>
            <div class="file">${name}.jpg</div>
            <a class="btn second download" href="${App.thumbUrl(id, name)}" download="${id}_${name}.jpg" target="_blank" rel="noopener noreferrer">下載</a>
          </div>`;
                const image = card.querySelector("img");
                let settled = false;
                const settle = (ok) => {
                    if (settled) return;
                    settled = true;
                    clearTimeout(timer);
                    if (request !== this.request) return;
                    if (!ok) card.remove();
                    if (--pending === 0) this.finish(id);
                };
                const timer = setTimeout(() => settle(false), 15000);
                image.onload = () => settle(image.naturalWidth >= width && image.naturalHeight >= height);
                image.onerror = () => settle(false);
                App.$("grid").append(card);
                image.src = App.thumbUrl(id, name);
            });
        },
        // 綁定所有點擊與網址初始化事件
        initEvents() {
            const App = YoutubeThumbnailApp;
            const submit = () => {
                const id = App.parseVideoId(App.$("url").value);
                if (id) {
                    this.showThumbnails(id);
                } else {
                    this.request = (this.request || 0) + 1;
                    App.$("grid").replaceChildren();
                    App.$("result").hidden = true;
                    App.$("msg").textContent = '無法辨識這個網址，請貼上 YouTube 影片網址或 11 碼影片 ID。';
                }
            };
            App.$("form").addEventListener('submit', (event) => {
                event.preventDefault();
                submit();
            });
            App.$("recent-list").addEventListener('click', (event) => {
                const button = event.target.closest('[data-video-id]');
                if (!button) return;
                App.$("url").value = button.dataset.videoId;
                submit();
            });
            // 圖片下載邏輯
            App.$("grid").addEventListener("click", async (event) => {
                const link = event.target.closest("a.download");
                if (!link) return;
                event.preventDefault();
                try {
                    const response = await fetch(link.href);
                    if (!response.ok) throw new Error(response.status);
                    const objectUrl = URL.createObjectURL(await response.blob());
                    const download = Object.assign(document.createElement("a"), { href: objectUrl, download: link.download });
                    document.body.append(download);
                    download.click();
                    download.remove();
                    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
                    App.$("msg").textContent = '已開始下載縮圖。';
                } catch {
                    App.$("msg").textContent = '瀏覽器無法直接下載，請使用圖片連結開啟後，按右鍵另存圖片。';
                    const fallback = document.createElement('a');
                    fallback.href = link.href;
                    fallback.target = '_blank';
                    fallback.rel = 'noopener noreferrer';
                    fallback.textContent = '開啟縮圖';
                    App.$("msg").append(' ', fallback);
                }
            });

            // 清除按鈕
            App.$("clear").addEventListener("click", () => {
                App.Storage.save([]);
                this.renderRecent([]);
            });

            // 初始化讀取網址
            const query = new URLSearchParams(location.search).get("url");
            this.renderRecent(App.Storage.read());

            if (query && query.trim()) {
                App.$("url").value = query;
                submit();
            }
        }
    }
};
// ==========================================
// 4. 最後手動執行初始化
// ==========================================
YoutubeThumbnailApp.UI.initEvents();
