#!/usr/bin/env python3
"""
最简单的中国象棋人机对战程序
使用 pikafish 引擎作为 AI
"""

import subprocess
import re
import sys

# 棋盘初始局面（FEN 格式）
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

# 棋子符号
PIECES = {
    'r': '车', 'n': '马', 'b': '象', 'a': '士', 'k': '将', 'c': '炮', 'p': '卒',
    'R': '车', 'N': '马', 'B': '相', 'A': '仕', 'K': '帅', 'C': '炮', 'P': '兵'
}

class XiangqiBoard:
    def __init__(self):
        self.board = [[None for _ in range(9)] for _ in range(10)]
        self.load_fen(INITIAL_FEN)

    def load_fen(self, fen):
        """从 FEN 字符串加载棋盘"""
        parts = fen.split()
        rows = parts[0].split('/')

        for r, row in enumerate(rows):
            c = 0
            for ch in row:
                if ch.isdigit():
                    c += int(ch)
                else:
                    self.board[r][c] = ch
                    c += 1

    def get_piece(self, r, c):
        """获取棋子"""
        if 0 <= r < 10 and 0 <= c < 9:
            return self.board[r][c]
        return None

    def set_piece(self, r, c, piece):
        """放置棋子"""
        self.board[r][c] = piece

    def make_move(self, move_uci):
        """执行走法（UCI 格式：如 e2e4）"""
        from_col = ord(move_uci[0]) - ord('a')
        from_row = 9 - int(move_uci[1])
        to_col = ord(move_uci[2]) - ord('a')
        to_row = 9 - int(move_uci[3])

        # 验证走法是否符合规则
        if not self.is_valid_move(from_row, from_col, to_row, to_col):
            return False

        piece = self.board[from_row][from_col]
        self.board[from_row][from_col] = None
        self.board[to_row][to_col] = piece
        return True

    def check_game_over(self):
        """检查游戏是否结束（将/帅被吃掉）"""
        red_king = False
        black_king = False

        for row in self.board:
            for piece in row:
                if piece == 'k':  # 黑将
                    black_king = True
                elif piece == 'K':  # 红帅
                    red_king = True

        if not red_king:
            return {'gameOver': True, 'winner': 'black', 'reason': '红帅被吃掉，黑方获胜！'}
        if not black_king:
            return {'gameOver': True, 'winner': 'red', 'reason': '黑将被吃掉，红方获胜！'}

        return {'gameOver': False}

    def display(self):
        """显示棋盘"""
        print("\n  九 八 七 六 五 四 三 二 一")
        print("  a  b  c  d  e  f  g  h  i")
        print("  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┐")

        for r in range(10):
            row_str = f"{10-r} │"
            for c in range(9):
                piece = self.board[r][c]
                if piece:
                    row_str += f" {PIECES.get(piece, piece)} "
                else:
                    row_str += " · "
                if c < 8:
                    row_str += "│"
            row_str += "│ " + str(10-r)
            print(row_str)

            if r == 4:  # 楚河汉界
                print("  ├───┴───┴───┴───┴───┴───┴───┴───┴───┤ 楚河        汉界")
            elif r < 9:
                print("  ├───┼───┼───┼───┼───┼───┼───┼───┼───┤")
            else:
                print("  └───┴───┴───┴───┴───┴───┴───┴───┴───┘")

        print("  a  b  c  d  e  f  g  h  i")
        print("  一 二 三 四 五 六 七 八 九\n")

    def to_fen(self):
        """将棋盘转换为 FEN 字符串"""
        rows = []
        for r in range(10):
            empty = 0
            row_str = ""
            for c in range(9):
                piece = self.board[r][c]
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
        return "/".join(rows) + " w - - 0 1"

    def is_valid_move(self, from_row, from_col, to_row, to_col):
        """验证走法是否符合中国象棋规则"""
        if not (0 <= from_row < 10 and 0 <= from_col < 9):
            return False
        if not (0 <= to_row < 10 and 0 <= to_col < 9):
            return False

        piece = self.board[from_row][from_col]
        target = self.board[to_row][to_col]

        if not piece:
            return False

        # 不能吃自己的棋子
        if target:
            if piece.isupper() and target.isupper():
                return False
            if piece.islower() and target.islower():
                return False

        # 根据棋子类型验证走法
        piece_type = piece.lower()

        if piece_type == 'r':  # 车 - 直线行走，不能越过棋子
            return self.validate_rook(from_row, from_col, to_row, to_col)
        elif piece_type == 'n':  # 马 - 日字，检查蹩马腿
            return self.validate_horse(from_row, from_col, to_row, to_col)
        elif piece_type == 'b':  # 象/相 - 田字，不能过河，检查塞象眼
            return self.validate_elephant(from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'a':  # 士/仕 - 斜走，只能在九宫格内
            return self.validate_advisor(from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'k':  # 将/帅 - 直走，只能在九宫格内
            return self.validate_general(from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'c':  # 炮 - 直线移动，隔子打子
            return self.validate_cannon(from_row, from_col, to_row, to_col)
        elif piece_type == 'p':  # 兵/卒 - 直走，过河后可横走
            return self.validate_pawn(from_row, from_col, to_row, to_col, piece.isupper())

        return False

    def validate_rook(self, from_row, from_col, to_row, to_col):
        """验证车的走法 - 直线行走，不能越过棋子"""
        if from_row != to_row and from_col != to_col:
            return False

        # 检查路径上是否有棋子
        if from_row == to_row:  # 横向移动
            step = 1 if to_col > from_col else -1
            for c in range(from_col + step, to_col, step):
                if self.board[from_row][c]:
                    return False
        else:  # 纵向移动
            step = 1 if to_row > from_row else -1
            for r in range(from_row + step, to_row, step):
                if self.board[r][from_col]:
                    return False

        return True

    def validate_horse(self, from_row, from_col, to_row, to_col):
        """验证马的走法 - 日字，检查蹩马腿"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)

        # 马走日字
        if not ((row_diff == 2 and col_diff == 1) or (row_diff == 1 and col_diff == 2)):
            return False

        # 检查蹩马腿
        if row_diff == 2:
            # 竖着走，检查马腿位置
            leg_row = from_row + (1 if to_row > from_row else -1)
            leg_col = from_col
        else:
            # 横着走，检查马腿位置
            leg_row = from_row
            leg_col = from_col + (1 if to_col > from_col else -1)

        if self.board[leg_row][leg_col]:
            return False  # 蹩马腿

        return True

    def validate_elephant(self, from_row, from_col, to_row, to_col, is_red):
        """验证象/相的走法 - 田字，不能过河，检查塞象眼"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)

        # 象走田字
        if not (row_diff == 2 and col_diff == 2):
            return False

        # 象眼位置
        eye_row = from_row + (to_row - from_row) // 2
        eye_col = from_col + (to_col - from_col) // 2

        # 检查塞象眼
        if self.board[eye_row][eye_col]:
            return False

        # 不能过河
        if is_red:  # 红相不能到黑方半场（0-4 行）
            if to_row < 5:
                return False
        else:  # 黑象不能到红方半场（5-9 行）
            if to_row > 4:
                return False

        return True

    def validate_advisor(self, from_row, from_col, to_row, to_col, is_red):
        """验证士/仕的走法 - 斜走，只能在九宫格内"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)

        # 士走斜线
        if not (row_diff == 1 and col_diff == 1):
            return False

        # 检查是否在九宫格内
        if is_red:  # 红仕的九宫格
            if not (7 <= to_row <= 9 and 3 <= to_col <= 5):
                return False
        else:  # 黑士的九宫格
            if not (0 <= to_row <= 2 and 3 <= to_col <= 5):
                return False

        return True

    def validate_general(self, from_row, from_col, to_row, to_col, is_red):
        """验证将/帅的走法 - 直走，只能在九宫格内"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)

        # 将帅走直线
        if not ((row_diff == 1 and col_diff == 0) or (row_diff == 0 and col_diff == 1)):
            return False

        # 检查是否在九宫格内
        if is_red:  # 红帅的九宫格
            if not (7 <= to_row <= 9 and 3 <= to_col <= 5):
                return False
        else:  # 黑将的九宫格
            if not (0 <= to_row <= 2 and 3 <= to_col <= 5):
                return False

        return True

    def validate_cannon(self, from_row, from_col, to_row, to_col):
        """验证炮的走法 - 直线移动，隔子打子"""
        if from_row != to_row and from_col != to_col:
            return False

        # 计算路径上的棋子数
        count = 0
        if from_row == to_row:  # 横向
            step = 1 if to_col > from_col else -1
            for c in range(from_col + step, to_col, step):
                if self.board[from_row][c]:
                    count += 1
        else:  # 纵向
            step = 1 if to_row > from_row else -1
            for r in range(from_row + step, to_row, step):
                if self.board[r][from_col]:
                    count += 1

        target = self.board[to_row][to_col]

        if target:  # 吃子 - 必须正好有一个棋子隔着
            return count == 1
        else:  # 移动 - 路径上不能有棋子
            return count == 0

    def validate_pawn(self, from_row, from_col, to_row, to_col, is_red):
        """验证兵/卒的走法 - 直走，过河后可横走"""
        row_diff = to_row - from_row
        col_diff = to_col - from_col

        # 红方在棋盘下方（row 5-9），黑方在上方（row 0-4）
        # 河界：红方半场 row >= 5, 黑方半场 row <= 4
        if is_red:  # 红兵 - 向上走（row 减小）
            # 只能前进（row 减小）
            if row_diff > 0:
                return False
            # 未过河（row > 4）只能前进
            if from_row > 4:
                if col_diff != 0:
                    return False
                if row_diff != -1:
                    return False
            else:  # 已过河（row <= 4），可以横走或前进
                if abs(row_diff) + abs(col_diff) != 1:
                    return False
        else:  # 黑卒 - 向下走（row 增加）
            # 只能前进（row 增加）
            if row_diff < 0:
                return False
            # 未过河（row < 5）只能前进
            if from_row < 5:
                if col_diff != 0:
                    return False
                if row_diff != 1:
                    return False
            else:  # 已过河（row >= 5），可以横走或前进
                if abs(row_diff) + abs(col_diff) != 1:
                    return False

        return True


class PikafishEngine:
    def __init__(self, engine_path, nnue_path):
        self.engine_path = engine_path
        self.nnue_path = nnue_path
        self.process = None

    def start(self):
        """启动引擎"""
        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # 设置最大棋力选项
        self._send_command("setoption name Skill Level value 20")
        self._send_command(f"setoption name EvalFile value {self.nnue_path}")
        self._send_command("setoption name Threads value 4")
        self._send_command("setoption name Hash value 512")
        self._send_command("setoption name MultiPV value 1")
        self._send_command("uci")
        self._read_until("uciok")

    def stop(self):
        """停止引擎"""
        if self.process:
            self._send_command("quit")
            self.process.terminate()

    def _send_command(self, cmd):
        """发送命令到引擎"""
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

    def _read_until(self, marker):
        """读取输出直到找到指定标记"""
        output = []
        while True:
            line = self.process.stdout.readline().strip()
            output.append(line)
            if marker in line:
                break
        return output

    def set_position(self, fen):
        """设置局面"""
        self._send_command(f"position fen {fen}")

    def get_best_move(self, depth=10):
        """获取最佳走法"""
        self._send_command(f"go depth {depth}")

        while True:
            line = self.process.stdout.readline().strip()
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
                break
        return None


def parse_human_move(move_str, board):
    """解析人类输入的走法（支持坐标格式如 32-36）"""
    # 支持格式：32-36（列行 - 列行，列从右到左 1-9，行从下到上 1-10）
    match = re.match(r'(\d)(\d)-(\d)(\d)', move_str)
    if match:
        from_col = 9 - int(match.group(1))  # 1-9 -> 8-0
        from_row = int(match.group(2)) - 1  # 1-10 -> 0-9
        to_col = 9 - int(match.group(3))
        to_row = int(match.group(4)) - 1

        # 转换为 UCI 格式
        from_uci = chr(ord('a') + from_col) + str(from_row + 1)
        to_uci = chr(ord('a') + to_col) + str(to_row + 1)
        return from_uci + to_uci

    # 也支持直接输入 UCI 格式
    if re.match(r'[a-i]\d[a-i]\d', move_str):
        return move_str

    return None


def main():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    engine_path = os.path.join(script_dir, "pikafish-sse41-popcnt.exe")
    nnue_path = os.path.join(script_dir, "pikafish.nnue")

    print("=" * 50)
    print("    中国象棋人机对战")
    print("    引擎：Pikafish")
    print("=" * 50)

    # 初始化和启动引擎
    engine = PikafishEngine(engine_path, nnue_path)
    print("正在启动 AI 引擎...")
    engine.start()
    print("引擎启动完成！")

    # 初始化棋盘
    board = XiangqiBoard()

    print("\n走法输入格式：列行 - 列行")
    print("例如：32-36 表示从第 3 列第 2 行移动到第 3 列第 6 行")
    print("列从右到左为 1-9，行从下到上为 1-10")
    print("输入 'q' 退出游戏\n")

    board.display()

    # 游戏主循环
    while True:
        # 人类走棋（红方先行）
        while True:
            move_str = input("请输入你的走法：").strip()

            if move_str.lower() == 'q':
                print("游戏结束")
                engine.stop()
                return

            human_move = parse_human_move(move_str, board)

            if human_move:
                # 验证走法是否合法
                try:
                    from_col = ord(human_move[0]) - ord('a')
                    from_row = int(human_move[1]) - 1
                    to_col = ord(human_move[2]) - ord('a')
                    to_row = int(human_move[3]) - 1
                    piece = board.get_piece(from_row, from_col)
                    if piece and piece.isupper():  # 红方棋子
                        # 验证走法是否符合中国象棋规则
                        if board.is_valid_move(from_row, from_col, to_row, to_col):
                            success = board.make_move(human_move)
                            if success:
                                break
                            else:
                                print("无效的走法！该棋子不能这样走。")
                        else:
                            print("无效的走法！该棋子不能这样走。")
                    else:
                        print("无效的移动！请选择红方棋子。")
                except Exception as e:
                    print(f"无效的移动格式！{e}")
            else:
                print("无效的走法格式！请使用如 32-36 的格式")

        board.display()

        # 检查游戏是否结束
        fen = board.to_fen()
        engine.set_position(fen)

        # 检查游戏是否结束（将/帅是否被吃掉）
        game_state = board.check_game_over()
        if game_state['gameOver']:
            print(f"\n{game_state['reason']}")
            print("游戏结束！")
            engine.stop()
            return

        # AI 走棋（黑方）
        print("AI 思考中...")
        ai_move = engine.get_best_move(depth=20)

        if ai_move:
            print(f"AI 走法：{ai_move}")
            board.make_move(ai_move)
            board.display()

            # 检查 AI 走棋后游戏是否结束
            game_state = board.check_game_over()
            if game_state['gameOver']:
                print(f"\n{game_state['reason']}")
                print("游戏结束！")
                engine.stop()
                return

            # 更新局面
            fen = board.to_fen()
            engine.set_position(fen)
        else:
            print("AI 无法走棋，游戏结束！")
            break


if __name__ == "__main__":
    main()
