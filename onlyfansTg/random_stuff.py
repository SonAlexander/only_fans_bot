import io
import math
import subprocess
from pprint import pprint
import os
import string
import sys
import re
import datetime
import shutil
import json
import time
import asyncio
from threading import Thread, Semaphore, Event, Lock
import socket
from tqdm import tqdm
import itertools
from collections import deque, defaultdict
from time import perf_counter as timer
from weakref import finalize
import traceback
import logging
from PIL import Image
import random
import select
import hashlib
from typing import List, Tuple, Dict
import typing
from operator import itemgetter, attrgetter
from collections.abc import Iterable
from functools import reduce
import argparse
import configparser
import logging
import multiprocessing as mp
from queue import Queue as QueueWaiting
from hashlib import sha256
from subprocess import Popen, PIPE

empty_function = lambda *args, **kwargs : None
CYCLE_ITERATION_TIMEOUT_SECONDS = .01
english = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
TIMEDELTA_DAY = datetime.timedelta(days=1)

def get_local_path():
    LOCAL_PATH = None
    if getattr(sys, 'frozen', False):
        LOCAL_PATH = os.path.abspath(os.path.dirname(sys.executable)) + '/'
    elif __file__:
        LOCAL_PATH = os.path.abspath(os.path.dirname(__file__)) + '/'
    return LOCAL_PATH

class ImmutableBuffer:
    def __init__(self):
        self.item = None
        self.done = False

    def set(self, item):
        self.item = item
        self.done = True

def last_exception(limit = 4000):
    return traceback.format_exc()[:limit]

def stringify_exception():
    err = last_exception()
    logging.error(traceback.format_exc())
    return err


def current_time():
    return clear_tzinfo(datetime.datetime.now(datetime.timezone.utc))

def clear_tzinfo(date : datetime.datetime) :
    return date.replace(tzinfo = None)


def try_until_no_exception(timedelta, nb_tries, function, args, exception_message='can not do stuff...'):
    tries = 0
    while tries < nb_tries:
        time.sleep(timedelta)
        try:
            temp = function(*args)
            # print('found element without error, args : ', ';'.join(args))
            return temp
        except BaseException as e:
            pass
    print('not found element waiting for exception')
    raise Exception(exception_message)


def hashbytes(item):
    return sha256(item).hexdigest()


def strip_exif(path, format = '.jpg') -> None :
    image = Image.open(path)

    # next 3 lines strip exif
    image_data = list(image.getdata())
    image_without_exif = Image.new(image.mode, image.size)
    image_without_exif.putdata(image_data)
    size = image_without_exif.size
    image_without_exif = image_without_exif.resize((int(size[0] * (0.95 + random.random() / 10)),
                                                    int(size[1] * (0.95 + random.random() / 10))),
                                                   Image.ANTIALIAS)
    image_without_exif = image_without_exif.convert('RGB')
    image_without_exif.save(path)

def datetime_to_int(date):
    return int(date.timestamp())

def current_time_int():
    return datetime_to_int(current_time())

def current_time_zeroed_after_days() :
    now = current_time()
    return datetime.datetime(year=now.year, month=now.month, day=now.day)

def yesterday() :
    return current_time_zeroed_after_days() - datetime.timedelta(days=1)

def date_stringify(date) :
    return date.strftime("%d %B %Y")

def date_before_now(hours = 0, minutes = 0) :
    return current_time() - datetime.timedelta(hours=hours, minutes=minutes)


map_month_int = {
    "jan" : 1,
    "feb" : 2,
    "mar" : 3,
    "apr" : 4,
    "may" : 5,
    "jun" : 6,
    "jul" : 7,
    "aug" : 8,
    "sep" : 9,
    "oct" : 10,
    "nov" : 11,
    "dec" : 12,
}

map_int_month = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def get_current_month_int() :
    return current_time().month

def get_current_month_string() :
    return date_stringify(current_time()).split()[1]

