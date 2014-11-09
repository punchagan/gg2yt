""" Parse messages and post links to youtube. """

from __future__ import print_function

import email
import logging
from os.path import join
import re

def configure_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('yt.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

LOGGER = configure_logger()
URL_RE = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
VID_RE = re.compile('(v=(?P<query>[^&]*))|(youtu.be/(?P<path>.*))')

def get_message_text(message):
    msg = email.message_from_string(message)

    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/plain':
            text = part.get_payload()

            if 'X-Google-Groups:' in text: # email has double headers!
                text = get_message_text(text)

            break

    else:
        raise RuntimeError('No text for email ...')

    return text


def get_urls(text):
    urls = set()
    for line in text.splitlines():
        if not line.startswith('>'):
            urls.update(set(URL_RE.findall(line)))

    for url in urls:
        yield url

def get_video_id(url):
    m = VID_RE.search(url)
    if m is not None:
        return m.groupdict()['query'] or m.groupdict()['path']


def get_yt_client(username, password, developer_key):
    from gdata.youtube.service import YouTubeService
    yt = YouTubeService()
    yt.ClientLogin(username, password, 'gg2yt')
    yt.developer_key = developer_key
    return yt

def add_video_to_playlist(yt_client, playlist_id, video_id):
    playlist_uri = 'http://gdata.youtube.com/feeds/api/playlists/%s' % playlist_id
    try:
        yt_client.AddPlaylistVideoEntryToPlaylist(playlist_uri, video_id)
    except Exception as e:
        LOGGER.error('Failed to upload %s with error %s' % (video_id, e.message))


if __name__ == '__main__':
    from gg import WebSession
    from settings import (group_id, topic_id, playlist_id, username, password, developer_key)

    yt_client = get_yt_client(username, password, developer_key)

    for page_number in range(1, 33):
        session = WebSession(username, password)
        for msg_id, message in session.get_messages_in_page(group_id, topic_id, page_number):
            url_counter = 0
            message_path = join(session.cache_dir, group_id, topic_id, str(page_number), msg_id)
            LOGGER.info('Processing message - %s' % message_path)
            text = get_message_text(message)

            for url in get_urls(text):
                url_counter += 1
                video_id = get_video_id(url)
                if video_id is not None:
                    add_video_to_playlist(yt_client, playlist_id, video_id)
                    LOGGER.info('Uploading %s' % video_id)
                else:
                    LOGGER.error('Failed to parse url: %s' % url)

            if url_counter == 0:
                LOGGER.warn('No urls found in: %s' % message_path)

        session.close()
