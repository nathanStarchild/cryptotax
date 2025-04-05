import pdfkit

def getScreenshot(tx):
    pdfkit.from_url(tx.explorerUrl(), 'test.pdf')
    return ""
