#!/usr/bin/env python
# coding: utf-8
# Python script to be run in Moneydance to perform amazing feats of financial scripting

from com.infinitekind.moneydance.model import *
from urllib2 import Request, urlopen, URLError, HTTPError
import json
import sys
import time
import os
import xml.etree.ElementTree as elementtree
from datetime import datetime
from datetime import timedelta

try:
	import ssl
except ImportError:
	print "error: no ssl support"


# = CONSTANTS ====================================================================
# Set to your API key with alphavantage.co
APIKEY = 'YOUR API KEY'

OVERRIDE = True   # used to add quote information even if data for date already exists
HIST_DEPTH = 35   # how many history days we want to get for load

IF_ERROR_REPAT_TIMES = 1  # always =1. Times to resend information

TIME_DELAY_SEC = 20

DEBUG = True   # True or False for debug output
DEBUG = False   # True or False for debug output

SEC_FUNC = 'TIME_SERIES_DAILY&symbol='

# =================================================================================
CBR_CURRENCY_CODES = {
    'USD': 'R01235',      # US_Dollar
    'EUR': 'R01239'       # Euro  
}

SECURITY_EXCLUDE_LIST = [
	'',
	'MY_001'
]

FILES = {
	'FXAU.ME': '8_FXAU.csv',
	'FXCN.ME': '8_FXCN.csv',
	'FXDE.ME': '8_FXDE.csv',
	'FXGD.ME': '8_FXGD.csv',
	'FXIT.ME': '8_FXIT.csv',
	'FXJP.ME': '8_FXJP.csv',
	'FXMM.ME': '8_FXMM.csv',
	'FXRB.ME': '8_FXRB.csv',
	'FXRL.ME': '8_FXRL.csv',
	'FXRU.ME': '8_FXRU.csv',
	'FXUK.ME': '8_FXUK.csv',
	'FXUS.ME': '8_FXUS.csv',
}

# =================================================================================
AccountsSecurityList = {}

# =================================================================================

# # get my private APIKEY from hidden settings.py file ------------------------------
# add current file dir to path for importing from settings.py
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__))) # set to path file dir

try:
	from settings import APIKEY
	print 'Use my API key - {0}'.format(APIKEY)

	from settings import FILESPATH
	print 'File Path  - {0}'.format(FILESPATH)
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
	if DEBUG: print 'setting price for {0} date {1}: {2}'.format(symbol, dateint, price)
	price = 1/price
	currency = currencies.getCurrencyByIDString(symbol)
	if not currency:
		return

	if dateint:
		snapsec = currency.setSnapshotInt(dateint, price)
		snapsec.syncItem()
	else:   
		currency.setUserRate(price)
		currency.syncItem()  

def format_dateint(datestr, delimiter, reverse=False):
	part = datestr.split(delimiter)
	if reverse:
		rez = part[0]+part[1]+part[2] 
	else:
		rez = part[2]+part[1]+part[0]
	return int(rez)

def get_cbr_currency(currency):
	curdate = datetime.today().strftime('%d/%m/%Y')
	olddate = (datetime.today()-timedelta(HIST_DEPTH)).strftime('%d/%m/%Y')

	url = 'http://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={0}&date_req2={1}&VAL_NM_RQ={2}'.format(olddate,curdate,CBR_CURRENCY_CODES[currency] )
	if DEBUG: print url

	f = urlopen(url)
	data = f.read()
	root = elementtree.fromstring(data)
	rez_data = {}
	for tree in root[::-1]:
		str_date = format_dateint(datestr = tree.get('Date'), delimiter= '.', reverse=False)
		val = tree.find('Value').text.replace(",", ".")
		rez_data[str_date]=val
		if DEBUG: print str_date, val

	if DEBUG: print rez_data		
	return rez_data

