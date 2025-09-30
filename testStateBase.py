from src.Model import TestModel
from src.ExplorerStateBase import Explorer
from src.EngineStateBase import SearchEngine
# from utils.dot_exporter import export_tree_to_dot, export_tree_to_networkx

# 探索対象アクション
search_acts = [
    "CAN_IGOFF", "CAN_ACCON", "CAN_IGON",
    "ADBAudioOFF", "ADBFM", "ADBAM", "ADBBT-A"
]

# リセット時のアクション
reset_acts = [
]

# 待機範囲
wait_range = [1, 3]

# バグ定義
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

# モデル
model = TestModel()
model.set_acts(search_acts)
model.set_reset_acts(reset_acts)
model.set_bugs(bugs)

# 探索木
graph = Explorer(search_acts, max_steps=5, freeze_limit=4)

# 探索エンジン
engine = SearchEngine(
    model=model,
    graph=graph,
    max_iter=100,
    seed=666,
    log=True
)

# 探索開始
engine.run()
engine.print_results()
engine.save_root_to_pickle("root.pickle")
graph.export_dot()

# export_tree_to_networkx(root)
