from taxApp.models import *

def run():
    ttxs = TokenTransfer.objects.all()
    saves = set()
    for ttx in ttxs:
        dupes = TokenTransfer.objects.filter(
            transaction = ttx.transaction,
            fromAddr = ttx.fromAddr,
            toAddr = ttx.toAddr,
            value = ttx.value,
            token = ttx.token,
        ).order_by('id')
        saves.add(dupes.first().id)
    dels = ttxs.exclude(id__in=saves)
    dels.delete()
    print("done")