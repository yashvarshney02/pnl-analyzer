import streamlit as st
import pandas as pd
import json
import requests
import time
import datetime as dt
import matplotlib.pyplot as plt
import streamlit.components.v1 as components


access_token = open("access_token.txt", "r").read() # in access_token.txt write as {api_key}:{access_token}
access_token = f"token {access_token}"
data = {}
 

def fetchOHLC(code, interval, duration, date_given, tries=0): 
	global access_token

	try:      
		date_given = dt.datetime.strptime(date_given, '%Y-%m-%d')
	except:
		pass
	  
	try:
		date1, date2 = (date_given -
						dt.timedelta(duration)).strftime("%Y-%m-%d"), (
							date_given).strftime("%Y-%m-%d")         
		headers = {"authorization": access_token}
		r = requests.get('https://api.kite.trade/instruments/historical/' +
							str(code) + '/' + str(interval) +
							'?user_id=XXXXXX&oi=24&from=' + str(date1) + '&to=' +
							str(date2),
							headers=headers).json()
		if (r['status'] == 'error' and r['message'] == 'Too many requests'):
			time.sleep(0.2)
			return fetchOHLC(code, interval, duration, date_given)
		res = {}
		if (r['status'] == 'error' and r['error_type'] == 'TokenException'):
			res['data'] = pd.DataFrame()
			return pd.DataFrame()
		if (r['status'] == 'error' and r['error_type'] == 'InputException'):
			return pd.DataFrame()
		try:
			d = r['data']['candles']
		except:
			return pd.DataFrame()
		df = pd.DataFrame(d)
		df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
		df['Time'] = pd.to_datetime(df['Time'])
		df['Time'] = df['Time'].dt.strftime("%H:%M:%S")
		return df
	except Exception as E:
		return None # instead you can return an empty DataFrame

def get_pnl(orders, fund):
	
	global data
	time_wise_pnl = []
	
	orders['order_timestamp'] = pd.to_datetime(orders['order_timestamp'])
	orders['order_timestamp'] = orders['order_timestamp'].dt.strftime('%H:%M:00')
	orders = orders[orders['status'] == 'COMPLETE']
	orders = orders.sort_values("order_timestamp")	
	t = "09:15:00"
	times = []
	while t <= min("15:29:00", dt.datetime.now().time().strftime('%H:%M:00')):
		times.append(t)
		t = dt.datetime.strptime(t, "%H:%M:%S")
		t = t + dt.timedelta(minutes=1)
		t = t.strftime('%H:%M:%S')
  
	
	# collect data, you can also store this data somewhere if you want to use it repeatedly, might save you some ohlc requests
	for symbol, instrument_token in zip(orders['tradingsymbol'].values, orders['instrument_token'].values):
		x = fetchOHLC(instrument_token, 'minute', 0, str(dt.date.today()))
		data[symbol] = x

	for t in times:
		df = orders[orders['order_timestamp']<=t]
		positions = {}
		for instrument_token, symbol, qty, txn_type, price, tt in zip(df['instrument_token'].values, df['tradingsymbol'].values, df['quantity'].values, df['transaction_type'].values, df['average_price'].values, df['order_timestamp'].values):
			if symbol not in positions:
				positions[symbol] = {
					"sell_value": 0,
					"buy_value": 0,
					"qty": 0,
					"ltp": 0
				}
			value = qty * price
			if txn_type == "SELL":
				positions[symbol]['sell_value'] += value
				positions[symbol]['qty'] -= qty
			else:
				positions[symbol]['buy_value'] += value
				positions[symbol]['qty'] += qty

			temp_data = data[symbol]			
			temp_data = temp_data[temp_data['Time'] == t]
			if temp_data.empty:
				temp_data = data[symbol][data[symbol]['Time'] <= t]
			temp_data = temp_data.tail(1)  # take out the latest row

			ltp = temp_data.Open.values[0]
			positions[symbol]['ltp'] = ltp
		total_pnl = 0
		for symbol, pos in positions.items():
			pnl =  (pos['sell_value'] - pos['buy_value']) + (pos['qty'] * pos['ltp'] * 1)
			total_pnl += pnl
		time_wise_pnl.append([t, total_pnl])
	time_wise_pnl = pd.DataFrame(time_wise_pnl, columns=['TIME', 'PNL'])
	if fund != 0:
		time_wise_pnl['PNL']  = time_wise_pnl['PNL'] *100 / fund
		time_wise_pnl.columns = ['TIME', 'PNL%']
	return time_wise_pnl



# Streamlit app
def main():
	st.title('Order Book Analysis (Currently for Zerodha only)')
	st.write("Upload a JSON file containing the order book:\njson should look like this: {data:'list of zerodha orders'}")
	uploaded_file = st.file_uploader("Choose a file", type=['json'])
	fund = st.number_input("Write Your Fund value(optional)")
	fund = int(fund)

	if uploaded_file is not None:
		# Load JSON file
		order_book = json.load(uploaded_file)
		order_book = pd.DataFrame(order_book['data'])
		time_wise_pnl = get_pnl(orders=order_book, fund=fund)
		st.markdown("***")
  		# Render the line chart
		st.line_chart(data=time_wise_pnl, x="TIME", y=time_wise_pnl.columns[1])

if __name__ == '__main__':
	main()
