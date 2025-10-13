import yaml
import threading
import time
import re
import ast
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.Config import Config

def convert_str_to_list(str_value):
    """ "[a,b,c]" -> ["a", "b", "c"] """
    str_value = str_value.strip()
    if str_value.startswith("[") and str_value.endswith("]"):
        items = str_value[1:-1].split(",")
        return [item.strip().strip('"').strip("'") for item in items]
    else:
        raise ValueError(f"リスト形式ではありません: {str_value}")

def evaluate_condition(current_value, condition_str):
    """シンプルなDSLを評価する"""
    if condition_str == "else":
        return True

    if "not in " in condition_str:
        _, rhs = condition_str.split("not in ")
        try:
            values = ast.literal_eval(rhs.strip())
        except:
            values = convert_str_to_list(rhs.strip())
        return current_value not in values
    elif "in " in condition_str:
        _, rhs = condition_str.split("in ")
        try:
            values = ast.literal_eval(rhs.strip())
        except:
            values = convert_str_to_list(rhs.strip())
        return current_value in values
    elif "==" in condition_str:
        lhs, rhs = condition_str.split("==")
        return current_value == rhs.strip()
    elif "!=" in condition_str:
        lhs, rhs = condition_str.split("!=")
        return current_value != rhs.strip()
    else:
        raise ValueError(f"Unknown condition: {condition_str}")

def get_next_state(action_def, current_states):
    """
    action_def: YAMLを読み込んだ辞書
    current_states: {"Audio": "Pause", "Display": "Stop", "Power": "Off"}
    """
    next_states = current_states.copy()
    transitions = action_def.get("transitions", {})

    for category, rules in transitions.items():
        # Power: On のような書き方に対応
        if isinstance(rules, str):
            next_states[category] = rules
            continue

        matched = False
        else_rule = None
        for rule in rules:
            cond = rule.get("condition")
            next_value = rule["next"]

            if cond == "else":
                else_rule = next_value
                continue

            current_value = current_states.get(category)
            if evaluate_condition(current_value, cond):
                next_states[category] = next_value
                matched = True
                break

        # どれにも一致しなかった場合 else を適用
        if not matched and else_rule is not None:
            next_states[category] = else_rule

    return next_states

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
        def check(key, condition_strs, all_):
            results = []
            for condition_str in condition_strs:
                current = self.get(key)
                results.append(evaluate_condition(current, condition_str.get("condition")))
            if all_:
                return all(results)
            else:
                return any(results)

        all_of = conditions.get("all_of", {})
        any_of = conditions.get("any_of", {})

        if all_of and not all(check(k, v, True) for k, v in all_of.items()):
            return False
        if any_of and not any(check(k, v, False) for k, v in any_of.items()):
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
        next_state = get_next_state(op_def, self.ctx.state)
        print(f"Next State: {next_state}")
        self.ctx.set(next_state)
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