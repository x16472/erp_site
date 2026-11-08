const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function createGame() {
    const elements = new Map();
    const listeners = {};
    const panel = { classList: { contains: () => true } };
    function getElementById(id) {
        if (!elements.has(id)) {
            elements.set(id, {
                style: {},
                width: 120,
                height: id === 'teris-next-canvas' ? 450 : 90,
                getContext: () => ({ fillRect() {}, strokeRect() {} }),
                closest: () => panel,
                focus() {},
                addEventListener(event, callback) { this[event] = callback; },
            });
        }
        return elements.get(id);
    }
    const context = vm.createContext({
        document: { getElementById, addEventListener: (event, callback) => { listeners[event] = callback; } },
        localStorage: { getItem: () => null, setItem() {} },
        MutationObserver: class { observe() {} },
        requestAnimationFrame() {},
        cancelAnimationFrame() {},
        performance: { now: () => 0 },
    });
    const source = fs.readFileSync(path.join(__dirname, '../static/teris.js'), 'utf8');
    vm.runInContext(source.replace(/\}\)\(\);\s*$/, `
        globalThis.game = {
            startGame, hardDrop,
            state: () => JSON.parse(JSON.stringify({ piece, nextPieces, heldType, holdUsed, gameOver })),
            blockSpawn: () => board[0].fill(1),
        };
    })();`), context);
    context.game.key = (key, options = {}) => listeners.keydown({
        key, target: { closest: () => null }, preventDefault() {}, ...options,
    });
    context.game.startGame();
    return context.game;
}

test('首次儲存會取出佇列首個方塊，預覽始終保留五個', () => {
    const game = createGame();
    const before = game.state();
    assert.equal(before.nextPieces.length, 5);
    game.key('c');
    const after = game.state();
    assert.equal(after.heldType, before.piece.type);
    assert.equal(after.piece.type, before.nextPieces[0]);
    assert.deepEqual(after.nextPieces.slice(0, 4), before.nextPieces.slice(1));
    assert.equal(after.nextPieces.length, 5);
    game.key('Shift');
    assert.deepEqual(game.state(), after);
    game.hardDrop();
    assert.equal(game.state().holdUsed, false);
    assert.equal(game.state().nextPieces.length, 5);
});

test('落地後可交換，交換重設方向與位置且不消耗預覽佇列', () => {
    const game = createGame();
    const initial = game.state().piece;
    game.key('c');
    game.hardDrop();
    game.key('ArrowUp');
    game.key('ArrowLeft');
    game.key('ArrowDown');
    const before = game.state();
    game.key('Shift');
    const after = game.state();
    assert.deepEqual(after.piece, initial);
    assert.equal(after.heldType, before.piece.type);
    assert.deepEqual(after.nextPieces, before.nextPieces);
    assert.equal(after.holdUsed, true);
});

test('暫停與按鍵自動重複不會儲存，重開會清除儲存狀態', () => {
    const game = createGame();
    const initial = game.state();
    game.key('c', { repeat: true });
    assert.deepEqual(game.state(), initial);
    game.key('p');
    game.key('c');
    assert.deepEqual(game.state(), initial);
    game.key('p');
    game.key('C');
    assert.equal(game.state().holdUsed, true);
    game.startGame();
    assert.equal(game.state().heldType, null);
    assert.equal(game.state().holdUsed, false);
    assert.equal(game.state().nextPieces.length, 5);
});

test('儲存或交換後出場位置被擋住會結束遊戲', () => {
    for (const hasHeldPiece of [false, true]) {
        const game = createGame();
        if (hasHeldPiece) {
            game.key('c');
            game.hardDrop();
        }
        game.blockSpawn();
        game.key('c');
        assert.equal(game.state().gameOver, true);
        const ended = game.state();
        game.key('c');
        assert.deepEqual(game.state(), ended);
    }
});
