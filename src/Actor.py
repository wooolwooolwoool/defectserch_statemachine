import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.Config import Config

class Actor:
    def __init__(self):
        self._actions = {}

    def get_action(self):
        """
        実行可能な行動一覧を返す
        """
        return list(self._actions.keys())

    def register_action(self, name, func):
        """アクションを登録する"""
        self._actions[name] = func

    def perform_action(self, action):
        """
        指定された action を実行する。
        - get_action に含まれていない場合は False
        - 含まれている場合は True
        """
        if action in self.get_action():
            # 本来は実行処理を書く。ここでは成功扱いにする
            return True
        else:
            return False


class DummyActor(Actor):
    def __init__(self,
                 actions=["CAN_ACCON", "CAN_IGON", "CAN_IGOFF", "ADBFM", 'ADBAudioOFF']):
        """
        actions: 実行可能な行動のリスト
        """
        super().__init__()
        # ダミー実装
        for act in actions:
            self.register_action(act, lambda: True)


class MasterActor(DummyActor):
    pass