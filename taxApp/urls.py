from django.urls import path, include
# from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('user/addresses', views.addresses, name='addresses'),
    path('ajax/user/addresses/new', views.ajaxNewAddress, name='ajaxNewAddress'),
    path('import/exchange', views.importExchangeTrades, name='importExchange'),
    path('import/transactions', views.importTransactions, name='importTransactions'),
    path('ajax/import/transactions', views.ajaxImportTransactions, name='ajaxImportTransactions'),
    path('ajax/import/transactions/fees', views.ajaxImportTxFees, name='ajaxImportTxFees'),
    path('ajax/import/transactions/fees/spends', views.ajaxTxFeeSpends, name='ajaxTxFeeSpends'),
    path('ajax/import/transactions/fees/poll', views.ajaxPollTxFees, name='ajaxPollTxFees'),
    path('reports/buys', views.buysReport, name='buysReport'),
    path('reports/transactions', views.transactionsReport, name='transactionsReport'),
    path('reports/transactions/<txId>', views.viewTransaction, name='viewTransaction'),
    path('reports/sales', views.salesReport, name='salesReport'),
    path('reports/withdrawals', views.withdrawalsReport, name='withdrawalsReport'),
    path('ajax/withdrawals/<wId>/received', views.ajaxAddWithdrawalReceived, name='ajaxAddWithdrawalReceived'),
    
] #+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)