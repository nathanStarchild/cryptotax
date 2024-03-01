from taxApp.models import Coin
from django.db import transaction
import csv

def run():
    with open('CoinGecko Token API List.csv', 'r') as f:
        reader = csv.DictReader(f)
        with transaction.atomic():
            for row in reader:
                print(row)
                c = Coin(
                    name=row["Name"],
                    symbol=row["Symbol"],
                    coingecko_id=row["Id (API id)"]
                )
                c.save()