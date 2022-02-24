from requests_html import HTMLSession
from collections import deque
from .preprocessor import encode_url
from django.contrib.staticfiles import finders
import os
import pickle
import atexit
import threading
import time


URL_PREFIX = 'https://www.bbc.com'
STARTING_POINT = '/news/world-us-canada-57065381'
VALID_ROOT = '/news'
RESULTS_DIR = finders.find('svd/bbc_data')
PICKLE_DIR = finders.find('svd/.pickled')
ALREADY_SEEN_FN = 'already_seen_set'
HREF_QUEUE_FN = 'queue_deque'
N_THREADS = 15
# might be slightly exceeded
LIMIT = 45000

session = HTMLSession()
mutex = threading.Lock()


def extract_text_content(html):
    _TITLE_SELECTOR = '#main-heading'
    _TEXT_SELECTORS = [
        '#main-content article div[data-component="text-block"] p',
        'main-content article #main-heading',
        'main-content article p'
    ]

    text_content = []
    title = html.find(_TITLE_SELECTOR, first=True)
    title = f'{title.text}\n' if title is not None else '\n'

    for selector in _TEXT_SELECTORS:
        for elem in html.find(selector, first=False):
            text_content.append(elem.text)

    return title + ' '.join(text_content) if len(text_content) > 0 else None


def extract_feature_links(html):
    return html.links


def crawl(already_seen, queue, limit):
    while True:
        mutex.acquire()

        if limit[0] <= 0 or len(queue) == 0:
            mutex.release()
            return

        route = queue.popleft()

        mutex.release()

        url = f'{URL_PREFIX}{route}'
        r = session.get(url)

        text = extract_text_content(r.html)
        hrefs = extract_feature_links(r.html)

        print(f'{threading.get_ident()} | fetched data from {url}')

        for href in hrefs:
            if href.startswith(VALID_ROOT) and href not in already_seen:
                already_seen.add(href)
                queue.append(href)

        if text is not None:
            filename = encode_url(url)

            with open(f'{RESULTS_DIR}/{filename}', 'w') as out:
                out.write(text)

            mutex.acquire()
            limit[0] -= 1
            mutex.release()


def pickle_utils(set_, queue_):
    with open(f'{PICKLE_DIR}/{ALREADY_SEEN_FN}', 'wb') as set_file:
        pickle.dump(set_, set_file)
        print('set succesfully pickled')

    with open(f'{PICKLE_DIR}/{HREF_QUEUE_FN}', 'wb') as queue_file:
        pickle.dump(queue_, queue_file)
        print('queue succesfully pickled')


def unpickle_utils():
    try:
        with open(f'{PICKLE_DIR}/{ALREADY_SEEN_FN}', 'rb') as set_file:
            set_ = pickle.load(set_file)

        with open(f'{PICKLE_DIR}/{HREF_QUEUE_FN}', 'rb') as queue_file:
            queue_ = pickle.load(queue_file)

        return set_, queue_
    except FileNotFoundError:
        print(
            f'Pickled files not found, creating new set and deque with starting point: {STARTING_POINT}')
        queue_ = deque()
        queue_.append(STARTING_POINT)
        return set(), queue_


def crawler():
    if not os.path.isdir(PICKLE_DIR):
        os.mkdir(PICKLE_DIR)

    if not os.path.isdir(RESULTS_DIR):
        os.mkdir(RESULTS_DIR)

    already_seen, queue = unpickle_utils()
    atexit.register(pickle_utils, already_seen, queue)
    n_threads = N_THREADS
    # has to be in list to be mutable
    limit = [LIMIT]
    threads = [threading.Thread(
        target=crawl, args=(already_seen, queue, limit)) for _ in range(n_threads)]

    for i, thread in enumerate(threads):
        print(f'starting thread {i}')
        # ugly, but will do in this case, wait for previous thread(s) to add something to queue
        # so this thread won't terminate asap
        while len(queue) == 0:
            time.sleep(1)
        thread.start()


if __name__ == '__main__':
    crawler()
