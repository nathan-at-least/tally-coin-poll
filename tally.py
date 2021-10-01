#! /usr/bin/env python3

import re
import csv
import datetime
import json
import logging
import sys
import subprocess
from pathlib import Path


POLL_ADDRESS = 'zs1j54w96syddfnrh2ehx40lyy7zej67z496nrqtg39r6jv00ks4pjyt57xz59kzy289c2rkdr6rhe'
POLL_VIEWING_KEY = 'zxviews1q0lfzpc7qqqqpqyp35tvhhl3gkwtfp06g3kulvraxqyr4zr8xxaxu895x5g64ss4t5uspgxwes4gqdppdqjkdlzgjetgjssz7mnq7e2axmn5k6xtn6fk658sylx97ng3ndfatv8qy3xry0l3agk49wraq8mhmfq6xaxzut4zgtrexx8llzzhyduw4egkszzgqldjx55xnckcrnrymcm3l4enpefkypptr6v8cezmmqjp78xjjres36hn47v2uujvj63fadrv6jw3q7gtf2vtj'
POLL_START_HEIGHT = 1398360


def main(args=sys.argv[1:]):
    basedir = Path.home() / 'tally-coin-poll'

    cli = ZcashClient()
    height = cli.getinfo()['blocks']

    csvdir = basedir / 'csvs'
    csvdir.mkdir(parents=True, exist_ok=True)
    csvpath = csvdir / f'tally-{height}.csv'

    if csvpath.exists():
        raise SystemExit()
    else:
        print(f'Tally path {csvpath} does not exist; generating...')

    init_logging(basedir, height)
    logging.info('Importing viewing key for zec-coin-poll tally address: %s', POLL_ADDRESS)
    cli.z_importviewingkey(POLL_VIEWING_KEY, 'whenkeyisnew', POLL_START_HEIGHT)

    with csvpath.open('w') as f:
        csvf = csv.DictWriter(
            f,
            [
                'is valid',
                'taddr',
                'balance',
                'answer 1',
                'answer 1 comment',
                'answer 2',
                'answer 2 comment',
                'answer 3',
                'answer 3 comment',
                'parse issue',
                'txid',
                'block height recorded',
            ],
        )
        csvf.writeheader()

        height = cli.getinfo()['blocks']
        for receivedinfo in cli.z_listreceivedbyaddress(POLL_ADDRESS):
            row = create_row(cli, receivedinfo)
            row['block height recorded'] = height
            logging.debug('Writing row: %r', row)
            csvf.writerow(row)


def init_logging(basedir, height):
    logdir = basedir / 'logs'
    logdir.mkdir(parents=True, exist_ok=True)

    logpath = logdir / 'log_height-{}_{}.txt'.format(height, datetime.datetime.now().isoformat())
    logfile = logpath.open('w')
    logging.basicConfig(level=logging.DEBUG, stream=logfile, format='[%(levelname) -5s] %(message)s')


def create_row(cli, receivedinfo):
    txid = receivedinfo['txid']

    row = {
        'txid': txid,
    }
    issues = []

    try:
        memo = decode_memo(receivedinfo['memo'])
    except MalformedInput as e:
        issues.append(f'{e}')
    else:
        try:
            answers = parse_answers(memo)
        except MalformedInput as e:
            issues.append(f'{e}')
        else:
            for (i, (answer, comment)) in enumerate(answers):
                qnum = i+1
                row[f'answer {qnum}'] = answer
                row[f'answer {qnum} comment'] = comment

    try:
        taddr = get_sending_addr(cli, txid)
    except MalformedInput as e:
        issues.append(f'{e}')
    else:
        row['taddr'] = taddr
        try:
            row['balance'] = get_balance(cli, taddr)
        except MalformedInput as e:
            issues.append(f'{e}')

    row['is valid'] = len(issues) == 0
    row['parse issue'] = '; '.join(issues)
    return row


def decode_memo(memhex):
    try:
        membytes = bytes.fromhex(memhex)
    except ValueError as e:
        raise MalformedInput(f'Internal zcashd API failure, could not decode memo hex: {e}')

    try:
        utf8 = membytes.decode('utf-8')
    except UnicodeDecodeError as e:
        raise MalformedInput(f'Malformed memo utf-8 in {membytes!r}: {e}')

    return utf8.strip('\0').strip()


def parse_answers(memo):
    answers = []
    responses = memo.split(';')

    junkfields = [f for f in responses[3:] if len(f.strip()) > 0]
    if junkfields:
        raise MalformedInput(f'Unexpected extra fields: {"; ".join(junkfields)}')

    for (ix, response) in enumerate(responses):
        response = response.strip()
        qnum = str(ix+1)
        if response.startswith(qnum):
            fullanswer = response[len(qnum):]
            if len(fullanswer) == 0:
                raise MalformedInput('Could not parse memo response {qnum}: {response!r}')

            option = fullanswer[0].lower()
            if (qnum in (1, 2) and option not in 'abcde') or (qnum == 3 and option not in 'yn'):
                raise MalformedInput('Could not parse memo response {qnum}, unknown option {option!r} in {response!r}')

            extra = fullanswer[1:].strip()
            answers.append((option, extra))

    return answers


def get_sending_addr(cli, txid):
    txinfo = cli.getrawtransaction(txid, 1)

    taddrs = set()
    intxids = set()
    for txin in txinfo['vin']:
        intxid = txin['txid']
        intxids.add(intxid)
        invout = txin['vout']

        intxinfo = cli.getrawtransaction(intxid, 1)
        inout = intxinfo['vout'][invout]
        try:
            [taddr] = inout['scriptPubKey']['addresses']
        except ValueError:
            raise MalformedInput(f'Sending txid {intxid} vout {invout} has unexpected number of scriptPubKeys {inout}')

        taddrs.add(taddr)

    if len(taddrs) == 0:
        raise MalformedInput(
            f'Voting memo came from fully shielded transfers with no associated taddr.'
        )
    elif len(taddrs) > 1:
        raise MalformedInput(
            f'Voting memo came from {len(taddrs)} taddrs, {", ".join(taddrs)}, where a single taddr was expected; ' +
            f'sending txids {", ".join(intxids)}'
        )

    return taddrs.pop()


def get_balance(cli, taddr):
    return cli.getaddressbalance({'addresses': [taddr]})['balance']


class MalformedInput (Exception):
    '''
    Throw this exception if a polling input is malformed. The process
    will log the issue and continue scanning other inputs.
    '''
    pass


class ZcashClient:
    def __getattr__(self, mname):
        return ZcashClientMethod(mname)


class ZcashClientMethod:
    def __init__(self, methodname):
        self._methodname = methodname

    def __call__(self, *args):
        def convert_arg(v):
            if type(v) is str:
                return v
            else:
                return json.dumps(v)

        fullargs = ['zcash-cli', self._methodname] + list(map(convert_arg, args))
        logging.debug('Executing: %r', fullargs)
        output = subprocess.check_output(fullargs)
        return json.loads(output)


if __name__ == '__main__':
    main()
