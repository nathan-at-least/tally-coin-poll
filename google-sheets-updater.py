import logging
import json
from pathlib import Path
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='[%(levelname) -5s] %(message)s'
    )
    u = Updater()
    raise NotImplementedError(u)


class Updater:
    def __init__(self):
        [api_key, self.sheet_id, self.sheet_title] = self._load_config()
        logging.info(
            'Loaded config with api_key=***, sheet_id=%r, sheet_title=%r',
            self.sheet_id,
            self.sheet_title,
        )
        self.service = build('sheets', 'v4', developerKey=api_key)
        self.subsheet_id = self._get_subsheet_id()
        logging.info(
            'Resolved subsheet_id=%r for %r',
            self.subsheet_id,
            self.sheet_title,
        )

    def update_from_csv(self, csvpath):
        with csvpath.open('r') as f:
            csvdata = f.read()

        request = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                'requests': [{
                    'pasteData': {
                        "coordinate": {
                            "sheetId": self.subsheet_id,
                            "rowIndex": "0",
                            "columnIndex": "0",
                        },
                        "data": csvdata,
                        "type": 'PASTE_NORMAL',
                        "delimiter": ',',
                    }
                }],
            },
        )
        return request.execute()

    @staticmethod
    def _load_config():
        confpath = Path.home() / 'tally-coin-poll-updater-config.json'
        with confpath.open('r') as f:
            config = json.load(f)

        keys = ['api_key', 'sheet_id', 'sheet_title']
        results = [ config.pop(k) for k in keys ]
        if config:
            raise ValueError(f'Unexpected entries in {confpath}: {config!r}')
        return results

    def _get_subsheet_id(self):
        for sheet in self._get_subsheets():
            props = sheet['properties']
            if props.get('title') == self.sheet_title:
                return props['sheetId']

    def _get_subsheets(self):
        query = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id],
            fields='sheets.properties',
        )
        return query.execute().get('sheets')


if __name__ == '__main__':
    main()