def get_current_month_short_string() :
    return get_current_month_string()[ : 3].lower()

def run_many_threaded_functions_and_await_all_output(functions_args_kwargs, timeout = 1000_000_000_000_000_000):
    buffers = []
    threads = []
    for func, args, kwargs in functions_args_kwargs:
        buff = ImmutableBuffer()
        th = Thread(
            target = lambda *args, **kwargs: buff.set(func(*args, **kwargs)),
            args = args,
            kwargs = kwargs,
            daemon = True
        )
        th.start()
        threads.append(th)
        buffers.append(buff)
    endtime = timer() + timeout
    while not all([a.done for a in buffers]) :
        if timer() > endtime :
            raise TimeoutError(f'function is not returning for too long({timeout}) seconds')
        time.sleep(CYCLE_ITERATION_TIMEOUT_SECONDS)

    res = [b.item for b in buffers]
    return res

async def run_coro_and_return_to_buffer(coro, buffer: ImmutableBuffer):
    buffer.set(await coro)


def run_coro_sync(loop, coro, *args):
    buff = ImmutableBuffer()
    loop.create_task(run_coro_and_return_to_buffer(coro(*args), buffer=buff))
    while not buff.done:
        time.sleep(0.01)
    return buff.item


def run_coro_threaded(self, coro, *args, thread_name='crashsafe_coro_thread'):
    Thread(
        target=self.run_coro_sync_crashsafe,
        args=[coro, *args],
        name=thread_name,
        daemon=True
    ).start()


async def execute_sync_function_async(func, *args, **kwargs):
    logging.debug('IN execute_sync_function_async', func, args, kwargs)
    buff = ImmutableBuffer()

    def return_to_buffer(buff, func, *args, **kwargs):
        # print(f'{buff=}, {func=}, {args=}, {kwargs=}')
        buff.set(func(*args, **kwargs))

    Thread(target=return_to_buffer, args=(buff, func, *args), kwargs=kwargs,
           name='sync_to_async_function_executor').start()
    while not buff.done:
        await asyncio.sleep(0.01)

    return buff.item


def isiterable(obj):
    return isinstance(obj, Iterable)


def create_image(width=3, height=3):
    img = Image.new('RGB', (width, height), (random.randint(1, 250), random.randint(1, 250), random.randint(1, 250)))
    buff = io.BytesIO()
    img.save(buff, format='PNG')
    return buff.getvalue()


class NamedLogger(object):
    def __init__(self, name):
        self.logger, self.name = logging.getLogger(name), name
        self.logger.setLevel(logging.INFO)

def get_free_name_in_dir(prefix = None, postfix = None):
    prefix, postfix = os.path.abspath(prefix) + '/' if prefix else '/tmp/', postfix if postfix else ''
    while 1:
        name = os.path.abspath(f'{prefix}{random.random()}{postfix}')
        if not os.path.exists(name):
            return name


def resize_image(infile, size : tuple, outfile = None, image_format = '.png') :
    with TempFile(postfix = image_format) as out :
        im = Image.open(infile)
        im = im.resize(size, Image.ANTIALIAS)
        im = im.convert('RGB')
        im.save(out.name)
        if outfile :
            out.clone(outfile)
        return out.read()

