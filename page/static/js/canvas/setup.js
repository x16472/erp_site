export class CanvasSurface {
    constructor(canvas, { width = canvas?.width, height = canvas?.height } = {}) {
        if (!canvas) throw new Error('找不到繪圖區域。');
        this.canvas = canvas;
        this.canvas.width = width;
        this.canvas.height = height;
        this.context = canvas.getContext('2d');
        if (!this.context) throw new Error('瀏覽器無法建立 Canvas 畫筆。');
    }
}