def loadAccounts(parentAcct):
	sz = parentAcct.getSubAccountCount()
	for i in range(sz):
		acct = parentAcct.getSubAccount(i)
		if acct.getAccountType() == parentAcct.AccountType.valueOf("SECURITY") :
			if(acct.getCurrentBalance() != 0 ):
				ctTicker = acct.getCurrencyType()
				Ticker = ctTicker.getTickerSymbol()

				if Ticker not in SECURITY_EXCLUDE_LIST:
					listSnap = ctTicker.getSnapshots()
					iSnapIndex = listSnap.size()-1

					FullName=ctTicker.getName()
					Currency = ctTicker.getParameter(ctTicker.TAG_RELATIVE_TO_CURR)
					if Currency is None:
						print '  >>> ERROR. No Currency. Ticker {0}'.format(Ticker)
						raise ('ERROR. No Currency')
					if (iSnapIndex < 0):
						DateInt = 0
						Price = 1.0
					else:
						ctssLast = listSnap.get(iSnapIndex)
						if (ctssLast != None):
							DateInt = ctssLast.getDateInt()
							Price = 1.0/ctssLast.getUserRate()
						else:
							DateInt = 0
							Price = 1.0
					AccountsSecurityList[Ticker] = dict(Ticker = Ticker, FullName=FullName, Currency=Currency, Price=Price, DateInt=DateInt)
					print Ticker, dict(Ticker = Ticker, FullName=FullName, Currency=Currency, Price=Price, DateInt=DateInt)
					
		loadAccounts(acct)

def buildUrl(func, symbol, apikey):
	# Creates url used for JSON quote return
	# Visit www.alphavantage.co to obtain a free api key
	url = 'https://www.alphavantage.co/query?function=' + func + symbol + '&outputsize=compact&apikey=' + apikey
	return url

def getLastRefreshedTimeSeries(func, symbol, apikey):
	url = buildUrl(func, symbol, apikey)
	print url
	
	time.sleep(TIME_DELAY_SEC)
	req = Request(url)

	# Attempt to open the URL, print errors if there are any, otherwise read results 
	i = IF_ERROR_REPAT_TIMES
	while i>0:
		try: 
			resp = urlopen(req)
			content = resp.read().decode().strip()
			i = 0
		except IOError, e:
			i -= 1
			time.sleep(TIME_DELAY_SEC)			

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

def get_local_security_data(ticker):
	if DEBUG: print 'LOAD locally'
	
	curdate = datetime.today().strftime('%Y-%m-%d')
	olddate = (datetime.today()-timedelta(HIST_DEPTH)).strftime('%Y-%m-%d')

	hist_data = {}
	error = False   # Set to True when data needed for update fails

	try:
		filename = os.path.join(FILESPATH, FILES[ticker])
		f = open(filename)

		for st in f.readlines():
			data = st.split(',')
			if data[0]>=olddate:
				QuoteDate = format_dateint(datestr=data[0], delimiter='-', reverse=True)
				hist_data[data[0]]= dict(dateint = QuoteDate, 
										 close = float(data[4]), 
										 vol = long(data[5]))
		f.close()

		last_date = sorted(hist_data, reverse=True)[0]
		recentQuoteDate = hist_data[last_date]['dateint']
		last_close = hist_data[last_date]['close']
		last_volume = hist_data[last_date]['vol']
		hist_data[0]= dict(dateint = recentQuoteDate, close = last_close, vol = last_volume)	
		
		if DEBUG: print hist_data

	except Exception as e:
		error = True
		print '\n>> ERROR---- LOAD locally. Security {0}: Invalid ticker symbol'.format(
				symbol.encode('utf-8')
				).decode('utf-8')
		print '>> ERROR: {0} \n'.format(e)
	return hist_data, error

def get_internet_security_data(ticker):
	if DEBUG: print 'LOAD from Internet'
	hist_data = {}
	error = False   # Set to True when data needed for update fails
	try:
		getQuote = getLastRefreshedTimeSeries(SEC_FUNC, ticker, APIKEY)

		recentQuoteDate = str(getQuote['Meta Data']['3. Last Refreshed'])[:10]
		last_close = float(getQuote['Time Series (Daily)'][recentQuoteDate]['4. close'])
		last_volume = long(float(getQuote['Time Series (Daily)'][recentQuoteDate]['5. volume']))

		recentQuoteDate = format_dateint(datestr=recentQuoteDate, delimiter='-', reverse=True)

		# load last data to hist_data[]		
		hist_data[0] = dict(dateint = recentQuoteDate, close = last_close, vol = last_volume)

		# load history date to hist_data[]		
		dates = getQuote['Time Series (Daily)'].keys()
		dates.sort(reverse=False)
		for cdate in dates[-HIST_DEPTH:]:
			close = float(getQuote['Time Series (Daily)'][cdate]['4. close'])
			volume = long(float(getQuote['Time Series (Daily)'][cdate]['5. volume']))
			hist_data[cdate]=dict(dateint = format_dateint(datestr=cdate, delimiter='-', reverse=True), close = close, vol = volume)
		# print symbol, close, high, low, volume , recentQuoteDate
		if DEBUG: print hist_data

	except Exception as e:
		error = True
		print '\n>> ERROR---- LOAD from Internet. Security {0}: Invalid ticker symbol'.format(
				symbol.encode('utf-8')
				).decode('utf-8')
		print '>> ERROR: {0} \n'.format(e)
	return hist_data, error

