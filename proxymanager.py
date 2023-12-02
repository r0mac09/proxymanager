from loguru import logger as log
import pandas as pd

from collectors import get_scrapingant_proxies, get_socksproxy_proxies


class ProxyManager:
    def __init__(self) -> None:
        pass

    def dict(self) -> dict:
        return self._proxies_dict

    def df(self) -> pd.DataFrame:
        return self._proxies_df

    def list(self) -> list:
        return list(self._proxies_dict.values())

    def addresses(self) -> list:
        return list(self._proxies_dict.keys())

    def countries(self) -> list:
        return list(self._proxies_df["countries"].unique())

    def collect_proxies(self) -> None:
        log.info("Collecting proxies")
        dfs = []
        for collector in (get_socksproxy_proxies, get_scrapingant_proxies):
            df = collector()
            if df is None:
                log.warning("Failed to collect proxies from this source")
            dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)
        # Identify and drop duplicates based on address and protocol
        self._proxies_df = df[~df.duplicated(subset=["ip", "port", "protocol"])]

        self._proxies_dict = {}
        for row in self._proxies_df.itertuples():
            address = f"{row.protocol}://{row.ip}:{row.port}"
            self._proxies_dict[address] = {
                "ip": row.ip,
                "port": row.port,
                "country": row.country,
                "protocol": row.protocol,
            }

        log.info(f"Collected {len(self._proxies_dict.keys())} proxies")
