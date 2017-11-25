#!/usr/bin/env python
# Python script to be run in Moneydance to perform amazing feats of financial scripting

from com.infinitekind.moneydance.model import *
from urllib2 import Request, urlopen, URLError, HTTPError
import json
import sys
import time

try:
	import ssl
except ImportError:
	print "error: no ssl support"

# =================================================================================
# Set to your API key with alphavantage.co
apikey = 'YOUR_API_KEY'

override = True   # used to add quote information even if data for date already exists


mapCurrent = []
mapDates = []
mapCurrency = []
mapAccounts = []
# =================================================================================

def setPriceForSecurity(currencies, symbol, price, high, low, volume, dateint, relative_curr):
	
	use_curr = currencies.getCurrencyByIDString(relative_curr) 
	# print 'Setting price for {0}: {1} {2} '.format(symbol,price, use_curr)

	price = 1/price
	security = currencies.getCurrencyByTickerSymbol(symbol)
	if not security:
		return
	if dateint:
		snapsec = security.setSnapshotInt(dateint, price, use_curr)
		# snapsec.setUserDailyHigh(1/high)
		# snapsec.setUserDailyLow(1/low)
		snapsec.setDailyVolume(volume)
		snapsec.syncItem()

	security.setUserRate(price, use_curr)
	security.syncItem()  

def loadAccounts(parentAcct):
	# This function is a derivative of Mike Bray's Moneydance 2015 Security Price Load module (LoadPricesWindow.java) code and has been modified to work in python
	# Original code located here: https://bitbucket.org/mikerb/moneydance-2015/src/346c42555a9ec4be2b05ef5c4469e183135db4cc/src/com/moneydance/modules/features/securitypriceload/?at=master
	# Get list of accounts to iterate through
	sz = parentAcct.getSubAccountCount()
	i = 0
	for i in xrange(0,sz):
		acct = parentAcct.getSubAccount(i)
		if acct.getAccountType() == parentAcct.AccountType.valueOf("SECURITY") :
			if(acct.getCurrentBalance() != 0 ):
				ctTicker = acct.getCurrencyType()
				# print ctTicker.TAG_RELATIVE_TO_CURR, '==========================================='
				# print ctTicker.getParameter(ctTicker.TAG_RELATIVE_TO_CURR)
				if (ctTicker != None):
					if (ctTicker.getTickerSymbol() != ''):
						listSnap = ctTicker.getSnapshots()
						iSnapIndex = listSnap.size()-1
						if (iSnapIndex < 0):
							mapCurrent.append((ctTicker.getTickerSymbol(), 1.0, ctTicker.getName()))
							mapDates.append((ctTicker.getTickerSymbol(),0))
							mapCurrency.append((ctTicker.getTickerSymbol(),ctTicker.getParameter(ctTicker.TAG_RELATIVE_TO_CURR)))
							mapAccounts.append((ctTicker.getTickerSymbol(),acct))
						else:
							ctssLast = listSnap.get(iSnapIndex)
							if (ctssLast != None):
								mapCurrent.append((ctTicker.getTickerSymbol(),1.0/ctssLast.getUserRate(),ctTicker.getName()))
							mapDates.append((ctTicker.getTickerSymbol(), ctssLast.getDateInt()))
							mapCurrency.append((ctTicker.getTickerSymbol(),ctTicker.getParameter(ctTicker.TAG_RELATIVE_TO_CURR)))
							mapAccounts.append((ctTicker.getTickerSymbol(), acct))
		loadAccounts(acct)

def buildUrl(func, symbol, apikey):
	# Creates url used for JSON quote return
	# Visit www.alphavantage.co to obtain a free api key
	url = 'https://www.alphavantage.co/query?function=' + func + symbol + '&outputsize=compact&apikey=' + apikey
	return url

def getLastRefreshedTimeSeries(func, symbol, apikey):
	url = buildUrl(func, symbol, apikey)
	req = Request(url)
	# Attempt to open the URL, print errors if there are any, otherwise read results 
	try: 
		resp = urlopen(req)
		content = resp.read().decode().strip()
	except IOError, e:
		if hasattr(e, 'code'): # HTTPError
			message = 'http error code: ', e.code
			print message
		elif hasattr(e, 'reason'): # URLError
			message = "can't connect, reason: ", e.reason
			print message
			print e
		else:
			content = resp.read()
			raise
	# convert from JSON data to Python dict and return to calling program
	return json.loads(content)

#===============================================================================
# Iterate through symbols here
root=moneydance.getCurrentAccountBook()
ra = root.getRootAccount() 

loadAccounts(ra)



currencylist = root.getCurrencies().getAllCurrencies()

for currency in currencylist:
	if (currency.getCurrencyType() == currency.getCurrencyType().valueOf("CURRENCY")):
		symbol = currency.getIDString()
		name = currency.getName()
		# print symbol, name


for security, sDate, acct, curr in zip(mapCurrent, mapDates, mapAccounts, mapCurrency):
	symbol = security[0]
	name = security[2]
	func = 'TIME_SERIES_DAILY&symbol='
	# 
	recentQuoteDate = sDate[1]   # Set recentQuoteDate to the last security updated date just in case getQuote fails
	skip = False   # Set to True when data needed for update fails

	# print security, curr, sDate

	try:
		getQuote = getLastRefreshedTimeSeries(func, symbol, apikey)
		recentQuoteDate = str(getQuote['Meta Data']['3. Last Refreshed'])[:10]
		high = float(getQuote['Time Series (Daily)'][recentQuoteDate]['2. high'])
		low = float(getQuote['Time Series (Daily)'][recentQuoteDate]['3. low'])
		close = float(getQuote['Time Series (Daily)'][recentQuoteDate]['4. close'])
		volume = long(float(getQuote['Time Series (Daily)'][recentQuoteDate]['5. volume']))

		# print getQuote
		# print security
		# print symbol, close, high, low, volume , recentQuoteDate
	except:
		print 'Security {0} ({1}): Invalid ticker symbol'.format(name,symbol)
		skip = True

	# if not already updated or override has been specified AND retrieval didn't fail
	if (recentQuoteDate != sDate[1] or override) and not skip:
		rel_curr = curr[1]

		part = recentQuoteDate.split("-")
		lastRefreshDate = part[0]+part[1]+part[2]
		lastRefreshDate = int(lastRefreshDate)
		setPriceForSecurity(root.getCurrencies(), symbol, close, high, low, volume, lastRefreshDate, rel_curr)
		setPriceForSecurity(root.getCurrencies(), symbol, close, high, low, volume, 0, rel_curr)
		print 'Security %s (%s):- updated on %s: %s %s( H:%s, L:%s, V:%s )'%(name,symbol,recentQuoteDate,root.getCurrencies().getCurrencyByIDString(rel_curr),close,high,low,volume)
		skip = False

