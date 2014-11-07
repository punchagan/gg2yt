#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    newschimp.social.gg
    ~~~~~~~~~~~~~~~~~~~

    Google Group curator

    :author: Martin Putniorz
    :year: 2014

Terminology:
    - topic :: each thread of emails
    - post/message :: an individual email.

'''

import gettext
import logging
from datetime import date
import json
from os.path import exists, join
from urllib.request import quote

import click
from selenium import webdriver
from selenium.common import exceptions

t = gettext.translation('gg', 'locale', fallback=True)
_ = t.gettext

MONTHS = {
    _('january'): 1,
    _('february'): 2,
    _('march'): 3,
    _('april'): 4,
    _('may'): 5,
    _('june'): 6,
    _('july'): 7,
    _('august'): 8,
    _('september'): 9,
    _('october'): 10,
    _('november'): 11,
    _('december'): 12,
}

GOOGLE_GROUP_BASE = 'https://groups.google.com/forum/'
GOOGLE_GROUP_URL = GOOGLE_GROUP_BASE + '#!forum/{}'
GOOGLE_GROUP_RAW_URL = GOOGLE_GROUP_BASE + 'message/raw?msg={}/{}/{}'
#fixme: move to settings, later...
COOKIES_FILE = 'cookies.txt'
COOKIES_FILE_ARG = '--cookies-file=%s' % COOKIES_FILE

LOGGER = logging.getLogger(__name__)

def date_parse(raw_date):
    '''Make some sense for default Group datetime string'''
    tokens = raw_date.split()
    day = int(tokens[1].strip('.'))
    month = MONTHS[tokens[2].lower()]
    year = int(tokens[3])
    return date(year, month, day)


class WebSession():

    def __init__(self, username, password):
        self.browser = webdriver.PhantomJS(service_args=[COOKIES_FILE_ARG])
        self.browser.set_window_size(1024, 768)
        self.username = username
        self.password = password
        self.cache_dir = 'cache'
        self.cache_index = join(self.cache_dir, 'cache.json')
        self._cache_data = self._read_cache()

    def login(self):
        # fixme: this url means we are always prompted to login...
        url = 'https://www.google.com/a/UniversalLogin?continue=%s' % quote(GOOGLE_GROUP_BASE)
        browser = self.browser
        username = self.username
        password = self.password

        self.browser.get(url)

        if 'sign in' in browser.title.lower():
            email = browser.find_element_by_css_selector('#Email')
            passwd = browser.find_element_by_css_selector('#Passwd')
            signin = browser.find_element_by_css_selector('#signIn')

            if email.is_displayed():
                email.send_keys(username)
            passwd.send_keys(password)
            signin.click()

    def click_adult_warning_if_appeared(self):
        try:
            adult = self.browser.find_element_by_partial_link_text(
                'do not want to view this content'
            )
        except exceptions.NoSuchElementException:
            return False

        else:
            # click proceed
            proceed = adult.find_element_by_xpath('../../span/*/input/../span')
            proceed.click()
        return True

    def close(self):
        self.browser.quit()

    def get_message_urls(self, group_id, topic_id, page_number=1):
        message_ids = self._get_message_ids_from_cache(
            group_id, topic_id, page_number
        )

        if message_ids is None:
            page_url = self._get_page_url(group_id, topic_id, page_number)
            self.browser.get(page_url)
            self.click_adult_warning_if_appeared()
            message_ids = self._get_message_ids_on_page()

        message_urls = [
            GOOGLE_GROUP_RAW_URL.format(group_id, topic_id, message_id)
            for message_id in message_ids
        ]

        self._put_message_ids_in_cache(
            group_id, topic_id, page_number, message_ids
        )

        return message_urls

    def _get_message_ids_from_cache(self, group_id, topic_id, page_number):
        topic_cache = self._cache_data.get(group_id, {}).get(topic_id, {})
        message_ids = topic_cache.get(str(page_number), [])
        return message_ids if len(message_ids) == 25 else None

    def _put_message_ids_in_cache(self, group_id, topic_id, page_number, message_ids):
        new_data = {group_id: {topic_id: {page_number: message_ids}}}
        self._cache_data.update(new_data)
        self._save_cache()

    def _get_message_ids_on_page(self):
        posts = self.browser.find_elements_by_xpath('//table[@role="listitem"]')
        message_snippets = [
            post.find_element_by_xpath(
                './/span[@role="gridcell" and contains(@id, "message_snippet")]'
            )

            for post in posts
        ]

        n = len('message_snippet_')
        message_ids = [
            message.get_attribute('id')[n:] for message in message_snippets
        ]

        return message_ids

    def _get_page_url(self, group_id, topic_id, page_number):
        topic_url = GOOGLE_GROUP_URL.format(group_id).replace('#!forum', '#!topic')
        start, end = (page_number-1) * 25 + 1, page_number * 25
        topic_path = '/{}/discussion[{}-{}-false]'.format(topic_id, start, end)
        return topic_url + quote(topic_path)

    def _read_cache(self):
        if exists(self.cache_index):
            with open(self.cache_index) as f:
                data = json.load(f)
        else:
            data = {}

        return data

    def _save_cache(self):
        with open(self.cache_index, 'w') as f:
            json.dump(self._cache_data, f, indent=2)


@click.command()
@click.option('--group', help='Group ID')
@click.pass_context
def cli(ctx, group):
    '''Google Groups curator'''

    #from getpass import getpass

    username = 'punchagan'
    password = '' #getpass('Password for %s@gmail.com: ' % username)
    session = WebSession(username, password)
    # fixme: parse cookie file, and check if we need to login?
    # or try going to page, detect error and then call login.
    # session.login()
    print(session.get_message_urls(group, '4JaKHpOy__o', 1))
    session.close()
