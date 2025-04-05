from taxApp.models import *
from taxApp.importScripts.onchainTransactions import getWeb3
import os
import requests
import json

def run():
    for user in User.objects.all():
        print(f"Updating transfers for {user.name}")
        for addr in user.address_set.all():
            for ch in Chain.objects.all():
                print(f"{ch.name} transactions for {addr.address}")
                updated = updateTransfers(ch, addr)
                print(f"{updated} transfers updated")

def updateTransfers(chain, address):
    web3 = getWeb3(chain)
    api_key = os.environ.get(f"ALCHEMY_APIKEY")
    url = f"{chain.endpoint}{api_key}"
    payloads = [{
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [
            {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": address.address,
                "category": ["erc20"],
                # "category": ["external"],
                "withMetadata": True,
                "excludeZeroValue": True,
                #"maxCount": "0x3e8"
            }
        ]
    },
    {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [
            {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "fromAddress": address.address,
                "category": ["erc20"],
                # "category": ["external"],
                "withMetadata": True,
                "excludeZeroValue": True,
                #"maxCount": "0x3e8"
            }
        ]
    }
    ]
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    saved = 0
    for payload in payloads:
        response = requests.post(url, json=payload, headers=headers)

        dat = json.loads(response.text)
        try:
            txs = dat['result']['transfers']
        except KeyError:
            print("no transfers")
            continue
        for tx in txs:
            if not tx['to']:
                print(f"no to address. skipping {tx['hash']}")
                continue

            try:
                t = Transaction.objects.get(chain=chain, hash=tx['hash'])
            except Transaction.DoesNotExist:
                print("new? skipping")
                continue

            try:
                txFromAddr = Address.objects.get(address=tx['from'])
                txToAddr = Address.objects.get(address=tx['to'])
                tokenAddr = tx['rawContract']['address']
                token = Token.objects.get(address=tokenAddr, chain=chain)
            except Exception as e:
                print(e)
                print("new? skipping")
                continue

            try:
                ttxs = TokenTransfer.objects.filter(
                    transaction = t,
                    fromAddr = txFromAddr,
                    toAddr = txToAddr,
                    coin = token.coin,
                )
                saved += ttxs.update(token=token)
            except Exception as e:
                print(str(e))
                pass

    return saved