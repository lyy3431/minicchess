# 中国象棋项目开发笔记 - 问题与解决方案

## 2026-03-09 调试记录

---

## 问题一：棋子位置偏移，未落在交叉点上

### 现象
所有棋子向右下方偏移，没有准确落在棋盘交叉点上。

### 原因
`.cells` 容器设置了 `top: -20px; left: -20px;` 的偏移，但棋子的坐标计算是基于棋盘左上角 (0,0) 的，导致棋子整体偏移。

### 解决方案
```css
/* 修改前 */
.cells {
    top: -20px;
    left: -20px;
}

/* 修改后 */
.cells {
    top: 0;
    left: 0;
}
```

---

## 问题二：走棋后旧位置棋子未清除

### 现象
移动棋子后，原位置和新位置都有棋子，且原位置棋子仍可被选中。

### 原因
`loadFEN` 函数解析 FEN 时，只更新有棋子的位置，空位（数字 1-9）只是跳过对应的列索引，没有将 `boardState` 对应位置设为 `null`。原来位置的棋子数据保留在数组中，导致渲染时旧位置和新位置都显示棋子。

### 解决方案
```javascript
// 修改前
function loadFEN(fen) {
    const parts = fen.split(' ');
    const rows = parts[0].split('/');
    for (let r = 0; r < 10; r++) {
        let col = 0;
        for (const ch of rows[r]) {
            if (ch >= '1' && ch <= '9') {
                col += parseInt(ch);
            } else {
                boardState[r][col] = ch;
                col++;
            }
        }
    }
    renderPieces();
}

// 修改后
function loadFEN(fen) {
    const parts = fen.split(' ');
    const rows = parts[0].split('/');
    // 清空 boardState
    boardState = Array(10).fill(null).map(() => Array(9).fill(null));
    for (let r = 0; r < 10; r++) {
        let col = 0;
        for (const ch of rows[r]) {
            if (ch >= '1' && ch <= '9') {
                col += parseInt(ch);
            } else {
                boardState[r][col] = ch;
                col++;
            }
        }
    }
    renderPieces();
}
```

---

## 问题三：AI 走棋后棋盘不更新

### 现象
AI 走棋后只有棋步信息输出，棋盘上的棋子没有相应移动。

### 原因分析
1. 最初怀疑是 `result.fen` 为空或条件判断问题
2. 添加调试日志后发现 FEN 返回值正常
3. 继续追踪发现服务器端 `make_move` 和 `get_ai_move` 的 FEN 更新逻辑有问题

### 解决方案
简化 `aiMove` 函数，直接使用服务器返回的 FEN 更新棋盘：
```javascript
async function aiMove() {
    try {
        const fen = toFEN();
        const response = await fetch('/api/ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fen: fen, depth: 10 })
        });

        const result = await response.json();

        // 直接使用服务器返回的 FEN 更新棋盘
        loadFEN(result.fen);

        addHistory(`AI: ${result.move}`);
        // ...
    } catch (e) {
        // ...
    }
}
```

---

## 问题四：AI 总是返回相同的走法 e2e6

### 现象
无论用户走什么，AI 都返回 `e2e6` 这个走法。

### 原因
Pikafish 引擎的坐标系统与项目中的 board 坐标系统不一致：
- **引擎视角**：row 0 = 底部（红方），row 9 = 顶部（黑方）
- **项目 board**：board[0] = 顶部（黑方），board[9] = 底部（红方）

引擎收到的 FEN 中黑方在顶部，但引擎认为第一行是 rank 9（顶部），导致引擎在错误的行上寻找棋子。

### 解决方案
修正 UCI 坐标转换公式：
```javascript
// 前端：坐标转 UCI
function toUCIMove(move) {
    const fromCol = String.fromCharCode(97 + move.from.col);
    const fromRow = 9 - move.from.row;  // board row 0(顶)=engine 9, board row 9(底)=engine 0
    const toCol = String.fromCharCode(97 + move.to.col);
    const toRow = 9 - move.to.row;
    return `${fromCol}${fromRow}${toCol}${toRow}`;
}

// 前端：UCI 转坐标
function fromUCIMove(uci) {
    return {
        from: {
            col: uci.charCodeAt(0) - 97,
            row: 9 - parseInt(uci[1])  // engine row 9=board 0, engine row 0=board 9
        },
        to: {
            col: uci.charCodeAt(2) - 97,
            row: 9 - parseInt(uci[3])
        }
    };
}
```

```python
# 后端：解析 UCI 走法
def parse_uci_move(self, uci):
    if len(uci) != 4:
        return None
    try:
        from_col = ord(uci[0]) - ord('a')
        # 引擎 row 0=底部，row 9=顶部；board row 0=顶部，row 9=底部
        # board_row = 9 - engine_row
        from_row = 9 - int(uci[1])
        to_col = ord(uci[2]) - ord('a')
        to_row = 9 - int(uci[3])
        return {
            'from': (from_row, from_col),
            'to': (to_row, to_col)
        }
    except:
        return None
```

