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
from src.Monitor import Monitor, DummyMonitor
from src.Config import Config


class Model:
    def __init__(self):
        self.total_bug_count = 0
        self.total_act_count = 0
        self.acts = []
        self.reset_acts = []
        self.state = []
        self.sm = StateMachine()
        self.actor = MasterActor()
        self.monitor = Monitor()
        self.last_action = None
        self.config = Config()

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
            monitor_state = self.monitor.get_state()
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


    def check_bug_triggered(self, categorys):
        """バグが発生しているかチェック
        @retval: True -> Bug
        @retval: False -> not Bug
        """
        result = True
        for c in categorys:
            excepted_state = self.sm.get_expected_state()[c]
            timeout = self.config.get_timeout(c)
            # print(f"expected_state={excepted_state} timeout={timeout}")
            result &= self.wait_state_transition(c, excepted_state[c], timeout)
        return not result


# class RealModel(Model):
#     def __init__(self, snd_device=1, snd_threshold=0.2, snd_duration=1.0):
#         super().__init__()
#         self.monitor = VolumeMonitor(snd_device, snd_threshold, snd_duration)

#     def perform_action(self, action):
#         if action in self.acts:
#             if self.sm.trigger(action):
#                 self.actor.perform_action(action)
#                 self.state.append(f"act:{action}")
#                 self.total_act_count += 1
#                 return True
#             else:
#                 print(f"{action} is not allowed!!")
#                 return False
#         else:
#             print(f"{action} is not found!!")
#             return False

#     def wait(self, duration):
#         time.sleep(duration)
#         self.state.append(f"wait:{duration}")
#         return True

#     def check_bug_triggered(self):
#         """バグが発生しているかチェック"""
#         # TODO: 実際のVolumeMonitorでチェックする処理を追加
#         pass


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
        self.bug_state = self.sm.get_all_states()
        for k in self.bug_state.keys():
            self.bug_state[k] = "ok"
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
