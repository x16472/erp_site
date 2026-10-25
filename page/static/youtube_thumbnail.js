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
    $: (id) => document.getElementById(id),
    thumbUrl: (id, name) => `https://ytimg.com{id}/${name}.jpg`,
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
                .map((id) => `<a href="?url=${id}"><img src="${App.thumbUrl(id, "mqdefault")}" alt="" width="320" height="180" loading="lazy"><span>${id}</span></a>`)
                .join("");
        },
        finish(id) {
            const App = YoutubeThumbnailApp;
            const found = App.$("grid").children.length > 0;
            App.$("empty").hidden = found;
            if (!found) return;
            const ids = [id, ...App.Storage.read().filter((item) => item !== id)].slice(0, App.MAX_ITEMS);
            App.Storage.save(ids);
            this.renderRecent(ids);
        },
        showThumbnails(id) {
            const App = YoutubeThumbnailApp;
            App.$("video-id").textContent = id;
            App.$("result").hidden = false;
            let pending = App.SIZES.length;

            App.SIZES.forEach(([name, width, height, tag]) => {
                const card = document.createElement("article");
                card.className = "card";
                card.innerHTML = `
          <img src="${App.thumbUrl(id, name)}" alt="${tag} 縮圖" width="${width}" height="${height}">
          <div class="card__body">
            <div class="card__meta"><span class="tag">${tag}</span><span class="size">${width} × ${height}</span></div>
            <div class="file">${name}.jpg</div>
            <a class="download" href="${App.thumbUrl(id, name)}" download="${id}_${name}.jpg" target="_blank" rel="noopener">下載</a>
          </div>`;
                const image = card.querySelector("img");
                const settle = (ok) => {
                    if (!ok) card.remove();
                    if (--pending === 0) this.finish(id);
                };
                image.onload = () => settle(image.naturalWidth >= width / 2 && image.naturalHeight >= height / 2);
                image.onerror = () => settle(false);
                App.$("grid").append(card);
            });
        },
        // 綁定所有點擊與網址初始化事件
        initEvents() {
            const App = YoutubeThumbnailApp;
            // 圖片下載邏輯
            App.$("grid").addEventListener("click", async (event) => {
                const link = event.target.closest("a.download");
                if (!link) return;
                event.preventDefault();
                try {
                    const response = await fetch(link.href);
                    if (!response.ok) throw new Error(response.status);
                    const objectUrl = URL.createObjectURL(await response.blob());
                    Object.assign(document.createElement("a"), { href: objectUrl, download: link.download }).click();
                    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
                } catch {
                    window.open(link.href, "_blank", "noopener");
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
                const id = App.parseVideoId(query);
                if (id) {
                    this.showThumbnails(id);
                } else {
                    App.$("msg").textContent = "無法辨識這個網址，請貼上 YouTube 影片網址或 11 碼 Video ID。";
                    App.$("msg").hidden = false;
                }
            }
        }
    }
};
// ==========================================
// 4. 最後手動執行初始化
// ==========================================
YoutubeThumbnailApp.UI.initEvents();