def create_slideshow(images : list, video_size : Tuple[int, int], time_for_frame = 1, image_format = '.png', video_format = '.mp4', audio_path = None, outfile = None) :
    if images :
        adder = pow(10, int(math.log10(len(images)) + 1))
        video_size = (video_size[0] // 2 * 2, video_size[1] // 2 * 2)
        with TempDir() as folder :
            for j, data in enumerate(images) :
                if isinstance(data, str) :
                    with open(data, 'rb') as f :
                        data = f.read()

                with TempFile(prefix = folder.name, postfix = image_format, from_bytes = data) as f :
                    resize_image(f.name, video_size, f'{folder.name}{j + adder}{image_format}', image_format = image_format)

            with TempFile(postfix=video_format, prefix = folder.name, clean=True) as vid :
                subprocess.run(
                    ['ffmpeg', '-framerate', f'1/{time_for_frame}', '-pattern_type', 'glob', '-i', f'{folder.name}/*{image_format}'] +
                    (['-i', audio_path] if audio_path else []) +
                    ["-c:v", "libx264", "-c:a", "copy", '-shortest', "-r", "30", "-pix_fmt", "yuv420p", "-strict", "-2", vid.name],
                    stderr = PIPE,
                    stdin = PIPE,
                    stdout = PIPE
                )
                if outfile :
                    vid.clone(outfile)
                return vid.read()

class TempFile:
    def __init__(self, binary=True, from_file=None, from_text=None, from_bytes=None, prefix = './tmp/', postfix = None, clean = False, self_destructive = False):
        self.postfix = postfix if isinstance(postfix, str) else ''

        if from_text :
            binary = False

        if self_destructive :
            finalize(self, self.__exit__)
        if not os.path.isdir(prefix) :
            os.system(f'mkdir -p {prefix}')
        self.write_mode = 'wb' if binary else 'w+'
        self.read_mode = 'rb' if binary else 'r+'
        self.name = get_free_name_in_dir(prefix, postfix)
        if not clean :
            self.write()
        if from_file:
            shutil.copy(from_file, self.name)
        elif from_text:
            self.write(from_text)
        elif from_bytes:
            self.write(from_bytes)
        self.closed = False

    def clone(self, path):
        os.system(f'cp {self.name} {path}')

    def move(self, path):
        os.system(f'mv {self.name} {path}')
        self.name = path

    def read(self):
        with open(self.name, self.read_mode) as f:
            return f.read()

    def write(self, data=None):
        with open(self.name, self.write_mode) as f:
            if data:
                f.write(data)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self.closed :
            self.closed = True
            os.unlink(self.name)

    def close(self):
        self.__exit__()


class TempDir:
    def __init__(self, from_dir=None, postfix = None, prefix = './tmp/', self_destructive = False):
        if self_destructive :
            finalize(self, self.close)
        if not os.path.isdir(prefix) :
            os.system(f'mkdir -p {prefix}')
        self.name = get_free_name_in_dir(prefix, postfix) + "/"
        if from_dir:
            from_dir = os.path.abspath(from_dir)
            os.system(f'cp -R {from_dir} {self.name}')
        else :
            os.mkdir(self.name)
        self.closed = False

        self.nb_tempfiles = 0
        self.tempfiles : Dict[str, TempFile] = {}
        self.temppaths = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self.closed :
            for file in self.tempfiles.values() :
                file.close()
            os.system(f'rm -rf {self.name}')
            self.closed = True

    def add_file(self, from_bytes = None, from_file = None, postfix = None):
        self.nb_tempfiles += 1
        tempfile = TempFile(from_bytes = from_bytes, from_file = from_file, postfix = postfix, prefix = self.name)
        self.temppaths.append(tempfile.name)
        self.tempfiles[tempfile.name] = tempfile

    def close(self, try_infinite = True):
        tries = 0
        while os.path.exists(self.name):
            try :
                tries += 1
                os.system(f'rm -rf {self.name}')
            except BaseException :
                pass
            time.sleep(0.01)
            if tries >= 10000:
                print(f'can not delete {self.name}, reason = {last_exception()}')
                return False
        return True

    def iterfiles(self):
        for filename, file in self.tempfiles.items() :
            yield filename, file

    def rename_alphabetical(self):
        for j, filename in enumerate(self.temppaths) :
            t = self.tempfiles[filename]
            t.move(f'{self.name}{j}{t.postfix}')


def get_month_shifted(month, shift: int):
    is_str = isinstance(month, str)
    i = ((map_month_int[month] if is_str else month) + shift - 1) % 12 + 1
    return map_int_month[i - 1] if is_str else i

if __name__ == '__main__':
    print(get_month_shifted(3, -2))

