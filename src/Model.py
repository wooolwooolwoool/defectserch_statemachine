import re
import time
import random
import sys
from pathlib import Path
import copy

# 上位ディレクトリをパスに追加
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.Actor import MasterActor, DummyActor
# from VolumeMonitor import VolumeMonitor
from src.StateMachine import StateMachine
from src.Monitor.Monitor import Monitor, DummyMonitor
from src.Config import Config

DEBUG = False

class Model:
    def __init__(self, custom_actor=[], custom_monitor=[]):
        self.total_bug_count = 0
        self.total_act_count = 0
        self.acts = []
        self.reset_acts = []
        self.state = []
        self.sm = StateMachine()
        import pkgutil
        import inspect

        self.actor = MasterActor()


        self.monitor = {}
        from src import Monitor as monitor_module
        def is_monitor_subclass(obj):
            return inspect.isclass(obj) and issubclass(obj, Monitor) and obj is not Monitor

        monitors = [
            cls() for _, name, _ in pkgutil.iter_modules(monitor_module.__path__)
            for cls in vars(__import__(f"src.Monitor.{name}", fromlist=[""])).values()
            if is_monitor_subclass(cls)
        ] + [monitor() for monitor in custom_monitor]
        for m in monitors:
            self.monitor[m.category] = m

        if DEBUG:
            for cat in self.monitor.keys():
                print(f"Monitor loaded: {cat} -> {self.monitor[cat].__class__.__name__}")
            input(":")
        self.last_action = None
        self.config = Config()
        self.bug_state = self.sm.get_all_states()
        for k in self.bug_state.keys():
            self.bug_state[k] = "ok"

    def get_acts(self):
        """実行可能な操作のリストを取得"""
        return self.acts

    def set_acts(self, acts):
        self.acts = acts

    def get_current_state(self):
        return self.sm.ctx.state

    def set_reset_acts(self, acts):
        self.reset_acts = acts

    def reset(self):
        self.state = []
        for a in self.reset_acts:
            self.perform_action(a)

    def perform_action(self, action, simulate=False):
        if simulate:
            sm = self.sm.copy()
        else:
            sm = self.sm
        self.last_action = action
        if action in self.acts:
            if sm.trigger(action):
                if not simulate:
                    self.actor.perform_action(action)
                self.state.append(f"act:{action}")
                self.total_act_count += 1
                return True
            else:
                print(f"{action} is not allowed!!")
                return False
        else:
            print(f"{action} is not found!!")
            return False

    def wait(self, duration):
        time.sleep(duration)
        self.state.append(f"wait:{duration}")
        return True

    def wait_state_transition(self, category, expect, timeout=0):
        """状態遷移が起こるまで待つ（timeout 秒で打ち切り）
        @param category: 監視する状態のカテゴリ
        @param expect: 監視する状態の期待値
        @param timeout: タイムアウト時間（秒）
        @retval: True -> 状態遷移が起こった, False -> タイムアウト
        """
        start_time = time.time()
        initial_state = copy.deepcopy(self.sm.get_expected_state())
        while True:
            current_state = self.actor.get_current_state()
            monitor_state = self.monitor[category].get_state()
            # print(f"current_state={current_state} monitor_state={monitor_state}")
            if current_state != initial_state:
                if category in monitor_state:
                    if re.match(expect, str(monitor_state[category])):
                        return True
            if timeout > 0 and (time.time() - start_time > timeout):
                print("wait_state_transition timeout")
                return False
            if timeout == 0:
                return False
            time.sleep(0.1)

    def wait_state_transition(self, timeout=10):
        """状態遷移が起こるまで待つ（timeout 秒で打ち切り）"""
        start_time = time.time()
        initial_state = copy.deepcopy(self.sm.get_expected_state())
        while True:
            current_state = self.actor.get_current_state()
            if current_state != initial_state:
                return True
            if time.time() - start_time > timeout:
                print("wait_state_transition timeout")
                return False
            time.sleep(0.1)

    def check_bug_triggered(self, categories=[]):
        """バグが発生しているかチェック
        @retval:
        {
            audio: "ok"/"ng",
            video: "ok"/"ng",
            ...
        }
        """
        for cat in categories:
            if cat in self.monitor:
                expect = self.sm.get_expected_state().get(cat, None)
                timeout = self.config.get_monitor_timeout(cat)
                self.wait_state_transition(cat, expect, timeout)
                self.bug_state[cat] = self.monitor[cat].check_bug_triggered()
            else:
                self.bug_state[cat] = "ok"
        return self.bug_state

class TestModel(Model):
    def __init__(self):
        super().__init__()
        self.actor = DummyActor()
        self.acts = self.actor.get_action()
        self.monitor = None
        self.sm = StateMachine()
        self.reset_acts = []
        self.total_bug_count = 0
        self.total_act_count = 0
        self.checked = False
        self.bugs = []
        self.reset()

    def reset(self):
        super().reset()
        self.hist = []
        self.checked = False
        for k in self.bug_state.keys():
            self.bug_state[k] = "ok"

    def set_bugs(self, bugs):
        """
        bugs: list of dict
        例:
        bugs = [
            {
                "path": ["CAN_ACCON", "ADBFM"],
                "prob": 0.8,
                "bug": ["audio"]
            },
            {
                "path": ["CAN_ACCON", "ADBFM"],
                "prob": 0.8,
                "bug": ["audio"]
            }
        ]
        """
        self.bugs = bugs

    def perform_action(self, action, simulate=False):
        ret = super().perform_action(action, simulate)
        if ret:
            self.hist.append(action)
        return ret

    def wait(self, duration):
        # super().wait(duration) は実際にはsleepするので省略
        self.hist.append(f"wait:{duration}")
        return True

    def check_bug_triggered(self):
        """バグ発生したか確認"""
        for k in self.bug_state.keys():
            self.bug_state[k] = "ok"
        for bug in self.bugs:
            plen = len(bug["path"])
            for i in range(len(self.hist) - plen + 1):
                if self.hist[i:i + plen] == bug["path"]:
                    if bug["prob"] > random.uniform(0, 1.0):
                        for k in bug["bug"]:
                            self.bug_state[k] = "ng"
                        if not self.checked:
                            self.checked = True
                            self.total_bug_count += 1
                            print(f"Bug!! path={bug['path']} "
                                  f"total_act={self.total_act_count} "
                                  f"bug_count={self.total_bug_count}")
                        return self.bug_state
        return self.bug_state
