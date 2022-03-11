import datetime
from packages.BrowserManager.BrowserServer import *
from threading import Semaphore
from selenium.webdriver.common.keys import Keys
import re
import string
import os
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from random_stuff import logging, NamedLogger, timer, create_slideshow, date_before_now, yesterday, empty_function, map_month_int

class DropBrowser(NamedLogger):
    DATE_PATTERN_ONLYFANS = "\D\D\D \d{1,2}, \d\d\d\d\n{0,1} {0,1}\d{1,2}:\d\d \D\D"
    EARNING_PATTERN_ONLYFANS = "\$\d*\.\d* [^\$]"
    DATE_PATTERN_DATETIME = "%b %d, %Y %I:%M %p"

    def __init__(self, name, browser_server : BrowserServer):
        super(DropBrowser, self).__init__(name)
        self.name = name
        self.browser_server : BrowserServer = browser_server
        self.driver, self.wait, self.stop = None, empty_function, empty_function
        self.driver : Browser = None
        self.wait : WebDriverWait = None
        # self.get_post_page()
        self.sem = Semaphore()

    @property
    def vnc_port(self) -> int :
        if self.driver :
            return self.driver.vnc_port
        return 0

    def stop_driver(self):
        with self.sem :
            self.browser_server.stop_browser(self.name)
            self.driver = None

    def start_driver(self):
        with self.sem :
            if self.driver is None :
                self.driver = self.browser_server.start_browser(
                    profile = self.name,
                    virtual = True,
                    sem = True,
                    clone_profile = False
                )
                assert self.driver is not None
                self.stop, self.wait = self.driver.stop, self.driver.wait

    def restart_driver(self):
        with self.sem :
            self.stop_driver()
            self.start_driver()

    def set_driver(self, driver):
        if self.driver is None:
            self.driver = driver
            self.wait, self.stop = self.driver.wait, self.driver.stop

    def scroll_by(self, amount: int):
        self.driver.execute_script(f"window.scrollBy(0, {amount});")

    def scroll_to(self, elem):
        ActionChains(self.driver).move_to_element(elem).perform()

    def sc(self, filename = None):
        sc = self.driver.get_screenshot_as_png()
        if isinstance(filename, str):
            with open('temp/' + filename, 'wb') as f:
                f.write(sc.encode())
        return sc

    def click_on_mid(self):
        os.system(f'DISPLAY=:{self.driver.display} xdotool mousemove 200 20 click 1')

    def click_on_left(self):
        os.system(f'DISPLAY=:{self.driver.display} xdotool mousemove 40 200 click 1')

    def get_post_page(self):
        self.driver.get("https://onlyfans.com/posts/create")

    def get_main_page(self):
        self.driver.get("https://onlyfans.com/")

    def make_post(self, img_path, post_text):
        with self.sem :
            try:
                self.get_post_page()
                try:
                    alert_object = self.driver.switch_to.alert
                    alert_object.accept()
                    self.logger.debug('alert handled')
                except BaseException as e:
                    self.logger.debug(f'can not handle alert')

                time.sleep(0.2)
                self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "l-wrapper__content")))

                try:
                    cancel_image_loading_button = self.driver.find_element(By.XPATH, "//button[@title='Delete']")
                    cancel_image_loading_button.send_keys(Keys.ENTER)
                except BaseException as e:
                    self.logger.debug('can not cancel image')

                time.sleep(0.2)
                try:
                    cancel_image_loading_button = self.driver.find_element(By.XPATH, "//button[@class='m-btn-clear-draft']")
                    cancel_image_loading_button.send_keys(Keys.ENTER)
                except BaseException as e:
                    self.logger.debug("can not clear all draft")

                time.sleep(0.2)

                try :
                    upload_image_form = self.driver.find_element(By.ID, "fileupload_photo")
                    upload_image_form.send_keys(img_path)
                    self.logger.info('found upload image form')
                except BaseException :
                    pass

                button = self.driver.find_element(By.ID, 'attach_file_photo')

                button.send_keys(Keys.ENTER)
                for i in range(5) :
                    self.driver.copy(img_path)
                time.sleep(0.7)
                self.click_on_left()
                time.sleep(0.7)
                self.driver.send_ctrlv()
                time.sleep(0.7)
                self.click_on_mid()
                time.sleep(0.5)
                self.driver.send_enter()
                time.sleep(0.5)

                self.driver.copy(post_text)
                text_field = self.wait.until(ec.element_to_be_clickable((By.ID, "new_post_text_input")))
                text_field.send_keys(Keys.CONTROL + "a")
                text_field.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                text_field.send_keys(Keys.CONTROL + "v")

                try:
                    timeout_button = self.wait.until(
                        ec.element_to_be_clickable((By.CLASS_NAME, "b-make-post__expire-period-btn")))
                    time.sleep(0.2)
                    timeout_button.send_keys(Keys.ENTER)
                    time.sleep(0.1)
                except BaseException:
                    timeout_button = None

                if timeout_button is not None:
                    self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "b-tabs__nav__item")))
                    one_day_buttton = self.driver.find_elements(By.CLASS_NAME, "b-tabs__nav__item")[1]
                    one_day_buttton.send_keys(Keys.ENTER)
                    save_button = self.wait.until(
                        ec.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save')]")))
                    save_button.send_keys(Keys.ENTER)
                    time.sleep(0.4)

                post_button = self.wait.until(ec.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Post')]")))
                # post_button = self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "m-sm-width")))
                post_button.send_keys(Keys.ENTER)
                time_waited_for_id_start = timer()
                self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "b-post")))
                time_waited_for_id_start = timer() - time_waited_for_id_start
                time_to_sleep = 7 - time_waited_for_id_start
                time_to_sleep = time_to_sleep if time_to_sleep > 0 else 0
                time.sleep(time_to_sleep)
                return self.driver.current_url
            except BaseException as e :
                self.logger.setLevel(logging.DEBUG)
                err = last_exception(limit=10000)
                # self.logger.error(err)
                try:
                    self.logger.info('trying to handle onlyfans alert')
                    button_close = self.driver.find_element(By.XPATH, "//button[contains(text, 'Close')]")
                    button_close.send_keys(Keys.ENTER)
                    time.sleep(1)
                except BaseException as e:
                    self.logger.info("can not handle onlyfans alert")

                try:
                    self.logger.info('trying to cancel image')
                    cancel_image_loading_button = self.driver.find_element(By.XPATH, "//button[@title='Delete']")
                    cancel_image_loading_button.send_keys(Keys.ENTER)
                    self.logger.info('image cancelled')
                except BaseException:
                    self.logger.info("cant cancel image")

                try:
                    make_post_error_elem = self.driver.find_element(By.CLASS_NAME, 'make_post_error')
                    self.scroll_to(make_post_error_elem)
                    make_post_error = make_post_error_elem.text
                except BaseException:
                    make_post_error = ''

                if make_post_error == '' and self.is_logout() :
                    make_post_error = 'logout'

                try:
                    sc = self.sc()
                except BaseException:
                    sc = None
                    self.logger.critical(last_exception())
                self.logger.setLevel(logging.INFO)
                raise RuntimeError(err, make_post_error, sc, self.driver.current_url)

    def enter_passwd_and_login(self, login : str, passwd : str):
        with self.sem :
            time.sleep(3)
            current = self.driver.current_url.split('?')[0]
            print(f'{self.name} : {current=}')
            if current == 'https://onlyfans.com/' :
                try:
                    login_field = self.driver.find_elements(By.NAME, "email")[0]
                    passwd_field = self.driver.find_elements(By.NAME, "password")[0]
                    self.driver.clean_field(login_field)
                    time.sleep(0.1)
                    self.driver.clean_field(passwd_field)
                    time.sleep(0.1)
                    self.driver.paste(login_field, login)
                    time.sleep(0.5)
                    self.driver.paste(passwd_field, passwd)
                except BaseException as e:
                    print(f'{self.driver.name}, so not loging in ')

                print(f'{self.driver.name} : {current=}, entered')
            else:
                print(f'{self.driver.name} : {current=}, so not loging in ')

    def open_fc(self, load = True):
        if load :
            self.get_main_page()
        button = self.driver.wait.until(ec.element_to_be_clickable(
            (By.XPATH, '//button[@class="l-header__menu__item m-avatar-item m-avatar-item"]')))
        button.send_keys(Keys.ENTER)

    def get_tag(self, load = True) -> str :
        if load :
            self.open_fc()
        time.sleep(0.1)
        return '@' + self.driver.find_element(By.CLASS_NAME, 'g-user-realname__wrapper').get_attribute('href').split('/')[-1].strip()

    def record_proof(self, links):
        before = timer()
        with self.sem :
            t = timer()
            self.logger.info(f'recording proof, {len(links)=}')
            for tries in range(3) :
                try :
                    self.open_fc()
                    break
                except BaseException :
                    if self.is_logout() :
                        self.logger.critical('LOGOUT ENCOUNTERED WHILE RECORDING PROOF')
                        raise RuntimeError('logout', self.sc())
                    self.logger.info(f'trial {tries} to open fc')
            time.sleep(3)
            sc = [self.sc()]
            for j, link in enumerate(links) :
                for tries in range(3) :
                    try :
                        self.driver.get(link)
                        # self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "l-wrapper__content")))
                        self.wait.until(ec.element_to_be_clickable((By.ID, f"postId_{link.split('/')[-2]}")))
                        time.sleep(1)
                        sc.append(self.sc())
                        break
                    except BaseException :
                        self.logger.critical(last_exception())
            self.logger.info(f'time spent while recording proof : {timer() - t}, time spent waiting for semaphore : {t - before}, amount of sc : {len(sc)}')
            slideshow = create_slideshow(
                sc,
                (500, 700),
                image_format='.jpg',
                audio_path='./resources/noice.ogg',
            )
            return slideshow, sc

    def is_logout(self) -> bool :
        try :
            return bool({self.driver.find_elements(By.NAME, "email")[0], self.driver.find_elements(By.NAME, "password")[0]})
        except BaseException :
            return False

    def get_monthly_stats(self) :
        with self.sem :
            stats_link = 'https://onlyfans.com/my/stats/earnings'
            for trial_to_get_monthly_stats in range(3) :
                self.logger.info(f'{trial_to_get_monthly_stats = }')
                try:
                    res = []
                    self.driver.get(stats_link)
                    self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, 'b-stats-row')))
                    time.sleep(3)
                    stats_rows = self.driver.find_elements(By.CLASS_NAME, 'b-stats-row')
                    assert stats_rows
                    for row in stats_rows[1:]:
                        txt = row.text.strip().replace(',', '').split()
                        res.append({
                            'month_str_full': txt[0],
                            'month_str_short': txt[0][:3].lower(),
                            'month_int': map_month_int[txt[0][:3].lower()],
                            'year': int(txt[1]),
                            'net': float(txt[2][1:])
                        })
                    return res
                except BaseException:
                    self.logger.critical(last_exception())
            return []

    def count_subs(self):
        with self.sem :
            for tries in range(3) :
                self.logger.info(f'counting subs {tries=}')
                try :
                    for tries in range(3) :
                        try :
                            self.driver.get('https://onlyfans.com/my/notifications/subscribed')
                            self.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "g-date")))
                            break
                        except BaseException :
                            if tries == 2 :
                                raise RuntimeError('loading page error', last_exception(limit=10000000))

                    time.sleep(1)
                    nb_iterations_limit, nb_pointless_scrolls, max_nb_pointless_scrolls, nb_ending_scrolls, max_nb_ending_scrolls, prev_date_text = 500, 0, 30, 0, 10, ''
                    for i in range(nb_iterations_limit) :
                        pointless = False
                        try :
                            last_div = self.wait.until(ec.element_to_be_clickable((By.XPATH, "//div[@class='b-notifications__list__item'][last()]")))
                            date_text = last_div.text.lower().split('subscribed to your profile!')[1].split('\n')[1]
                            if ('yesterday' not in date_text and 'ago' not in date_text) :
                                nb_ending_scrolls += 1
                                if nb_ending_scrolls >= max_nb_ending_scrolls :
                                    break
                            else :
                                nb_ending_scrolls = 0
                        except BaseException :
                            date_text = ''
                            pointless = True

                        if pointless or date_text == prev_date_text :
                            nb_pointless_scrolls += 1
                            if nb_pointless_scrolls > max_nb_pointless_scrolls:
                                break
                        else :
                            nb_pointless_scrolls = 0

                        prev_date_text = date_text
                        self.scroll_by(1000)
                        time.sleep(0.5)

                    try :
                        table = self.driver.find_element(By.XPATH, '//div[@class="b-notifications__list"]')
                    except BaseException :
                        continue
                    table_text = table.text.lower()
                    parsed_table = ['y' if 'yesterday' in a else 'a' for a in
                                    [a.split('\n')[1] for a in table_text.split('subscribed to your profile!') if
                                     ('ago' in a or 'yesterday' in a) and '\n' in a]]
                    return parsed_table.count('y'), parsed_table.count('a'), len(parsed_table)
                except BaseException :
                    self.logger.error(f'exception while counting subs(returning 0 0 0) {last_exception(limit=100000000)}')
            return 0, 0, 0

    def get_table(self):
        for n in range(5):
            if self.driver.current_url == 'https://onlyfans.com/my/statements/earnings':
                for i in range(30):
                    try:
                        return self.driver.find_element(By.CLASS_NAME, "m-earnings")
                    except BaseException:
                        time.sleep(0.2)
            else:
                self.get_earnings_page()
        raise RuntimeError('can not get table')

    def get_last_row(self):
        return self.get_table().find_element(By.XPATH, ".//tr[.//td[@class='b-table__date']][last()]")

    def get_earnings_page(self):
        self.driver.get('https://onlyfans.com/my/statements/earnings')

    def get_table_text(self):
        for i in range(50):
            text = self.get_table().text
            if string.capwords(text) != '':
                return text
            time.sleep(0.2)

    def get_returned_rows_text(self):
        return [a.text for a in self.driver.find_elements(By.XPATH, "//tr[.//*[local-name()='use' and @*[local-name()='href']='#icon-undo']]")]

    def count_gains(self):
        with self.sem :
            for trials in range(3) :
                self.logger.info(f'couting gains {trials=}')
                begin, end = yesterday(), date_before_now(minutes = 1)
                try:
                    prev_last_row, current_last_row = None, None
                    nb_no_update_in_a_row = 0
                    max_nb_no_update_in_a_row = 10
                    seconds_wait_if_no_update = 1
                    self.driver.get('https://onlyfans.com/my/statements/earnings')
                    self.get_table_text()
                    for i in range(4000):
                        self.scroll_by(10000000)
                        current_last_row = self.get_last_row().text
                        if self.parse_row(current_last_row)['date'] <= begin :
                            self.logger.info(f'updated to : {begin}, number of paginations : {i}')
                            break

                        if current_last_row == prev_last_row:
                            nb_no_update_in_a_row += 1
                            if nb_no_update_in_a_row == max_nb_no_update_in_a_row:
                                self.logger.info('too much updateless scrolls in a row')
                                break
                            time.sleep(seconds_wait_if_no_update)
                        else:
                            nb_no_update_in_a_row = 0
                            prev_last_row = current_last_row

                    table_text = self.get_table_text()
                    returned_rows = [string.capwords(a).lower() for a in self.get_returned_rows_text()]
                    if returned_rows :
                        self.logger.info(f'{returned_rows=}')
                    data = self.parse_table(table_text, returned_rows)
                    filtered = list(filter(lambda row: end >= row['date'] > begin, data))
                    return filtered
                except BaseException:
                    e = last_exception(10000)
                    self.logger.critical(e)

    def parse_table(self, table, excepted_rows=()):
        data = re.findall(self.DATE_PATTERN_ONLYFANS + ".*\n", table.lower() + "\n")
        data = [self.parse_row(d) for d in data]
        indexes_to_delete = []
        for j, row in enumerate(data):
            s = row['str']
            if s in excepted_rows:
                self.logger.info(f'{s} is excepted')
                indexes_to_delete.append(j)
                excepted_rows.pop(excepted_rows.index(s))

        for deleted_counter, index_to_delete in enumerate(indexes_to_delete):
            data.pop(index_to_delete - deleted_counter)
        return data

    def parse_row(self, row):
        row = row.lower()
        res = {
            "str": string.capwords(row).lower(),
            "date": datetime.datetime.strptime(re.findall(self.DATE_PATTERN_ONLYFANS, row)[0],
                                               self.DATE_PATTERN_DATETIME),
            "earning": float(re.findall(self.EARNING_PATTERN_ONLYFANS, row)[0][1:-1]),
            'type': ['tip', 'msg', 'sub', 'post'][[a in row for a in
                                                   ['tip from', 'payment for message from', 'subscription from',
                                                    'purchase by']].index(True)]
        }
        return res

    def get_fc(self):
        with self.sem :
            for tries in range(5) :
                self.logger.info(f'getting fc {tries=}')
                try :
                    self.driver.get('https://onlyfans.com/my/subscribers/active')
                    self.driver.wait.until(ec.element_to_be_clickable((By.CLASS_NAME, "b-tabs__nav__text")))
                    time.sleep(1)
                    active_label = self.driver.find_elements(By.CLASS_NAME, "b-tabs__nav__text")[1]
                    return int(active_label.text.split()[-1])
                except BaseException :
                    err = last_exception(2332132132312)
                    self.logger.critical(err)
            return None
