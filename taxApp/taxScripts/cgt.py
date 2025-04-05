from django.db.utils import IntegrityError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db import transaction

from taxApp.models import *

import datetime
from zoneinfo import ZoneInfo

def createCGTEntries(year, user):
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
    #all transactions processed
    transactions = Transaction.objects.filter(
        fromAddr__user=user, 
        date__range=[startDate, endDate],
        processed = False
        )
    assert not transactions.exists(), f"You have unprocessed transactions: {[t.id for t in transactions]}"
    #all vault incomes processed - not really, if the transaction is processed it should be
    #all exchange withdrawals processed
    withdrawals = ExchangeWithdrawal.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        processed = False
        )
    assert not withdrawals.exists(), f"You have unprocessed Exchange withdrawals: {[w.id for w in withdrawals]}"
    #all token bridges processed
    bridges = TokenBridge.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        processed = False
        )
    assert not bridges.exists(), f"You have unprocessed Token bridges: {[b.id for b in bridges]}"

    saved = 0
    sales = Sale.objects.filter(date__range=[startDate, endDate], user=user)
    for s in sales:
        c = CGTEvent(
            coin = s.coin,
            units = s.units,
            unitPrice = ((s.units * s.unitPrice) + s.feeAUD) / s.units,
            date = s.date,
            user = s.user,
            sale = s,
        ) 
        try:
            c.save()
            saved += 1
        except IntegrityError:
            print('already exists')

    spends = Spend.objects.filter(date__range=[startDate, endDate], user=user)
    for s in spends:
        c = CGTEvent(
            coin = s.coin,
            units = s.units,
            unitPrice = s.unitPrice,
            date = s.date,
            user = s.user,
            spend = s,
        ) 
        try:
            c.save()
            saved += 1
        except IntegrityError:
            print('already exists')
    return saved

def calculateCGT(year, user, method, applyLossesAndDiscount=False):
    with transaction.atomic():
        if method == "LIFO":
            order = "-date"
        elif method == "FIFO":
            order = "date"
        else:
            raise ValueError(f'Unrecognised CGT method {method}. Options are LIFO or FIFO')
        startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
        endDate = datetime.datetime(year+1, 6, 30)
        endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
        cgtEvents = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user)
        cgtEvents = cgtEvents.order_by('date')
        grandTotalGain = 0

        # Calculate all the cgt events
        for evt in cgtEvents:
            discountDate = evt.date.replace(year=evt.date.year-1)
            costBases = CostBasis.objects.filter(
                user = user,
                coin = evt.coin,
                date__lt = evt.date,
                remaining__gt=Decimal(0),
            ).order_by(order)
            totalConsumed = Decimal(0)
            totalGain = Decimal(0)
            for cb in costBases:
                consumed = min(evt.units - totalConsumed, cb.remaining)
                discountable = cb.date < discountDate
                gain = (evt.unitPrice - cb.unitPrice) * consumed
                # discount = Decimal(0.5) if discounted else Decimal(1)
                # if applyDiscount:
                #     gain = min(gain, gain * discount)
                c = CGTtoCostBasis(
                    cgtEvent = evt,
                    costBasis = cb,
                    consumed = consumed,
                    discountable = discountable,
                    grossGain = gain,
                )
                c.save()
                cb.remaining = cb.remaining - consumed
                cb.save()
                totalGain += gain
                totalConsumed += consumed
                if evt.units == totalConsumed:
                    break
            evt.gain = totalGain
            evt.method = method
            evt.save()
            grandTotalGain += totalGain
        
        if not applyLossesAndDiscount:
            print("not applying losses and discount")
            return grandTotalGain
        
        # categorise into losses and gains
        currYearGains = CGTtoCostBasis.objects.filter(
            cgtEvent__in = cgtEvents,
            grossGain__gte = Decimal(0)
        )
        totalCurrYearGains = currYearGains.aggregate(t=Coalesce(Sum('grossGain'), Decimal(0)))['t']
        currYearLosses = CGTtoCostBasis.objects.filter(
            cgtEvent__in = cgtEvents,
            grossGain__lt = Decimal(0)
        )
        totalCurrYearLosses = currYearLosses.aggregate(t=Coalesce(Sum('grossGain'), Decimal(0)))['t']
        lossesRemaining = -totalCurrYearLosses

        #subtract from non-discountable gains first
        for c in currYearGains.order_by('discountable'):
            consumed = min(c.grossGain, lossesRemaining)
            c.netGain = c.grossGain - consumed
            c.save()
            lossesRemaining -= consumed

        # claculate the net losses
        appliedLosses = -totalCurrYearLosses - lossesRemaining
        appliedLossesRemaining = appliedLosses
        for c in currYearLosses:
            consumed = min(-c.grossGain, appliedLossesRemaining)
            c.netGain = c.grossGain + consumed
            c.save()
            appliedLossesRemaining -= consumed

        # get losses from prior years
        priorLosses = CapitalGain.objects.filter(
            user = user,
            year__lt = year,
            gain__lt = Decimal(0),
            remaining__gt = Decimal(0)
        ).order_by('year')

        for loss in priorLosses:
            for c in currYearGains.filter(netGain__gt=Decimal(0)).order_by('discountable'):
                consumed = min(c.netGain, loss.remaining)
                c.netGain = c.netGain - consumed
                c.save()
                loss.remaining -= consumed
                loss.save()
                grandTotalGain -= consumed
                plc = PriorLossConsumption.objects.create(
                    cgtToCostBasis = c,
                    capitalGain = loss,
                    consumed = consumed
                )
                if loss.remaining == Decimal(0):
                    break

        # Apply discount
        for c in currYearGains.filter(netGain__gt=Decimal(0), discountable=True):
            c.netGain *= Decimal(0.5)
            grandTotalGain -= c.netGain
            c.save()

        # save the grand total gain
        CapitalGain.objects.create(
            user = user,
            year = year,
            gain = grandTotalGain,
            remaining = Decimal(0) if grandTotalGain > Decimal(0) else -grandTotalGain
        )

        print("losses and discount applied")
        
        return grandTotalGain

def rollbackCGT(year, user):
    with transaction.atomic():
        startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
        endDate = datetime.datetime(year+1, 6, 30)
        endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
        cgtEvents = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user)
        cgtEvents = cgtEvents.order_by('date')
        for evt in cgtEvents:
            for cb in evt.cgttocostbasis_set.all():
                cb.costBasis.remaining += cb.consumed
                cb.costBasis.save()
                for priorLoss in cb.priorlossconsumption_set.all():
                    priorLoss.capitalGain.remaining += priorLoss.consumed
                    priorLoss.capitalGain.save()
                cb.delete()
            evt.gain = None
            evt.method = None
            evt.save()
        try:
            CapitalGain.objects.get(user=user, year=year).delete()
        except CapitalGain.DoesNotExist:
            pass
        



