#!/usr/bin/env python3
"""
中国象棋网页版后端服务器
"""

import subprocess
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import threading

# 初始 FEN
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

class XiangqiGame:
    def __init__(self, engine_path, nnue_path):
        self.engine_path = engine_path
        self.nnue_path = nnue_path
        self.process = None
        self.history = []
        self.current_fen = INITIAL_FEN
        self.start_engine()

    def start_engine(self):
        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # 设置最大棋力选项
        self._send("setoption name Skill Level value 20")
        self._send(f"setoption name EvalFile value {self.nnue_path}")
        self._send("setoption name Threads value 4")
        self._send("setoption name Hash value 512")
        self._send("setoption name MultiPV value 1")
        self._send("uci")
        self._read_until("uciok")

    def _send(self, cmd):
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

    def _read_until(self, marker):
        while True:
            line = self.process.stdout.readline().strip()
            if marker in line:
                break

    def reset(self):
        self.history = []
        self.current_fen = INITIAL_FEN

    def make_move(self, uci_move):
        """执行走法（玩家 - 红方）"""
        # 解析当前局面并执行走法
        board = self.fen_to_board(self.current_fen)
        # 转换 UCI 坐标到 board 坐标（引擎 row 0=底部，board row 0=顶部）
        # board_row = 9 - engine_row
        move = self.parse_uci_move(uci_move)

        if not move:
            return False

        from_row, from_col = move['from']
        to_row, to_col = move['to']

        piece = board[from_row][from_col]
        if not piece:
            return False

        # 验证走法是否符合中国象棋规则
        if not self.is_valid_move(board, from_row, from_col, to_row, to_col):
            return False

        # 执行走法
        board[to_row][to_col] = piece
        board[from_row][from_col] = None

        # 保存历史
        self.history.append(self.current_fen)
        # 玩家走完后，轮到黑方（b）
        self.current_fen = self.board_to_fen(board, 'b')

        # 设置新位置给引擎
        self._send(f"position fen {self.current_fen}")
        return True

    def check_game_over(self):
        """检查游戏是否结束（将/帅被吃掉）"""
        board = self.fen_to_board(self.current_fen)
        red_king = False
        black_king = False

        for row in board:
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

    def is_valid_move(self, board, from_row, from_col, to_row, to_col):
        """验证走法是否符合中国象棋规则"""
        if not (0 <= from_row < 10 and 0 <= from_col < 9):
            return False
        if not (0 <= to_row < 10 and 0 <= to_col < 9):
            return False

        piece = board[from_row][from_col]
        target = board[to_row][to_col]

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

        if piece_type == 'r':  # 车
            return self.validate_rook(board, from_row, from_col, to_row, to_col)
        elif piece_type == 'n':  # 马
            return self.validate_horse(board, from_row, from_col, to_row, to_col)
        elif piece_type == 'b':  # 象/相
            return self.validate_elephant(board, from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'a':  # 士/仕
            return self.validate_advisor(board, from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'k':  # 将/帅
            return self.validate_general(board, from_row, from_col, to_row, to_col, piece.isupper())
        elif piece_type == 'c':  # 炮
            return self.validate_cannon(board, from_row, from_col, to_row, to_col)
        elif piece_type == 'p':  # 兵/卒
            return self.validate_pawn(board, from_row, from_col, to_row, to_col, piece.isupper())

        return False

    def validate_rook(self, board, from_row, from_col, to_row, to_col):
        """验证车的走法"""
        if from_row != to_row and from_col != to_col:
            return False
        if from_row == to_row:
            step = 1 if to_col > from_col else -1
            for c in range(from_col + step, to_col, step):
                if board[from_row][c]:
                    return False
        else:
            step = 1 if to_row > from_row else -1
            for r in range(from_row + step, to_row, step):
                if board[r][from_col]:
                    return False
        return True

    def validate_horse(self, board, from_row, from_col, to_row, to_col):
        """验证马的走法"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)
        if not ((row_diff == 2 and col_diff == 1) or (row_diff == 1 and col_diff == 2)):
            return False
        if row_diff == 2:
            leg_row = from_row + (1 if to_row > from_row else -1)
            leg_col = from_col
        else:
            leg_row = from_row
            leg_col = from_col + (1 if to_col > from_col else -1)
        if board[leg_row][leg_col]:
            return False
        return True

    def validate_elephant(self, board, from_row, from_col, to_row, to_col, is_red):
        """验证象的走法"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)
        if not (row_diff == 2 and col_diff == 2):
            return False
        eye_row = from_row + (to_row - from_row) // 2
        eye_col = from_col + (to_col - from_col) // 2
        if board[eye_row][eye_col]:
            return False
        if is_red:
            if to_row < 5:
                return False
        else:
            if to_row > 4:
                return False
        return True

    def validate_advisor(self, board, from_row, from_col, to_row, to_col, is_red):
        """验证士的走法"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)
        if not (row_diff == 1 and col_diff == 1):
            return False
        if is_red:
            if not (7 <= to_row <= 9 and 3 <= to_col <= 5):
                return False
        else:
            if not (0 <= to_row <= 2 and 3 <= to_col <= 5):
                return False
        return True

    def validate_general(self, board, from_row, from_col, to_row, to_col, is_red):
        """验证将/帅的走法"""
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)
        if not ((row_diff == 1 and col_diff == 0) or (row_diff == 0 and col_diff == 1)):
            return False
        if is_red:
            if not (7 <= to_row <= 9 and 3 <= to_col <= 5):
                return False
        else:
            if not (0 <= to_row <= 2 and 3 <= to_col <= 5):
                return False
        return True

    def validate_cannon(self, board, from_row, from_col, to_row, to_col):
        """验证炮的走法"""
        if from_row != to_row and from_col != to_col:
            return False
        count = 0
        if from_row == to_row:
            step = 1 if to_col > from_col else -1
            for c in range(from_col + step, to_col, step):
                if board[from_row][c]:
                    count += 1
        else:
            step = 1 if to_row > from_row else -1
            for r in range(from_row + step, to_row, step):
                if board[r][from_col]:
                    count += 1
        target = board[to_row][to_col]
        if target:
            return count == 1
        else:
            return count == 0

    def validate_pawn(self, board, from_row, from_col, to_row, to_col, is_red):
        """验证兵的走法"""
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

    def get_ai_move(self, depth=20):
        """获取 AI 走法（AI - 黑方）"""
        # 先检查游戏是否已经结束
        check_result = self.check_game_over()
        if check_result['gameOver']:
            return {
                'move': None,
                'gameOver': True,
                'fen': self.current_fen,
                'winner': check_result['winner'],
                'reason': check_result['reason']
            }

        board = self.fen_to_board(self.current_fen)

        # 首先检查是否有直接吃掉红帅的棋步（一步杀）
        win_move = self.find_winning_move(board)
        if win_move:
            # 有直接获胜的走法，直接执行
            self._send(f"position fen {self.current_fen}")
            board[win_move['to'][0]][win_move['to'][1]] = board[win_move['from'][0]][win_move['from'][1]]
            board[win_move['from'][0]][win_move['from'][1]] = None
            self.history.append(self.current_fen)
            self.current_fen = self.board_to_fen(board, 'w')
            self._send(f"position fen {self.current_fen}")
            # 转换为 UCI 格式
            from_col = chr(ord('a') + win_move['from'][1])
            from_row = 9 - win_move['from'][0]
            to_col = chr(ord('a') + win_move['to'][1])
            to_row = 9 - win_move['to'][0]
            engine_move = f"{from_col}{from_row}{to_col}{to_row}"
            return {
                'move': engine_move,
                'gameOver': True,
                'fen': self.current_fen,
                'winner': 'black',
                'reason': '黑方吃掉红帅，获胜！'
            }

        # 没有直接获胜的走法，让引擎计算最优走法
        self._send(f"position fen {self.current_fen}")
        self._send(f"go depth {depth}")

        while True:
            line = self.process.stdout.readline().strip()
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    engine_move = parts[1]

                    # 检查引擎是否返回有效走法
                    if engine_move in ['(none)', '0000']:
                        # 无棋可走，可能被将死
                        return {
                            'move': None,
                            'gameOver': True,
                            'fen': self.current_fen,
                            'winner': 'red',
                            'reason': '黑方无棋可走，红方获胜！'
                        }

                    # 解析走法
                    from_col = ord(engine_move[0]) - ord('a')
                    from_row = 9 - int(engine_move[1])
                    to_col = ord(engine_move[2]) - ord('a')
                    to_row = 9 - int(engine_move[3])

                    board = self.fen_to_board(self.current_fen)

                    if 0 <= from_row < 10 and 0 <= from_col < 9 and board[from_row][from_col]:
                        # 执行走法
                        board[to_row][to_col] = board[from_row][from_col]
                        board[from_row][from_col] = None
                        self.history.append(self.current_fen)
                        # AI 走完后，轮到红方（w）
                        self.current_fen = self.board_to_fen(board, 'w')

                        # 检查是否吃掉红帅
                        check_result = self.check_game_over()
                        if check_result['gameOver']:
                            self._send(f"position fen {self.current_fen}")
                            return {
                                'move': engine_move,
                                'gameOver': True,
                                'fen': self.current_fen,
                                'winner': check_result['winner'],
                                'reason': check_result['reason']
                            }

                        # 更新引擎位置
                        self._send(f"position fen {self.current_fen}")
                        return {
                            'move': engine_move,
                            'gameOver': False,
                            'fen': self.current_fen
                        }
        return {'move': None, 'gameOver': False, 'fen': self.current_fen}

    def find_winning_move(self, board):
        """查找是否有可以直接吃掉红帅的棋步"""
        # 找到红帅的位置
        red_king_pos = None
        for r in range(10):
            for c in range(9):
                if board[r][c] == 'K':  # 红帅
                    red_king_pos = (r, c)
                    break
            if red_king_pos:
                break

        if not red_king_pos:
            return None  # 红帅不存在

        # 遍历所有黑方棋子，检查是否能直接吃掉红帅
        for r in range(10):
            for c in range(9):
                piece = board[r][c]
                if piece and piece.islower():  # 黑方棋子
                    # 检查这个棋子是否能合法移动到红帅位置
                    if self.is_valid_move(board, r, c, red_king_pos[0], red_king_pos[1]):
                        return {
                            'from': (r, c),
                            'to': red_king_pos
                        }

        return None  # 没有找到直接获胜的走法

    def undo(self):
        """悔棋（撤销两步：AI 和玩家）"""
        if len(self.history) >= 2:
            self.history.pop()  # 撤销 AI
            self.current_fen = self.history.pop()  # 撤销玩家
            self._send(f"position fen {self.current_fen}")
            return True
        elif len(self.history) >= 1:
            self.current_fen = self.history.pop()
            self._send(f"position fen {self.current_fen}")
            return True
        return False

    def fen_to_board(self, fen):
        """FEN 转棋盘数组 - FEN 格式：第 1 行=黑方底线，第 10 行=红方底线"""
        rows = fen.split()[0].split('/')
        board = [[None for _ in range(9)] for _ in range(10)]
        for r, row in enumerate(rows):
            c = 0
            for ch in row:
                if ch.isdigit():
                    c += int(ch)
                else:
                    board[r][c] = ch
                    c += 1
        return board

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

    def parse_uci_move(self, uci):
        """解析 UCI 走法"""
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


# 全局游戏实例
game = None

class RequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif parsed.path.startswith('/api/'):
            self.handle_api(parsed.path)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            self.handle_api(parsed.path, data)
        else:
            self.send_error(404)

    def handle_api(self, path, data=None):
        global game

        if path == '/api/newgame':
            game.reset()
            self.json_response({'fen': game.current_fen})

        elif path == '/api/move':
            success = game.make_move(data['move'])
            # 玩家走棋后检查游戏是否结束（是否吃掉黑将）
            check_result = game.check_game_over()
            self.json_response({
                'success': success,
                'fen': game.current_fen,
                'gameOver': check_result['gameOver'],
                'winner': check_result.get('winner'),
                'reason': check_result.get('reason')
            })

        elif path == '/api/ai':
            result = game.get_ai_move(data.get('depth', 20))
            self.json_response(result)

        elif path == '/api/undo':
            success = game.undo()
            self.json_response({'success': success, 'fen': game.current_fen})

        else:
            self.json_response({'error': 'Unknown endpoint'}, 404)

    def json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[Server] {args[0]}")


def main():
    global game

    script_dir = os.path.dirname(os.path.abspath(__file__))
    engine_path = os.path.join(script_dir, "pikafish-sse41-popcnt.exe")
    nnue_path = os.path.join(script_dir, "pikafish.nnue")

    print("=" * 50)
    print("    中国象棋网页版服务器")
    print("    引擎：Pikafish")
    print("=" * 50)

    # 初始化游戏
    print("正在启动 AI 引擎...")
    game = XiangqiGame(engine_path, nnue_path)
    print("引擎启动完成！")

    # 启动服务器
    port = 8080
    server = HTTPServer(('localhost', port), RequestHandler)
    print(f"\n服务器已启动：http://localhost:{port}")
    print("按 Ctrl+C 停止服务器\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        if game.process:
            game.process.stdin.write("quit\n")
            game.process.stdin.flush()
            game.process.terminate()
        server.shutdown()
        print("服务器已关闭")


if __name__ == "__main__":
    main()
