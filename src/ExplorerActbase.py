import random
import math


def PRINT(msg):
    """ログ出力"""
    if 0:
        print(msg)

class Count:
    def __init__(self):
        self.reset()

    def reset(self):
        self.total = 0   # 試行回数
        self.ok = 0      # OK（バグなし）
        self.ng = 0      # NG（バグあり）

    def bug_rate(self):
        return (self.ng / self.total) if self.total > 0 else 0.0

    def ok_rate(self):
        return (self.ok / self.total) if self.total > 0 else 0.0

class ExplorerNode:
    def __init__(self, name, is_action, acts=None,
                 wait_range=(1, 3, 1), probability=1.0,
                 probability_limit=(0.1, 0.9),
                 freeze_count=2, path_hist=None):

        self.name = name
        self.is_action = is_action  # 行動か、待機か
        self.children = []
        self.probability = probability
        self.expanded = False  # 初回展開済みか
        self.count = Count()   # 検索回数
        self.probability_limit = probability_limit  # 分岐確率のLimit
        self.acts = acts if acts is not None else []  # 行動
        self.wait_range = wait_range  # Waitの範囲

        if len(wait_range) == 3:
            interval = wait_range[2]
        else:
            interval = 1
        self.wait = list(range(wait_range[0], wait_range[1] + 1, interval))

        self.freeze_count = freeze_count  # Freezeするカウント
        self.freezed = False              # Freezeされたか
        self.last_probability = -1        # Freeze時の分岐確率

        if path_hist is None:
            self.path_hist = []
        else:
            self.path_hist = list(path_hist)

        self.path_hist.append(self.name)

    def get_bug_rate(self):
        return self.count.bug_rate()

    def ucb_score(self, parent_total_visits, c=1.0):
        """
        UCB スコア（バグ率 + exploration bonus）。
        parent_total_visits: 親ノード（あるいは全部の子合計）の総試行回数
        c: 探索係数（大きいほど未訪問探索を優先）
        """
        if parent_total_visits < 1:
            parent_total_visits = 1
        # exploit = 観測されたバグ率（高いほど注目）
        exploit = self.get_bug_rate()
        explore = c * math.sqrt(math.log(parent_total_visits) / (1 + self.count.total))
        # PRINT(f"UCB {self.name}: exploit={exploit:.3f}, explore={explore:.3f}")
        return exploit + explore

    def expand(self):
        if self.expanded:
            return
        self.expanded = True

        if not self.is_action:  # 行動ノードを展開
            p = 1 / len(self.acts) if self.acts else 1.0
            for act in self.acts:
                self.children.append(
                    ExplorerNode(
                        name=act,
                        is_action=True,
                        acts=self.acts,
                        wait_range=self.wait_range,
                        probability=p,
                        probability_limit=self.probability_limit,
                        freeze_count=self.freeze_count,
                        path_hist=self.path_hist.copy()
                    )
                )
        else:  # 待機ノードを展開
            p = 1 / len(self.wait) if self.wait else 1.0
            for wait in self.wait:
                self.children.append(
                    ExplorerNode(
                        name=str(wait),
                        is_action=False,
                        acts=self.acts,
                        wait_range=self.wait_range,
                        probability=p,
                        probability_limit=self.probability_limit,
                        freeze_count=self.freeze_count,
                        path_hist=self.path_hist.copy()
                    )
                )


    def mul_probability(self, v):
        """確率を乗算（limit範囲内のみ更新）"""
        if (not self.freezed) and (
            (v < 1 and self.probability > self.probability_limit[0]) or
            (v > 1 and self.probability < self.probability_limit[1])
        ):
            self.probability *= v

    def add_probability(self, v):
        """確率を加算"""
        if not self.freezed:
            self.probability += v

    def total_count_inc(self):
        self.count.total += 1
        # total_countが更新されるとFreezeされるかもしれないので試す
        self.try_to_freeze()

    def ok_count_inc(self):
        self.count.ok += 1

    def ng_count_inc(self):
        self.count.ng += 1

    def try_to_freeze(self):
        """指定回数探索後、かつ子ノードがすべてFreeze済ならFreezeする"""
        if self.freezed:
            return True
        elif (len(self.children) > 0 and self.all_children_is_freezed()) or \
             (len(self.children) == 0 and self.count.total >= self.freeze_count):
            self.last_probability = self.probability
            self.freezed = True
            PRINT(f"{'-'.join(self.path_hist)} is freezed. "
                  f"NG ratio:{self.count.ng/self.count.total:.2f}")
            return True
        else:
            return False

    def force_freeze(self):
        """強制的にFreezeする"""
        self.probability = 0
        self.freezed = True

    def is_freezed(self):
        return self.freezed

    def all_children_is_freezed(self):
        return all(c.is_freezed() for c in self.children)

