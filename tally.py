#! /usr/bin/env python3

import re
import csv
import json
import logging
import sys
import subprocess


POLL_ADDRESS = 'zs1j54w96syddfnrh2ehx40lyy7zej67z496nrqtg39r6jv00ks4pjyt57xz59kzy289c2rkdr6rhe'
POLL_VIEWING_KEY = 'zxviews1q0lfzpc7qqqqpqyp35tvhhl3gkwtfp06g3kulvraxqyr4zr8xxaxu895x5g64ss4t5uspgxwes4gqdppdqjkdlzgjetgjssz7mnq7e2axmn5k6xtn6fk658sylx97ng3ndfatv8qy3xry0l3agk49wraq8mhmfq6xaxzut4zgtrexx8llzzhyduw4egkszzgqldjx55xnckcrnrymcm3l4enpefkypptr6v8cezmmqjp78xjjres36hn47v2uujvj63fadrv6jw3q7gtf2vtj'
POLL_START_HEIGHT = 1398360


def main(args=sys.argv[1:]):
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='[%(levelname) -5s] %(message)s')
    logging.info('zec-coin-poll tally address: %s', POLL_ADDRESS)

    cli = ZcashClient()
    cli.z_importviewingkey(POLL_VIEWING_KEY, 'whenkeyisnew', POLL_START_HEIGHT)

    csvf = csv.DictWriter(
        sys.stdout,
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
        ],
    )
    csvf.writeheader()

    for receivedinfo in cli.z_listreceivedbyaddress(POLL_ADDRESS):
        txid = receivedinfo['txid']

        row = {
            'is valid': False,
            'txid': txid,
        }
        try:
            (taddr, answers) = parse_sender_and_memo(cli, txid, receivedinfo)
        except MalformedInput as e:
            row['parse issue'] = f'{e}'
        else:
            row['taddr'] = taddr
            for (i, (answer, comment)) in enumerate(answers):
                qnum = i+1
                row[f'answer {qnum}'] = answer
                row[f'answer {qnum} comment'] = comment

            try:
                bal = get_balance(cli, taddr)
            except MalformedInput as e:
                row['parse issue'] = f'{e}'
            else:
                row['balance'] = bal
                row['is valid'] = True

        csvf.writerow(row)


def parse_sender_and_memo(cli, txid, receivedinfo):
    memo = decode_memo(receivedinfo['memo'])
    sendaddr = get_sending_addr(cli, txid)
    return (sendaddr, memo)


def decode_memo(memhex):
    text = bytes.fromhex(memhex).decode('utf-8').strip('\0').strip()
    answers = []
    responses = text.split(';')
    if len(responses) > 3:
        raise MalformedInput(f'Could not parse memo {text!r}')

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

    try:
        [txin] = txinfo['vin']
    except ValueError:
        raise MalformedInput(f'Voting txid {txid} has unexpected number of inputs: {len(txinfo["vin"])}')

    intxid = txin['txid']
    invout = txin['vout']

    intxinfo = cli.getrawtransaction(intxid, 1)
    inout = intxinfo['vout'][invout]
    try:
        [addr] = inout['scriptPubKey']['addresses']
    except ValueError:
        raise MalformedInput(f'Sending txid {intxid} vout {invout} has unexpected number of scriptPubKeys {inout}')

    return addr


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
