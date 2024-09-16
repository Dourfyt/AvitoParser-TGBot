import os
import random
import time
import sqlite3
import threading
import csv
import re
from notifiers.logging import NotificationHandler
from seleniumbase import SB
from loguru import logger
from locator import LocatorAvito


class AvitoParse:
    """
    Парсинг  товаров на avito.ru
    """

    def __init__(self,
                 urls: list,
                 keysword_list: list,
                 count: int = 10,
                 tg_token: str = None,
                 max_price: int = 0,
                 min_price: int = 0,
                 geo: str = None,
                 debug_mode: int = 0,
                 check_comission: int = 0):
        self.urls = urls  # список URL
        self.keys_word = keysword_list
        self.count = count
        self.data = []
        self.tg_token = tg_token
        self.title_file = self.__get_file_title()
        self.max_price = int(max_price)
        self.min_price = int(min_price)
        self.geo = geo
        self.debug_mode = debug_mode
        self.check_comission = 0

    def __get_url(self):
        self.driver.open(self.url)

        if "Доступ ограничен" in self.driver.get_title():
            time.sleep(2)
            raise Exception("Перезапуск из-за блокировки IP")

        self.driver.open_new_window()  # сразу открываем и вторую вкладку
        self.driver.switch_to_window(window=0)

    def __paginator(self):
        """Кнопка далее"""
        logger.info('Страница успешно загружена. Просматриваю объявления')
        self.__create_file_csv()
        while self.count > 0:
            self.__parse_page()
            time.sleep(random.randint(5, 7))
            """Проверяем есть ли кнопка далее"""
            if self.driver.find_elements(LocatorAvito.NEXT_BTN[1], by="css selector"):
                self.driver.find_element(LocatorAvito.NEXT_BTN[1], by="css selector").click()
                self.count -= 1
                logger.debug("Следующая страница")
            else:
                logger.info("Нет кнопки дальше")
                break

    def __check_comission(self, text):
        if "без комиссии" in text.lower():
            return True
        else:
            return False
        

    @logger.catch
    def __parse_page(self):
        """Парсит открытую страницу"""

        """Ограничение количества просмотренных объявлений"""
        if os.path.isfile('viewed.txt'):
            with open('viewed.txt', 'r') as file:
                self.viewed_list = list(map(str.rstrip, file.readlines()))
                if len(self.viewed_list) > 5000:
                    self.viewed_list = self.viewed_list[-900:]
        else:
            with open('viewed.txt', 'w') as file:
                self.viewed_list = []

        titles = self.driver.find_elements(LocatorAvito.TITLES[1], by="css selector")
        items = []
        for title in titles:
            time.sleep(1)
            name_element = title.find_element(*LocatorAvito.NAME)
            name = name_element.text if name_element else "Без названия"
            if title.find_elements(*LocatorAvito.DESCRIPTIONS):
                description = title.find_element(*LocatorAvito.DESCRIPTIONS).text
            else:
                description = ''

            url = title.find_element(*LocatorAvito.URL).get_attribute("href")
            price = title.find_element(*LocatorAvito.PRICE).get_attribute("content")
            comission = title.find_element(*LocatorAvito.COMISSION).text
            ads_id = title.get_attribute("data-item-id")
            items.append({
                'name': name,
                'description': description,
                'comission' : comission,
                'url': url,
                'price': price,
                'ads_id': ads_id
            })

        for data in items:
            ads_id = data.pop('ads_id')
            name = data.get('name')
            description = data.get('description')
            comission = data.get('comission')
            url = data.get('url')
            price = data.get('price')
            if self.is_viewed(ads_id):
                continue
            self.viewed_list.append(ads_id)
            
            # """Проверяем комиссию"""
            # if self.check_comission == 1 and self.__check_comission(comission):
                
            """Определяем нужно ли нам учитывать ключевые слова"""
            if self.keys_word != ['']:
                if any([item.lower() in (description.lower() + name.lower()) for item in self.keys_word]) \
                        and \
                        self.min_price <= int(
                    price) <= self.max_price:
                    self.data.append(self.__parse_full_page(url, data))
                    """Проверка адреса если нужно"""
                    if self.geo and self.geo.lower() not in self.data[-1].get("geo", self.geo.lower()):
                        continue
                    """Отправляем в телеграм"""
                    self.__pretty_log(data=data)
                    self.__save_data(data=data)
            elif self.min_price <= int(price) <= self.max_price:

                self.data.append(self.__parse_full_page(url, data))
                """Проверка адреса если нужно"""
                if self.geo and self.geo.lower() not in self.data[-1].get("geo", self.geo.lower()):
                    continue
                """Отправляем в телеграм"""
                self.__pretty_log(data=data)
                self.__save_data(data=data)
            else:
                continue
        # else:
        #     continue

    def __pretty_log(self, data):
        """Красивый вывод"""
        logger.success(
            f'\n{data.get("name", "-")}\n'
            f'Цена: {data.get("price", "-")}\n'
            f'Описание: {data.get("description", "-")[:30]}\n'
            f'Просмотров: {data.get("views", "-")}\n'
            f'Дата публикации: {data.get("date_public", "-")}\n'
            f'Продавец: {data.get("seller_name", "-")}\n'
            f'Ссылка: {data.get("url", "-")}\n')

    def __parse_full_page(self, url: str, data: dict) -> dict:
        """Парсит для доп. информации открытое объявление на отдельной вкладке"""
        self.driver.switch_to_window(window=1)
        self.driver.get(url)

        """Если не дождались загрузки"""
        try:
            self.driver.wait_for_element(LocatorAvito.TOTAL_VIEWS[1], by="css selector", timeout=10)
        except Exception:
            """Проверка на бан по ip"""
            if "Доступ ограничен" in self.driver.get_title():
                logger.success("Доступ ограничен: проблема с IP. \nПоследние объявления будут без подробностей")

            self.driver.switch_to_window(window=0)
            logger.debug("Не дождался загрузки страницы")
            return data

        """Гео"""
        if self.geo and self.driver.find_elements(LocatorAvito.GEO[1], by="css selector"):
            geo = self.driver.find_element(LocatorAvito.GEO[1], by="css selector").text
            data["geo"] = geo.lower()

        """Количество просмотров"""
        if self.driver.find_elements(LocatorAvito.TOTAL_VIEWS[1], by="css selector"):
            total_views = self.driver.find_element(LocatorAvito.TOTAL_VIEWS[1]).text.split()[0]
            data["views"] = total_views

        """Дата публикации"""
        if self.driver.find_elements(LocatorAvito.DATE_PUBLIC[1], by="css selector"):
            date_public = self.driver.find_element(LocatorAvito.DATE_PUBLIC[1], by="css selector").text
            if "· " in date_public:
                date_public = date_public.replace("· ", '')
            data["date_public"] = date_public

        """Имя продавца"""
        if self.driver.find_elements(LocatorAvito.SELLER_NAME[1], by="css selector"):
            seller_name = self.driver.find_element(LocatorAvito.SELLER_NAME[1], by="css selector").text
            data["seller_name"] = seller_name

        """Возвращается на вкладку №1"""
        self.driver.switch_to_window(window=0)
        return data

    def is_viewed(self, ads_id: str) -> bool:
        """Проверяет, смотрели мы это или нет"""
        if ads_id in self.viewed_list:
            return True
        return False

    def __save_data(self, data: dict):
        """Сохраняет результат в файл keyword*.csv"""
        with open(f"result/{self.title_file}.csv", mode="a", newline='', encoding='utf-8', errors='ignore') as file:
            writer = csv.writer(file)
            writer.writerow([
                data.get("name", '-'),
                data.get("price", '-'),
                data.get("url", '-'),
                data.get("description", '-'),
                data.get("views", '-'),
                data.get("date_public", '-'),
                data.get("seller_name", 'no'),
                data.get("geo", '-')
            ])

        """сохраняет просмотренные объявления"""
        with open('viewed.txt', 'w') as file:
            for item in set(self.viewed_list):
                file.write("%s\n" % item)

    @property
    def __is_csv_empty(self) -> bool:
        """Пустой csv или нет"""
        os.makedirs(os.path.dirname("result/"), exist_ok=True)
        try:
            with open(f"result/{self.title_file}.csv", 'r', encoding='utf-8', errors='ignore') as file:
                reader = csv.reader(file)
                try:
                    # Попытка чтения первой строки
                    next(reader)
                except StopIteration:
                    # файл пустой
                    return True
                return False
        except FileNotFoundError:
            return True

    @logger.catch
    def __create_file_csv(self):
        """Создает файл и прописывает названия если нужно"""

        if self.__is_csv_empty:
            with open(f"result/{self.title_file}.csv", 'a', encoding='utf-8', errors='ignore') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Название",
                    "Цена",
                    "Ссылка",
                    "Описание",
                    "Просмотров",
                    "Дата публикации",
                    "Продавец",
                    "Адрес"
                ])

    def __get_file_title(self) -> str:
        """Определяет название файла"""
        if self.keys_word != ['']:
            title_file = "-".join(list(map(str.lower, self.keys_word)))

        else:
            title_file = 'all'
        return title_file

    def parse(self):
        """Метод для вызова парсинга"""
        chrome_args = [
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
            "--disable-blink-features=AutomationControlled",  # Скрытие автоматизации
            f"--proxy-server=http://{proxy}"  # Использование прокси
        ]
        
        for url in self.urls:  # проход по каждому URL
            try:
                self.count = 1
                with SB(uc=True,
                        browser="chrome",
                        headed=True if self.debug_mode else False,
                        headless=True if not self.debug_mode else False,
                        page_load_strategy="eager",
                        block_images=True,
                        proxy=proxy,
                        undetectable=True,
                        chromium_arg=chrome_args,
                        incognito=True,
                        ad_block_on=True
                        ) as self.driver:
                    
                    # Отключение автоматизации через JS
                    self.driver.execute_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
                    )
                    self.driver.execute_script("""
                        var getContext = HTMLCanvasElement.prototype.getContext;
                        HTMLCanvasElement.prototype.getContext = function() {
                            if (arguments[0] === 'webgl' || arguments[0] === 'experimental-webgl') {
                                return null;
                            }
                            return getContext.apply(this, arguments);
                        };
                    """)

                    # Установка текущего URL для парсинга
                    self.url = url  
                    self.__get_url()  # Загрузка страницы
                    self.__paginator()  # Пагинация и сбор данных
                    logger.info(f"Парсинг завершен для {url}")
            
            except Exception as error:
                logger.error(f"Ошибка при обработке {url}: {error}")


