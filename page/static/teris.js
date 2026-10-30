(() => {
    const teris_canvas = document.getElementById('teris_canvas');
    const ctx = teris_canvas.getContext('2d');
    const nextCanvas = document.getElementById('teris-next-canvas');
    const nextCtx = nextCanvas.getContext('2d');
    const overlay = document.getElementById('teris-overlay');
    const terisPanel = teris_canvas.closest('.panel');

    const COLS = 10;
    const ROWS = 20;
    const BLOCK = 30;
    // 方塊顏色
    const COLORS = [
        null,
        '#00d2ff', // I - 青
        '#ffd700', // O - 黃
        '#bf5fff', // T - 紫
        '#5fff7f', // S - 綠
        '#ff5f5f', // Z - 紅
        '#5f9fff', // J - 藍
        '#ff9f3f', // L - 橙
    ];
    // 方塊形狀
    const SHAPES = [
        null,
        [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]], // I
        [[2, 2], [2, 2]],                               // O
        [[0, 3, 0], [3, 3, 3], [0, 0, 0]],                   // T
        [[0, 4, 4], [4, 4, 0], [0, 0, 0]],                   // S
        [[5, 5, 0], [0, 5, 5], [0, 0, 0]],                   // Z
        [[6, 0, 0], [6, 6, 6], [0, 0, 0]],                   // J
        [[0, 0, 7], [7, 7, 7], [0, 0, 0]],                   // L
    ];
    let board, piece, nextPiece, score, highScore, level, lines, animId, lastTime, dropCounter, dropInterval;
    let gameOver = true;
    let paused = false;

    highScore = parseInt(localStorage.getItem('tetrisHighScore')) || 0;
    document.getElementById('teris-high-score').textContent = highScore;

    function createBoard() {
        return Array.from({ length: ROWS }, () => Array(COLS).fill(0));
    }

    function createPiece(type) {
        return {
            type,
            shape: SHAPES[type].map(row => [...row]),
            x: Math.floor(COLS / 2) - Math.floor(SHAPES[type][0].length / 2),
            y: 0
        };
    }

    function randomType() {
        return Math.floor(Math.random() * 7) + 1;
    }

    function drawBlock(context, x, y, colorIndex, alpha = 1) {
        if (!colorIndex) return;
        const color = COLORS[colorIndex];
        context.globalAlpha = alpha;
        context.fillStyle = color;
        context.fillRect(x * BLOCK + 1, y * BLOCK + 1, BLOCK - 2, BLOCK - 2);

        // 光澤效果
        context.fillStyle = 'rgba(255,255,255,0.25)';
        context.fillRect(x * BLOCK + 1, y * BLOCK + 1, BLOCK - 2, 6);
        context.fillRect(x * BLOCK + 1, y * BLOCK + 1, 6, BLOCK - 2);

        // 陰影邊框
        context.strokeStyle = 'rgba(0,0,0,0.3)';
        context.lineWidth = 1;
        context.strokeRect(x * BLOCK + 1.5, y * BLOCK + 1.5, BLOCK - 3, BLOCK - 3);

        context.globalAlpha = 1;
    }

    function drawBoard() {
        // 背景格線
        ctx.fillStyle = '#0d1b2a';
        ctx.fillRect(0, 0, teris_canvas.width, teris_canvas.height);

        for (let r = 0; r < ROWS; r++) {
            for (let c = 0; c < COLS; c++) {
                if (board[r][c]) {
                    drawBlock(ctx, c, r, board[r][c]);
                } else {
                    ctx.fillStyle = 'rgba(255,255,255,0.03)';
                    ctx.fillRect(c * BLOCK, r * BLOCK, BLOCK, BLOCK);
                }
            }
        }
    }

    function drawPiece(p, context = ctx, offsetX = 0, offsetY = 0, alpha = 1) {
        p.shape.forEach((row, r) => {
            row.forEach((val, c) => {
                if (val) {
                    drawBlock(context, c + p.x + offsetX, r + p.y + offsetY, val, alpha);
                }
            });
        });
    }

    function drawGhost() {
        let ghost = { shape: piece.shape, x: piece.x, y: piece.y };
        while (!collide(board, { ...ghost, y: ghost.y + 1 })) ghost.y++;
        ghost.shape.forEach((row, r) => {
            row.forEach((val, c) => {
                if (val) {
                    ctx.globalAlpha = 0.18;
                    ctx.fillStyle = COLORS[val];
                    ctx.fillRect((c + ghost.x) * BLOCK + 1, (r + ghost.y) * BLOCK + 1, BLOCK - 2, BLOCK - 2);
                    ctx.strokeStyle = COLORS[val];
                    ctx.lineWidth = 1;
                    ctx.strokeRect((c + ghost.x) * BLOCK + 1.5, (r + ghost.y) * BLOCK + 1.5, BLOCK - 3, BLOCK - 3);
                    ctx.globalAlpha = 1;
                }
            });
        });
    }

    function drawNextPiece() {
        nextCtx.fillStyle = '#0d1b2a';
        nextCtx.fillRect(0, 0, nextCanvas.width, nextCanvas.height);
        const shape = nextPiece.shape;
        const offX = Math.floor((4 - shape[0].length) / 2) - nextPiece.x + 0.2;
        const offY = Math.floor((4 - shape.length) / 2) - nextPiece.y + 0.5;
        drawPiece(nextPiece, nextCtx, offX, offY);
    }

    function collide(board, p) {
        return p.shape.some((row, r) =>
            row.some((val, c) => {
                if (!val) return false;
                const nx = p.x + c, ny = p.y + r;
                return nx < 0 || nx >= COLS || ny >= ROWS || (ny >= 0 && board[ny][nx]);
            })
        );
    }

    function merge() {
        piece.shape.forEach((row, r) => {
            row.forEach((val, c) => {
                if (val) board[piece.y + r][piece.x + c] = val;
            });
        });
    }

    function clearLines() {
        let cleared = 0;
        for (let r = ROWS - 1; r >= 0; r--) {
            if (board[r].every(v => v !== 0)) {
                board.splice(r, 1);
                board.unshift(Array(COLS).fill(0));
                cleared++;
                r++;
            }
        }
        if (cleared > 0) {
            const pts = [0, 100, 300, 500, 800];
            score += (pts[cleared] || 800) * level;
            lines += cleared;
            const newLevel = Math.floor(lines / 10) + 1;
            if (newLevel !== level) {
                level = newLevel;
                dropInterval = Math.max(100, 1000 - (level - 1) * 90);
            }
            updateUI();
        }
    }

    function updateUI() {
        document.getElementById('teris-score').textContent = score;
        document.getElementById('teris-level').textContent = level;
        document.getElementById('teris-lines').textContent = lines;
        const progress = (lines % 10) / 10 * 100;
        document.getElementById('teris-level-bar').style.width = progress + '%';
        if (score > highScore) {
            highScore = score;
            localStorage.setItem('tetrisHighScore', highScore);
            document.getElementById('teris-high-score').textContent = highScore;
        }
    }

    function rotate(shape) {
        const n = shape.length;
        const m = shape[0].length;
        const rotated = Array.from({ length: m }, () => Array(n).fill(0));
        for (let r = 0; r < n; r++)
            for (let c = 0; c < m; c++)
                rotated[c][n - 1 - r] = shape[r][c];
        return rotated;
    }

    function rotatePiece() {
        const orig = piece.shape;
        piece.shape = rotate(piece.shape);
        // 壁踢
        let offset = 1;
        while (collide(board, piece)) {
            piece.x += offset;
            offset = -(offset < 0 ? offset - 1 : offset + 1);
            if (offset > piece.shape[0].length + 1) {
                piece.shape = orig;
                return;
            }
        }
    }

    function drop() {
        piece.y++;
        if (collide(board, piece)) {
            piece.y--;
            merge();
            clearLines();
            spawnPiece();
        }
        dropCounter = 0;
    }

    function hardDrop() {
        while (!collide(board, { ...piece, y: piece.y + 1 })) piece.y++;
        merge();
        clearLines();
        spawnPiece();
        dropCounter = 0;
    }

    function spawnPiece() {
        piece = nextPiece;
        piece.x = Math.floor(COLS / 2) - Math.floor(piece.shape[0].length / 2);
        piece.y = 0;
        nextPiece = createPiece(randomType());
        drawNextPiece();
        if (collide(board, piece)) {
            endGame();
        }
    }

    function endGame() {
        gameOver = true;
        cancelAnimationFrame(animId);
        overlay.style.display = 'flex';
        overlay.innerHTML = `<div>💥 遊戲結束</div><div class="sub">分數：${score}</div><div class="sub">按「開始遊戲」重試</div>`;
        document.getElementById('teris-pause-btn').disabled = true;
    }

    function gameLoop(timestamp) {
        if (gameOver || paused) return;
        const delta = timestamp - lastTime;
        lastTime = timestamp;
        dropCounter += delta;
        if (dropCounter >= dropInterval) drop();
        drawBoard();
        drawGhost();
        drawPiece(piece);
        animId = requestAnimationFrame(gameLoop);
    }

    function startGame() {
        cancelAnimationFrame(animId);
        board = createBoard();
        score = 0;
        level = 1;
        lines = 0;
        dropInterval = 1000;
        dropCounter = 0;
        lastTime = 0;
        gameOver = false;
        paused = false;
        nextPiece = createPiece(randomType());
        spawnPiece();
        overlay.style.display = 'none';
        document.getElementById('teris-pause-btn').disabled = false;
        document.getElementById('teris-pause-btn').textContent = '暫停';
        updateUI();
        teris_canvas.focus({ preventScroll: true });
        animId = requestAnimationFrame(gameLoop);
    }

    function togglePause() {
        if (gameOver) return;
        paused = !paused;
        document.getElementById('teris-pause-btn').textContent = paused ? '繼續' : '暫停';
        if (paused) {
            overlay.style.display = 'flex';
            overlay.innerHTML = `<div>⏸ 已暫停</div><div class="sub">按「繼續」或 P 繼續遊戲</div>`;
            cancelAnimationFrame(animId);
        } else {
            overlay.style.display = 'none';
            lastTime = performance.now();
            teris_canvas.focus({ preventScroll: true });
            animId = requestAnimationFrame(gameLoop);
        }
    }

    document.getElementById('teris-start-btn').addEventListener('click', startGame);
    document.getElementById('teris-pause-btn').addEventListener('click', togglePause);

    // 切走遊戲時暫停，避免編輯 Python 時遊戲仍在背景落下。
    new MutationObserver(() => {
        if (!terisPanel.classList.contains('active') && !gameOver && !paused) togglePause();
    }).observe(terisPanel, { attributes: true, attributeFilter: ['class'] });

    document.addEventListener('keydown', e => {
        if (gameOver || !terisPanel.classList.contains('active') || e.isComposing ||
            e.target.closest('input, textarea, select, button, [contenteditable="true"]')) return;
        switch (e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                if (!paused) { piece.x--; if (collide(board, piece)) piece.x++; }
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (!paused) { piece.x++; if (collide(board, piece)) piece.x--; }
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (!paused) drop();
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (!paused) rotatePiece();
                break;
            case ' ':
                e.preventDefault();
                if (!paused) hardDrop();
                break;
            case 'p':
            case 'P':
                togglePause();
                break;
        }
    });
})();
