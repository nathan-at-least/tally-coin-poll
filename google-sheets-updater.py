#! /usr/bin/env python3
#
# References:
# https://developers.google.com/sheets/api/guides/concepts

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
            updatepath = csvdir / (csvpath.name + '.sheet-updated')

            if csvpath.exists():
                if not updatepath.exists():
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
        self.spreadsheet_id = config['spreadsheet_id']
        self.sheet_id = config['sheet_id']

        logging.info(
            'Loaded config with spreadsheet_id=%r, sheet_id=%r',
            self.spreadsheet_id,
            self.sheet_id,
        )
        self.service = build('sheets', 'v4')

    def update_from_csv(self, csvpath):
        with csvpath.open('r') as f:
            csvdata = f.read()

        request = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                'requests': [{
                    'pasteData': {
                        "coordinate": {
                            "sheetId": self.sheet_id,
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


def load_config(basedir):
    confpath = basedir / 'google-sheets-updater-config.json'
    with confpath.open('r') as f:
        config = json.load(f)

    if set(config.keys()) == set(['spreadsheet_id', 'sheet_id']):
        return config
    else:
        raise ValueError(f'Unexpected or missing entries in {confpath}: {config!r}')


if __name__ == '__main__':
    main()