class ExplorerTree:
    def __init__(self, root: 'ExplorerNode', max_depth: int = 10,
                 update_prob_inc=1.5, update_prob_dec=0.5,
                 update_prob_method="mul",
                 selection_method="probability",  # "probability" | "ucb" | "epsilon_greedy"
                 ucb_c=1.0,
                 epsilon=0.1):
        self.root = root
        self.path = None
        self.max_depth = max_depth
        self.update_prob_inc = update_prob_inc
        self.update_prob_dec = update_prob_dec
        self.update_prob_method = update_prob_method
        # selection params
        self.selection_method = selection_method
        self.ucb_c = ucb_c
        self.epsilon = epsilon

    def explore_once(self):
        """操作手順を決定"""
        current = self.root
        path = [current]

        # 操作手順がmax_depthまで探索
        for depth in range(self.max_depth):
            # 未展開ノードなら展開
            if not current.expanded:
                current.expand()

            if (len(current.children) == 0) or current.all_children_is_freezed():
                PRINT(f"{'-'.join(current.path_hist)} has no children or all freezed.")
                # 探索打ち切り
                if current.all_children_is_freezed():
                    current.force_freeze()
                return None

            # 分岐確率に基づいて子ノードを選択
            for c in current.children:
                PRINT(f"  child {c.name} p={c.probability:.3f} freezed={c.freezed} total={c.count.total} bug_rate={c.get_bug_rate():.3f}")
            current = self.choose_child(current.children)
            PRINT(f"-> choose {current.name} (p={current.probability:.3f})")
            path.append(current)

        # pathを逆にたどりFreezeできるところはFreezeする
        for p in path[::-1]:
            p.try_to_freeze()

        self.path = path
        return self.path

    def choose_by_random(self, children):
        children = [c for c in children if not c.is_freezed()]
        return random.choice(children)

    def choose_by_probability(self, children):
        children = [c for c in children if not c.is_freezed()]
        total = sum(max(0.0, c.probability) for c in children) or 1.0
        r = random.uniform(0, total)
        upto = 0.0
        for child in children:
            upto += child.probability
            if upto >= r:
                return child
        return children[-1]

    def choose_by_ucb(self, children):
        children = [c for c in children if not c.is_freezed()]
        parent_total = sum(c.count.total for c in children) or 1
        # 未訪問の子があれば優先的に選ぶ（UCB が高くなる）
        best = max(children, key=lambda c: c.ucb_score(parent_total, c=self.ucb_c))
        return best

    def choose_epsilon_greedy(self, children):
        children = [c for c in children if not c.is_freezed()]
        if random.random() < self.epsilon:
            return random.choice(children)
        else:
            # exploitation: 最大バグ率を選ぶ
            return max(children, key=lambda c: c.get_bug_rate())

    def choose_child(self, children):
        if not children:
            return None
        if self.selection_method == "random":
            return self.choose_by_random(children)
        elif self.selection_method == "probability":
            return self.choose_by_probability(children)
        elif self.selection_method == "ucb":
            return self.choose_by_ucb(children)
        elif self.selection_method == "epsilon_greedy":
            return self.choose_epsilon_greedy(children)
        else:
            return self.choose_by_probability(children)

    def feedback(self, result: bool):
        self._update_count(result)
        if result:
            self.update_probability(self.update_prob_inc, self.update_prob_method)
        else:
            self.update_probability(self.update_prob_dec, self.update_prob_method)

    def update_probability(self, value=0.5, method="mul"):
        current = self.root
        for p in self.path[1:]:  # 最初のSTARTノードは飛ばす
            if not current.all_children_is_freezed():
                for c in current.children:
                    if p.name == c.name:
                        if method == "add":
                            c.add_probability(value)
                        elif method == "mul":
                            c.mul_probability(value)
                        # 合計1になるよう正規化
                        total = sum(cc.probability for cc in current.children)
                        for x in current.children:
                            x.probability /= total
                        current = c
                        break

    def _update_count(self, result: bool):
        """pathで通ったnodeのCountを+1する"""
        current = self.root
        for p in self.path:
            for c in current.children:
                if p.name == c.name:
                    if not result:
                        c.ok_count_inc()
                    else:
                        c.ng_count_inc()
                    c.total_count_inc()
                    current = c
                    break