def monitor_database():
    """Функция мониторинга базы данных для обновления списка URL-ов и пользователей"""
    previous_persons = set()  # Множество для хранения предыдущего списка пользователей

    while True:
        try:
            time.sleep(15)  # Задержка на проверку: раз в 15 секунд
            db = sqlite3.connect('users.db')
            current_persons = {row[0] for row in db.execute('SELECT chat_id FROM Users ORDER BY rowid').fetchall()}
            global urls
            urls = [row[0] for row in db.execute('SELECT URL FROM URLS ORDER BY rowid').fetchall()]
            # Проверка новых пользователей
            for person in current_persons:
                if person not in added:
                    if token and person:
                        params = {
                            'token': token,
                            'chat_id': person
                        }
                        tg_handler = NotificationHandler("telegram", defaults=params)

                        """Все логи уровня SUCCESS и выше отсылаются в телегу"""
                        handler_id = logger.add(tg_handler, level="SUCCESS", format="{message}")
                        print(f"Хендлер добавлен для {person} с id {handler_id}")
                        added[person] = handler_id  # Сохраняем идентификатор хендлера для последующего удаления
            
            # Проверка удаленных пользователей
            removed_persons = previous_persons - current_persons
            for removed_person in removed_persons:
                if removed_person in added:
                    handler_id = added[removed_person]
                    logger.remove(handler_id)  # Удаляем хендлер по идентификатору
                    print(f"Хендлер удален для {removed_person} с id {handler_id}")
                    del added[removed_person]  # Удаляем пользователя из словаря

            # Обновляем список предыдущих пользователей
            previous_persons = current_persons

            db.close()  # Закрываем соединение с базой данных
            return urls
        except Exception as e:
            print(e)
            continue

