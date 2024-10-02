from django.shortcuts import render, resolve_url, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Q, OuterRef, Subquery, Prefetch, Value, Case, When, ExpressionWrapper, Func
from django.db.models import DecimalField, FloatField, BooleanField, CharField
from django.db.models.functions import Coalesce, Greatest, Least, Concat, Substr, LPad

import threading
import traceback
from io import StringIO

from .forms import *
from taxApp.importScripts.exchangeTrades import *
from taxApp.importScripts.onchainTransactions import *
from taxApp.taxScripts.cgt import createCGTEntries, calculateCGT, rollbackCGT
from taxApp.taxScripts.reporting import getData, totalHoldings
from taxApp.utils import getPrice, savePrice

# Create your views here.
def index(request):
    try:
        user = request.user.cryptoTaxUser
        name = user.name
    except:
        user = request.user
        name = None
        
    # print(reverse('/static/js/nuggetApp.js'))
    context = {
        "name":  name,
        "message": "",
        # "authorities": [p.auth for p in user.permissions.all()],
        "user": user,
        # "has_tmadm": has_permission(["tmadm"], user)
    }
    return render(request, 'taxApp/index.html', context)

#user

@login_required
def addresses(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser

    addresses = user.address_set.all()

    return render(request, 'user/addresses.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        'addresses': addresses
    })

@login_required()
def ajaxNewAddress(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        if request.method == "POST":
            form = newAddressForm(request.POST)

            ok = True
            errors = None
            newAddress = None
            if form.is_valid():
                n = form.save()
                #update the date format
                newAddress = n.address
                msg = "New address created successfully."
            else:
                errors = form.errors.as_json()
                msg = "Details not updated."

            return JsonResponse({
                'ok': ok,
                'msg': msg,
                'errors': errors,
                'newAddress': newAddress,
            })
        return JsonResponse({"ok": ok, "msg": "a messssage"})
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})


#imports

@login_required
def importExchangeTrades(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser

    if request.method == 'POST':
        form = UploadExchangeForm(request.POST, request.FILES)
        if form.is_valid():
            source = form.cleaned_data["source"]
            if source == "BTCMarkets":
                importBtcMarkets(request.FILES['file'], user) 
            elif source == "binanceTrades":
                importBinanceTrades(request.FILES['file'], user)
            elif source == "binanceAll":
                importBinanceAll(request.FILES['file'], user)
            elif source == "swyftx":
                importSwyftx(request.FILES['file'], user)
            elif source == "swyftxAUD":
                importSwyftxAUD(request.FILES['file'], user)
    else:
        form = UploadExchangeForm()
    return render(request, 'import/exchange.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        'form': form
    })

@login_required
def importTransactions(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    feesRunning = False
    if "txFees status" in request.session:
        feesRunning = request.session['txFees status'] == "running"
        msg = "txFees is running"

    if request.method == "POST":
        current = Transaction.objects.get(pk=request.POST['current'])
        if 'next' in request.POST:
            tx = Transaction.objects.filter(
                fromAddr__user=user,
                date__gte=current.date, 
                processed=False
            ).exclude(pk=current.id).order_by('-date').first()
            direction = "new"
        elif 'prev' in request.POST:
            tx = Transaction.objects.filter(
                fromAddr__user=user,
                date__lte=current.date, 
                processed=False
            ).exclude(pk=current.id).order_by('date').first()
            direction = "old"

        if not new:
            tx = current
            msg = f"Already at {direction}est transaction"
    else:
        tx = Transaction.objects.filter(fromAddr__user=user, processed=False).order_by('date').first()

    unprocessed = Transaction.objects.filter(fromAddr__user=user, processed=False).count()

            

    return render(request, 'import/transactions.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "running": feesRunning,
        "unprocessed": unprocessed,
    })

