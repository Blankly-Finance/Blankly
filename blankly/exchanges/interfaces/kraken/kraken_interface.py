import time

import requests
import pandas as pd
from typing import List
import warnings

# import blankly.utils.time_builder
import blankly.utils.utils as utils
from blankly.exchanges.auth.utils import load_auth
import blankly.exchanges.interfaces.kraken.kraken_interface_utils as interface_utils
from blankly.exchanges.interfaces.exchange_interface import ExchangeInterface
from blankly.exchanges.orders.limit_order import LimitOrder
from blankly.exchanges.orders.market_order import MarketOrder
# from blankly.exchanges.orders.stop_limit import StopLimit
# from blankly.utils.exceptions import APIException, InvalidOrder


class KrakenInterface(ExchangeInterface):

    # NOTE: kraken has no sandbox mode
    def __init__(self, exchange_name, authenticated_api):
        super().__init__(exchange_name, authenticated_api, valid_resolutions=None)

        self.account_levels_to_max_open_orders = {
            "Starter": 60,
            "Express": 60,
            "Intermediate": 80,
            "Pro": 225
        }

    def init_exchange(self):
        try:
            position = self.kraken_request('/0/private/Balance', {
                "nonce": str(int(1000 * time.time()))
            })
        except Exception as e:
            if position['error'] == 'EAPI:Invalid key':
                raise KeyError('Wrong Keys')
            else:
                raise e

    def kraken_request(self, path, data):
        api_url = "https://api.kraken.com"
        auth = load_auth('kraken')
        headers = {}
        headers['API-Key'] = auth[1]['API_KEY']
        headers['API-Sign'] = self.get_calls()._sign(data, path)
        req = requests.post((api_url + path), headers=headers, data=data).json()
        return req

    def get_products(self) -> list:

        needed_asset_pairs = []
        symbol = {"pair": "XXBTZUSD"}
        needed = self.needed["get_products"]
        asset_pairs = self.get_calls().query_public('AssetPairs', symbol)

        asset_pairs["symbol"] = asset_pairs['result'][symbol['pair']]["wsname"].replace('/', '-')
        asset_pairs["base_asset"] = asset_pairs['result'][symbol['pair']]["base"]
        asset_pairs["quote_asset"] = asset_pairs['result'][symbol['pair']]["quote"]
        asset_pairs["base_min_size"] = asset_pairs['result'][symbol['pair']]["ordermin"]
        asset_pairs["base_max_size"] = 99999999999
        asset_pairs["base_increment"] = 10 ** (-1 * float(asset_pairs['result'][symbol['pair']]["lot_decimals"]))
        asset_pairs["kraken_id"] = None
        needed_asset_pairs.append(utils.isolate_specific(needed, asset_pairs))

        return needed_asset_pairs

    def get_account(self, symbol=None):
        symbol = 'XXBT'

        positions = self.kraken_request('/0/private/Balance', {
            "nonce": str(int(1000 * time.time()))
        })

        positions_dict = utils.AttributeDict({})

        for position in positions['result']:
            positions_dict[position] = utils.AttributeDict({
                'available': float(positions['result'][position]),
                'hold': 0.0
            })

        if symbol is not None:
            if symbol in positions_dict:
                return utils.AttributeDict({
                    'available': float(positions_dict[symbol]['available']),
                    'hold': float(positions_dict[symbol]['hold'])
                })
            else:
                raise KeyError('Symbol not found.')

        if symbol == 'USD':
            return utils.AttributeDict({
                'available': positions_dict['USD']['available'],
                'hold': positions_dict['USD']['hold']
            })

        return positions_dict

    def market_order(self, symbol: str, side: str, size: float):
        """
        Needed:
        'market_order': [
                ["symbol", str],
                ["id", str],
                ["created_at", float],
                ["size", float],
                ["status", str],
                ["type", str],
                ["side", str]
            ],
        """
        #symbol = interface_utils.blankly_symbol_to_kraken_symbol(symbol)
        symbol = 'XBTUSD'
        response = self.kraken_request('/0/private/AddOrder', {
                    "nonce": str(int(1000*time.time())),
                    "ordertype": "market",
                    "type": side,
                    "volume": size,
                    "pair": symbol,
                })

        txid = response["txid"]
        order_info = self.kraken_request('/0/private/QueryOrders', {
                    "nonce": str(int(1000*time.time())),
                    "txid": txid,
                    "trades": True #default is false, so dk bout this
                })

        order_info["symbol"] = symbol
        order_info["id"] = txid
        order_info["created_at"] = order_info['result'][txid]['opentim']
        order_info["size"] = size
        order_info["type"] = "market"
        order_info["side"] = side

        order = {
            'size': size,
            'side': side,
            'symbol': symbol,
            'type': 'market'
        }

        return MarketOrder(order, order_info, self)

    def limit_order(self, symbol: str, side: str, price: float, size: float):
        #symbol = interface_utils(symbol)
        response = self.kraken_request('/0/private/AddOrder', {
                    "nonce": str(int(1000*time.time())),
                    "ordertype": "limit",
                    "type": side,
                    "volume": size,
                    "pair": symbol,
                    "price": price
                })
        txid = response["txid"]

        order_info = self.kraken_request('/0/private/QueryOrders', {
                    "nonce": str(int(1000*time.time())),
                    "txid": txid,
                    "trades": True #default is false, so dk bout this
                })

        order_info["symbol"] = symbol
        order_info["id"] = txid
        order_info["created_at"] = order_info['result'][txid]['opentim']
        order_info["size"] = size
        order_info["type"] = "market"
        order_info["side"] = side

        order = {
            'size': size,
            'side': side,
            'symbol': symbol,
            'type': 'market'
        }

        return LimitOrder(order, order_info, self)

    def cancel_order(self, symbol: str, order_id: str):
        return self.kraken_request('/0/private/CancelOrder', {
                    "nonce": str(int(1000*time.time())),
                    "txid": order_id
                })

    def get_open_orders(self, symbol: str = None) -> list:
        """
        List open orders.
        Args:
            symbol (optional) (str): Asset such as BTC-USD
        """
        response = self.kraken_request('/0/private/OpenOrders', {
                    "nonce": str(int(1000*time.time())),
                    "trades": True #default is false, dk bout this
                })

        response_needed_fulfilled = []
        if len(response) == 0:
            return []

        for open_order_id in response['result']['open']:
            for open_order_info in response['result']['open'][open_order_id]:
                needed = self.choose_order_specificity(open_order_info['type'])

                open_order_info['id'] = open_order_info['trades'][0]
                open_order_info["symbol"] = open_order_info["descr"]["pair"]
                open_order_info["size"] = open_order_info['vol']
                open_order_info["type"] = open_order_info["descr"]["ordertype"]
                open_order_info["side"] = open_order_info["descr"]["type"]
                open_order_info["status"] = None #no status given
                open_order_info["price"] = open_order_info["descr"]["price"]
                open_order_info["time_in_force"] = "GTC"
                open_order_info['created_at'] = open_order_info['opentm']

                open_order_info = utils.isolate_specific(needed, open_order_info)

                response_needed_fulfilled.append(open_order_info)

        return response_needed_fulfilled

    #https://docs.kraken.com/rest/#operation/getOrdersInfo
    #private function
    def get_order(self, symbol: str, order_id: str) -> dict:
        """
        Get a certain order
        Args:
            symbol: Asset that the order is under
            order_id: The unique ID of the order.
        """
        response = self.kraken_request('/0/private/QueryOrders', {
                    "nonce": str(int(1000*time.time())),
                    "txid": order_id,
                    "trades": True
                })
        utils.pretty_print_JSON(response, actually_print=True)

        order_type = response["descr"].pop("ordertype")

        needed = self.choose_order_specificity(order_type)

        response["id"] = order_id
        response['type'] = order_type
        response['symbol'] = interface_utils.kraken_symbol_to_blankly_symbol(response['descr']['pair'])
        response['created_at'] = response.pop('opentm')
        response['price'] = response['descr'].pop('price')
        response['size'] = response.pop("vol")
        response['side'] = response["descr"].pop("type")
        # NOTE, what is funds in needed?

        if order_type == "limit":
            response['time_in_force'] = "GTC"

        response = utils.isolate_specific(needed, response)
        return response

    # NOTE fees are dependent on asset pair, so this is a required parameter to call the function
    def get_fees(self, symbol) -> dict:
        asset_symbol = {"pair": "XBTUSDT"}
        size = 1
        assets_pair_info = self.get_calls().query_public('AssetPairs', asset_symbol)
        asset_pair_info = assets_pair_info['result'][asset_symbol['pair']]

        fees_maker: List[List[float]] = asset_pair_info["fees_maker"]
        fees_taker: List[List[float]] = asset_pair_info["fees"]

        # fees_maker: List[List[float]] = asset_pair_info[interface_utils.blankly_symbol_to_kraken_symbol(asset_symbol)]["fees_maker"]
        # fees_taker: List[List[float]] = asset_pair_info[interface_utils.blankly_symbol_to_kraken_symbol(asset_symbol)]["fees"]

        for volume_fee in reversed(fees_maker):
            if size > volume_fee[0]:
                fee_maker = volume_fee[1]

        for volume_fee in reversed(fees_taker):
            if size > volume_fee[0]:
                fee_taker = volume_fee[1]

        return {
            "maker_fee_rate": fee_maker,
            "taker_fee_rate": fee_taker,
        }

    def overridden_history(self, symbol, epoch_start, epoch_stop, resolution, **kwargs) -> pd.DataFrame:
        """
        Kraken is strange because it's exclusive instead of inclusive. This generally invovles adding an extra
        datapoint so this is here to do some of that work
        """
        to = kwargs['to']

        if isinstance(to, str):
            epoch_start -= resolution
        elif isinstance(to, int):
            epoch_start = epoch_stop - (to * resolution)

        return self.get_product_history(symbol, epoch_start, epoch_stop, resolution)

    def get_product_history(self, symbol, epoch_start, epoch_stop, resolution)-> pd.DataFrame:

        # symbol = interface_utils.blankly_symbol_to_kraken_symbol(symbol)

        # epoch_start = int(utils.convert_epochs(epoch_start))
        # epoch_stop = int(utils.convert_epochs(epoch_stop))

        accepted_grans = [60, 300, 900, 1800, 3600, 14400, 86400, 604800, 1296000]

        if resolution not in accepted_grans:
            utils.info_print("Granularity is not an accepted granularity...rounding to nearest valid value.")
            resolution = accepted_grans[min(range(len(accepted_grans)),
                                            key=lambda i: abs(accepted_grans[i] - resolution))]

        param_dict = {"pair": "XBTUSDT", "interval": resolution/60, "since":epoch_start}

        # resolution = int(resolution)
        #
        # epoch_start -= resolution

        # kraken processes resolution in seconds, so the granularity must be divided by 60
        product_history = self.get_calls().query_public('OHLC', param_dict)
        #symbol = "XXBTZUSD"
        historical_data_raw = product_history['result'][param_dict['pair']]
        historical_data_block = []
        num_intervals = len(historical_data_raw)

        for i, interval in enumerate(historical_data_raw):

            time = interval[0]
            open_ = interval[1]
            high = interval[2]
            low = interval[3]
            close = interval[4]
            volume = interval[5]

            historical_data_block.append([time, open_, close, high, low, volume])

            if time > epoch_stop:
                break

        utils.update_progress(i / num_intervals)

        df = pd.DataFrame(historical_data_block, columns=['time', 'open', 'close', 'high', 'low', 'volume'])
        df[['time']] = df[['time']].astype(int)
        # df_start = df["time"][0]

        if df is not None:
            if df["time"][0] > epoch_start:
                warnings.warn(
                    f"Due to kraken's API limitations, we could only collect OHLC data as far back as unix epoch {df['time'][0]}")

        df = df.astype({
            'open': float,
            'high': float,
            'low': float,
            'close': float,
            'volume': float
        })

        return df

    def get_order_filter(self, symbol: str) -> dict:

        symbol = {"pair": "XBTUSDT"}
        kraken_symbol = symbol
        # kraken_symbol = interface_utils.blankly_symbol_to_kraken_symbol(symbol)

        asset_info = self.get_calls().query_public('AssetPairs', kraken_symbol)

        price = self.get_calls().query_public('Ticker', kraken_symbol)["result"][symbol['pair']]['p'][0]

        return {
            "symbol": symbol['pair'],
            "base_asset": asset_info['result'][kraken_symbol['pair']]["wsname"].split("/")[0],
            "quote_asset": asset_info['result'][kraken_symbol['pair']]["wsname"].split("/")[1],
            "max_orders": self.account_levels_to_max_open_orders[
                self.user_preferences["settings"]["kraken"]["account_type"]],
            "limit_order": {
                "base_min_size": asset_info['result'][kraken_symbol['pair']]["ordermin"],
                "base_max_size": 999999999,
                "base_increment": asset_info['result'][kraken_symbol['pair']]["lot_decimals"],
                "price_increment": asset_info['result'][kraken_symbol['pair']]["pair_decimals"],
                "min_price": float(asset_info['result'][kraken_symbol['pair']]["ordermin"]) * float(price),
                "max_price": 999999999,
            },
            "market_order": {
                "base_min_size": asset_info['result'][kraken_symbol['pair']]["ordermin"],
                "base_max_size": 999999999,
                "base_increment": asset_info['result'][kraken_symbol['pair']]["lot_decimals"],
                "quote_increment": asset_info['result'][kraken_symbol['pair']]["pair_decimals"],
                "buy": {
                    "min_funds": 0,
                    "max_funds": 999999999,
                },
                "sell": {
                    "min_funds": 0,
                    "max_funds": 999999999
                },

            },
            "exchange_specific": {}

        }

    def get_price(self, symbol: str) -> float:
        """
        Returns just the price of a symbol.
        Args:
            symbol: The asset such as (BTC-USD, or MSFT)
        """
        symbol = {"pair": "XBTUSD"} #needs symbol
        response_symbol = 'XXBTZUSD'
        # symbol = interface_utils.blankly_symbol_to_kraken_symbol(symbol)

        response = self.get_calls().query_public('Ticker', symbol)

        volume_weighted_average_price = float(response['result'][response_symbol]["p"][0])

        return volume_weighted_average_price
