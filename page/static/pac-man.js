
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// ─── 地圖定義 ───────────────────────────────────────────────
// 0=豆子, 1=牆壁, 2=空地, 3=大力丸, 4=鬼魂門
const TILE = 20;
const MAP_COLS = 21;
const MAP_ROWS = 23;
canvas.width = TILE * MAP_COLS;
canvas.height = TILE * MAP_ROWS;

const BASE_MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 3, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 3, 1],
    [1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 0, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 0, 1, 1, 1, 1],
    [2, 2, 2, 1, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 1, 2, 2, 2],
    [1, 1, 1, 1, 0, 1, 2, 1, 1, 4, 4, 4, 1, 1, 2, 1, 0, 1, 1, 1, 1],
    [2, 2, 2, 2, 0, 2, 2, 1, 2, 2, 2, 2, 2, 1, 2, 2, 0, 2, 2, 2, 2],
    [1, 1, 1, 1, 0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 2, 1, 0, 1, 1, 1, 1],
    [2, 2, 2, 1, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 1, 2, 2, 2],
    [1, 1, 1, 1, 0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 2, 1, 0, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1],
    [1, 3, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1, 0, 3, 1],
    [1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1],
    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
];

// ─── 遊戲狀態 ─────────────────────────────────────────────
let map, score, highScore, lives, level, gameOver, won, paused;
let pacman, ghosts, powerTimer, blinkTimer;
const GHOST_COLORS = ['#FF0000', '#FFB8FF', '#00FFFF', '#FFB852'];
const GHOST_NAMES = ['小紅', '小粉', '小藍', '小橘'];

function deepCopyMap(src) { return src.map(r => [...r]); }

function initGame() {
    map = deepCopyMap(BASE_MAP);
    score = 0;
    lives = 3;
    level = 1;
    gameOver = false;
    won = false;
    paused = false;
    powerTimer = 0;
    blinkTimer = 0;
    spawnPacman();
    spawnGhosts();
    updateUI();
}

function spawnPacman() {
    pacman = {
        x: 10, y: 16,
        dx: 0, dy: 0,
        nextDx: 0, nextDy: 0,
        mouthOpen: 0,
        mouthDir: 1,
        moving: false,
        speed: 1,
        timer: 0
    };
}

function spawnGhosts() {
    const starts = [{ x: 9, y: 10 }, { x: 10, y: 10 }, { x: 11, y: 10 }, { x: 10, y: 9 }];
    ghosts = starts.map((s, i) => ({
        x: s.x, y: s.y,
        dx: 0, dy: i < 2 ? -1 : 1,
        color: GHOST_COLORS[i],
        name: GHOST_NAMES[i],
        frightened: false,
        eaten: false,
        timer: 0,
        speed: 1 + level * 0.05,
        outOfHouse: i === 0
    }));
}

// ─── UI 更新 ──────────────────────────────────────────────
function updateUI() {
    document.getElementById('score').textContent = score;
    document.getElementById('highscore').textContent = highScore || 0;
    document.getElementById('level').textContent = level;
    const h = ['❤️', '❤️', '❤️'].slice(0, lives).join('') || '💀';
    document.getElementById('lives').textContent = h;
}

function setMessage(msg) { document.getElementById('message').textContent = msg; }

// ─── 繪圖 ─────────────────────────────────────────────────
function drawMap() {
    for (let r = 0; r < MAP_ROWS; r++) {
        for (let c = 0; c < MAP_COLS; c++) {
            const x = c * TILE, y = r * TILE, v = map[r][c];
            if (v === 1) {
                ctx.fillStyle = '#1a1aff';
                ctx.fillRect(x, y, TILE, TILE);
                ctx.strokeStyle = '#4444ff';
                ctx.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
            } else if (v === 0) {
                ctx.fillStyle = '#000';
                ctx.fillRect(x, y, TILE, TILE);
                ctx.fillStyle = '#FFD700';
                ctx.beginPath();
                ctx.arc(x + TILE / 2, y + TILE / 2, 2.5, 0, Math.PI * 2);
                ctx.fill();
            } else if (v === 3) {
                ctx.fillStyle = '#000';
                ctx.fillRect(x, y, TILE, TILE);
                blinkTimer % 20 < 10
                    ? (ctx.fillStyle = '#FFD700', ctx.beginPath(), ctx.arc(x + TILE / 2, y + TILE / 2, 6, 0, Math.PI * 2), ctx.fill())
                    : null;
            } else {
                ctx.fillStyle = '#000';
                ctx.fillRect(x, y, TILE, TILE);
            }
        }
    }
}

