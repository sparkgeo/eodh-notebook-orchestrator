import json
import os


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "template_config.json")


def load_config(config_path):
    with open(config_path, "r") as f:
        return json.load(f)


def get_template_path_for_collection(collection, config, templates_dir="templates"):
    # Looks up the template for the given collection in the config
    template_file = config["collections"][collection]["template"]
    return os.path.join(os.path.dirname(__file__), templates_dir, template_file)


def get_template_path(collection):
    config = load_config(CONFIG_PATH)
    template_path = get_template_path_for_collection(collection, config)
    return template_path