def get_security_data(ticker):
	if ticker in FILES:
		return get_local_security_data(ticker)
	else:
		return get_internet_security_data(ticker)

#===============================================================================
#===============================================================================
root=moneydance.getCurrentAccountBook()
ra = root.getRootAccount() 

loadAccounts(ra)

print '- START -----------------------------------------------------------------------------------------------------'
print '- CURRENCY --------------------------------------------------------------------------------------------------'
# Update all currencies we can find with most recent currency quote
DEF_CURRENCY = 'RUB'

# take only CURRENCY excluding DEF_CURRENCY
currencylist = [x for x in root.getCurrencies().getAllCurrencies() 
				if x.getCurrencyType() == x.getCurrencyType().valueOf("CURRENCY") 
				and x.getIDString()!=DEF_CURRENCY]

for currency in currencylist:
	symbol = currency.getIDString()
	name = currency.getName()

	try:
		print 'Currency: {1}. ({0})'.format(symbol, name)
		rez = get_cbr_currency(symbol)
		
		# dates
		for dateint in rez.keys():
			close = float(rez[dateint])
			print '	date {0} set {1} value'.format(dateint, close)
			setPriceForCurrency(root.getCurrencies(), symbol, close, dateint)
		
		# last close
		last_close = rez[max(rez.keys())]  # max date value
		last_close = float(last_close)
		setPriceForCurrency(root.getCurrencies(), symbol, last_close, 0)
	
	except Exception as e:
		print '\n>> ERROR: Currency {0} ({1}) - Invalid currency'.format(name,symbol)
		print '>> ERROR: {0} \n'.format(e)

print '- SECURITY ------------------------------------------------------------------------------------------------------'
print '      Total {} securitis to update'.format(len(AccountsSecurityList))

for symbol in AccountsSecurityList.keys():
	# if symbol not in ['FXCN.ME']:
	# if symbol in ['MY_001',
				  # 'SNGSP.ME',
				  # 'GXC','SCHR','SCHM','SCHH','VSS',
				  # 'IAU','ERUS','EWY',
				  # 'FXRU.ME','FXRL.ME','FXCN.ME','FXRU.ME',
				  # 'FXIT.ME',
				  # '' ]:
		# continue

	name = AccountsSecurityList[symbol]['FullName']
	print symbol, name

	# get data
	hist_data, skip = get_security_data(symbol)

	# # if not already updated or override has been specified AND retrieval didn't fail
	if not skip:
		if (hist_data[0]['dateint'] != AccountsSecurityList[symbol]['DateInt'] or OVERRIDE):
			rel_curr = AccountsSecurityList[symbol]['Currency']

			if len(hist_data)>1:
				for date in sorted(hist_data.keys()): 
					if date not in [0]:
						print '   Security {0} Date: {1} - {2}  {4}'.format(symbol, 
																				   hist_data[date]['dateint'], 
																				   hist_data[date]['close'], 
																				   0, #hist_data[date]['vol'], 
																				   root.getCurrencies().getCurrencyByIDString(rel_curr))
						
						setPriceForSecurity(root.getCurrencies(), 
											symbol, 
											hist_data[date]['close'], 
											0, #hist_data[date]['vol'], 
											hist_data[date]['dateint'],
											rel_curr)

			setPriceForSecurity(root.getCurrencies(), 
								symbol, 
								hist_data[0]['close'], 
								0, #hist_data[0]['vol'], 
								0,
								rel_curr)
			print '   DONE - Security {0}:- updated on {1}: {2} {3}'.format(symbol,
																			 hist_data[0]['dateint'],
																			 root.getCurrencies().getCurrencyByIDString(rel_curr),
																			 hist_data[0]['close'])



