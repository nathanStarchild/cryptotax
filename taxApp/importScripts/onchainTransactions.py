from taxApp.models import *
from taxApp.utils import getPrice, savePrice

from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import ABIFunctionNotFound, ContractLogicError
from eth_utils import event_abi_to_log_topic
import os
import subprocess
import requests
import json
import datetime
from zoneinfo import ZoneInfo
from decimal import *
import traceback

from importlib import import_module
from django.conf import settings
from django.db import transaction, connection
from django.db.models import Sum
from django.db.models.functions import Coalesce



SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

def getWeb3(chain):
    api_key = os.environ.get(f"APIKEY_{chain.symbol}")
    url = f"{chain.endpoint}{api_key}"
    web3 = Web3(Web3.HTTPProvider(url))
    if chain.name == "Polygon POS":
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return web3

def tryMultipleKeys(myDict, keysToCheck):
    val = None
    for k in keysToCheck:
        val = myDict.get(k)
        if val is not None:
            break
    else:
        raise KeyError(f"None of the keys ({keysToCheck}) were found in {myDict}")
    return val

def saveTxHashes(address, chain):
    api_key = os.environ.get(f"APIKEY_{chain.symbol}")
    url = f"{chain.endpoint}{api_key}"
    web3 = getWeb3(chain)
    pageKey = None
    saved = 0
    while (True):
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "alchemy_getAssetTransfers",
            "params": [
                {
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "fromAddress": address.address,
                    # "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                    "category": ["external"],
                    "withMetadata": True,
                    "excludeZeroValue": False,
                    #"maxCount": "0x3e8"
                }
            ]
        }

        if pageKey:
            payload["params"]["pageKey"] = pageKey

        headers = {
            "accept": "application/json",
            "content-type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        dat = json.loads(response.text)
        txs = dat['result']['transfers']
        try:
            pageKey = dat['result']['pageKey']
        except KeyError:
            pass
        # print(txs[0])
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
        for tx in txs:
            # t = saveTx(tx['hash'], chain, web3)
            # saveTxFee(t)
            # saveTxFeeSpend(t)
            date = datetime.datetime.strptime(tx['metadata']['blockTimestamp'], fmt)
            # fromAddr, _ = Address.objects.get_or_create(address=address)
            toAddr, _ = Address.objects.get_or_create(address=web3.to_checksum_address(tx['to']))
            try:
                t, created = Transaction.objects.get_or_create(
                    fromAddr = address,
                    toAddr = toAddr,
                    chain = chain,
                    hash = tx['hash'],
                    date=date.replace(tzinfo=ZoneInfo('UTC')),
                )
                # t.save()
                saved += 1
            except Exception as e:
                print(str(e))
        if not pageKey:
            break

    return saved

def saveIncomingTxs(toAddress, chain):
    web3 = getWeb3(chain)
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
                "toAddress": toAddress.address,
                "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                # "category": ["external"],
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
    # return
    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
    saved = 0
    noUser = User.objects.get(name="noUser")
    for tx in txs:
        try:
            t = Transaction.objects.get(chain=chain, hash=tx['hash'])
            print('already exists')
            continue
        except Transaction.DoesNotExist:
            pass
        date = datetime.datetime.strptime(tx['metadata']['blockTimestamp'], fmt)
        if not tx['category'] == "external":
            tx = web3.eth.get_transaction(tx['hash'])
            # print(tx.value)
        if not (tx['to']):
            print('no To address')
            continue
        # continue
        # txTo = web3.to_checksum_address(tx['to'])

        toAddr, _ = Address.objects.get_or_create(address=web3.to_checksum_address(tx['to']))
        fromAddr, _ = Address.objects.get_or_create(address=web3.to_checksum_address(tx['from']))
        # try:
        #     fromAddr = Address.objects.get(address=tx['from'])
        # except Address.DoesNotExist:
        #     fromAddr = Address(address=tx['from'])
        #     fromAddr.save()

        t = Transaction(
            fromAddr = fromAddr,
            toAddr = toAddr,
            chain = chain,
            hash = web3.to_hex(tx['hash']),
            date=date.astimezone(ZoneInfo('UTC')),
            value=web3.from_wei(tx['value'], 'ether'),
            feeCoin=chain.feeCoin,
        )
        try:
            t.save()
            saved += 1
        except Exception as e:
            print(traceback.format_exc())
            print(tx['hash'])
            # raise

    return saved

def saveTx(hash, chain, web3=None):
    if web3 is None:
        web3 = getWeb3(chain)
    try:
        t = Transaction.objects.get(hash=hash, chain=chain)
        return t
    except:
        pass
    tx = web3.eth.get_transaction(hash)
    timestamp = web3.eth.get_block(tx.blockHash).timestamp
    d = datetime.datetime.fromtimestamp(timestamp).astimezone(ZoneInfo('UTC'))
    fromAddr, _ = Address.objects.get_or_create(address=tx['from'])
    toAddr, _ = Address.objects.get_or_create(address=tx['to'])

    t, created = Transaction.objects.get_or_create(
        fromAddr = fromAddr,
        toAddr = toAddr,
        chain = chain,
        hash = hash,
        date = d,
        value = web3.from_wei(tx.value, 'ether')
    )
    try:
        t.save()
        return t
    except Exception as e:
        print(str(e))
        raise

def saveIncomingInternalTxs(toAddress, chain):
    web3 = getWeb3(chain)
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
                "toAddress": toAddress.address,
                "category": ["internal"],
                # "category": ["external"],
                "withMetadata": True,
                "excludeZeroValue": True,
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
    saved = 0
    for tx in txs:
        try:
            t = Transaction.objects.get(chain=chain, hash=tx['hash'])
            print('already exists')
        except Transaction.DoesNotExist:
            t = saveTx(tx['hash'], chain, web3)

        txFromAddr, _ = Address.objects.get_or_create(address=tx['from'])
        txToAddr, _ = Address.objects.get_or_create(address=tx['to'])
        coin = chain.feeCoin
        assert coin.symbol.lower() == tx['asset'].lower(), 'unexpected internal transfer asset'

        itx = InternalTransaction(
            transaction = t,
            fromAddr = txFromAddr,
            toAddr = txToAddr,
            coin = coin,
            value = tx['value'],
        )
        try:
            itx.save()
            saved += 1
        except Exception as e:
            print(str(e))

    return saved

def saveIncomingTokenTransfers(toAddress, chain):
    web3 = getWeb3(chain)
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
                "toAddress": toAddress.address,
                "category": ["erc20"],
                # "category": ["external"],
                "withMetadata": True,
                "excludeZeroValue": True,
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
    saved = 0
    for tx in txs:
        if not tx['to']:
            print(f"no to address. skipping {tx['hash']}")
            continue
        try:
            t = Transaction.objects.get(chain=chain, hash=tx['hash'])
            # print('already exists')
        except Transaction.DoesNotExist:
            t = saveTx(tx['hash'], chain, web3)

        txFromAddr, _ = Address.objects.get_or_create(address=tx['from'])
        txToAddr, _ = Address.objects.get_or_create(address=tx['to'])
        tokenAddr = tx['rawContract']['address']
        token = getOrCreateToken(tokenAddr, chain, web3)
        if tx['value'] is None:
            print("gotNull")
            assert tx['rawContract']['value'] is not None, f"null value transfer? {tx}"
            val = web3.to_int(hexstr=tx['rawContract']['value'])
            val = web3.from_wei(val, 'ether')
            try:
                ttx = TokenTransfer.objects.get(
                    transaction = t,
                    fromAddr = txFromAddr,
                    toAddr = txToAddr,
                    coin = token.coin,
                    value = Decimal(0),
                )
                ttx.value = val
                ttx.save()
                print(f"token transfer {ttx} value updated from 0 to {val}")
                continue
            except TokenTransfer.DoesNotExist:
                pass
        else:
            val = tx['value']

        ttx = TokenTransfer(
            transaction = t,
            fromAddr = txFromAddr,
            toAddr = txToAddr,
            coin = token.coin,
            value = val,
        )
        try:
            ttx.save()
            saved += 1
        except Exception as e:
            print(str(e))
            pass

    return saved

def saveOutgoingTokenTransfers(fromAddress, chain):
    web3 = getWeb3(chain)
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
                "fromAddress": fromAddress.address,
                "category": ["erc20"],
                # "category": ["external"],
                "withMetadata": True,
                "excludeZeroValue": True,
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
    saved = 0
    for tx in txs:
        if not tx['to']:
            print(f"no to address. skipping {tx['hash']}")
            continue
        try:
            t = Transaction.objects.get(chain=chain, hash=tx['hash'])
            # print('already exists')
        except Transaction.DoesNotExist:
            t = saveTx(tx['hash'], chain, web3)

        txFromAddr, _ = Address.objects.get_or_create(address=tx['from'])
        txToAddr, _ = Address.objects.get_or_create(address=tx['to'])
        tokenAddr = tx['rawContract']['address']
        token = getOrCreateToken(tokenAddr, chain, web3)
        if tx['value'] is None:
            print("gotNull")
            assert tx['rawContract']['value'] is not None, f"null value transfer? {tx}"
            val = web3.to_int(hexstr=tx['rawContract']['value'])
            val = web3.from_wei(val, 'ether')
            try:
                ttx = TokenTransfer.objects.get(
                    transaction = t,
                    fromAddr = txFromAddr,
                    toAddr = txToAddr,
                    coin = token.coin,
                    value = Decimal(0),
                )
                ttx.value = val
                ttx.save()
                print(f"token transfer {ttx} value updated from 0 to {val}")
                continue
            except TokenTransfer.DoesNotExist:
                pass
        else:
            val = tx['value']

        ttx = TokenTransfer(
            transaction = t,
            fromAddr = txFromAddr,
            toAddr = txToAddr,
            coin = token.coin,
            value = val,
        )
        try:
            ttx.save()
            saved += 1
        except Exception as e:
            # print(str(e))
            pass

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

def saveTxValues(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            tx.value = getTxValue(tx)
            tx.save()
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        msg = f"{processed} tx values successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(e)
        updateSession(sessionKey, status="error", msg=str(e))
    finally:
        connection.close()

def saveTxTos(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            saveTxTo(tx)
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
        "params": [tx.hash]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    dat = json.loads(response.text)
    return dat

def saveTxFee(tx):
    if tx.fee is not None:
        return
    dat = getTxReceipt(tx)
    # print(dat)
    gasUsed = Decimal(int(dat['result']['gasUsed'], 16))
    gasPrice  = Decimal(int(dat['result']['effectiveGasPrice'], 16))
    fee = gasUsed * gasPrice * Decimal('1E-18')
    # print(f"{tx.hash} - {fee}")
    tx.fee = fee
    tx.feeCoin = tx.chain.feeCoin
    tx.save()

def saveTxTo(tx):
    toAddr = getTxTo(tx)
    tx.toAddr, _ = Address.objects.get_or_create(toAddr)
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

def processApprovals(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            tx.processed = isApproval(tx)
            tx.save()
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

def isApproval(tx):
    print(tx.id)
    inputs = decodeInput(tx)
    if not inputs:
        return False
    return inputs[0].fn_name == "approve"

def isDexTrade(tx):
    print(tx.id)
    inputs = decodeInput(tx)
    if not inputs:
        return False
    return inputs[0].fn_name in ["multicall", "swapExactETHForTokens"]

def isDepositOrSend(tx, web3=None, transfers=None, decodedLogs=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    if decodedLogs is None:
        decodedLogs = decodeLogs(tx, web3)
    if transfers is None:
        transfers = getTransfersInOut(tx, web3, decodedLogs)
    incoming, outgoing = transfers
    if outgoing and not incoming:
        return True
    if len(outgoing) == 1 and len(incoming) == 1:
        if outgoing[0]['coin'] == incoming[0]['coin']:
            if outgoing[0]['amount'] == incoming[0]['amount']:
                return True
    return False

def processDexTrades(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            if isDexTrade(tx):
                processDexTrade(tx)
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        msg = f"{processed} tx fees successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())
        updateSession(sessionKey, status="error", msg=traceback.format_exc())
    finally:
        connection.close()

def processDepositsAndSends(txs, sessionKey):
    try:
        count = txs.count()
        processed = 0
        for tx in txs:
            if isDepositOrSend(tx):
                print(f"{tx.id} is deposit)")
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        msg = f"{processed} tx fees successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())
        updateSession(sessionKey, status="error", msg=traceback.format_exc())
    finally:
        connection.close()

def processDexOops(buys, sales, sessionKey):
    try:
        count = buys.count() + sales.count()
        processed = 0
        for sale in sales:
            print()
            print(Sale.objects.filter(pk=sale.id).values())
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        sales.delete()
        for buy in buys:
            costBasis = CostBasis.objects.filter(date=buy.date)
            tx = Transaction.objects.get(date=buy.date)
            print()
            print(Buy.objects.filter(pk=buy.id).values())
            print(costBasis.values())
            costBasis.delete()
            print(tx)
            tx.processed = False
            tx.save()
            processed += 1
            progress = round(100*processed/count)
            updateSession(sessionKey, progress=progress)
        buys.delete()
        msg = f"{processed} tx fees successfully processed"
        updateSession(sessionKey, status="complete", msg=msg)
    except Exception as e:
        print(str(e))
        print(traceback.format_exc())
        updateSession(sessionKey, status="error", msg=traceback.format_exc())
    finally:
        connection.close()

def processBridgeSend(tx, web3=None, decodedLogs=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    if decodedLogs is None:
        decodedLogs = decodeLogs(tx, web3)
    incoming, outgoing = getTransfersInOut(tx, web3, decodedLogs)
    if not outgoing:
        return f"nothing going out. Not a bridge send? {tx.hash}"
    if incoming:
        return f"what's this coming in? Not a bridge send? {tx.hash}"
    if len(outgoing)>1:
        return f"too many outgoing tokens. {outgoing}\n{tx.hash}"
    outgoing = outgoing[0]
    
    bs = TokenBridge(
        coin = outgoing['coin'],
        unitsSent = outgoing['amount'],
        date=tx.date,
        user=tx.fromAddr.user,
        feeCoin = outgoing['coin'],
        note = "Bridge Transfer",
        transactionSend = tx
    )
    bs.save()
    tx.processed = True
    tx.save()
    print("TokenBridge created")
    return "processed as TokenBridge"

def processVaultDeposit(tx, web3=None, amount=None, coin=None, address=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    if amount is None and coin is None:
        outs = tx.tokentransfer_set.filter(fromAddr=tx.fromAddr)
        assert outs.count() <= 1, f"hhhmmm, too many outgoing transfers {outs.values()}"
        if not outs.exists():
            amount = tx.value
            coin = tx.feeCoin
            assert amount > 0, f"No transfers out and no tx value? {tx.hash}"
        else:
            amount = outs[0].value
            coin = outs[0].coin

    if address is None:
        address = tx.toAddr.address
    # try:
    #     Token.objects.get(address=address, chain=tx.chain)
    #     print("yep")
    #     address = outs[0].toAddr.address
    # except Token.DoesNotExist:
    #     pass
    vault, created = Vault.objects.get_or_create(chain=tx.chain, address=address)
    if created:
        vault.name = getContractName(vault.address, tx.chain, web3)

    d = VaultDeposit(
        vault = vault,
        user = tx.fromAddr.user,
        coin = coin,
        amount = amount,
        transaction = tx
    )
    d.save()
    return "vault deposit processed"

def getVaultNames():
    for v in Vault.objects.filter(name__isnull=True):
        v.name = getContractName(v.address, v.vaultdeposit_set.first().transaction.chain)
        v.save()

def processVaultWithdrawal(tx, web3=None, amount=None, coin=None, address=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    if address is None:
        address = tx.toAddr.address
    if address == "0x88DCDC47D2f83a99CF0000FDF667A468bB958a78":
        vault = Vault.objects.get(pk=6)
    else:
        vault = Vault.objects.get(chain=tx.chain, address=address)
    
    if amount is None and coin is None:
        ins = tx.tokentransfer_set.filter(toAddr=tx.fromAddr)
        assert ins.count() <= 1, f"hhhmmm, too many incoming transfers {ins.values()}"
        if not ins.exists():
            ins = tx.internaltransaction_set.filter(toAddr=tx.fromAddr)
            assert ins.count() == 1, f"hhhmmm, too many incoming transfers {ins.values()}"

        amount = ins[0].value
        coin = ins[0].coin

    balance = vault.getBalance()

    income = max(amount - balance, Decimal(0))
    withdrawn = amount - income

    w = VaultWithdrawal(
        vault = vault,
        user = tx.fromAddr.user,
        coin = coin,
        amount = withdrawn,
        transaction = tx
    )
    w.save()

    msg = "Vault withdrawal saved successfully."

    if income:
        i = VaultIncome(
            vault = vault,
            user = tx.fromAddr.user,
            coin = coin,
            amount = income,
            transaction = tx
        )
        i.save()
        i.refresh_from_db()
        i.createIncome()

        msg += " Vault income saved Successfully"

    return msg

def processVaultIncome(tx, web3=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    vault = Vault.objects.get(chain=tx.chain, address=tx.toAddr.address)
    ins = tx.tokentransfer_set.filter(toAddr=tx.fromAddr)
    assert ins.count() <= 1, f"hhhmmm, too many incoming transfers {ins.values()}"
    if not ins.exists():
        ins = tx.internaltransaction_set.filter(toAddr=tx.fromAddr)
        assert ins.count() == 1, f"hhhmmm, too many incoming transfers {ins.values()}"

    amount = ins[0].value
    coin = ins[0].coin

    i = VaultIncome(
        vault = vault,
        user = tx.fromAddr.user,
        coin = coin,
        amount = amount,
        transaction = tx
    )
    i.save()
    i.createIncome()
    return "Income saved successfully"

def processVaultRestake(tx, web3=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    vault = Vault.objects.get(chain=tx.chain, address=tx.toAddr.address)
    ins = tx.tokentransfer_set.filter(toAddr=tx.fromAddr)
    assert ins.count() <= 1, f"hhhmmm, too many incoming transfers {ins.values()}"
    if not ins.exists():
        ins = tx.internaltransaction_set.filter(toAddr=tx.fromAddr)
        assert ins.count() == 1, f"hhhmmm, too many incoming transfers {ins.values()}"

    amount = ins[0].value
    coin = ins[0].coin

    i = VaultIncome(
        vault = vault,
        user = tx.fromAddr.user,
        coin = coin,
        amount = amount,
        transaction = tx
    )
    i.save()
    i.createIncome()
    msg = "Income saved successfully."

    d = VaultDeposit(
        vault = vault,
        user = tx.fromAddr.user,
        coin = coin,
        amount = amount,
        transaction = tx
    )
    d.save()
    msg += " Vault deposit saved successfully."
    return msg

# def migrateVault(tx, oldVault, newVault, web3=None):
#     if web3 is None:
#         web3 = getWeb3(tx.chain)
#     balance = oldVault.getBalance()

#     w = VaultWithdrawal(
#         vault = oldVault,
#         user = tx.fromAddr.user,
#         coin = oldVault.vaultdeposit_set.first().coin,
#         amount = balance,
#         transaction = tx
#     )
#     w.save()

#     d = VaultDeposit(
#         vault = newVault,
#         user = tx.fromAddr.user,
#         coin = oldVault.vaultdeposit_set.first().coin,
#         amount = balance,
#         transaction = tx
#     )
#     d.save()

#     return "vault migration processed"


    


def processDexTrade(tx, bought=None, sold=None):
    print(tx.hash)
    if bought is None and sold is None:
        bought, sold = getTransfersInOut(tx)
        if not sold:
            print(f"nothing going out. Not a dex trade? {tx.hash}")
        if not bought:
            print(f"nothing coming in. Not a dex trade? {tx.hash}")
            return
        if len(sold)>1 or len(bought)>1:
            print(f"too many tokens coming in or out: \nbought: {bought}\nsoud: {sold}\n{tx.hash}")
            return
        bought = bought[0]
        sold = sold[0]
        sold['priceAUD'] = getPrice(sold['coin'], tx.date)
        try:
            bought['priceAUD'] = sold['priceAUD'] * sold['amount'] / bought['amount']
        except KeyError:
            print(bought)
            print(sold)
            raise

    b = Buy(
        coin=bought['coin'],
        units=bought['amount'],
        unitPrice=bought['priceAUD'],
        date=tx.date,
        user=tx.fromAddr.user,
        feeAUD=tx.feeAUD,
        fee = tx.fee,
        feeCoin = tx.feeCoin,
        note=f"Dex trade {bought['coin'].symbol} {sold['coin'].symbol}",
        refId=tx.hash,
    )
    b.save()
    b.refresh_from_db()
    b.savePrice()
    b.createCostBasis()
    print('buy order entered')

    s = Sale(
        coin=sold['coin'],
        units=sold['amount'],
        unitPrice=sold['priceAUD'],
        date=tx.date,
        user=tx.fromAddr.user,
        feeAUD=tx.feeAUD,
        fee = tx.fee,
        feeCoin = tx.feeCoin,
        note=f"Dex trade {bought['coin'].symbol} {sold['coin'].symbol}",
        refId=tx.hash,
    )
    s.save()
    s.savePrice()
    print('sale entered')
    tx.processed = True
    tx.save()
    
def getTransfersInOut(tx, web3=None, decodedLogs=None, addresses=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    if decodedLogs is None:
        decodedLogs = decodeLogs(tx, web3)
    if addresses is None:
        addresses = [tx.fromAddr.address]
    incoming = []
    outgoing = []
    for log in decodedLogs:
        if log.event in ["Transfer", "LogTransfer"]:
            try:
                coin = Token.objects.get(address=log.address, chain=tx.chain).coin
            except Token.DoesNotExist:
                coin = "unknown"
            try:
                toAddress = tryMultipleKeys(log.args, ['to', '_to'])
                if toAddress in addresses:
                    amt = tryMultipleKeys(log.args, ["amount", "_amount", "value", "_value"])
                    amt = web3.from_wei(amt, 'ether')
                    incoming.append({"coin": coin, "amount": amt})
                    print("somethin")
            except KeyError:
                pass
            except AttributeError:
                print(tx.hash)
                print(log)
                raise
            try:
                fromAddress = tryMultipleKeys(log.args, ['from', '_from'])
                if fromAddress in addresses:
                    amt = tryMultipleKeys(log.args, ["amount", "_amount", "value", "_value"])
                    amt = web3.from_wei(amt, 'ether')
                    outgoing.append({"coin": coin, "amount": amt})
                    print("somethin")
            except KeyError:
                pass
            except AttributeError:
                print(tx.hash)
                print(log)
                raise

    if not tx.value:
        val = getTxValue(tx, web3)
        tx.value = val
        tx.save()
    if tx.value:
        for out in outgoing:
            if out['coin'] == tx.feeCoin and out['amount'] == tx.value:
                break
            else:
                outgoing.append({"coin": tx.feeCoin, "amount": tx.value})
        if not outgoing:
            outgoing.append({"coin": tx.feeCoin, "amount": tx.value})
    return incoming, outgoing

def getOrCreateToken(address, chain, web3=None):
    if web3 is None:
        web3 = getWeb3(chain)
    try:
        token = Token.objects.get(address=address, chain=chain)
        return token
    except Token.DoesNotExist:
        spam = Coin.objects.get(name__iexact="spam")
        address = web3.to_checksum_address(address)
        contract = loadContract(address, chain, web3)
        if not contract:
            print(f"no contract for {address} on {chain.name}, saving as spam")
            token = Token(
                chain = chain,
                address = address,
                coin = spam
                )
            token.save()
            return token
        name = getContractName(address, chain, web3, contract)
        symbol = getContractSymbol(address, chain, web3, contract)
        try:
            name = web3.to_text(name).replace('\x00', '')
        except:
            pass
        try:
            symbol = web3.to_text(symbol).replace('\x00', '')
        except:
            pass
        print(f"gonna create {name} - {symbol}\nfor {address} on {chain.name}")
        try:
            coin = Coin.objects.get(symbol__iexact=symbol)
        except Coin.DoesNotExist:
            print("no coin found, saving as spam")
            token = Token(
                chain = chain,
                address = address,
                coin = spam
                )
            token.save()
            return token

        token = Token(
            address = address,
            chain = chain,
            coin = coin,
        )
        token.save()
        return token


#ABIs
def getABI(contractAddress, chain):
    try:
        contract = Contract.objects.get(address=contractAddress, chain=chain)
        # print("loading ABI from db")
    except Contract.DoesNotExist:
        # print("downloading abi")
        api_key = os.environ.get(f"EXPLORER_APIKEY_{chain.symbol}")
        url = f"https://api.{chain.explorer}/api?module=contract&action=getabi&address={contractAddress}&apikey={api_key}"
        contract = Contract(address=contractAddress, chain=chain)
        contract.saveABI(requests.get(url).text)
        # assert False, 'yep'
        contract.save()
        # contract.refresh_from_db()
    return contract.getABI()

def loadContract(address, chain, web3):
    abi = getABI(address, chain)
    if abi == 'Contract source code not verified':
        return None
    contract = web3.eth.contract(address, abi=abi)
    try:
        newAddress = contract.functions.implementation().call()
        print(f"proxy for: {newAddress}")
        abi = getABI(newAddress, chain)
        if abi == 'Contract source code not verified':
            return None
        contract = web3.eth.contract(newAddress, abi=abi)
    except (ABIFunctionNotFound, ContractLogicError):
        try:
            # for eip1967 proxy contracts (see https://eips.ethereum.org/EIPS/eip-1967)
            implementationSlot = web3.to_hex(web3.to_int(web3.keccak(text='eip1967.proxy.implementation')) - 1)
            beaconSlot = web3.to_hex(web3.to_int(web3.keccak(text='eip1967.proxy.beacon')) - 1)
            implementation = web3.eth.get_storage_at(address, implementationSlot)
            beacon = web3.eth.get_storage_at(address, beaconSlot)
            if web3.to_int(implementation):
                # remove leading zeros
                # newAddress = web3.to_hex(web3.to_int(implementation))
                newAddress = web3.to_checksum_address(web3.to_hex(web3.to_int(implementation)))
                print(f"proxy for: {newAddress}")
                abi = getABI(newAddress, chain)
                if abi == 'Contract source code not verified':
                    return None
                contract = web3.eth.contract(newAddress, abi=abi)
            if web3.to_int(beacon):
                # remove leading zeros
                beaconAddress = web3.to_hex(web3.to_int(beacon))
                print(f"beacon at: {beaconAddress}")
                beaconAbi = getABI(beaconAddress, chain)
                if beaconAbi == 'Contract source code not verified':
                    return None
                beaconContract = web3.eth.contract(beaconAddress, abi=beaconAbi)
                assert False, "beacon"
        except:
            raise
    return contract

def decodeInput(tx):
    web3 = getWeb3(tx.chain)
    contract = loadContract(tx.toAddr.address, tx.chain, web3)
    if not contract:
        return None
    txDetails = getTx(tx)
    try:
        decoded = contract.decode_function_input(txDetails.input)
        return decoded
    except ValueError:
        return None

def decodeLog(tx, logIndex, web3=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    # receipt = getTxReceipt(tx)
    receipt = web3.eth.get_transaction_receipt(tx.hash)
    for log in receipt['logs']:
        if not log['logIndex'] == logIndex:
            continue
        contract = loadContract(log['address'], tx.chain, web3)
        if not contract:
            print("no abi")
            return
        receipt_event_signature_hex = web3.to_hex(log["topics"][0])
        abi_events = [a for a in contract.abi if a["type"] == "event"]
        # Determine which event in ABI matches the transaction log you are decoding
        for event in abi_events:
            # print(f"trying {event['name']}")
            # or get it from web3
            eventABI = contract.events[event["name"]]()
            event_signature = event_abi_to_log_topic(eventABI.abi)

            if web3.to_hex(event_signature) == receipt_event_signature_hex:

            # Find match between log's event signature and ABI's event signature
            # if event_signature_hex == receipt_event_signature_hex:
                # Decode matching log
                for decoded_logs in contract.events[event["name"]]().process_receipt(receipt):
                    if decoded_logs.logIndex == logIndex:
                        return decoded_logs
                    
        print(f"index {logIndex} event not decoded")
        return
    
def decodeLogs(tx, web3=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    # receipt = getTxReceipt(tx)
    receipt = web3.eth.get_transaction_receipt(tx.hash)
    decoded_logs_out = []
    for log in receipt['logs']:
        found = False
        log_index = log['logIndex']
        contract = loadContract(log['address'], tx.chain, web3)
        if not contract:
            print("no abi")
            continue
        receipt_event_signature_hex = web3.to_hex(log["topics"][0])
        abi_events = [a for a in contract.abi if a["type"] == "event"]
        # Determine which event in ABI matches the transaction log you are decoding
        for event in abi_events:
            # print(f"trying {event['name']}")
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
                        found = True
                        break
            if found:
                break
        if not found:
            print(f"index {log_index} event not decoded")
    return decoded_logs_out

def checkForTransfers(tx):
    tokens = []
    decoded = decodeLogs(tx)
    for log in decoded:
        if log.event in ["Transfer", "LogTransfer"]:
            try:
                if tx.fromAddr.address == log.args['to']:
                    tokens.append(json.dumps({"address": log.address, "chainId": tx.chain.id}))
                    print("somethin")
            except KeyError:
                pass
            try:
                if tx.fromAddr.address == log.args['from']:
                    tokens.append(json.dumps({"address": log.address, "chainId": tx.chain.id}))
                    print("somethin")
            except KeyError:
                pass
    return tokens

def getContractName(address, chain, web3=None, contract=None):
    if web3 is None:
        web3 = getWeb3(chain)
    if contract is None:
        contract = loadContract(address, chain, web3)
        if not contract:
            return None
    try:
        name =  contract.functions.name().call()
    except ABIFunctionNotFound:
        name = None
    return name

def getContractSymbol(address, chain, web3=None, contract=None):
    if web3 is None:
        web3 = getWeb3(chain)
    if contract is None:
        contract = loadContract(address, chain, web3)
    try:
        symbol =  contract.functions.symbol().call()
    except ABIFunctionNotFound:
        symbol = None
    return symbol



def getTxValue(tx, web3=None):
    if web3 is None:
        web3 = getWeb3(tx.chain)
    return web3.from_wei(web3.eth.get_transaction(tx.hash).value, 'ether')

def getTxTo(tx):
    web3 = getWeb3(tx.chain)
    return getTx(tx).to

def getTx(tx):
    web3 = getWeb3(tx.chain)
    return web3.eth.get_transaction(tx.hash)




def getTxRecipt(tx):
    web3 = getWeb3(tx.chain)
    # receipt = getTxReceipt(tx)
    return web3.eth.get_transaction_receipt(tx.hash)


def checkITXDates():
    for chain in Chain.objects.all():
        web3 = getWeb3(chain)
        for itx in TokenTransfer.objects.filter(transaction__chain=chain):
            tx = itx.transaction
            txInfo = web3.eth.get_transaction(tx.hash)
            timestamp = web3.eth.get_block(txInfo.blockHash).timestamp
            dReal = datetime.datetime.fromtimestamp(timestamp).replace(tzinfo=ZoneInfo('UTC'))
            if not dReal == tx.date:
                print(dReal - tx.date)
            else:
                print("ok")


def checkTxDates():
    for chain in Chain.objects.all():
        web3 = getWeb3(chain)
        wrong = 0
        nope = 0
        for tx in Transaction.objects.filter(chain=chain, fromAddr__user__isnull=False)[:1]:
            try:
                txInfo = web3.eth.get_transaction(tx.hash)
                timestamp = web3.eth.get_block(txInfo.blockHash).timestamp
            except:
                nope += 1
                raise
            dReal = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo('UTC'))
            if not dReal == tx.date:
                # print(dReal - tx.date)
                # print(tx.explorerUrl())
                print(tx.date)
                print(dReal)
                print(tx.hash)
                print(timestamp)
                wrong += 1
            else:
                print("ok")
        print(f"{wrong} wrong dates")
        print(f"{nope} nopes")

def theBigDateFix():
    #search all transactions, check the date. If it's wrong, fix the date. then
    #find all associated entries with a date:
    # - Buy, Sale, Income, Spend
    # -- 

    #or just delete everything and do it again from scratch?
    # will deleting the user delete everything?
    # Pretty sure that yes.
    # Dump the db
    # delete the stardust user
    # recreate it
    # import all the exchange data
    # Import the transactions
    # import the internalTransactions
    # import TokenTransfers
    # get transaction fees
    # create fee spends
    pass