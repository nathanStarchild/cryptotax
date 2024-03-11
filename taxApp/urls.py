from django.urls import path, include
# from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('user/addresses', views.addresses, name='addresses'),
    path('ajax/user/addresses/new', views.ajaxNewAddress, name='ajaxNewAddress'),
    path('import/exchange', views.importExchangeTrades, name='importExchange'),
    path('import/transactions', views.importTransactions, name='importTransactions'),
    path('import/tokens', views.importTokens, name='importTokens'),
    path('ajax/tokens/new', views.ajaxNewToken, name='ajaxNewToken'),
    path('import/testAutocomplete', views.testAutocomplete, name='testAutocomplete'),
    path('ajax/import/transactions', views.ajaxImportTransactions, name='ajaxImportTransactions'),
    path('ajax/import/incomingTransactions', views.ajaxImportIncomingTransactions, name='ajaxImportIncomingTransactions'),
    path('ajax/import/incomingInternalTransactions', views.ajaxImportIncomingInternal, name='ajaxImportIncomingInternal'),
    path('ajax/import/tokenTransfer', views.ajaxImportTokenTransfers, name='ajaxImportTokenTransfers'),
    path('ajax/import/transactions/tos', views.ajaxImportTxTos, name='ajaxImportTxTos'),
    path('ajax/import/transactions/fees', views.ajaxImportTxFees, name='ajaxImportTxFees'),
    path('ajax/import/transactions/values', views.ajaxImportTxValues, name='ajaxImportTxValues'),
    path('ajax/import/transactions/fees/spends', views.ajaxTxFeeSpends, name='ajaxTxFeeSpends'),
    path('ajax/import/transactions/fees/poll', views.ajaxPollTxFees, name='ajaxPollTxFees'),
    path('ajax/process/transactions/approvals', views.ajaxProcessApprovals, name='ajaxProcessApprovals'),
    path('ajax/process/transactions/dexTrades', views.ajaxProcessDexTrades, name='ajaxProcessDexTrades'),
    path('ajax/process/transactions/dexTrades/oops', views.ajaxProcessDexOops, name='ajaxProcessDexOops'),
    path('ajax/process/transactions/depositsAndSends', views.ajaxProcessDepositsAndSends, name='ajaxProcessDepositsAndSends'),
    path('ajax/process/transactions/<txId>/bridgeSend', views.ajaxProcessBridgeSend, name='ajaxProcessBridgeSend'),
    path('reports/buys', views.buysReport, name='buysReport'),
    path('reports/transactions', views.transactionsReport, name='transactionsReport'),
    path('reports/transactions/<txId>', views.viewTransaction, name='viewTransaction'),
    path('reports/transactions/<txId>/nextUnprocessed/<direction>', views.nextUnprocessed, name='nextUnprocessed'),
    path('reports/sales', views.salesReport, name='salesReport'),
    path('reports/withdrawals', views.withdrawalsReport, name='withdrawalsReport'),
    path('reports/tokens', views.tokensReport, name='tokensReport'),
    path('reports/holdings', views.holdingsReport, name='holdingsReport'),
    path('ajax/withdrawals/<wId>/received', views.ajaxAddWithdrawalReceived, name='ajaxAddWithdrawalReceived'),
    path('ajax/coins/search/', views.ajaxSearchCoins, name='ajaxSearchCoins'),
    
] #+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)