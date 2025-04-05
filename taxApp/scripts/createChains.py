from taxApp.models import Chain, Coin

def run():
    eth = Coin.objects.get(symbol='eth')
    matic = Coin.objects.get(symbol='matic')
    chains = [
        {
            'name': 'Ethereum',
            'symbol': 'ETH_MAINNET',
            'endpoint': 'https://eth-mainnet.g.alchemy.com/v2/',
            'explorer': 'etherscan.io',
            'feeCoin': eth,
        },
        {
            'name': 'Polygon POS',
            'symbol': 'MATIC_MAINNET',
            'endpoint': 'https://polygon-mainnet.g.alchemy.com/v2/',
            'explorer': 'polygonscan.com',
            'feeCoin': matic,
        },
        {
            'name': 'ZKsync Era',
            'symbol': 'ZKSYNC_MAINNET',
            'endpoint': 'https://zksync-mainnet.g.alchemy.com/v2/',
            'explorer': 'explorer.zksync.io',
            'feeCoin': eth,
        },
        {
            'name': 'Optimism',
            'symbol': 'OPT_MAINNET',
            'endpoint': 'https://opt-mainnet.g.alchemy.com/v2/',
            'explorer': 'optimistic.etherscan.io',
            'feeCoin': eth,
        },
        {
            'name': 'Arbitrum One',
            'symbol': 'ARB_MAINNET',
            'endpoint': 'https://arb-mainnet.g.alchemy.com/v2/',
            'explorer': 'arbiscan.io',
            'feeCoin': eth,
        },
        {
            'name': 'Base',
            'symbol': 'BASE_MAINNET',
            'endpoint': 'https://base-mainnet.g.alchemy.com/v2/',
            'explorer': 'basescan.org',
            'feeCoin': eth,
        },

    ]

    for c in chains:
        chain, created = Chain.objects.get_or_create(**c)
        print(f"{'created' if created else 'already got'} {chain.name}")
    print("done")