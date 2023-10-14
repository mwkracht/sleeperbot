from sleeperbot.manager import manage


def handler(event, context):
    result = manage()

    return f"Ran manager. Output: {result}"
