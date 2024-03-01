from django.shortcuts import render, resolve_url, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

import threading

from .forms import *
from taxApp.importScripts.exchangeTrades import *
from taxApp.importScripts.onchainTransactions import *
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
    msg = ""
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
        msg = ""
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
        print(str(e))
        return JsonResponse({"ok":False, "msg":str(e)})


#imports

@login_required
def importExchangeTrades(request):
    msg = ""
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
    msg = ""
    user = request.user.cryptoTaxUser
    feesRunning = False
    if "txFees status" in request.session:
        feesRunning = request.session['txFees status'] == "running"
        msg = "txFees is running"

    return render(request, 'import/transactions.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "running": feesRunning,
    })

@login_required
def ajaxImportTransactions(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = ""
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
        print(str(e))
        return JsonResponse({"ok":False, "msg":str(e)})
    
@login_required
def ajaxImportTxFees(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = ""
        ok = False
        txs = Transaction.objects.filter(address__user=user, fee__isnull=True)

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
        print(str(e))
        return JsonResponse({"ok":False, "msg":str(e)})
    
@login_required
def ajaxTxFeeSpends(request):
    try:
        user = request.user.cryptoTaxUser
        # if not has_permission(['wrlman', 'tmadm'], user):
        #     raise PermissionDenied
        msg = ""
        ok = False
        txs = Transaction.objects.filter(address__user=user, feeAUD__isnull=True).exclude(fee__isnull=True)

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
        print(str(e))
        return JsonResponse({"ok":False, "msg":str(e)})
    
@login_required()
def ajaxPollTxFees(request):
    try:
        msg = ""
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
        print(str(e))
        print(e)
        return JsonResponse({"ok":False, "msg":str(e)})


#reports

@login_required
def buysReport(request):
    msg = ""
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
    msg = ""
    user = request.user.cryptoTaxUser
    transactions = Transaction.objects.filter(address__user=user).order_by('-date')
    return render(request, 'reports/transactions.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": transactions
    })

@login_required
def viewTransaction(request, txId):
    msg = ""
    user = request.user.cryptoTaxUser
    transaction = Transaction.objects.get(pk=txId)
    receipt = getTxReceipt(transaction)
    logs = decodeLogs(transaction)
    txValue = Decimal(getTxValue(transaction)) * Decimal('1E-18')
    # print(logs[0])
    # print(logs[0][0].event)
    return render(request, 'reports/viewTransaction.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "tx": transaction,
        "receipt": receipt,
        "logs": logs,
        "txValue": txValue
    })


@login_required
def salesReport(request):
    msg = ""
    user = request.user.cryptoTaxUser
    sales = Sale.objects.filter(user=user).order_by('-date')
    return render(request, 'reports/sales.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": sales
    })

@login_required
def withdrawalsReport(request):
    msg = ""
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
        msg = ""
        ok = False
        if request.method == "POST":
            withdrawal = ExchangeWithdrawal.objects.get(pk=wId)

            ok = True
            received = Decimal(request.POST['received'])
            withdrawal.unitsReceived = received
            withdrawal.save()
            withdrawal.refresh_from_db()
            if not withdrawal.feeAUD:
                fee = withdrawal.unitsSent - withdrawal.unitsReceived
                feeCoin = withdrawal.coin
                price = getPrice(feeCoin, withdrawal.date)
                feeAUD = fee * price
                withdrawal.fee = fee
                withdrawal.feeCoin = feeCoin
                withdrawal.feeAUD = feeAUD
                withdrawal.save()
                withdrawal.refresh_from_db()
                withdrawal.createFeeSpend()
            msg = "withdrawal details updated"

            return JsonResponse({
                'ok': ok,
                'msg': msg,
            })
        return JsonResponse({"ok": ok, "msg": "a messssage"})
    except Exception as e:
        print(str(e))
        return JsonResponse({"ok":False, "msg":str(e)})
