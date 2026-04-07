import os
import pandas as pd
from edgar import set_identity, Company
from datetime import date, timedelta
from utils.logging import setup_logger

logger = setup_logger(__name__)

class EdgarProvider:
	def __init__(self):
		self.identity = os.environ.get("EDGAR_IDENTITY")
		if not self.identity:
			raise ValueError("EDGAR identity not found in environment variables.")
		logger.info(f"Using EDGAR identity: {self.identity}")
		#set_identity(self.identity)

	def _get_filings(self, symbol: str, forms: list, days: int = 90) -> list:
		"""
		Fetches filings for a given symbol, form types, and date range.
		Returns a list of filing objects.
		"""
		try:
			company = Company(symbol)
			end_date = date.today()
			start_date = end_date - timedelta(days=days)
			date_range = f"{start_date.strftime('%Y-%m-%d')}:{end_date.strftime('%Y-%m-%d')}"
			logger.info(f"Fetching filings {forms} for {symbol} from {start_date} to {end_date}")
			filings = company.get_filings(
				form=forms,
				filing_date=date_range
			)
			return filings
		except Exception as e:
			logger.error(f"An error occurred while fetching filings {forms} for {symbol}: {e}")
			return []

	def get_insider_trading_data(self, symbol: str, days: int) -> pd.DataFrame:
		"""
		Pulls insider trading data (Form 4 and 5) for a given stock symbol using edgar library.
		Returns a pandas DataFrame of transactions.
		"""
		filings = self._get_filings(symbol, ["4", "5"], days)
		all_transactions = []
		for filing in filings:
			try:
				transaction_data = filing.obj().to_dataframe()
				all_transactions.append(transaction_data)
			except Exception as e:
				logger.error(f"Could not parse Form 4/5 filing for {getattr(filing, 'accession_number', 'unknown')}: {e}")

		if all_transactions:
			full_df = pd.concat(all_transactions, ignore_index=True)
			return full_df
		else:
			return pd.DataFrame()
		
	def get_etf_holdings(self, symbol: str):
		"""
		Pulls ETF holdings data for a given ETF symbol using edgar.find and get_portfolio.
		Returns a pandas DataFrame of ETF holdings from the latest portfolio.
		"""
		from edgar import find
		try:
			logger.debug(f"Attempting to find fund for symbol: {symbol}")
			fund = find(symbol)
			logger.debug(f"find({symbol}) returned: {fund}")
			if fund is None:
				logger.error(f"No fund found for symbol {symbol}")
				return pd.DataFrame()
			classes = fund.get_classes()
			logger.debug(f"fund.get_classes() returned: {classes}")
			logger.info(f"Fund has {len(classes)} share classes")
			if not classes:
				logger.error(f"No share classes found for fund {symbol}")
				return pd.DataFrame()
			logger.debug(f"Attempting to get portfolio from first class: {classes[0]}")
			portfolio = classes[0].get_portfolio()
			logger.debug(f"get_portfolio() returned: {type(portfolio)}, shape: {getattr(portfolio, 'shape', None)}")
			if portfolio is not None and not portfolio.empty:
				# Optionally, show top 10 holdings by value
				top_holdings = portfolio.sort_values('value', ascending=False).head(10)
				logger.info(f"Top 10 holdings for {symbol}:\n{top_holdings}")
				return portfolio
			else:
				logger.error(f"No portfolio holdings found for fund {symbol}")
				return pd.DataFrame()
		except Exception as e:
			logger.error(f"Error fetching ETF holdings for {symbol}: {e}")
			return pd.DataFrame()
	
	def get_insider_trading_summary(self, symbol: str, days: int, top_n: int = 5):
		"""
		Returns a summary dict for insider trading activity:
		- sale_total: total value of sales
		- buy_total: total value of buys
		- top_sellers: list of dicts with insider, position, and total value
		- top_buyers: list of dicts with insider, position, and total value
		"""
		df = self.get_insider_trading_data(symbol, days)
		if df.empty:
			return {
				"sale_total": 0.0,
				"buy_total": 0.0,
				"top_sellers": [],
				"top_buyers": []
			}
		logger.debug(f"DataFrame columns: {df.columns.tolist()}")

		# Use correct columns from example DataFrame
		# Transaction type: 'Transaction Type Code'
		# Shares: 'Shares'
		# Price: 'Price'
		# Value: 'Value' (already calculated)
		# Insider: 'Insider'
		# Position: 'Position'

		# Transaction type and value
		sale_mask = df['Transaction Type'].str.contains('sale', case=False, na=False)
		buy_mask = df['Transaction Type'].str.contains('purchase|buy', case=False, na=False)

		# If 'Value' column exists, use it; otherwise, calculate
		if 'Value' in df.columns:
			df['value'] = df['Value'].astype(float)
		else:
			df['value'] = df['Shares'].astype(float) * df['Price'].astype(float)

		sale_total = float(df.loc[sale_mask, 'value'].sum())
		buy_total = float(df.loc[buy_mask, 'value'].sum())

		# Group by insider and position for sellers
		group_cols = ['Insider', 'Position']
		sellers_grouped = df.loc[sale_mask].groupby(group_cols)['value'].sum().reset_index()
		top_sellers = sellers_grouped.sort_values('value', ascending=False).head(top_n)
		top_sellers_list = [
			{
				"insider": row['Insider'],
				"position": row['Position'],
				"total_value": row['value']
			}
			for _, row in top_sellers.iterrows()
		]

		# Group by insider and position for buyers
		buyers_grouped = df.loc[buy_mask].groupby(group_cols)['value'].sum().reset_index()
		top_buyers = buyers_grouped.sort_values('value', ascending=False).head(top_n)
		top_buyers_list = [
			{
				"insider": row['Insider'],
				"position": row['Position'],
				"total_value": row['value']
			}
			for _, row in top_buyers.iterrows()
		]

		# Monthly trend calculation
		monthly_trend = {}
		if 'Date' in df.columns:
			df['Month'] = pd.to_datetime(df['Date']).dt.to_period('M').astype(str)
			months = df['Month'].unique()
			for month in months:
				month_df = df[df['Month'] == month]
				sale_mask_month = month_df['Transaction Type'].str.contains('sale', case=False, na=False)
				buy_mask_month = month_df['Transaction Type'].str.contains('purchase|buy', case=False, na=False)
				sale_total_month = float(month_df.loc[sale_mask_month, 'value'].sum())
				buy_total_month = float(month_df.loc[buy_mask_month, 'value'].sum())
				buy_vs_sell_ratio_month = buy_total_month / sale_total_month if sale_total_month != 0 else None
				monthly_trend[month] = {
					"sale_total": sale_total_month,
					"buy_total": buy_total_month,
					"buy_vs_sell_ratio": buy_vs_sell_ratio_month # If >1, more buying than selling; if <1, more selling than buying.
				}

		buy_vs_sell_ratio = buy_total / sale_total if sale_total != 0 else None
		return {
			"sale_total": sale_total,
			"buy_total": buy_total,
			"buy_vs_sell_ratio_total": buy_vs_sell_ratio,
			"top_sellers": top_sellers_list,
			"top_buyers": top_buyers_list,
			"monthly_trend": monthly_trend
		}

	def get_institutional_holdings_data(self, symbol: str, days: int = 90):
		"""
		Pulls institutional holdings data (Form 13F) for a given stock symbol using edgar library.
		Returns a pandas DataFrame of institutional holders and their positions from the latest filing only.
		"""
		logger.debug(f"Requesting 13F-HR filings for symbol: {symbol}, days: {days}")
		filings = self._get_filings(symbol, ["13F-HR"], days)
		logger.debug(f"Found {len(filings)} 13F filings for {symbol} in the last {days} days.")
		if filings:
			latest_filing = filings[0]
			logger.debug(f"Processing latest filing: {getattr(latest_filing, 'accession_number', 'unknown')}")
			try:
				obj = latest_filing.obj()
				logger.debug(f"latest_filing.obj() returned type: {type(obj)}")
				if hasattr(obj, "infotable"):
					logger.debug(f"obj.infotable exists, type: {type(obj.infotable)}")
					if obj.infotable is not None:
						logger.debug(f"Returning infotable DataFrame with shape: {getattr(obj.infotable, 'shape', None)}")
						return obj.infotable
					else:
						logger.error(
							f"13F filing object for {getattr(latest_filing, 'accession_number', 'unknown')} has infotable attribute but it is None. "
							f"obj type: {type(obj)}, infotable type: {type(getattr(obj, 'infotable', None))}"
						)
				else:
					logger.error(
						f"13F filing object for {getattr(latest_filing, 'accession_number', 'unknown')} does not have infotable attribute. "
						f"obj type: {type(obj)}"
					)
			except Exception as e:
				logger.error(f"Could not parse 13F filing for {getattr(latest_filing, 'accession_number', 'unknown')}: {e}")
		else:
			logger.debug(f"No filings found for symbol: {symbol} in the last {days} days.")
		logger.debug("Returning empty DataFrame for institutional holdings data.")
		return pd.DataFrame()

