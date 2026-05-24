import subprocess
import os
import time

class PikafishEngine:
    """
    UCI Python wrapper for local Pikafish engine binary.
    Communicates via subprocess stdin/stdout pipes to issue standard chess engine commands
    and parse telemetry telemetry (bestmove, score, principal variations) in real-time.
    """
    def __init__(self, engine_path="pikafish.exe"):
        self.engine_path = engine_path
        self.proc = None

    def start(self):
        """
        Launches the Pikafish subprocess and initializes the standard UCI interface handshake.
        """
        # Resolve engine path relative to main script location if not absolute
        if not os.path.isabs(self.engine_path):
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.engine_path)
            if os.path.exists(local_path):
                self.engine_path = local_path
                
        if not os.path.exists(self.engine_path):
            raise FileNotFoundError(
                f"Không tìm thấy engine Pikafish tại '{self.engine_path}'!\n"
                f"Vui lòng đặt file 'pikafish.exe' vào cùng thư mục chạy ứng dụng."
            )

        # Launch background engine process with suppressed CMD window on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0 # SW_HIDE

        self.proc = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            startupinfo=startupinfo
        )

        # Initialize UCI connection protocol
        self.send_command("uci")
        self.wait_for_response("uciok")
        
        # Multi-variant engines like Fairy-Stockfish require setting UCI_Variant to xiangqi
        if "fairy" in self.engine_path.lower():
            self.send_command("setoption name UCI_Variant value xiangqi")
            
        self.send_command("isready")
        self.wait_for_response("readyok")
        self.send_command("ucinewgame")

    def send_command(self, cmd):
        """Sends a raw string command to the engine stdin."""
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()

    def wait_for_response(self, expected_token, timeout=5):
        """Polls engine stdout lines until the expected UCI confirmation token is found."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            line = self.proc.stdout.readline().strip()
            if expected_token in line:
                return
            time.sleep(0.005)
        raise TimeoutError(f"Engine phản hồi timeout (không nhận được '{expected_token}' trong {timeout}s).")

    def analyze(self, fen, depth=10):
        """
        Runs complete analysis on the provided board state FEN at specified depth.
        Reads UCI outputs in real-time, parsing score, pv, and returning on 'bestmove'.
        """
        if not self.proc:
            raise RuntimeError("Engine chưa được khởi động! Hãy gọi start() trước.")

        self.send_command(f"position fen {fen}")
        self.send_command(f"go depth {depth}")

        bestmove = None
        score = "0.00"
        pv = []

        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()

            # Parse the final recommended bestmove
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                break

            # Parse intermediate info metrics
            if line.startswith("info") and "depth" in line:
                parts = line.split()
                
                # Extract evaluation scores (centipawns or force-mates)
                if "score" in parts:
                    try:
                        idx = parts.index("score")
                        score_type = parts[idx + 1]  # 'cp' or 'mate'
                        score_val = parts[idx + 2]
                        if score_type == "cp":
                            score = f"{int(score_val) / 100.0:+.2f}"
                        elif score_type == "mate":
                            score = f"M{score_val}"
                    except (ValueError, IndexError):
                        pass

                # Extract Principal Variation line
                if "pv" in parts:
                    try:
                        idx = parts.index("pv")
                        pv = parts[idx + 1:]
                    except (ValueError, IndexError):
                        pass

        return {
            "bestmove": bestmove,
            "score": score,
            "pv": pv
        }

    def stop(self):
        """Gracefully terminates the Pikafish process."""
        if self.proc:
            try:
                self.send_command("quit")
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None
