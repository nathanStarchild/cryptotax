from django.shortcuts import render, resolve_url, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Q, OuterRef, Subquery, Prefetch, Value, Case, When, ExpressionWrapper, Func
from django.db.models import DecimalField, FloatField, BooleanField, CharField
from django.db.models.functions import Coalesce, Greatest, Least, Concat, Substr, LPad

import threading
import traceback

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
    return render(request, 'reports/holdings.html', {
        "name":  user.name,
        "user": user,
        "message": msg,
        "data": data,
        "total": total,
    })

@login_required()
def ajaxSearchCoins(request):
    query = request.GET['q']
    # print (query)
    coins = Coin.objects.filter(name__icontains=query).values('id', 'name').order_by('id')
    results = [{'value': j['id'], 'text': f"{j['id']} - {j['name']}"} for j in coins]
    print(results)
    return JsonResponse(results, safe=False)