@login_required
def ajaxImportTransactions(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        saved = 0
        for addr in user.address_set.all():
            for ch in Chain.objects.all():
                print(f"{ch.name} transactions for {addr.address}")
                saved += saveTxHashes(addr, ch)
        msg = f"{saved} new transactions saved"

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportIncomingTransactions(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        saved = 0
        for addr in user.address_set.all():
            for ch in Chain.objects.all():
                print(f"{ch.name} transactions for {addr.address}")
                saved += saveIncomingTxs(addr, ch)
                # saveIncomingTxs(addr, ch)
        msg = f"{saved} new transactions saved"

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportIncomingInternal(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        saved = 0
        for addr in user.address_set.all():
            for ch in Chain.objects.all():
                print(f"{ch.name} transactions for {addr.address}")
                saved += saveIncomingInternalTxs(addr, ch)
                # saveIncomingTxs(addr, ch)
        msg = f"{saved} new transactions saved"

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportTokenTransfers(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        saved = 0
        for addr in user.address_set.all():
            for ch in Chain.objects.all():
                print(f"{ch.name} transactions for {addr.address}")
                saved += saveIncomingTokenTransfers(addr, ch)
                saved += saveOutgoingTokenTransfers(addr, ch)
                # saveIncomingTxs(addr, ch)
        msg = f"{saved} new transactions saved"

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportTxFees(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, fee__isnull=True)

        sessionKey = request.session.session_key
        task = threading.Thread(target=saveTxFees, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "txFees is running"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxTxFeeSpends(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, feeAUD__isnull=True).exclude(fee__isnull=True)

        sessionKey = request.session.session_key
        task = threading.Thread(target=saveTxFeeSpends, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "txFees is running"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportTxTos(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, to__isnull=True)

        sessionKey = request.session.session_key
        task = threading.Thread(target=saveTxTos, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "txFees is running"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxImportTxValues(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, value__isnull=True)

        sessionKey = request.session.session_key
        task = threading.Thread(target=saveTxValues, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "txValues is running"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required()
def ajaxPollTxFees(request):
    try:
        msg = request.session.pop('msg', '')
        user = request.user.cryptoTaxUser

        status = request.session["txFees status"]
        progress = request.session["txFees progress"]
        msg = request.session["txFees msg"]
        if status == "complete":
            del request.session["txFees status"]
            del request.session["txFees progress"]
            del request.session["txFees msg"]
        return JsonResponse({"ok": True, "msg": msg, "status": status, "progress": progress})

    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def ajaxProcessApprovals(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, processed=False)

        sessionKey = request.session.session_key
        task = threading.Thread(target=processApprovals, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "processing approvals"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessDexTrades(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, processed=False)

        sessionKey = request.session.session_key
        task = threading.Thread(target=processDexTrades, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "processing dex trades"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessDepositsAndSends(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        txs = Transaction.objects.filter(fromAddr__user=user, processed=False)

        sessionKey = request.session.session_key
        task = threading.Thread(target=processDepositsAndSends, args=(txs, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "processing deposits and sends"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def ajaxProcessDexOops(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        buys = Buy.objects.filter(user=user, note__startswith="Dex")
        sales = Sale.objects.filter(user=user, note__startswith="Dex")

        sessionKey = request.session.session_key
        task = threading.Thread(target=processDexOops, args=(buys, sales, sessionKey), daemon=True)
        task.start()
        request.session["txFees status"] = "running"
        request.session["txFees progress"] = 0
        msg = "processing dex trades"
        request.session["txFees msg"] = msg

        return JsonResponse({
            'ok': True,
            'msg': msg,
            'running': True,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def ajaxProcessBridgeSend(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        msg = processBridgeSend(tx)

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessVaultDeposit(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        msg = processVaultDeposit(tx)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessVaultIncome(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        msg = processVaultIncome(tx)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessVaultWithdrawal(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        msg = processVaultWithdrawal(tx)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessVaultRestake(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        msg = processVaultRestake(tx)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def ajaxProcessVaultMigrate(request, txId):
    try:
        assert request.method == "POST", "POST requests only"
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        web3 = getWeb3(tx.chain)
        amount = request.POST['amount']
        coin = Coin.objects.get(pk=request.POST['coin'])
        if request.POST['denomination'] == "wei":
            amount = web3.from_wei(int(amount), 'ether')
        oldAddress = web3.to_checksum_address(request.POST['oldAddress'])
        newAddress = web3.to_checksum_address(request.POST['newAddress'])
        # msg = f"{coin.name}"
        msg = processVaultWithdrawal(tx, amount=amount, coin=coin, address=oldAddress)
        msg += processVaultDeposit(tx, amount=amount, coin=coin, address=newAddress)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxProcessVaultWithdrawAndTrade(request, txId):
    try:
        assert request.method == "POST", "POST requests only"
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        web3 = getWeb3(tx.chain)
        withdrawAmount = Decimal(request.POST['withdrawAmount'])
        if request.POST['withdrawDenomination'] == "wei":
            withdrawAmount = web3.from_wei(withdrawAmount, 'ether')
        withdrawCoin = Coin.objects.get(pk=request.POST['withdrawCoin'])
        receiveAmount = Decimal(request.POST['receiveAmount'])
        if request.POST['receiveDenomination'] == "wei":
            receiveAmount = web3.from_wei(receiveAmount, 'ether')
        receiveCoin = Coin.objects.get(pk=request.POST['receiveCoin'])
        address = web3.to_checksum_address(request.POST['address'])
        # msg = f"{coin.name}"
        msg = processVaultWithdrawal(tx, amount=withdrawAmount, coin=withdrawCoin, address=address)
        sold = {
            'coin': withdrawCoin,
            'amount': withdrawAmount,
            'priceAUD': getPrice(withdrawCoin, tx.date)
        }
        bought = {
            'coin': receiveCoin,
            'amount': receiveAmount,
            'priceAUD': sold['priceAUD'] * sold['amount'] / receiveAmount
        }
        msg += processDexTrade(tx, bought=bought, sold=sold)
        tx.processed = True
        tx.save()

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxMarkAsProcessed(request, txId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        tx = Transaction.objects.get(pk=txId)
        tx.processed = True
        tx.save()
        msg = "Transaction marked as Processed"

        return JsonResponse({
            'ok': True,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def testAutocomplete(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    data = [1, 2, 3]

    return render(request, 'import/testAutocomplete.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": data,
    })

@login_required
def importTokens(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    transactions = Transaction.objects.filter(fromAddr__user=user, processed=False).order_by('date')
    tokens = set()
    for tx in transactions:
        tokens |= set(checkForTransfers(tx))
    known = []
    new = []
    for tokenString in tokens:
        token = json.loads(tokenString)
        chain = Chain.objects.get(pk=token['chainId'])
        try:
            tk = Token.objects.get(address=token['address'], chain=chain)
            known.append(tk)
        except Token.DoesNotExist:
            token['name'] = getContractName(token['address'], chain)
            token['chain'] = chain
            new.append(token)

    return render(request, 'import/tokens.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "known": known,
        "new": new,
    })

@login_required()
def ajaxNewToken(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        if request.method == "POST":
            form = newTokenForm(request.POST)

            ok = True
            errors = None
            newToken = None
            if form.is_valid():
                n = form.save()
                msg = "New token created successfully."
            else:
                errors = form.errors.as_json()
                msg = "Details not updated."

            return JsonResponse({
                'ok': ok,
                'msg': msg,
                'errors': errors,
            })
        return JsonResponse({"ok": ok, "msg": "a messssage"})
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})


#reports

@login_required
def buysReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    buys = Buy.objects.filter(user=user).order_by('-date')
    print(buys.values())
    return render(request, 'reports/buys.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": buys
    })

@login_required
def transactionsReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    transactions = Transaction.objects.filter(fromAddr__user=user).order_by('-date')
    return render(request, 'reports/transactions.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": transactions
    })

@login_required
def viewTransaction(request, txId):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    transaction = Transaction.objects.get(pk=txId)
    logs = decodeLogs(transaction)
    # txValue = Decimal(getTxValue(transaction)) * Decimal('1E-18')
    receipt = getTxReceipt(transaction)
    tx = getTx(transaction)
    inputs = decodeInput(transaction)
    # incoming, outgoing = getTransfersInOut(transaction, decodedLogs=logs)
    # print(logs[0])
    # print(logs[0][0].event)
    return render(request, 'reports/viewTransaction.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "tx": transaction,
        "logs": logs,
        # "txValue": txValue,
        "receipt": receipt,
        "txDetails": tx,
        "inputs": inputs,
        # "incoming": incoming,
        # "outgoing": outgoing,
    })

@login_required
def nextUnprocessed(request, txId, direction):
    #towards newer
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    current = Transaction.objects.get(pk=txId)
    tx = None
    if direction == "new":
        tx = Transaction.objects.filter(
            date__gte=current.date,
            fromAddr__user=user,
            processed=False,
        ).exclude(pk=current.id).order_by('date').first()
    elif direction == "old":
        tx = Transaction.objects.filter(
            date__lte=current.date,
            fromAddr__user=user,
            processed=False,
        ).exclude(pk=current.id).order_by('-date').first()
    if not tx:
        tx = current
        request.session['msg'] = f"No {direction}er unprocessed transactions"
    return redirect('viewTransaction', txId=tx.id)

@login_required
def salesReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    sales = Sale.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/sales.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": sales
    })

@login_required
def spendsReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    spends = Spend.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/spends.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": spends
    })

@login_required
def bridgesReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    bridges = TokenBridge.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/bridges.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": bridges
    })

@login_required
def withdrawalsReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    withdrawals = ExchangeWithdrawal.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/withdrawals.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": withdrawals
    })

@login_required()
def ajaxAddWithdrawalReceived(request, wId):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        if request.method == "POST":
            withdrawal = ExchangeWithdrawal.objects.get(pk=wId)

            ok = True
            received = Decimal(request.POST['received'])
            withdrawal.unitsReceived = received
            withdrawal.save()
            withdrawal.refresh_from_db()
            if not withdrawal.feeAUD:
                withdrawal.calculateFee()
            msg = "withdrawal details updated"

            return JsonResponse({
                'ok': ok,
                'msg': msg,
            })
        return JsonResponse({"ok": ok, "msg": "a messssage"})
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def tokensReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    tokens = Token.objects.all()
    return render(request, 'reports/tokens.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": tokens
    })

@login_required
def vaultsReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    vaults = Vault.objects.all().order_by('chain')
    deposits = VaultDeposit.objects.filter(user=user, vault=OuterRef('pk')).values('vault')
    deposits = deposits.annotate(deposits=Sum('amount')).order_by().values('deposits')
    withdrawals = VaultWithdrawal.objects.filter(user=user, vault=OuterRef('pk')).values('vault')
    withdrawals = withdrawals.annotate(withdrawals=Sum('amount')).order_by().values('withdrawals')
    incomes = VaultIncome.objects.filter(user=user, vault=OuterRef('pk')).values('vault')
    income = incomes.annotate(units=Sum('amount')).order_by().values('units')
    incomeAUD = incomes.annotate(AUD=Sum('income__amount')).order_by().values('AUD')
    coin = VaultDeposit.objects.filter(user=user, vault=OuterRef('pk')).values('coin__symbol')
    vaults = vaults.annotate(
        deposits=Coalesce(Subquery(deposits), Decimal(0)), 
        withdrawals=Coalesce(Subquery(withdrawals), Decimal(0)),
        income=Coalesce(Subquery(income), Decimal(0)),
        incomeAUD=Coalesce(Subquery(incomeAUD), Decimal(0)),
        coin=Subquery(coin[:1]),
    ).annotate(balance=F('deposits') - F('withdrawals'))
    for v in vaults.values():
        print(v)
    return render(request, 'reports/vaults.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": vaults,
    })


@login_required
def cgtReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    data = CGTEvent.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/cgt.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": data
    })

@login_required
def holdingsReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    coins = Coin.objects.filter(buy__user=user).distinct()
    print(coins.count())
    buys = Buy.objects.filter(user=user, coin=OuterRef('pk')).values('coin').annotate(bought=Sum('units')).order_by().values('bought')
    sales = Sale.objects.filter(user=user, coin=OuterRef('pk')).values('coin').annotate(sold=Sum('units')).order_by().values('sold')
    incomes = Income.objects.filter(user=user, coin=OuterRef('pk')).values('coin').annotate(incame=Sum('units')).order_by().values('incame')
    spends = Spend.objects.filter(user=user, coin=OuterRef('pk')).values('coin').annotate(spent=Sum('units')).order_by().values('spent')
    coins = coins.annotate(
        bought=Coalesce(Subquery(buys), Decimal(0)), 
        sold=Coalesce(Subquery(sales), Decimal(0)),
        incame=Coalesce(Subquery(incomes), Decimal(0)),
        spent=Coalesce(Subquery(spends), Decimal(0))
    )
    coins = coins.annotate(holding=F('bought') + F('incame') - F('sold') - F('spent'))
    data = []
    for c in coins:
        price = getPrice(c, "now")
        dat = {
            'coin': c,
            'holding': c.holding,
            'price': price,
            'value': price * c.holding,
        }
        data.append(dat)
    data.sort(key=lambda d: -d['value'])
    total = sum([d['value'] for d in data])

    #calculate AUD spent
    balanceAUD = ExchangeAUDTransaction.objects.filter(user=user).aggregate(t = Sum('amount'))['t']
    depositsAUD = ExchangeAUDTransaction.objects.filter(
        user=user,
        note="Swyftx AUD deposit"
    ).aggregate(t = Sum('amount'))['t']

    spentAUD = depositsAUD - balanceAUD

    return render(request, 'reports/holdings.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": data,
        "total": total,
        'spentAUD': spentAUD,
    })


@login_required
def audReport(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    data = ExchangeAUDTransaction.objects.filter(user=user).order_by('-date')
    # print(buys.values())
    return render(request, 'reports/aud.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": data
    })

#Tax

@login_required
def taxProcessing(request):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser

    return render(request, 'tax/processing.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
    })

@login_required
def ajaxGetCGTEvents(request, year):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        year = int(year)
        saved = createCGTEntries(year, user)
        msg = f"{saved} new CGT events saved"

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})
    
@login_required
def ajaxCalculateCGT(request, year):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = request.session.pop('msg', '')
        ok = False
        year = int(year)
        rollbackCGT(year, user)
        fifo = calculateCGT(year, user, "FIFO")
        rollbackCGT(year, user)
        lifo = calculateCGT(year, user, "LIFO")
        rollbackCGT(year, user)
        if (fifo < lifo):
            cg = calculateCGT(year, user, "FIFO")
            method = "FIFO"
        else:
            cg = calculateCGT(year, user, "LIFO")
            method = "LIFO"

        msg = f"Total capital gains: {cg} (LIFO: {lifo}, FIFO: {fifo}) "

        return JsonResponse({
            'ok': ok,
            'msg': msg,
        })
    except Exception as e:
        print(traceback.format_exc())
        print(e)
        return JsonResponse({"ok":False, "msg":traceback.format_exc()})

@login_required
def taxReportCsv(request, year):
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    #data: a list of dictionaries
    #order: a list of strings (matching the keys of the dicts)
    #filename: The name the file will be given (including extension)

    #create a file-like buffer to store the file
    buffer = StringIO()
    # c = Coin.objects.get(symbol="eth") 
    coins = Coin.objects.filter(buy__user=user).distinct().order_by('symbol')
    for c in coins:
        getData(c, int(year), user, buffer)
    filename = f"SAI Crypto Tax FY {year}.csv"
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    buffer.close()
    return response

@login_required
def financialYearSummary(request, year):
    year = int(year)
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('Australia/Sydney'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('Australia/Sydney'))
    earliestDate = Buy.objects.filter(user=user).order_by("date").first().date
    prevYearsDate = [datetime.date(year-i, 6, 30) for i in [0, 1]]

    #create a file-like buffer to store the file
    buffer = StringIO()
    writer = csv.writer(buffer)
    holdingsClosing, totalClosing = totalHoldings(endDate, user)
    holdingsOpening, totalOpening = totalHoldings(startDate, user)

    holdings = [{
        "coin": d["coin"],
        "openingBalance": 0,
        "closingBalance": d["holding"],
        "openingValue": 0,
        "closingValue": d["value"],
        }
        for d in holdingsClosing
    ]

    for d in holdingsOpening:
        for dd in holdings:
            if d["coin"] == dd["coin"]:
                dd["openingBalance"] = d["holding"]
                dd["openingValue"] = d["value"]
                break
        else:
            holdings.append({
                "coin": d["coin"],
                "openingBalance": d["holding"],
                "closingBalance": 0,
                "openingValue": d["value"],
                "closingValue": 0,
                })

    audBalanceClosing = ExchangeAUDTransaction.objects.filter(
        user = user,
        date__lte = endDate,
    ).aggregate(t = Sum('amount'))['t']

    audBalanceOpening = ExchangeAUDTransaction.objects.filter(
        user = user,
        date__lte = startDate,
    ).aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']

    writer.writerows([
        ["Financial Year Summary"],
        [f"{startDate.strftime('%d/%m/%Y')} - {endDate.strftime('%d/%m/%Y')}"],
        [""],
        ["Portfolio Valuation", "Opening", "Closing"],
        ["Total Crypto Assets", f"{totalOpening:.2f}", f"{totalClosing:.2f}"],
        ["Total AUD Balance", f"{audBalanceOpening:.2f}", f"{audBalanceClosing:.2f}"],
        ["Total", f"{totalOpening + audBalanceOpening:.2f}", f"{totalClosing + audBalanceClosing:.2f}"],
        [""],
        [f"Allocation as at {endDate.strftime('%d/%m/%Y')}"],
        ["Asset", "Opening Units", "Opening Value AUD", " Opening %", "Closing Units", "Closing Value AUD", " Closing %"]
    ])
    writer.writerows([
        [
            d['coin'].symbol, 
            f"{d['openingBalance']:.4f}", 
            f"{d['openingValue']:.2f}", 
            f"{(100*d['openingValue']/totalOpening if totalOpening else 0):.2f}",
            f"{d['closingBalance']:.4f}", 
            f"{d['closingValue']:.2f}", 
            f"{(100*d['closingValue']/totalClosing):.2f}",
        ]
        for d in holdings
    ])

    cgtTotal1yrPlus = 0
    cgtTotal1yrMinus = 0
    CGTevents = CGTEvent.objects.filter(user=user, date__gte=startDate, date__lte=endDate)
    for evt in CGTevents:
        for cb in evt.cgttocostbasis_set.all():
            if cb.discounted:
                cgtTotal1yrPlus += cb.gain
            else:
                cgtTotal1yrMinus += cb.gain
    # totalCGL = CGTevents.aggregate(total=Sum("gain"))['total']
    writer.writerows([
        [""],
        ["Total Capital Gains/Losses", f"{cgtTotal1yrPlus + cgtTotal1yrMinus:.2f}"],
        ["Assets held more than 1 year", f"{cgtTotal1yrPlus:.2f}"],
        ["Assets held less than 1 year", f"{cgtTotal1yrMinus:.2f}"],
    ])

    costs = CostBasis.objects.filter(user=user, date__lte=endDate)
    totalCost = 0
    #NOTE: This only works because we know CGT has only been calculated until the end date. This won't work if it's not the most recent 
    costOfRemaining = 0
    for cb in costs:
        if cb.sourceString().startswith("Purchase"):
            totalCost += cb.units * cb.unitPrice
            costOfRemaining += cb.remaining * cb.unitPrice

    proceeds = Sale.objects.filter(user=user, date__lte=endDate).aggregate(proceeds=Sum((F("units") * F("unitPrice")) - F("feeAUD")))['proceeds']



    writer.writerows([
        [""],
        ['Cost and Proceeds'],
        ['Total Cost of Purchases', f'{totalCost:.2f}'],
        ['Total Proceeds of Sales', f'{proceeds:.2f}'],
        [f"Cost of Cryptos held at {endDate.strftime('%d/%m/%Y')}", f'{costOfRemaining:.2f}']
    ])


    # r = ["Total Crypto Assets"]
    # holdings, total = totalHoldings(endDate, user)
    # r.append(f"${total:.2f}")
    # writer.writerow(["Total Crypto Assets", f"${total:.2f}"])
    # for d in prevYearsDate:
    #     if d < earliestDate:
    #         r.append("$0.00")
    #     else:
    #         _, t = totalHoldings(d, user)
    #         r.append(f"${t:.2f}")

    #Total income
    income = Income.objects.filter(user=user, date__gte=startDate, date__lte=endDate).aggregate(t = Sum('amount'))['t']
    writer.writerows([
        [""],
        ['Income'],
        ['Total Income', f'{income:.2f}']
    ])

    #fees
    swyftxBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Swyftx")
    binanceBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Binance")
    swyftxSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Swyftx")
    binanceSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Binance")

    swyftxSalesDistinct = []
    binanceSalesDistinct = []

    for s in swyftxSales:
        if not swyftxBuys.filter(date=s.date).exists():
            swyftxSalesDistinct.append(s.id)

    for s in binanceSales:
        if not binanceBuys.filter(date=s.date).exists():
            binanceSalesDistinct.append(s.id)

    swyftxSales = swyftxSales.filter(pk__in=swyftxSalesDistinct)
    binanceSales = binanceSales.filter(pk__in=binanceSalesDistinct)

    swyftxBuys = swyftxBuys.aggregate(t = Sum('feeAUD'))['t']
    binanceBuys = binanceBuys.aggregate(t = Sum('feeAUD'))['t']
    swyftxSales = swyftxSales.aggregate(t = Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']
    binanceSales = binanceSales.aggregate(t = Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']

    withdrawals = ExchangeWithdrawal.objects.filter(user=user, date__gte=startDate, date__lte=endDate)
    withdrawals = withdrawals.aggregate(t = Sum('feeAUD'))['t']

    transactionFees = Transaction.objects.filter(fromAddr__user=user, date__gte=startDate, date__lte=endDate)
    transactionFees = transactionFees.aggregate(t = Sum('feeAUD'))['t']

    writer.writerows([
        [""],
        ["Fees", f"{swyftxBuys + binanceBuys + swyftxSales + binanceSales + withdrawals + transactionFees:.2f}"],
        ["Centralised Exchange Brokerage Fees", f"{swyftxBuys + binanceBuys + swyftxSales + binanceSales:.2f}"],
        ["Centralised Exchange Withdrawal Fees", f"{withdrawals:.2f}"],
        ["Onchain Transaction Fees", f"{transactionFees:.2f}"]
    ])

    audTransactions = ExchangeAUDTransaction.objects.filter(
        user=user, 
        date__gte=startDate, 
        date__lte=endDate
    )

    audDeposits = audTransactions.filter(note__icontains="deposit").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audWithdrawals = audTransactions.filter(note__icontains="withdrawal").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audPurchases = audTransactions.filter(note__icontains="purchase").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audSales = audTransactions.filter(note__icontains="sell").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']

    writer.writerows([
        [""],
        ["AUD Transactions"],
        ["Deposits", f"{audDeposits:.2f}"],
        ["Withdrawals", f"{audWithdrawals:.2f}"],
        ["Crypto Purchases (incl Fees)", f"{audPurchases:.2f}"],
        ["Crypto Sales (incl Fees)", f"{audSales:.2f}"],

    ])

    filename = f"SAI Financial Year Summary {year}.csv"
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    buffer.close()
    return response


@login_required
def financialYearTotals(request, year):
    year = int(year)
    msg = request.session.pop('msg', '')
    user = request.user.cryptoTaxUser
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('Australia/Sydney'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('Australia/Sydney'))
    earliestDate = Buy.objects.filter(user=user).order_by("date").first().date
    prevYearsDate = [datetime.date(year-i, 6, 30) for i in [0, 1]]

    #create a file-like buffer to store the file
    buffer = StringIO()
    writer = csv.writer(buffer)

    audBalanceClosing = ExchangeAUDTransaction.objects.filter(
        user = user,
        date__lte = endDate,
    ).aggregate(t = Sum('amount'))['t']

    audBalanceOpening = ExchangeAUDTransaction.objects.filter(
        user = user,
        date__lte = startDate,
    ).aggregate(t = Sum('amount'))['t']

    writer.writerows([
        ["Financial Year Summary"],
        [f"{startDate.strftime('%d/%m/%Y')} - {endDate.strftime('%d/%m/%Y')}"],
        [""],
        # ["Portfolio Valuation"] + [f"value as at {d.strftime('%d/%m/%Y')}" for d in [endDate] + prevYearsDate],
        # ["Total Crypto Assets", f"{total:.2f}"],
        ["Opening AUD Balance", f"{audBalanceOpening:.2f}"],
        ["Closing AUD Balance", f"{audBalanceClosing:.2f}"],
        # ["Total", f"{total + audBalance:.2f}"],
        [""],
        # [f"Allocation as at {endDate.strftime('%d/%m/%Y')}"],
        # ["Asset", "Value", "%"]
    ])
    # writer.writerows([
    #     [d['coin'].symbol, f"{d['value']:.2f}", f"{(100*d['value']/total):.2f}"]
    #     for d in holdings
    # ])

    cgtTotal1yrPlus = 0
    cgtTotal1yrMinus = 0
    CGTevents = CGTEvent.objects.filter(user=user, date__gte=startDate, date__lte=endDate)
    for evt in CGTevents:
        for cb in evt.cgttocostbasis_set.all():
            if cb.discounted:
                cgtTotal1yrPlus += cb.gain
            else:
                cgtTotal1yrMinus += cb.gain
    # totalCGL = CGTevents.aggregate(total=Sum("gain"))['total']
    writer.writerows([
        [""],
        ["Total Capital Gains/Losses", f"{cgtTotal1yrPlus + cgtTotal1yrMinus:.2f}"],
        ["Assets held more than 1 year", f"{cgtTotal1yrPlus:.2f}"],
        ["Assets held less than 1 year", f"{cgtTotal1yrMinus:.2f}"],
    ])

    # r = ["Total Crypto Assets"]
    # holdings, total = totalHoldings(endDate, user)
    # r.append(f"${total:.2f}")
    # writer.writerow(["Total Crypto Assets", f"${total:.2f}"])
    # for d in prevYearsDate:
    #     if d < earliestDate:
    #         r.append("$0.00")
    #     else:
    #         _, t = totalHoldings(d, user)
    #         r.append(f"${t:.2f}")

    #Total income
    income = Income.objects.filter(user=user, date__gte=startDate, date__lte=endDate).aggregate(t = Sum('amount'))['t']
    writer.writerows([
        [""],
        ['Income'],
        ['Total Income', f'{income:.2f}']
    ])

    #fees
    swyftxBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Swyftx")
    binanceBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Binance")
    swyftxSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Swyftx")
    binanceSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=endDate, note__startswith = "Binance")

    swyftxSalesDistinct = []
    binanceSalesDistinct = []

    for s in swyftxSales:
        if not swyftxBuys.filter(date=s.date).exists():
            swyftxSalesDistinct.append(s.id)

    for s in binanceSales:
        if not binanceBuys.filter(date=s.date).exists():
            binanceSalesDistinct.append(s.id)

    swyftxSales = swyftxSales.filter(pk__in=swyftxSalesDistinct)
    binanceSales = binanceSales.filter(pk__in=binanceSalesDistinct)

    swyftxBuys = swyftxBuys.aggregate(t = Sum('feeAUD'))['t']
    binanceBuys = binanceBuys.aggregate(t = Sum('feeAUD'))['t']
    swyftxSales = swyftxSales.aggregate(t = Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']
    binanceSales = binanceSales.aggregate(t = Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']

    withdrawals = ExchangeWithdrawal.objects.filter(user=user, date__gte=startDate, date__lte=endDate)
    withdrawals = withdrawals.aggregate(t = Sum('feeAUD'))['t']

    transactionFees = Transaction.objects.filter(fromAddr__user=user, date__gte=startDate, date__lte=endDate)
    transactionFees = transactionFees.aggregate(t = Sum('feeAUD'))['t']

    writer.writerows([
        [""],
        ["Fees", f"{swyftxBuys + binanceBuys + swyftxSales + binanceSales + withdrawals + transactionFees:.2f}"],
        ["Centralised Exchange Brokerage Fees", f"{swyftxBuys + binanceBuys + swyftxSales + binanceSales:.2f}"],
        ["Centralised Exchange Withdrawal Fees", f"{withdrawals:.2f}"],
        ["Onchain Transaction Fees", f"{transactionFees:.2f}"]
    ])

    audTransactions = ExchangeAUDTransaction.objects.filter(
        user=user, 
        date__gte=startDate, 
        date__lte=endDate
    )

    audDeposits = audTransactions.filter(note__icontains="deposit").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audWithdrawals = audTransactions.filter(note__icontains="withdrawal").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audPurchases = audTransactions.filter(note__icontains="purchase").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']
    audSales = audTransactions.filter(note__icontains="sell").aggregate(t = Coalesce(Sum('amount'), Decimal(0.0)))['t']

    writer.writerows([
        [""],
        ["AUD Transactions"],
        ["Deposits", f"{audDeposits:.2f}"],
        ["Withdrawals", f"{audWithdrawals:.2f}"],
        ["Crypto Purchases (incl Fees)", f"{audPurchases:.2f}"],
        ["Crypto Sales (incl Fees)", f"{audSales:.2f}"],

    ])

    filename = f"SAI Financial Year Summary {year}.csv"
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    buffer.close()
    return response


#Utils

@login_required()
def ajaxSearchCoins(request):
    query = request.GET['q']
    # print (query)
    coins = Coin.objects.filter(name__icontains=query).values('id', 'name').order_by('id')
    results = [{'value': j['id'], 'text': f"{j['id']} - {j['name']}"} for j in coins]
    print(results)
    return JsonResponse(results, safe=False)