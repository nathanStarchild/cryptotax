from taxApp.models import *
from taxApp.utils import getPrice, savePrice

from web3 import Web3
from eth_utils import event_abi_to_log_topic
import os
import subprocess
import requests
import json
import datetime
from zoneinfo import ZoneInfo
from decimal import *

from importlib import import_module
from django.conf import settings
from django.db import transaction, connection



SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

def saveTxHashes(address, chain):
    api_key = os.environ.get(f"APIKEY_{chain.symbol}")
    url = f"{chain.endpoint}{api_key}"
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [
            {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "fromAddress": address.address,
                "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                "withMetadata": True,
                "excludeZeroValue": False,
                #"maxCount": "0x3e8"
            }
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    dat = json.loads(response.text)
    txs = dat['result']['transfers']
    # print(txs[0])
    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
    saved = 0
    for tx in txs:
        date = datetime.datetime.strptime(tx['metadata']['blockTimestamp'], fmt)
        t = Transaction(
            address = address,
            chain = chain,
            txHash = tx['hash'],
            date=date.astimezone(ZoneInfo('UTC')),
        )
        try:
            t.save()
            saved += 1
        except Exception as e:
            print(str(e))

    return saved

def updateSession(sessionKey, status=None, progress=None, msg=None):
    with transaction.atomic():
        session = SessionStore(session_key=sessionKey)
        if status:
            session["txFees status"] = status
        if progress:
            session["txFees progress"] = progress
        if msg:
            session["txFees msg"] = msg
        session.save()

def saveTxFees(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            saveTxFee(tx)
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        msg = f"{processed} tx fees successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(e)
        updateSession(sessionKey, status="error", msg=str(e))
    finally:
        connection.close()

def getTxReceipt(tx):
    api_key = os.environ.get(f"APIKEY_{tx.chain.symbol}")
    url = f"{tx.chain.endpoint}{api_key}"
    
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_getTransactionReceipt",
        "params": [tx.txHash]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    dat = json.loads(response.text)
    return dat

def saveTxFee(tx):
    dat = getTxReceipt(tx)
    # print(dat)
    gasUsed = Decimal(int(dat['result']['gasUsed'], 16))
    gasPrice  = Decimal(int(dat['result']['effectiveGasPrice'], 16))
    fee = gasUsed * gasPrice * Decimal('1E-18')
    # print(f"{tx.txHash} - {fee}")
    tx.fee = fee
    tx.feeCoin = tx.chain.feeCoin
    tx.save()

def saveTxFeeSpends(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            saveTxFeeSpend(tx)
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        msg = f"{processed} tx fees successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(e)
        updateSession(sessionKey, status="error", msg=str(e))
    finally:
        connection.close()

def saveTxFeeSpend(tx):
    price = getPrice(tx.feeCoin, tx.date)
    tx.feeAUD = tx.fee * price
    tx.save()
    tx.refresh_from_db()
    tx.createFeeSpend()


#ABIs
def getABI(contractAddress, chain):
    try:
        contract = Contract.objects.get(address=contractAddress, chain=chain)
        print("loading ABI from db")
    except Contract.DoesNotExist:
        print("downloading abi")
        api_key = os.environ.get(f"EXPLORER_APIKEY_{chain.symbol}")
        url = f"https://api.{chain.explorer}/api?module=contract&action=getabi&address={contractAddress}&apikey={api_key}"
        contract = Contract(address=contractAddress, chain=chain)
        contract.saveABI(requests.get(url).text)
        # assert False, 'yep'
        contract.save()
        # contract.refresh_from_db()
    return contract.getABI()

def decodeLogs(tx):
    api_key = os.environ.get(f"APIKEY_{tx.chain.symbol}")
    url = f"{tx.chain.endpoint}{api_key}"
    web3 = Web3(Web3.HTTPProvider(url))
    # receipt = getTxReceipt(tx)
    receipt = web3.eth.get_transaction_receipt(tx.txHash)
    decoded_logs_out = []
    for log in receipt['logs']:
        log_index = log['logIndex']
        print()
        print(f"index {log_index}")
        contractAddress = log['address']
        abi = getABI(contractAddress, tx.chain)
        contract = web3.eth.contract(contractAddress, abi=abi)
        receipt_event_signature_hex = web3.to_hex(log["topics"][0])
        abi_events = [a for a in contract.abi if a["type"] == "event"]
        # Determine which event in ABI matches the transaction log you are decoding
        for event in abi_events:
            # Get event signature components
            # name = event["name"]
            # inputs = [param["type"] for param in event["inputs"]]
            # inputs = ",".join(inputs)
            # # Hash event signature
            # event_signature_text = f"{name}({inputs})"
            # event_signature_hex = web3.to_hex(web3.keccak(text=event_signature_text))

            # or get it from web3
            eventABI = contract.events[event["name"]]()
            event_signature = event_abi_to_log_topic(eventABI.abi)

            if web3.to_hex(event_signature) == receipt_event_signature_hex:

            # Find match between log's event signature and ABI's event signature
            # if event_signature_hex == receipt_event_signature_hex:
                # Decode matching log
                for decoded_logs in contract.events[event["name"]]().process_receipt(receipt):
                    if decoded_logs.logIndex == log_index:
                        decoded_logs_out.append(decoded_logs)
                        break
    return decoded_logs_out


def getTxValue(tx):
    api_key = os.environ.get(f"APIKEY_{tx.chain.symbol}")
    url = f"{tx.chain.endpoint}{api_key}"
    web3 = Web3(Web3.HTTPProvider(url))
    # receipt = getTxReceipt(tx)
    return web3.eth.get_transaction(tx.txHash).value
