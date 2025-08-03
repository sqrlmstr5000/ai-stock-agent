import unittest
from unittest.mock import patch, MagicMock
from providers.alphavantage import AlphaVantageProvider
from models.marketdata import EarningsHistory

class TestAlphaVantageProvider(unittest.TestCase):

    @patch('providers.alphavantage.requests.get')
    def test_get_earnings_history(self, mock_get):
        # Mock responses for EARNINGS and INCOME_STATEMENT
        mock_earnings_response = MagicMock()
        mock_earnings_response.json.return_value = {
            "quarterlyEarnings": [
                {"fiscalDateEnding": "2024-12-31", "reportedEPS": "2.5", "estimatedEPS": "2.3"},
                {"fiscalDateEnding": "2024-09-30", "reportedEPS": "2.0", "estimatedEPS": "1.9"},
                {"fiscalDateEnding": "2024-06-30", "reportedEPS": "1.8", "estimatedEPS": "1.7"},
                {"fiscalDateEnding": "2024-03-31", "reportedEPS": "1.5", "estimatedEPS": "1.4"},
                {"fiscalDateEnding": "2023-12-31", "reportedEPS": "1.2", "estimatedEPS": "1.1"}
            ],
            "annualEarnings": [
                {"fiscalDateEnding": "2024-12-31", "reportedEPS": "8.0", "estimatedEPS": "7.8"},
                {"fiscalDateEnding": "2023-12-31", "reportedEPS": "6.0", "estimatedEPS": "5.9"}
            ]
        }
        mock_income_response = MagicMock()
        mock_income_response.json.return_value = {
            "quarterlyReports": [
                {"totalRevenue": "10000"},
                {"totalRevenue": "9500"},
                {"totalRevenue": "9000"},
                {"totalRevenue": "8500"},
                {"totalRevenue": "8000"}
            ],
            "annualReports": [
                {"totalRevenue": "40000"},
                {"totalRevenue": "35000"}
            ]
        }
        # The method calls requests.get twice, so we need to return the right mock in order
        mock_get.side_effect = [mock_earnings_response, mock_income_response]

        provider = AlphaVantageProvider(symbol="AAPL")
        provider.api_key = "test"  # Avoid env dependency
        result = provider.get_earnings_history()
        self.assertIsInstance(result, EarningsHistory)
        self.assertEqual(len(result.quarterly_earnings), 4)
        self.assertEqual(len(result.annual_earnings), 2)
        self.assertEqual(result.quarterly_earnings[0].reported_eps, 2.5)
        self.assertEqual(result.annual_earnings[0].reported_eps, 8.0)

        # Check revenue_growth_yoy and eps_growth_yoy for quarterly earnings
        # For quarterly_earnings[0]: current = 2.5, previous = 1.2
        # eps_growth_yoy = ((2.5 - 1.2) / 1.2) * 100 = 108.33
        self.assertAlmostEqual(result.quarterly_earnings[0].eps_growth_yoy, 108.33, places=2)
        # For quarterly_earnings[0]: current = 10000, previous = 8000
        # revenue_growth_yoy = ((10000 - 8000) / 8000) * 100 = 25.0
        self.assertAlmostEqual(result.quarterly_earnings[0].revenue_growth_yoy, 25.0, places=2)

        # Check revenue_growth_yoy and eps_growth_yoy for annual earnings
        # For annual_earnings[0]: current = 8.0, previous = 6.0
        # eps_growth_yoy = ((8.0 - 6.0) / 6.0) * 100 = 33.33
        self.assertAlmostEqual(result.annual_earnings[0].eps_growth_yoy, 33.33, places=2)
        # For annual_earnings[0]: current = 40000, previous = 35000
        # revenue_growth_yoy = ((40000 - 35000) / 35000) * 100 = 14.29
        self.assertAlmostEqual(result.annual_earnings[0].revenue_growth_yoy, 14.29, places=2)

if __name__ == "__main__":
    unittest.main()