function drawPacman() {
    const cx = pacman.x * TILE + TILE / 2;
    const cy = pacman.y * TILE + TILE / 2;
    const mouth = (pacman.mouthOpen / 45) * Math.PI;

    let startAngle, endAngle;
    const dir = pacman.dx !== 0 || pacman.dy !== 0
        ? Math.atan2(pacman.dy, pacman.dx)
        : 0;

    startAngle = dir + mouth;
    endAngle = dir - mouth + Math.PI * 2;

    ctx.fillStyle = '#FFD700';
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, TILE / 2 - 1, startAngle, endAngle);
    ctx.closePath();
    ctx.fill();

    // 眼睛
    const eyeX = cx + Math.cos(dir - 0.5) * 4;
    const eyeY = cy + Math.sin(dir - 0.5) * 4;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(eyeX, eyeY, 2, 0, Math.PI * 2);
    ctx.fill();
}

function drawGhost(g) {
    const x = g.x * TILE;
    const y = g.y * TILE;
    const cx = x + TILE / 2;

    if (g.eaten) {
        // 只顯示眼睛
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(cx - 3, y + 7, 3, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 3, y + 7, 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#00f';
        ctx.beginPath(); ctx.arc(cx - 3, y + 7, 1.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 3, y + 7, 1.5, 0, Math.PI * 2); ctx.fill();
        return;
    }

    let color;
    if (g.frightened) {
        color = (blinkTimer % 20 < 10 || powerTimer > 60) ? '#0000FF' : '#ffffff';
    } else {
        color = g.color;
    }

    ctx.fillStyle = color;
    // 身體
    ctx.beginPath();
    ctx.arc(cx, y + TILE / 2, TILE / 2 - 1, Math.PI, 0);
    ctx.lineTo(x + TILE - 1, y + TILE - 1);
    // 底部波浪
    for (let i = 3; i >= 0; i--) {
        const wx = x + 1 + i * (TILE - 2) / 3;
        const wy = y + TILE - (i % 2 === 0 ? 4 : 1);
        ctx.lineTo(wx, wy);
    }
    ctx.lineTo(x + 1, y + TILE - 1);
    ctx.closePath();
    ctx.fill();

    // 眼睛
    if (!g.frightened) {
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(cx - 3, y + 8, 3, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 3, y + 8, 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#00f';
        ctx.beginPath(); ctx.arc(cx - 3 + g.dx, y + 8 + g.dy, 1.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 3 + g.dx, y + 8 + g.dy, 1.5, 0, Math.PI * 2); ctx.fill();
    } else {
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(cx - 3, y + 8, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 3, y + 8, 2.5, 0, Math.PI * 2); ctx.fill();
    }
}

// ─── 邏輯 ─────────────────────────────────────────────────
function canMove(x, y) {
    if (x < 0 || x >= MAP_COLS) return true; // 穿牆
    if (y < 0 || y >= MAP_ROWS) return false;
    return map[y][x] !== 1;
}

function wrapX(x) { return (x + MAP_COLS) % MAP_COLS; }

function updatePacman() {
    pacman.timer++;
    blinkTimer++;

    // 嘗試轉彎
    const nx2 = wrapX(pacman.x + pacman.nextDx);
    const ny2 = pacman.y + pacman.nextDy;
    if (canMove(nx2, ny2)) {
        pacman.dx = pacman.nextDx;
        pacman.dy = pacman.nextDy;
    }

    if (pacman.timer >= 6 - Math.min(level - 1, 3)) {
        pacman.timer = 0;
        const nx = wrapX(pacman.x + pacman.dx);
        const ny = pacman.y + pacman.dy;
        if (canMove(nx, ny)) {
            pacman.x = nx;
            pacman.y = ny;
            pacman.moving = true;
            eatCell(pacman.x, pacman.y);
        } else {
            pacman.moving = false;
        }
    }

    // 嘴巴動畫
    if (pacman.moving) {
        pacman.mouthOpen += 5 * pacman.mouthDir;
        if (pacman.mouthOpen >= 45 || pacman.mouthOpen <= 0) pacman.mouthDir *= -1;
    } else {
        pacman.mouthOpen = 20;
    }
}

function eatCell(x, y) {
    const v = map[y][x];
    if (v === 0) {
        map[y][x] = 2;
        score += 10;
        updateUI();
        checkWin();
    } else if (v === 3) {
        map[y][x] = 2;
        score += 50;
        powerTimer = 300;
        ghosts.forEach(g => { if (!g.eaten) g.frightened = true; });
        updateUI();
        checkWin();
    }
}

function checkWin() {
    let dots = 0;
    for (let r = 0; r < MAP_ROWS; r++)
        for (let c = 0; c < MAP_COLS; c++)
            if (map[r][c] === 0 || map[r][c] === 3) dots++;
    if (dots === 0) nextLevel();
}

function nextLevel() {
    level++;
    won = true;
    setMessage(`🎉 第 ${level - 1} 關通關！準備第 ${level} 關...`);
    paused = true;
    setTimeout(() => {
        map = deepCopyMap(BASE_MAP);
        won = false; paused = false;
        spawnPacman();
        spawnGhosts();
        updateUI();
        setMessage('');
    }, 2000);
}

function updateGhosts() {
    if (powerTimer > 0) {
        powerTimer--;
        if (powerTimer === 0) {
            ghosts.forEach(g => { g.frightened = false; });
        }
    }

    ghosts.forEach(g => {
        g.timer++;
        const spd = g.eaten ? 3 : (g.frightened ? 9 : Math.max(4, 7 - level));
        if (g.timer < spd) return;
        g.timer = 0;

        // 離開鬼屋
        if (!g.outOfHouse) {
            if (g.y > 9) { g.y--; } else { g.outOfHouse = true; }
            return;
        }

        // 計算可走方向
        const dirs = [{ dx: 1, dy: 0 }, { dx: -1, dy: 0 }, { dx: 0, dy: 1 }, { dx: 0, dy: -1 }];
        let possible = dirs.filter(d => {
            const nx = wrapX(g.x + d.dx), ny = g.y + d.dy;
            return canMove(nx, ny) && !(d.dx === -g.dx && d.dy === -g.dy);
        });
        if (possible.length === 0)
            possible = dirs.filter(d => canMove(wrapX(g.x + d.dx), g.y + d.dy));

        let chosen;
        if (g.eaten) {
            // 回家
            const home = { x: 10, y: 10 };
            chosen = possible.reduce((best, d) => {
                const nx = wrapX(g.x + d.dx), ny = g.y + d.dy;
                const dist = Math.hypot(nx - home.x, ny - home.y);
                return dist < best.dist ? { d, dist } : best;
            }, { d: possible[0], dist: Infinity }).d;
            if (Math.abs(g.x - home.x) <= 1 && Math.abs(g.y - home.y) <= 1) g.eaten = false;
        } else if (g.frightened) {
            chosen = possible[Math.floor(Math.random() * possible.length)];
        } else {
            // 追蹤小精靈
            chosen = possible.reduce((best, d) => {
                const nx = wrapX(g.x + d.dx), ny = g.y + d.dy;
                const dist = Math.hypot(nx - pacman.x, ny - pacman.y);
                return dist < best.dist ? { d, dist } : best;
            }, { d: possible[0], dist: Infinity }).d;
        }

        g.dx = chosen.dx;
        g.dy = chosen.dy;
        g.x = wrapX(g.x + g.dx);
        g.y += g.dy;
    });
}

function checkCollision() {
    ghosts.forEach(g => {
        if (g.eaten) return;
        if (Math.abs(g.x - pacman.x) <= 0 && Math.abs(g.y - pacman.y) <= 0) {
            if (g.frightened) {
                g.frightened = false;
                g.eaten = true;
                g.outOfHouse = false;
                score += 200;
                updateUI();
            } else {
                loseLife();
            }
        }
    });
}

function loseLife() {
    lives--;
    updateUI();
    if (lives <= 0) {
        gameOver = true;
        if (score > (highScore || 0)) highScore = score;
        updateUI();
        setMessage('💀 遊戲結束！按 Enter 或點畫面重新開始');
    } else {
        setMessage(`💔 剩餘 ${lives} 條命，3秒後繼續...`);
        paused = true;
        setTimeout(() => {
            spawnPacman(); spawnGhosts(); paused = false;
            setMessage('');
        }, 2000);
    }
}

// ─── 主迴圈 ───────────────────────────────────────────────
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawMap();
    drawPacman();
    ghosts.forEach(drawGhost);
}

function update() {
    if (paused || gameOver) return;
    updatePacman();
    updateGhosts();
    checkCollision();
}

let lastTime = 0;
function loop(ts) {
    if (ts - lastTime >= 1000 / 60) {
        lastTime = ts;
        update();
        draw();
    }
    requestAnimationFrame(loop);
}

// ─── 控制 ─────────────────────────────────────────────────
document.addEventListener('keydown', e => {
    const map2 = {
        ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
        w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0],
        W: [0, -1], S: [0, 1], A: [-1, 0], D: [1, 0]
    };
    if (map2[e.key]) {
        e.preventDefault();
        const [dx, dy] = map2[e.key];
        pacman.nextDx = dx; pacman.nextDy = dy;
    }
    if ((e.key === 'Enter' || e.key === ' ') && gameOver) {
        initGame(); setMessage('');
    }
});

// 手機觸控
canvas.addEventListener('click', e => {
    if (gameOver) { initGame(); setMessage(''); return; }
    const rect = canvas.getBoundingClientRect();
    const tx = e.clientX - rect.left;
    const ty = e.clientY - rect.top;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const dx = tx - cx, dy = ty - cy;
    if (Math.abs(dx) > Math.abs(dy)) {
        pacman.nextDx = dx > 0 ? 1 : -1; pacman.nextDy = 0;
    } else {
        pacman.nextDx = 0; pacman.nextDy = dy > 0 ? 1 : -1;
    }
});

// ─── 啟動 ─────────────────────────────────────────────────
highScore = 0;
initGame();
requestAnimationFrame(loop);
