from taxApp.models import *
from taxApp.importScripts.onchainTransactions import *

def run():
    with open('updatedVals.txt', 'w') as f:
        for tx in Transaction.objects.filter(toAddr__id= 1402, value__isnull=False).exclude(value=Decimal(0)):
            savedVal = tx.value
            calcVal = getTxValue(tx)
            print(f"saved {savedVal}, calc {calcVal}")
            diff = abs(savedVal - calcVal)
            relDiff = diff/savedVal
            if relDiff > 0.1:
                tx.value = calcVal
                tx.save()
                print(f"{tx.id} updated")
                f.write(f"{tx.id},\n")
