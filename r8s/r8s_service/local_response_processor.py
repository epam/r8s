import json

MESSAGE = 'message'
ITEMS = 'items'
WARNINGS = 'warnings'
TABLE_TITLE = 'table_title'


class LocalCommandResponse:
    def __init__(self, body, code=200):
        self.status_code = code
        message = body.get(MESSAGE)
        items = body.get(ITEMS)
        warnings = body.get(WARNINGS, [])
        table_title = body.get(TABLE_TITLE)
        content = {WARNINGS: warnings}
        if message:
            content.update({MESSAGE: message})
        elif table_title and items:
            content.update({MESSAGE: items, TABLE_TITLE: table_title})
        else:
            content[WARNINGS].append(f'Please provide "{TABLE_TITLE}" '
                                     f'and "{ITEMS}" or "{MESSAGE}" parameter')
        self.text = json.dumps(content)
