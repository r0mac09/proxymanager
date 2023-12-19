import requests
from loguru import logger as log
from argparse import ArgumentParser
import re


def is_valid_proxy_url(proxy_url):
    # Define a regular expression pattern for a proxy URL
    pattern = re.compile(r'^(https?|socks[45])://(?:\S+:\S+@)?\S+:\d+$')

    # Check if the proxy URL matches the pattern
    return bool(re.match(pattern, proxy_url))


log.catch(reraise=True)
def get_ip(proxy_url="", timeout=10):
    if proxy_url:
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
    else:
        proxies = None

    response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
    if response.status_code != 200:
        response.raise_for_status()

    ip = response.json().get("origin", "")
    if not ip:
        raise ValueError(
            f"Request was successful but the returned value is invalid. proxies={proxies} response={response.json()}"
        )

    return ip, response.elapsed.total_seconds()


def is_ip_hidden_by_proxy(ip_actual, proxy_url):
    if not ip_actual:
        log.warning("Actual IP not provided. For multiple calls is prefered to pass it as parameter not to make pointless requests")
        ip_actual, _ = get_ip()

    ip_through_proy, _ = get_ip(proxy_url)

    log.debug(
        f"Checked proxy {proxy_url}: IP:{ip_actual} THROUGH_PROXY:{ip_through_proy}"
    )

    return ip_actual != ip_through_proy


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--proxy", type=str, required=True)
    parser.add_argument("-t", "--target", type=str, required=False)

    args = parser.parse_args()

    proxy_url = args.proxy
    
    if not is_valid_proxy_url(proxy_url):
        log.error("Provided proxy url is invalid")
        quit()
        
    ip_proxy = 'None'
    proxy_time = 'None'
    ip_actual, actual_time = get_ip()
    try:
        ip_proxy, proxy_time = get_ip(proxy_url)
    except requests.exceptions.ProxyError:
        log.error("Proxy error")
    except Exception as e:
        log.exception(e)
        

    print(f"STATS FROM {proxy_url}")
    print(f"CURRENT IP: {ip_actual}, response time: {actual_time}s")
    print(f"PROXY IP: {ip_proxy}, response time: {proxy_time}s")
