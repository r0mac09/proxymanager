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
            element = WebDriverWait(driver, 10).until(
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
