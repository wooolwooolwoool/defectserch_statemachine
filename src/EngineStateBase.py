from pathlib import Path
import sys, random, pickle
import math
import copy
import json
import datetime
import os
import time

def SLEEP(duration):
    """秒数待機"""
    if 0:
        time.sleep(duration)

def PRINT(msg):
    """ログ出力"""
    if 0:
        print(msg)

class SearchEngine:
    def __init__(self, model, graph, max_iter=100, seed=None, log=True, diagnose_bugs=True):
        self.model = model
        self.graph = graph
        self.max_iter = max_iter
        self.log = log
        if seed is not None:
            random.seed(seed)
        self.diagnose_bugs = diagnose_bugs
        self.result_bug_path = []

    def logger(self, *args):
        if self.log:
            print(*args)

    def run(self):
        self.result_bug_path = []
        i = 0
        self.finish = False
        self.graph.build_graph()
        while i < self.max_iter and not self.finish:
            i += 1
            self.logger(f"=== START iter={i} ===")
            self.logger("resetting")

            # 1. 状態のリセット
            self.model.reset()

            self.logger("=== Start act ===")
            # 2. 操作手順の決定
            state = self.model.get_current_state()
            path = self.graph.explore_once(state)
            if path is None:
                PRINT("Searched All Route!!")
                break
            SLEEP(1)

            # 3. 操作
            result = self._action(path)
            if result is not None:
                self.logger("== check bug triggered ==")
                # 4. バグ発生チェック
                result_bug = self.model.check_bug_triggered()
                for k, v in result_bug.items():
                    if v == "ng":
                        self.result_bug_path.append({
                            "i": i,
                            "path": path
                        })
                        break
                # ログ出力
                r = f"{i:04};" + ";".join(result) + (";BUG" if result_bug else ";OK")
                self.logger(r)

                # 探索木のUpdate
                self.graph.feedback(path, result_bug)
                SLEEP(1)
                self.logger(f"=== END iter={i} result_bug={result_bug} ===")
            else:
                self.logger(f"=== END iter={i} skip feedback ===")

    def _action(self, path, simulate=False):
        result = []
        for edge in path:
            if edge.action == "START":
                # 開始ノード
                result.append(f"act: {edge.action}")
            elif edge.is_action:
                # 行動ノード
                if self.model.perform_action(edge.action, simulate=simulate):
                    result.append(f"act: {edge.action}")
                else:
                    # 行動失敗（遷移不可な経路など）の場合はFeedbackスキップ
                    result = None
                    self.logger(f"force_freeze {edge.action}")
                    break
            elif not simulate:
                # 待機ノード
                self.model.wait(int(edge.action))
                result.append(f"wait: {edge.action}")
        return result

    def print_results(self):
        print(f"=== BUG num={len(self.result_bug_path)} ===")
        for p in self.result_bug_path:
            tmp = []
            for e in p["path"]:
                tmp.append(e.action)
            print(f"{p['i']:04} {'->'.join(tmp)}")
        print(f"=== BUG END ===")

    def save_root_to_pickle(self, name="root.pickle"):
        with open(name, mode="wb") as f:
            pickle.dump(self.graph.graph, f)
        PRINT(f"saved to {name}")

