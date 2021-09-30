# ECC tally-coin-poll utilities

This repository contains tools for tallying ZEC coin-weighted
poll results, such as the one operated by ECC described here:

https://forum.zcashcommunity.com/t/coin-holder-polling-instructions/40170

There are two utilities:

- [`tally.py`](#tally) uses `zcashd` to generate tally results in CSV format.
- [`google-sheets-updater.py`](#google-sheets-updater) uses `tally.py` and Google APIs to update a Google Sheets with the tally results.

## tally

The `tally.py` script calculates the tally results by querying a local
`zcashd` instance. It has the viewing key for the specific poll linked
above so that it should "just work" out of the box.

### Guide

To use it, follow these steps:

#### Step 1: Install `zcashd`

Follow the instructions here:

https://z.cash/download/

#### Step 2: Set up a separate instance of `zcashd`

We strongly recommend using a special-purpose `zcashd` deployment if you wish to use the `tally.py` script which is unrelated to any of your other `zcashd` usage, especially any wallet usage. This script _does not_ require any wallet access and it is prudent to never mix different use cases in with wallet use cases.

#### Step 3: Configure `zcashd` with indexing options

The `tally.py` script uses the full transaction index and taddr balance API features, so you must add these options into `~/.zcash/zcash.conf`:

```
txindex=1
experimentalfeatures=1
insightexplorer=1
```

#### Step 4: Sync and/or Reindex `zcashd`

If this is a brand new `zcashd` instance which you've *never* run before editing the config file, you need to wait for it to sync.

However, if you used this `zcashd` instance at all before editing the config file, you need to `reindex`. This is necessary and safe to do whether or not that instance is already synced to the network:

```
zcash-cli stop
zcashd -reindex
```

Reindexing or initial sync will take a fair amount of time. (On my cloud instance it took somewhere less than 24 hours.)

#### Step 4: Install `python3`

The `tally.py` script requires Python 3. Install it for your platform. On common debian-like linux setups, do this:

```
sudo apt update && sudo apt install python3
```

#### Step 5: Ensure `zcashd` is synced

I do this by running:

```
zcash-cli getinfo
```

-and then checking the `"blocks"` field against my other nodes or block explorers like https://zcashblockexplorer.com

#### Step 6: Run `tally.py`

The `tally.py` script has the specific polling viewing key baked in and will import it, request a rescan (if necessary), then query the blockchain APIs to generate the poll results.

It writes the poll results in a CSV format to `stdout` and writes debug information on `stderr`. You can save the results to a file with a command like this:

```
python3 ./tally.py > results.csv
```

You can then import those results into a spreadsheet app, or process them any other way.

## google-sheets-updater

The `google-sheets-updater.py` script runs `tally.py` periodically and uploads the results to a Google Sheets document. The following describes how to configure and operate this script:

### Step 1. Install Python 3 and `pip`

The `google-sheets-updater.py` script requires Python 3 and the `pip` dependency management tool. Install these for your platform. On common debian-like linux setups, do this:

```
sudo apt update && sudo apt install python3 python3-pip
```

To get a more recent and standardized `pip` install, run this on debian-like systems:

```
pip3 install --upgrade pip
```

Verify you now have the standard recent version of `pip`:

```
which pip
pip --version
```

### Step 2. Install Google API client libraries.

These instructions come directly from: https://developers.google.com/sheets/api/quickstart/python

```
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
