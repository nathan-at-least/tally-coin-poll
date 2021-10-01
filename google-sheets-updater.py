#! /usr/bin/env python3

from time import sleep
import logging
import datetime
import json
from pathlib import Path
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


POLL_CUTOFF_HEIGHT = 1410115
SLEEP_INTERVAL = 15


def main():
    basedir = Path.home() / 'tally-coin-poll'
    init_logging(basedir)
    config = load_config(basedir)

    u = Updater(config)
    csvdir = basedir / 'csvs'

    while True:
        for height in range(POLL_CUTOFF_HEIGHT, 1, -1):
            csvpath = csvdir / f'tally-{height}.csv'
            updatepath = csvpath + '.sheet-updated'
            if csvpath.exists() and not updatepath.exists():
                logging.info('Updating sheet with: %s', csvpath)
                u.update_from_csv(csvpath)
                updatepath.touch()
                if height == POLL_CUTOFF_HEIGHT:
                    logging.info('Updated final cutoff height %s.', height)
                    raise SystemExit()
                else:
                    break

        logging.debug('Sleeping for %s seconds...', SLEEP_INTERVAL)
        sleep(SLEEP_INTERVAL)


def init_logging(basedir):
    logdir = basedir / 'logs'
    logdir.mkdir(parents=True, exist_ok=True)

    logpath = logdir / 'gsu-log_{}.txt'.format(
        datetime.datetime.now().isoformat(),
    )
    logging.basicConfig(
        level=logging.DEBUG,
        filename=logpath,
        filemode='x',
        format='%(asctime)s [%(levelname) -5s] %(message)s',
    )
    return logpath


class Updater:
    def __init__(self, config):
        api_key = config['api_key']
        self.sheet_id = config['sheet_id']
        self.sheet_title = config['sheet_title']

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

    def _get_subsheet_id(self):
        for sheet in self._get_subsheets():
            props = sheet['properties']
            if props.get('title') == self.sheet_title:
                return props['sheetId']

    def _get_subsheets(self):
        query = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            fields='sheets.properties',
        )
        return query.execute().get('sheets')


def load_config(basedir):
    confpath = basedir / 'google-sheets-updater-config.json'
    with confpath.open('r') as f:
        config = json.load(f)

    if set(config.keys()) == set(['api_key', 'sheet_id', 'sheet_title']):
        return config
    else:
        raise ValueError(f'Unexpected or missing entries in {confpath}: {config!r}')


if __name__ == '__main__':
    main()
