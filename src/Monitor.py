from pathlib import Path
import sys, random

# 上位ディレクトリをパスに追加
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.StateMachine import StateMachine

class Monitor:
    def __init__(self):
        self._check_state = {}

    def register_check_state(self, category, func):
        """State確認用関数を登録する"""
        self._check_state[category] = func

    def get_state(self, category):
        """
        現在の状態を返す
        """
        if category in self._check_state:
            return self._check_state[category]()
        else:
            return "unknown"

class DummyMonitor(Monitor):
    def __init__(self,
                 category=["power", "audio"]):
        """
        operations: 実行可能な行動のリスト
        """
        super().__init__()
        self.current_state = {}
        # ダミー実装
        for cat in category:
            self.current_state[cat] = "unknown"
            self.register_check_state(cat, self.check_state)

    def check_state(self, category):
        return self.current_state[category]

    def set_state(self, category, value):
        self.current_state[category] = value
