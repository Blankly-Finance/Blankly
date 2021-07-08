"""
    Unit tests for Coinbase Pro.
    Copyright (C) 2021  Emerson Dove

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import Blankly
import unittest
import pytest

from pathlib import Path

from Blankly.exchanges.interfaces.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth
from Blankly.exchanges.interfaces.direct_calls_factory import DirectCallsFactory
from Blankly.exchanges.interfaces.coinbase_pro.coinbase_pro_interface import CoinbaseProInterface


class CoinbaseInterface2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.Coinbase_Pro = Blankly.CoinbasePro(portfolio_name="Sandbox Portfolio",
                                               keys_path='./tests/config/keys.json',
                                               settings_path="./tests/config/settings.json")
        cls.Coinbase_Pro_Interface = cls.Coinbase_Pro.get_interface()

    def test_get_exchange_type(self):
        coinbase_pro = self.Coinbase_Pro_Interface.get_exchange_type()
        self.assertEqual(coinbase_pro, "coinbase_pro")


@pytest.fixture
def coinbase_interface():
    keys_file_path = Path("tests/config/keys.json").resolve()
    settings_file_path = Path("tests/config/settings.json").resolve()

    auth_obj = CoinbaseProAuth(str(keys_file_path), "Sandbox Portfolio")
    _, coinbase_interface = DirectCallsFactory.create("coinbase_pro", auth_obj, str(settings_file_path))
    return coinbase_interface


def test_get_exchange(coinbase_interface: CoinbaseProInterface) -> None:
    assert coinbase_interface.get_exchange_type() == 'coinbase_pro'

    products = coinbase_interface.get_products()
    btc_usd_id = None

    for product in products:
        if product['base_asset'] == 'BTC' and product['quote_asset'] == 'USD':
            btc_usd_id = product['symbol']

    assert btc_usd_id

    #market_buy_order = coinbase_interface.market_order(btc_usd_id, 'buy', 200)


def test_get_price(coinbase_interface: CoinbaseProInterface) -> None:
    responses = []
    responses.append(coinbase_interface.get_price('BTC-USD'))
    responses.append(coinbase_interface.get_price('BTC-EUR'))
    responses.append(coinbase_interface.get_price('BTC-GBP'))
    responses.append(coinbase_interface.get_price('ETH-BTC'))
    for resp in responses:
        assert type(resp) is float
