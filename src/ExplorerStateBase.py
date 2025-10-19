import random, sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.StateMachine import StateMachine
from itertools import product



class GraphNode:
    def __init__(self, name, state):
        self.name = name
        self.state = state  # 状態の辞書
        self.edges = {}  # action -> GraphEdge

class GraphEdge:
    def __init__(self, action, dst):
        self.action = action
        self.dst = dst
        self.trials = 0
        self.freezed = False
        self.results = {}  # {"audio": {"ok": 0, "ng": 0}, "video": {...}}
        self.is_action = True

    def record_result(self, result: dict):
        self.trials += 1
        for k, v in result.items():
            if k not in self.results:
                self.results[k] = {}
            if v not in self.results[k]:
                self.results[k][v] = 0
            self.results[k][v] += 1

    def freeze_condition(self):
        """Freezeすべきか判定"""
        if self.trials >= self.freeze_limit:
            self.freezed = True

    def unfreeze(self):
        self.freezed = False


class Explorer:
    def __init__(self, actions, max_steps=5, freeze_limit=3, log=True):
        self.sm = StateMachine(log=False)
        self.actions = actions
        self.graph = {}  # state_name -> GraphNode
        self.max_steps = max_steps
        self.freeze_limit = freeze_limit
        self.total_trials = 0
        self.feedback_count = 0
        self.log = log

    def build_graph(self):
        states = self.sm.get_all_states()

        keys = list(states.keys())

        for values in product(*(states[k] for k in keys)):
            state = dict(zip(keys, values))
            name = self.sm.convert_state_to_str(state)
            node = self.graph.setdefault(name, GraphNode(name, state))
            for a in self.actions:
                self.sm.set_all_states(state.copy())
                if self.sm.trigger(a) is False:
                    continue
                expected_state = self.sm.get_expected_state()
                dst = self.sm.convert_state_to_str(expected_state)
                node.edges[a] = GraphEdge(a, dst)
            # print(f"状態: {state}, 遷移可能アクション: {[e.action for e in node.edges.values()]}")
        # init_state から到達可能なノードだけに絞る
        init_state = self.sm.get_init_state()
        init_name = self.sm.convert_state_to_str(init_state)
        reachable = set()
        to_visit = [init_name]
        while to_visit:
            current = to_visit.pop()
            if current in reachable:
                continue
            reachable.add(current)
            node = self.graph.get(current)
            if node:
                for edge in node.edges.values():
                    if edge.dst not in reachable:
                        to_visit.append(edge.dst)
        self.graph = {name: node for name, node in self.graph.items() if name in reachable}
        self.logger(f"Graph built with {len(self.graph)} nodes")


    def select_edge(self, node, method="random"):
        """エッジ選択メソッド"""
        candidates = [e for e in node.edges.values() if not e.freezed]
        if not candidates:
            return None
        while True:
            if method == "random":
                result = random.choice(candidates)
            elif method == "least_tried":
                # 試行回数が少ない順
                result = min(candidates, key=lambda e: e.trials)
            elif method == "weighted":
                # 成功率 or 逆試行回数で重みづけ
                weights = [(1 / (1 + e.trials)) for e in candidates]
                total = sum(weights)
                r = random.uniform(0, total)
                upto = 0
                for e, w in zip(candidates, weights):
                    upto += w
                    if upto >= r:
                        result = e
                result = candidates[-1]
            break
        result = random.choice(candidates)
        # print(f"{node.name} candidates: {[e.action for e in candidates]} dst: {[e.dst for e in candidates]} result:{result.action}")
        return result

    def logger(self, *args):
        if self.log:
            print(*args)

    def explore_once(self, state, method="random"):
        path = []
        name = self.sm.convert_state_to_str(state)
        cur = self.graph[name]

        for _ in range(self.max_steps):
            edge = self.select_edge(cur, method=method)
            if edge is None:
                break

            path.append(edge)
            cur = self.graph[edge.dst]
            self.total_trials += 1
        if len(path) == 0:
            return None
        self.logger(f"state: {state}, path: {[e.action for e in path]}")
        return path

    # StartとGoalを指定して幅有線探索で最短パスを返却
    def find_shortest_path(self, start_state, goal_state):
        start_name = self.sm.convert_state_to_str(start_state)
        goal_name = self.sm.convert_state_to_str(goal_state)

        from collections import deque
        queue = deque()
        queue.append((start_name, []))
        visited = set()
        visited.add(start_name)

        while queue:
            current_name, path = queue.popleft()
            if current_name == goal_name:
                return path

            current_node = self.graph.get(current_name)
            if current_node:
                for edge in current_node.edges.values():
                    if edge.dst not in visited:
                        visited.add(edge.dst)
                        queue.append((edge.dst, path + [edge]))
        return None  # ゴールに到達できない場合


    def maybe_unfreeze(self):
        """探索が進んだら Freeze 解除も検討"""
        # 例: グラフ全体で100試行ごとに freeze_limit を +1
        if self.total_trials % 100 == 0:
            self.freeze_limit += 1
            for node in self.graph.values():
                for edge in node.edges.values():
                    if edge.freezed:
                        edge.unfreeze()

    def feedback(self, path, result: dict):
        """
        Path と結果を受け取り、エッジに反映する
        """
        for edge in path:
            if edge:
                edge.record_result(result)

        self.feedback_count += 1

    def export_dot(self, filename="graph", fmt="svg"):
        from graphviz import Digraph
        dot = Digraph(format=fmt)
        dot.attr("node", style="filled")
        min_val = min((e.trials for n in self.graph.values() for e in n.edges.values()), default=0)
        max_val = max((e.trials for n in self.graph.values() for e in n.edges.values()), default=1)
        val_range = max_val - min_val if max_val > min_val else 1

        def get_color(val):
            ratio = (val - min_val) / val_range
            # ratio: 0.0 (薄い) → 1.0 (濃い)
            # 濃いCyan: rgb(0, 200, 200)
            # 薄いCyan: rgb(240, 255, 255)

            r = int(240 * (1 - ratio))        # 減らす → 0
            g = int(255 * (1 - 0.2 * ratio))  # 少しだけ暗く → 200
            b = int(255 * (1 - 0.2 * ratio))  # 同上

            return f"#{r:02x}{g:02x}{b:02x}"

        for node_name, node in self.graph.items():
            # ノードの通過回数を集計（全エッジの試行回数合計で近似）
            fillcolor = get_color(max(e.trials for e in node.edges.values()))
            dot.node(node_name, label=node_name.replace(",", "\n"), fillcolor=fillcolor)

            for edge in node.edges.values():
                # エッジ試行回数で色変化（青系）
                trials = edge.trials
                color_level = min(255, 50 + trials * 20)
                color = f"#{0:02x}{0:02x}{color_level:02x}"

                # NG 回数合計で太さ調整
                ng_count = sum(v for res in edge.results.values()
                            for k, v in res.items() if k == "ng")
                penwidth = 1 + ng_count

                label = f"{edge.action}\\nT:{trials} NG:{ng_count}"
                dot.edge(node_name, edge.dst, label=label,
                        color=color, penwidth=str(penwidth))

        # filename は拡張子なしで渡すのが安全
        outpath = dot.render(filename, cleanup=True)
        print(f"Graph exported to {outpath}")
