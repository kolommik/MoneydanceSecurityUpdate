#!/usr/bin/env python
# coding: utf-8
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
apikey = 'YOUR API KEY'

override = True   # used to add quote information even if data for date already exists
HIST_DEPTH = 14

mapCurrent = []
mapDates = []
mapCurrency = []
mapAccounts = []
# =================================================================================

# get my private apikey from hidden settings.py file ------------------------------
import os
import sys

# add current file dir to path for importing from settings.py
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__))) # set to path file dir

try:
	from settings import apikey
	print 'Use my API key - {}'.format(apikey)
except ImportError:
	pass
# =================================================================================


def setPriceForSecurity(currencies, symbol, price, volume, dateint, relative_curr):
	
	use_curr = currencies.getCurrencyByIDString(relative_curr) 
	# print 'Setting price for {0}: {1} {2} '.format(symbol,price, use_curr)

	if price!=0:
		price = 1/price
		security = currencies.getCurrencyByTickerSymbol(symbol)
		if not security:
			return
		if dateint:
			snapsec = security.setSnapshotInt(dateint, price, use_curr)
			snapsec.setDailyVolume(volume)
			snapsec.syncItem()

		security.setUserRate(price, use_curr)
		security.syncItem()  
	return

def setPriceForCurrency(currencies, symbol, price, dateint):
	#print 'setting price for ' + symbol + ': $' + str(price) 
	price = 1/price
	currency = currencies.getCurrencyByIDString(symbol)
	if not currency:
		return
	if dateint:
		snapsec = currency.setSnapshotInt(dateint, price)
		snapsec.syncItem()    
	currency.setUserRate(price)
	currency.syncItem()  

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
	# print url
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

def date_to_int(date):
	part = date.split("-")
	return int(part[0]+part[1]+part[2])

#===============================================================================
# Iterate through symbols here
root=moneydance.getCurrentAccountBook()
ra = root.getRootAccount() 

loadAccounts(ra)

print '- START ------------------------------------------------------------------------------------'
# Update all currencies we can find with most recent currency quote
func = 'CURRENCY_EXCHANGE_RATE&to_currency=RUB&from_currency='

currencylist = root.getCurrencies().getAllCurrencies()

for currency in currencylist:
	if (currency.getCurrencyType() == currency.getCurrencyType().valueOf("CURRENCY")):
		symbol = currency.getIDString()
		name = currency.getName()
		# print symbol, name
		try:
			getCurrency = getLastRefreshedTimeSeries(func, symbol, apikey)
			print getCurrency
			recentCurrencyDate = str(getCurrency['Realtime Currency Exchange Rate']['6. Last Refreshed'])[:10]
			close = float(getCurrency['Realtime Currency Exchange Rate']['5. Exchange Rate'])
			part = recentCurrencyDate.split("-")
			lastRefreshDate = part[0]+part[1]+part[2]
			lastRefreshDate = int(lastRefreshDate)
			setPriceForCurrency(root.getCurrencies(), symbol, close, lastRefreshDate)
			setPriceForCurrency(root.getCurrencies(), symbol, close, 0)
			print 'Currency %s (%s) - updated on %s: RUB %s'%(name,symbol,recentCurrencyDate,close)
		except:
			print 'Currency %s (%s) - Invalid currency'%(name,symbol)

print '- SECURITY -------------------------------------------------------------------------------'

# security update
for security, sDate, acct, curr in zip(mapCurrent, mapDates, mapAccounts, mapCurrency)[:]:
	symbol = security[0]
	# if symbol not in ['MTSS.ME']:
	# if symbol in ['GXC','SCHR','SCHM','SCHH','VSS',
	# 			  'IAU','ERUS','EWY','FXDE.ME','FXJP.ME',
	# 			  'MTSS.ME','MOEX.ME','NLMK.ME','SBERP.ME',
	# 			  'FXRU.ME','FXRL.ME','FXCN.ME','FXRU.ME',
	# 			  'FXIT.ME','SNGSP.ME']:
	# 	continue
	name = security[2]
	func = 'TIME_SERIES_DAILY&symbol='
	# 
	recentQuoteDate = sDate[1]   # Set recentQuoteDate to the last security updated date just in case getQuote fails
	skip = False   # Set to True when data needed for update fails

	# print security, curr, sDate

	hist_data = []
	try:
		getQuote = getLastRefreshedTimeSeries(func, symbol, apikey)
		recentQuoteDate = str(getQuote['Meta Data']['3. Last Refreshed'])[:10]
		last_close = float(getQuote['Time Series (Daily)'][recentQuoteDate]['4. close'])
		last_volume = long(float(getQuote['Time Series (Daily)'][recentQuoteDate]['5. volume']))

		# load history date to hist_data[]
		dates = getQuote['Time Series (Daily)'].keys()
		dates.sort(reverse=False)
		for cdate in dates[-HIST_DEPTH:]:
			close = float(getQuote['Time Series (Daily)'][cdate]['4. close'])
			volume = long(float(getQuote['Time Series (Daily)'][cdate]['5. volume']))
			hist_data.append((cdate, date_to_int(cdate), close, volume))

		# print symbol, close, high, low, volume , recentQuoteDate
	except:
		print name, symbol
		print '     >>>  ---ERROR---- Security {0} ({1}): Invalid ticker symbol'.format(
				name.encode('utf-8'),
				symbol.encode('utf-8')
				).decode('utf-8')
		skip = True

	# if not already updated or override has been specified AND retrieval didn't fail
	if (recentQuoteDate != sDate[1] or override) and not skip:
		rel_curr = curr[1]
		RefreshDate = date_to_int(recentQuoteDate)

		if len(hist_data)>0:
			for QuoteDate, RefreshDate, close, volume in hist_data:
				print 'Security {0} Date: {1} - {2}  {4}   vol:{3}'.format(symbol, QuoteDate, close, volume, root.getCurrencies().getCurrencyByIDString(rel_curr))
				setPriceForSecurity(root.getCurrencies(), symbol, close, volume, RefreshDate, rel_curr)

		setPriceForSecurity(root.getCurrencies(), symbol, last_close, last_volume, 0, rel_curr)
		print 'DONE - Security %s (%s):- updated on %s: %s %s( V:%s )'%(name,symbol,recentQuoteDate,root.getCurrencies().getCurrencyByIDString(rel_curr),close,volume)
		skip = False

