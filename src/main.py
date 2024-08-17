import time
import traceback
import asyncio
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from telegram import Bot
import logging

# Load configuration from config.yaml
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")

# Extract configurations from YAML
TELEGRAM_BOT_TOKEN = config["telegram"]["bot_token"]
CHAT_ID = config["telegram"]["user"]
USERNAME = config["credentials"]["username"]
PASSWORD = config["credentials"]["password"]
CHECK_INTERVAL = config["settings"]["check_interval"]
LOGIN_URL = config["portal"]["login_url"]
SERVICES = config["portal"]["services"]

# Initialize the Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)


# Function to check appointment availability
def check_appointments(driver, service):
    # Navigate to the login page
    driver.get(LOGIN_URL)

    # Wait for the login input field to be present
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "Login")))

    # Find the username and password fields
    username_field = driver.find_element(By.ID, "Login")
    password_field = driver.find_element(By.ID, "Password")

    # Enter your credentials
    username_field.send_keys(USERNAME)
    password_field.send_keys(PASSWORD)

    # Find and click the submit button
    login_button = driver.find_element(By.ID, "LoginSubmit")
    login_button.click()

    skierowania_button = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "//span[text()='Skierowania']/ancestor::app-shortcut-item")
        )
    )

    # Click the "Skierowania" button
    skierowania_button.click()

    okulistra_text_element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, f"//span[text()='{service}']"))
    )

    # Navigate up to the parent div that contains the button
    parent_div = okulistra_text_element.find_element(
        By.XPATH, "./ancestor::div[contains(@class, 'top')]"
    )

    # Now find the "Umów" button within this div
    umow_button = parent_div.find_element(By.XPATH, ".//button[@id='buttonBookTerm']")

    # Scroll the button into view
    driver.execute_script("arguments[0].scrollIntoView(true);", umow_button)

    # Optionally, wait a moment to ensure scrolling is completed
    WebDriverWait(driver, 1).until(
        EC.element_to_be_clickable((By.XPATH, ".//button[@id='buttonBookTerm']"))
    )

    # Use JavaScript to click the button
    driver.execute_script("arguments[0].click();", umow_button)

    # Wait until the "Szukaj" button is clickable
    szukaj_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Szukaj')]"))
    )

    # Scroll the button into view (optional)
    driver.execute_script("arguments[0].scrollIntoView(true);", szukaj_button)

    # Click the button
    szukaj_button.click()

    time.sleep(5)  # Allow time for content to load

    # Extract the page source after the appointments are loaded
    page_source = driver.page_source

    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(page_source, "html.parser")

    # Find all elements that contain appointment details
    terms = soup.find_all("app-term", class_="ng-star-inserted")

    appointments = []
    for term in terms:
        t = term.find("div", class_="time").text.strip()
        date_element = term.find_parent("app-terms-in-day")
        date = (
            date_element.find("div", class_="card-header-content")
            .find("span", class_="d-none d-xl-inline font-weight-bold")
            .text.strip()
        )
        address = term.find("span", class_="map-touch").find("span").text.strip()

        appointments.append((date, t, address))

    return appointments


# Function to send messages via Telegram bot
async def send_telegram_message(service, appointments):
    message = f"""
    Service: {service}
    Dates: {set(x[0] for x in appointments)}
    Time: {set(x[1] for x in appointments)}
    Address: {set(x[2] for x in appointments)}
    """
    await bot.send_message(chat_id=CHAT_ID, text=message)


# Main monitoring loop
async def monitor_appointments():
    while True:
        try:
            for service in SERVICES:
                # Set up the web driver
                driver = webdriver.Chrome()
                appointments = check_appointments(driver, service)
                if appointments:
                    await send_telegram_message(service, appointments)
        except KeyboardInterrupt:
            logging.info("Monitoring stopped.")
            break
        except Exception:
            traceback.print_exc()
            pass
        finally:
            driver.quit()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(monitor_appointments())
