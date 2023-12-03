import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger as log
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def table_to_df(table: BeautifulSoup, names_in_first_row=False) -> pd.DataFrame:
    data = []
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["th", "td"])
        data.append([cell.text.strip() for cell in cells])

    col_names = data[0] if names_in_first_row else None
    if names_in_first_row:
        data = data[1:]

    return pd.DataFrame(data, columns=col_names)


def socks_fix(x):
    if x.startswith("socks"):
        return x + "h"
    return x


def get_scrapingant_proxies():
    def clean_country(x):
        if x != "Unknown":
            x = x[3:]
        return x

    log.info("Collecting proxies from scrapingant.com ...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")

    with webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    ) as driver:
        driver.get("https://scrapingant.com/free-proxies")
        try:
            # Wait until the table is loaded
            element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "proxies-table"))
            )
            html_content = element.get_attribute("innerHTML")
        except Exception as e:
            log.exception(e)
            return None

    table = BeautifulSoup(html_content, "html.parser")

    df = table_to_df(table, True)

    # Drop columns that would not be used
    df.drop(["Last Checked"], inplace=True, axis=1)

    # Rename columns to appropriate values
    df.rename(
        columns={
            "IP": "ip",
            "Port": "port",
            "Country": "country",
            "Protocol": "protocol",
        },
        inplace=True,
    )

    # Remove the country unicode emoji if exists
    df["country"] = df["country"].apply(clean_country)

    # Changing protocols to be all uppercase and remove SOCKS version
    df["protocol"] = df["protocol"].str.lower().apply(socks_fix)

    return df


def get_socksproxy_proxies():
    log.info("Collecting proxies from socks-proxy.net ...")
    response = requests.get("https://www.socks-proxy.net/")
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the table in page, in this case it should be the first table
    table = soup.findAll("table")[0]
    if not table:
        log.error("Failed to find table")

    df = table_to_df(table, True)

    # Drop columns that would not be used
    df.drop(["Code", "Anonymity", "Last Checked", "Https"], inplace=True, axis=1)

    # Rename columns to appropriate values
    df.rename(
        columns={
            "IP Address": "ip",
            "Port": "port",
            "Country": "country",
            "Version": "protocol",
        },
        inplace=True,
    )

    # Changing protocols to be all uppercase and remove SOCKS version
    df["protocol"] = df["protocol"].str.lower().apply(socks_fix)

    return df


def get_freeproxylist_proxies():
    dfs = []
    for url in [
        "https://www.us-proxy.org/",
        "https://www.sslproxies.org/",
        "https://free-proxy-list.net/",
        "https://free-proxy-list.net/uk-proxy.html",
        "https://free-proxy-list.net/anonymous-proxy.html",
        "https://www.google-proxy.net/",
    ]:
        log.info(f"Collecting proxies from {url} ...")
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        # Find the table in page, in this case it should be the first table
        table = soup.findAll("table")[0]
        if not table:
            log.error("Failed to find table")

        df = table_to_df(table, True)

        # Drop columns that would not be used
        df.drop(["Code", "Anonymity", "Google", "Last Checked"], inplace=True, axis=1)

        # Rename columns to appropriate values
        df.rename(
            columns={
                "IP Address": "ip",
                "Port": "port",
                "Country": "country",
                "Https": "protocol",
            },
            inplace=True,
        )

        df["protocol"] = df["protocol"].apply(
            lambda x: "http" if x == "no" else "https"
        )

        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)


def get_proxylist_proxies():
    tmp_dir = Path("./.tmp")
    tmp_dir.mkdir(exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")

    # Set up Chrome options to automatically download files to a specific folder
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(tmp_dir.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    # The onclick function we are looking for
    onclick_function = "bnjsonn();"

    # Set a download timeout
    timeout = 10

    expected_file = tmp_dir / "Proxy List.json"

    dfs = []
    for url in [
        "https://www.proxy-list.download/HTTP",
        "https://www.proxy-list.download/HTTPS",
        "https://www.proxy-list.download/SOCKS4",
        "https://www.proxy-list.download/SOCKS5",
    ]:
        log.info(f"Collecting proxies from {url} ...")
        driver.get(url)
        try:
            # Use JavaScript to find the element by onclick attribute
            button = driver.execute_script(
                f"return document.querySelector('[onclick=\"{onclick_function}\"]');"
            )

            # Click the button to download the file
            button.click()

            start_time = time.time()
            while not expected_file.is_file():
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Download from {url} timed out")
                time.sleep(0.5)
        except Exception as e:
            log.exception(e)
            continue

        # Load the file into a dataframe
        df = pd.DataFrame(json.load(expected_file.open("r")))

        # Remove the file once it has been loaded
        os.remove(expected_file)

        df.drop(["ANON", "ISO", "PING"], inplace=True, axis=1)

        df.rename(
            columns={
                "IP": "ip",
                "PORT": "port",
                "COUNTRY": "country",
            },
            inplace=True,
        )

        protocol = url.split("/")[-1].lower()
        if protocol.startswith("socks"):
            protocol += "h"

        df["protocol"] = [protocol] * len(df)

        dfs.append(df)

    # Close the driver
    driver.quit()

    return pd.concat(dfs, ignore_index=True)
