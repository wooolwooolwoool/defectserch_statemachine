import yaml

yaml_path="data/config.yaml"

def set_yaml_path(path):
    global yaml_path
    yaml_path = path

class Config:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:  # 初回だけ生成
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
        self.states = config["states"]
        self.all_states = {name: defn.get("all", []) for name, defn in self.states.items()}
        self.actions = config["actions"]

    def get_timeout(self, category):
        if category in self.states and "timeout" in self.states[category]:
            return self.states[category]["timeout"]
        print(f"Warning: {category} timeout is not defined in config.yaml")
        return 0
