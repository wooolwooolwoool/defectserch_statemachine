from pathlib import Path
import sys, random, pickle
import math
import copy
import json
import datetime
import os
import time

# パス設定
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.Explorer import ExplorerTree, ExplorerNode

def SLEEP(duration):
    """秒数待機"""
    if 1:
        time.sleep(duration)

def PRINT(msg):
    """ログ出力"""
    if 0:
        print(msg)

class SearchEngine:
    def __init__(self, model, root, tree, max_iter=100, seed=None, log=True, diagnose_bugs=True):
        self.model = model
        self.max_iter = max_iter
        self.root = root
        self.tree = tree
        self.results = []
        self.log = log
        if seed is not None:
            random.seed(seed)
        self.diagnose_bugs = diagnose_bugs

    def logger(self, msg):
        if self.log:
            print(msg)

    def print_results(self):
        for r in self.results:
            PRINT(r)

    def run(self):
        self.results = []
        i = 0
        self.finish = False
        while i < self.max_iter and not self.finish:
            i += 1
            self.logger(f"=== START iter={i+1} ===")
            self.logger("resetting")

            # 1. 状態のリセット
            self.model.reset()

            self.logger("=== Start act ===")
            # 2. 操作手順の決定
            while True:
                # 見つかるまで探索
                path = self.tree.explore_once()
                if path is None:
                    # freezeに突き当たったらやり直し
                    if self.tree.root.all_children_is_freezed():
                        PRINT("Searched All Route!!")
                        self.finish = True
                        break
                    else:
                        PRINT("Try to other Route")
                        continue
                else:
                    # 実行のシミュレーション。実行不可な場合はやり直し
                    result = self._action(path, simulate=True)
                    if result is not None:
                        break
                    else:
                        PRINT("Try to other Route")
                        continue
            if self.finish:
                break
            SLEEP(1)

            # 3. 操作
            result = self._action(path)
            if result is not None:
                self.logger("== check bug triggered ==")
                # 4. バグ発生チェック
                result_bug = self.model.check_bug_triggered()
                # ログ出力
                r = f"{i+1:04};" + ";".join(result) + (";BUG" if result_bug else ";OK")
                self.logger(r)
                self.results.append(r)

                # 探索木のUpdate
                self.tree.feedback(result_bug)
                SLEEP(1)
                self.logger(f"=== END iter={i+1} result_bug={result_bug} ===")
            else:
                self.logger(f"=== END iter={i+1} skip feedback ===")

    def _action(self, path, simulate=False):
        result = []
        for node in path:
            if node.name == "START":
                # 開始ノード
                result.append(f"act: {node.name}")
            elif node.is_action:
                # 行動ノード
                if self.model.perform_action(node.name, simulate=simulate):
                    result.append(f"act: {node.name}")
                else:
                    # 行動失敗（遷移不可な経路など）の場合はFeedbackスキップ
                    result = None
                    self.logger(f"force_freeze {node.name}")
                    node.force_freeze()
                    for p in path[::-1]:
                        p.try_to_freeze()
                    # 子ノード削除（失敗ノード以下は探索しない）
                    node.children = []
                    break
            elif not simulate:
                # 待機ノード
                self.model.wait(int(node.name))
                result.append(f"wait: {node.name}")
        return result

    def save_root_to_pickle(self, name="root.pickle"):
        with open(name, mode="wb") as f:
            pickle.dump(self.root, f)
        PRINT(f"saved to {name}")

