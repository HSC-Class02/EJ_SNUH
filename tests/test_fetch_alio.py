import unittest

from src.fetch_alio import _table_records

class AlioFinancialParserTests(unittest.TestCase):
    def test_balance_sheet_table_converts_million_won(self):
        html = """
        <div>(단위: 백만원)</div>
        <table border="1">
          <thead>
            <tr>
              <th>구분</th>
              <th>2021년 결산</th>
              <th>2022년 결산</th>
              <th>2023년 결산</th>
              <th>2024년 결산</th>
              <th>2025년 결산</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>자산</td><td colspan="1">858,311</td><td>908,172</td><td>904,802</td><td>988,252</td><td>945,371</td></tr>
            <tr><td>자산총계</td><td>2,023,074</td><td>2,116,233</td><td>2,113,578</td><td>2,224,725</td><td>2,409,309</td></tr>
            <tr><td>유동자산</td><td>858,311</td><td>908,172</td><td>904,802</td><td>988,252</td><td>945,371</td></tr>
            <tr><td>유동부채</td><td>365,397</td><td>389,702</td><td>409,099</td><td>614,860</td><td>611,131</td></tr>
            <tr><td>부채총계</td><td>1,144,473</td><td>1,226,371</td><td>1,218,915</td><td>1,399,231</td><td>1,374,687</td></tr>
            <tr><td>자본총계</td><td>878,601</td><td>889,862</td><td>894,663</td><td>825,494</td><td>1,034,622</td></tr>
          </tbody>
        </table>
        """
        data = _table_records(html, "balance")
        self.assertEqual(data[2025]["assets"], 2_409_309_000_000)
        self.assertEqual(data[2025]["liabilities"], 1_374_687_000_000)
        self.assertEqual(data[2025]["equity"], 1_034_622_000_000)
        self.assertEqual(data[2025]["current_assets"], 945_371_000_000)

    def test_income_statement_handles_negative_values(self):
        html = """
        <div>(단위: 백만원)</div>
        <table border="1">
          <thead>
            <tr>
              <th>구분</th><th>2021년 결산</th><th>2022년 결산</th>
              <th>2023년 결산</th><th>2024년 결산</th><th>2025년 결산</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>매출</td><td>1,264,712</td><td>1,341,246</td><td>1,403,569</td><td>1,171,989</td><td>1,402,134</td></tr>
            <tr><td>영업이익</td><td>-64,295</td><td>-53,569</td><td>-91,692</td><td>-218,163</td><td>-156,400</td></tr>
            <tr><td>당기 순이익</td><td>289,391</td><td>1,076</td><td>-413</td><td>-108,279</td><td>30,764</td></tr>
          </tbody>
        </table>
        """
        data = _table_records(html, "income")
        self.assertEqual(data[2025]["revenue"], 1_402_134_000_000)
        self.assertEqual(data[2025]["operating_income"], -156_400_000_000)
        self.assertEqual(data[2025]["net_income"], 30_764_000_000)


if __name__ == "__main__":
    unittest.main()
