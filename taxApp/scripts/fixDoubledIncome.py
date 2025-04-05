from taxApp.models import *

def run():
    txs = Transaction.objects.all()
    mult = [t for t in txs if t.income_set.count() > 1]
    for m in mult:
        print(m)
        print(m.income_set.count())
        # for i in m.income_set.values():
        #     print(i)
        seen = []
        for i in m.income_set.all():
            deleted = False
            for s in seen:
                if s.coin == i.coin and s.units == i.units and s.amount == i.amount:
                    print(f"deleting {i}")
                    if i.costBasis:
                        i.costBasis.delete()
                    i.delete()
                    deleted = True
                    break
            if not deleted:
                seen.append(i)
        print()
    print("done")