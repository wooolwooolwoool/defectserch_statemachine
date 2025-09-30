import yaml
import threading
import time
import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.Config import Config

# 仮の実機状態取得関数（実際はあなたのコードに差し替え）
def get_actual_state(component):
    # 例：ハードウェアから読み取る
    return {
        "audio": "stopped",
        "video": "stopped",
        "power": "off"
    }.get(component, "unknown")


class Context:
    def __init__(self, initial_states, log=True):
        self.state = initial_states.copy()
        self.timers = {}
        self.log = log

    def get(self, key):
        return self.state.get(key)

    def set(self, updates):
        for key, value in updates.items():
            self.state[key] = value

    def logger(self, *args):
        if self.log:
            print(*args)

    def show(self):
        self.logger("現在の状態:", self.state)

    def satisfies(self, conditions):
        def parse_condition(cond_str):
            m = re.match(r'(\w+)\s*(==|in)\s*(.+)', cond_str)
            if not m:
                raise ValueError(f"条件パース失敗: {cond_str}")
            key, op, value = m.groups()
            if op == "in":
                # convert to [a, b] to ["a", "b"]
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    items = value[1:-1].split(",")
                    value = [item.strip().strip('"').strip("'") for item in items]
                else:
                    raise ValueError(f"in 演算子の値はリスト形式である必要があります: {value}")
            elif op == "==":
                value = value.strip().strip('"').strip("'")
            return key.strip(), op, value

        def check(cond_str):
            key, op, value = parse_condition(cond_str)
            current = self.get(key)
            if op == "==":
                return current == value
            elif op == "in":
                return current in value
            else:
                raise ValueError(f"Unknown: {op}")

        all_of = conditions.get("all_of", [])
        any_of = conditions.get("any_of", [])

        if all_of and not all(check(c) for c in all_of):
            return False
        if any_of and not any(check(c) for c in any_of):
            return False
        return True


class StateMachine:
    def __init__(self, log=True):
        self.log = log
        self.config = Config()
        self.states = self.config.states
        self.all_states = {name: defn.get("all", []) for name, defn in self.states.items()}
        self.actions = self.config.actions
        self.ctx = Context({name: defn["initial"] for name, defn in self.states.items()})
        self.setup_auto_transitions()

    def logger(self, *args):
        if self.log:
            print(*args)

    def set_all_states(self, states):
        self.ctx.state = states
        return

    def get_all_states(self):
        return self.all_states

    def setup_auto_transitions(self):
        for component, defn in self.states.items():
            if "auto_transitions" in defn:
                for state, rule in defn["auto_transitions"].items():
                    after = rule["after"]
                    to_state = rule["to"]

                    def create_auto_fn(comp=component, from_state=state, to_state=to_state):
                        def auto_transition():
                            if self.ctx.get(comp) == from_state:
                                self.logger(f"[AUTO] {comp}: {from_state} -> {to_state}")
                                self.ctx.set({comp: to_state})
                                if self.log:
                                    self.ctx.show()
                        return auto_transition

                    def schedule_auto_transition():
                        if self.ctx.get(component) == state:
                            timer = threading.Timer(after, create_auto_fn())
                            self.ctx.timers[component] = timer
                            timer.start()

                    # 最初の初期状態に該当する場合に自動起動
                    if self.ctx.get(component) == state:
                        schedule_auto_transition()

    def trigger(self, action):
        """_summary_

        Args:
            action (_type_): 操作名

        Returns:
            bool: success or not
        """
        if action not in self.actions:
            self.logger(f"[ERR] 操作 '{action}' は存在しません")
            return False

        op_def = self.actions[action]
        if not self.ctx.satisfies(op_def.get("required", {})):
            self.logger(f"[REJECT] 操作 '{action}' の条件を満たしません")
            return False

        self.logger(f"[OK] 操作 '{action}' 実行")
        self.ctx.set(op_def.get("transitions", {}))
        self.ctx.show()
        self.setup_auto_transitions()
        return True

    def get_expected_state(self):
        """

        Returns:
            dict: 期待される状態
        """
        return self.ctx.state

    def convert_state_to_str(self, state):
        sorted_items = sorted(state.items())
        return ",".join(f"{k}={v}" for k, v in sorted_items)

    def check_consistency_with_actual(self):
        mismatch = False
        for comp in self.states:
            expected = self.get_expected_state.get(comp)
            actual = get_actual_state(comp)
            if expected != actual:
                self.logger(f"[MISMATCH] {comp}: expect={expected} actual={actual}")
                mismatch = True
            else:
                self.logger(f"[MATCH] {comp}: state={expected}")
        return not mismatch

    def copy(self):
        new_sm = StateMachine.__new__(StateMachine)
        new_sm.__init__()
        new_sm.states = self.states
        new_sm.actions = self.actions
        new_sm.ctx = Context(self.ctx.state)
        new_sm.setup_auto_transitions()
        return new_sm


def main():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    sm = StateMachine(config)
    sm.ctx.show()

    sm.trigger("power_on")
    sm.trigger("play_audio")
    time.sleep(6)  # 自動遷移発生を待つ
    sm.trigger("shutdown")

    print("\n--- 実機との整合性チェック ---")
    sm.check_consistency_with_actual()


if __name__ == "__main__":
    main()