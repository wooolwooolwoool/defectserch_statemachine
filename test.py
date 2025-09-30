from src.Model import TestModel
from src.Explorer import ExplorerTree, ExplorerNode
from src.Engine import SearchEngine
# from utils.dot_exporter import export_tree_to_dot, export_tree_to_networkx

# 全アクション
all_acts = [
    "CAN_IGOFF", "CAN_ACCON", "CAN_IGON",
    "ADBAudioOFF", "ADBFM",

]

# 探索対象アクション
search_acts = [
    "CAN_ACCON", "CAN_IGON",
    "ADBAudioOFF", "ADBFM"
]

# リセット時のアクション
reset_acts = [
    "CAN_IGON",
    "ADBAudioOFF"
]

# 待機範囲
wait_range = [1, 3]

# バグ定義
bugs = [
    {
        "path": ["act:CAN_ACCON", "wait:1", "act:ADBFM"],
        "prob": 0.8
    },
    {
        "path": ["act:CAN_ACCON", "wait:2", "act:ADBFM"],
        "prob": 0.8
    }
]

# モデル
model = TestModel()
model.set_acts(all_acts)
model.set_acts(search_acts)
model.set_reset_acts(reset_acts)
model.set_bugs(bugs)

# 探索木
root = ExplorerNode(
    "START",
    acts=search_acts,
    wait_range=wait_range,
    probability=1.0,
    probability_limit=[0.1, 0.9],
    freeze_count=4,
    path_hist=[],
    is_action=False
)
tree = ExplorerTree(
    root,
    max_depth=5,
    update_prob_inc=1.5,
    update_prob_dec=0.5,
    update_prob_method="mul",
    selection_method="ucb",  # "probability" | "ucb" | "epsilon_greedy" | "random"
)

# 探索エンジン
engine = SearchEngine(
    model=model,
    root=root,
    tree=tree,
    max_iter=50,
    seed=666,
    log=True
)

# 探索開始
engine.run()
engine.print_results()
# engine.save_root_to_pickle("root.pickle")

# export_tree_to_networkx(root)
