import json


with open("config.json") as f:
    config: dict = json.load(f)

def get_config() -> dict:
    assert "spotify client secret" in config, "Provide the client secret in the config"
    assert "spotify client id" in config, "Provide the client id in the config"

    config.setdefault("update seconds", 1)

    config.setdefault("window center pos", (0, 0))
    config.setdefault("window size", (534, 300))

    config.setdefault("font size", 20)
    config.setdefault("seperation size", 15)

    config.setdefault("debug mode", False)
    config.setdefault("debug line", False)

    config.setdefault("save lyrics", False)

    return config


def save_config(config: dict) -> None:
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