---

## 问题五：AI 移动红方棋子而非黑方棋子

### 现象
AI 走棋时移动的是红方棋子，而不是应该移动的黑方棋子。

### 原因
FEN 中的回合标志（turn indicator）始终为 `w`（红方走棋），导致引擎认为应该红方走棋。

### 解决方案
修改 `board_to_fen` 函数，支持传入回合标志：
```python
def board_to_fen(self, board, turn='w'):
    """棋盘数组转 FEN - board[0]=黑方底线，board[9]=红方底线"""
    rows = []
    for r in range(10):  # 从 board[0]（黑方）到 board[9]（红方）
        empty = 0
        row_str = ""
        for c in range(9):
            piece = board[r][c]
            if piece:
                if empty > 0:
                    row_str += str(empty)
                    empty = 0
                row_str += piece
            else:
                empty += 1
        if empty > 0:
            row_str += str(empty)
        rows.append(row_str)
    return "/".join(rows) + f" {turn} - - 0 1"
```

并在走法函数中正确设置回合：
```python
def make_move(self, uci_move):
    """执行走法（玩家 - 红方）"""
    # ... 执行走法 ...
    # 玩家走完后，轮到黑方（b）
    self.current_fen = self.board_to_fen(board, 'b')
    return True

def get_ai_move(self, depth=10):
    """获取 AI 走法（AI - 黑方）"""
    # ... 执行走法 ...
    # AI 走完后，轮到红方（w）
    self.current_fen = self.board_to_fen(board, 'w')
    return True
```

---

## 问题六：棋子选中后向右下偏移

### 现象
鼠标点击棋子后，棋子向右下方偏移。

### 原因
`.piece.selected` 的动画 `pulse` 覆盖了 `transform` 属性，导致原本用于居中的 `translate(-50%, -50%)` 丢失。

### 解决方案
```css
/* 修改前 */
@keyframes pulse {
    from { transform: scale(1); }
    to { transform: scale(1.08); }
}

/* 修改后 */
@keyframes pulse {
    from { transform: translate(-50%, -50%) scale(1); }
    to { transform: translate(-50%, -50%) scale(1.08); }
}
```

---

## 问题七：棋盘两侧竖线未贯穿楚河汉界

### 现象
棋盘最左和最右的竖线在楚河汉界处断开。

### 解决方案
```javascript
// 绘制棋盘线时，左右边框竖线贯穿整个棋盘
for (let col = 0; col < cols; col++) {
    const x = col * cellSize;
    if (col === 0 || col === cols - 1) {
        // 左右边框竖线贯穿整个棋盘（包括楚河汉界）
        content += `<line x1="${x}" y1="0" x2="${x}" y2="${boardHeight}" />`;
    } else {
        // 中间竖线分上下两部分
        content += `<line x1="${x}" y1="0" x2="${x}" y2="${4 * cellSize}" />`;
        content += `<line x1="${x}" y1="${5 * cellSize}" x2="${x}" y2="${boardHeight}" />`;
    }
}
```

---

## 问题八：坐标数字未对齐棋子

### 现象
棋盘四周的数字坐标没有与棋子/棋盘格线对齐。

### 解决方案
```css
/* 上下坐标 */
.coord-top {
    top: -18px;
    left: 20px;  /* 第一个数字中心对齐第一个交叉点 */
    display: flex;
}

.coord-top span {
    width: 40px;  /* 与棋盘格间距一致 */
    text-align: center;
}

/* 左右坐标 */
.coord-left {
    left: -18px;
    top: 20px;  /* 第一个数字中心对齐第一个交叉点 */
    display: flex;
    flex-direction: column;
}

.coord-left span {
    height: 40px;  /* 与棋盘格间距一致 */
    text-align: center;
    line-height: 40px;
}
```

---

## 关键知识点总结

### 1. Pikafish 引擎坐标系统
- 引擎 row 0 = 底部（红方）
- 引擎 row 9 = 顶部（黑方）
- 列 a-i 从右到左（与中国象棋传统一致）

### 2. FEN 格式
- 标准格式：`位置 回合 王车易位 吃过路兵 半回合 回合`
- 回合标志：`w` = 白方/红方走棋，`b` = 黑方走棋
- 行顺序：第一行 = 顶部（黑方），第十行 = 底部（红方）

### 3. 坐标转换公式
```
board_row = 9 - engine_row
engine_row = 9 - board_row
```

### 4. 调试技巧
- 在服务器端添加 `[DEBUG]` 日志追踪 FEN 变化
- 在引擎输出中添加日志查看 bestmove
- 使用浏览器控制台查看 JavaScript 变量状态

---

## 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `index.html` | 修复 `.cells` 容器偏移、`loadFEN` 清空逻辑、坐标转换、棋子动画、棋盘线绘制、坐标对齐 |
| `server.py` | 修复 `parse_uci_move` 坐标转换、`board_to_fen` 回合标志、`make_move` 和 `get_ai_move` 回合设置 |