def main():
    import configparser

    config = configparser.ConfigParser(interpolation=None)
    config.read("settings.ini")  # читаем конфиг
    monitor_thread = threading.Thread(target=monitor_database)
    monitor_thread.start()
    global token
    global added
    added = {}
    global proxy
    proxy = config["Avito"]["PROXY"]
    token = config["Avito"]["TG_TOKEN"]
    num_ads = config["Avito"]["NUM_ADS"]
    freq = config["Avito"]["FREQ"]
    keys = config["Avito"]["KEYS"]
    max_price = config["Avito"].get("MAX_PRICE", "0") or "0"
    min_price = config["Avito"].get("MIN_PRICE", "0") or "0"
    geo = config["Avito"].get("GEO", "") or ""

    while True:
        try:
            urls = monitor_database()
            driver = AvitoParse(
                urls=urls,  # Передаем текущий URL в виде списка
                count=int(num_ads),
                keysword_list=keys.split(","),
                max_price=int(max_price),
                min_price=int(min_price),
                geo=geo
            )
            driver.parse()  # Парсим каждый URL
            logger.info(f"Завершен парсинг для URL: {urls}")
        except Exception as error:
            logger.error(f"Ошибка при парсинге URL {urls}: {error}")
            logger.error('Произошла ошибка, но работа будет продолжена через 30 сек. '
                            'Если ошибка повторится несколько раз - перезапустите скрипт.'
                            'Если и это не поможет - обратитесь к разработчику по ссылке ниже')
            time.sleep(30)  # Пауза перед следующей попыткой
        logger.info("Пауза перед следующим циклом")
        time.sleep(int(freq) * 60)

if __name__ == "__main__":
    main()