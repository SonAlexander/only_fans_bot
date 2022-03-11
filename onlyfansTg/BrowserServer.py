import logging
import subprocess
from threading import Thread, Semaphore, Event
from multiprocessing import Process, Queue
from pyvirtualdisplay import Display
from subprocess import Popen, PIPE, DEVNULL
from selenium.webdriver.common.keys import Keys
import random
import re
import string
import socket
import os
import time
import signal
from packages.Collections.Common import TempFile, TempDir, last_exception, finalize
from config import browser_config
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import Chrome, ChromeOptions

def copy(text: str, display: int = 0):
    with TempFile(from_text=text) as f :
        os.system(f'xclip -d :{display} -selection clipboard < {f.name}')

class Clipboard:
    def __init__(self):
        self.sem = Semaphore()
        self.copy = copy

    def __enter__(self):
        self.sem.acquire()

    def __exit__(self, *args):
        self.sem.release()

MB_SIZE = 1_048_576

class Chromium:
    debug_host = '127.0.0.1'
    cache_mb = 10

    def __init__(self, profile_path, tmp_path, debug_port, vnc_port, chromium_path, window_size,
                 clone_profile, start_page, headless = False):
        self.finalizer = finalize(self, self.finalize)
        self.logger = logging.getLogger(profile_path + 'chromium_process')
        self.logger.setLevel(logging.INFO)

        self.profile_dir = None
        if clone_profile:
            self.profile_dir = TempDir(profile_path, prefix = tmp_path, postfix='chromium_profile')
            self.profile_path = self.profile_dir.name
        else :
            self.profile_path = profile_path

        self.debug_port = debug_port
        self.args = [
            chromium_path,
            f'--remote-debugging-host={self.debug_host}',
            f"--remote-debugging-port={self.debug_port}",
            '--no-first-run',
            f'--disk-cache-size={self.cache_mb * MB_SIZE}',
            '--lang=en-US',
            f'--user-data-dir={self.profile_path}',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-session-crashed-bubble',
            '--disable-features=InfiniteSessionRestore',
        ]
        '''
        user_agent = None
        if isinstance(antidetect, dict):
            if 'user_agent' in antidetect:
                user_agent = antidetect["user_agent"]
                self.args.append(f'--user-agent="{antidetect["user_agent"]}"')
        '''
        if headless :
            self.args.append('--headless')
            '''
            if user_agent :
                self.args.append(f'--user-agent="{antidetect["user_agent"]}"')
            else :
                self.DEFAULT_USER_AGENT = ''
            '''

        print(f'{self.debug_port=}')
        if start_page :
            self.args.append(start_page)

        self.q = Queue()
        self.browser_process = Process(target=self.start_browser_vnc, args=(self.q, vnc_port, self.args, window_size),
                                       daemon=True)
        self.browser_process.start()
        try :
            self.display, self.display_pid, self.term_pid = self.q.get(timeout = 10)
        except BaseException as e :
            self.logger.error('timeout while starting chromium in process!')
            self.finalize()
            raise RuntimeError('timeout while starting chromium in process!')
        self.stop = self.finalize

    def finalize(self):
        self.finalizer.detach()
        try :
            os.kill(self.display_pid, signal.SIGKILL)
        except BaseException :
            self.logger.error(f'can not close display {last_exception()}')

        try :
            os.killpg(os.getpgid(self.term_pid), signal.SIGTERM)
        except BaseException :
            self.logger.error(f'can not close chromium_term {last_exception()}')

        try :
            self.browser_process.kill()
        except BaseException :
            self.logger.error(f'can not close browser proc {last_exception()}')

        if self.profile_dir:
            try :
                self.profile_dir.close()
            except BaseException :
                self.logger.info(f'can not close user data dir {last_exception()}')

    @staticmethod
    def start_browser_vnc(q: Queue, vnc_port, args, window_size):
        display, disp_pid, logger, env = 0, None, logging.getLogger(f'{vnc_port=}'), None
        logger.setLevel(logging.INFO)
        if vnc_port is not None:
            disp = Display(backend="xvnc", size=window_size, rfbport=vnc_port)
            disp.start()
            logger.info(f', virtual display = :{disp.display}, window size = {window_size}, vnc pid = {disp.pid}')
            env = os.environ.copy()
            env['DISPLAY'] = f':{disp.display}'
            display, disp_pid = disp.display, disp.pid
        term = Popen(
            args,
            bufsize = 0,
            stderr = DEVNULL,
            stdout = DEVNULL,
            stdin = DEVNULL,
            env = env,
            preexec_fn = os.setsid(),
        )
        q.put((display if display else int(os.popen('echo $DISPLAY').read()[1:-1]), disp_pid, term.pid))
        while 1 :
            time.sleep(1000)

class Browser(Chrome):
    waiter_default_time_secomds = 20

    class CanNotStartWebDriverError(BaseException) :
        ...

    def __init__(
        self,
        profile_path,
        tmp_path,
        debug_port,
        vnc_port = None,
        chromium_path = '/usr/bin/chromium-browser',
        chromedriver_path = './chromedriver',
        window_size = (500, 700),
        clip = None,
        clone_profile = True,
        start_page = None,
        headless = False,
    ):
        self.finalizer = finalize(self, self.stop)

        self.profile_path, self.tmp_path, self.debug_port, self.vnc_port, self.chromium_path, self.window_size, self.chromedriver_path, self.clip = profile_path, tmp_path, debug_port, vnc_port, chromium_path, window_size, chromedriver_path, clip
        self.logger = logging.getLogger(os.path.basename(self.profile_path))
        self.logger.setLevel(logging.INFO)
        self.logger.info('starting chromium')
        self.chromium = Chromium(profile_path, tmp_path, debug_port, vnc_port, chromium_path, window_size, clone_profile, start_page, headless)
        self.display = self.chromium.display
        self.logger.info(f'chromium_pid = {self.chromium.term_pid}')
        if not self.clip:
            self.clip = Clipboard()

        self.chromedriver = TempFile(from_file=self.chromedriver_path, postfix='chromedriver', prefix=self.tmp_path)
        self.patch_chromedriver(self.chromedriver.name)
        opt = ChromeOptions()
        opt.add_experimental_option("debuggerAddress", f"{self.chromium.debug_host}:{self.chromium.debug_port}")
        self.logger.info('starting chromedriver')
        try :
            super(Browser, self).__init__(options=opt, executable_path=self.chromedriver.name)
        except BaseException as e :
            self.logger.info('failed to start chromedriver')
            self.stop()
            raise self.CanNotStartWebDriverError(e)

        self.logger.info(f'chromedriver started')
        self.set_window_size(*self.window_size)
        self.wait = WebDriverWait(self, self.waiter_default_time_secomds)

        self.recording_event, self.recording, self.recording_result_event = None, None, None

    def clean_field(self, field):
        field.send_keys(Keys.ENTER)
        time.sleep(0.1)
        field.send_keys(Keys.CONTROL + "a")
        time.sleep(0.1)
        field.send_keys(Keys.BACKSPACE)

    def copy(self, text):
        self.clip.copy(text, self.display)

    def paste(self, elem, text):
        with self.clip:
            self.copy(text)
            time.sleep(0.01)
            elem.send_keys(Keys.CONTROL + 'v')
            time.sleep(0.01)

    def start_video_recording(self, path=None):
        if self.recording_event is not None:
            raise RuntimeError('ffmpeg is already recording a video')

        self.recording_event, self.recording_result_event = Event(), Event()
        Thread(target=self._start_video_recording, args=[path], daemon=True).start()
        return self.recording_event

    def _start_video_recording(self, path: str = None):
        self.logger.info('started video recording')
        with TempFile(postfix='.mp4', clean=True) as videofile :
            ffmpeg_term = Popen(
                args = ['ffmpeg', '-f', 'x11grab', '-video_size', f'{self.window_size[0]}x{self.window_size[1]}', '-draw_mouse', '0', '-i',
                      f':{self.display}', '-codec:v', 'libx264', '-r', '12', f'{videofile.name}'],
                stdout = PIPE,
                stdin = PIPE,
                stderr = PIPE,
            )
            time.sleep(1)
            self.recording_event.wait()
            self.recording_event = None
            ffmpeg_term.communicate(b'q')
            time.sleep(3)
            amount_of_fail = 0
            while subprocess.run(['ffprobe', videofile.name], stderr=PIPE, stdin=PIPE, stdout=PIPE).returncode:
                amount_of_fail += 1
                time.sleep(0.1)
            if amount_of_fail :
                self.logger.info(f'{amount_of_fail=}')
            ffmpeg_term.terminate()

            # adding audio to video
            '''
            with TempFile(postfix = '.mp4', clean = True) as noised :
                self.logger.info('adding noise')
                ffmpeg_term = Popen(
                    args=["ffmpeg", '-i', videofile.name, '-i', 'resources/noice.ogg', '-map', "0", "-map", "1:a", "-c:v", "copy", "-shortest", noised.name],
                    stdout = PIPE,
                    stdin = PIPE,
                    stderr = PIPE,
                )
                ffmpeg_term.communicate()
                amount_of_fail = 0
                while subprocess.run(['ffprobe', videofile.name], stderr=PIPE, stdin=PIPE, stdout=PIPE).returncode:
                    amount_of_fail += 1
                    time.sleep(0.1)
                time.sleep(1)
                # self.logger.info(f'{amount_of_fail=}')
                ffmpeg_term.terminate()
            '''
            self.recording = videofile.read()
            if path:
                videofile.clone(path)
            self.recording_result_event.set()
            self.recording_result_event = None

    def stop_video_recording(self):
        if self.recording_event is None:
            raise RuntimeError('can not stop recording if it is not started yet!')

        self.recording_event.set()
        self.recording_result_event.wait()
        self.logger.info('stopped video recording')
        return self.recording

    def send_comb_to_disp(self, comb):
        os.system(f'DISPLAY=:{self.display} xdotool key {comb}')

    def send_str_to_disp(self, s):
        os.system(f'DISPLAY=:{self.display} xdotool type "{s}"')

    def send_enter(self):
        self.send_comb_to_disp('Return')

    def send_ctrlv(self):
        self.send_comb_to_disp('ctrl+v')

    def send_escape(self):
        self.send_comb_to_disp('Escape')

    def stop(self):
        self.finalizer.detach()
        try :
            self.quit()
        except BaseException :
            self.logger.error(f'can not close webriver {last_exception()}')

        try :
            self.chromedriver.close()
            self.logger.info('stopped chromeriver')
        except BaseException :
            self.logger.error(f'can not close chromeriver {last_exception()}')

        try :
            self.chromium.stop()
        except BaseException :
            self.logger.error(f'can not close chromium {last_exception()}')

        try:
            self.stop_video_recording()
        except BaseException:
            pass

    def patch_chromedriver(self, path='./chromedriver'):
        linect = 0
        replacement = self.gen_random_cdc()
        with open(path, "r+b") as fh:
            for line in iter(lambda: fh.readline(), b""):
                if b"cdc_" in line:
                    fh.seek(-len(line), 1)
                    newline = re.sub(b"cdc_.{22}", replacement, line)
                    fh.write(newline)
                    linect += 1
            return linect

    def gen_random_cdc(self):
        cdc = random.choices(string.ascii_lowercase, k=26)
        cdc[-6:-4] = map(str.upper, cdc[-6:-4])
        cdc[2] = cdc[0]
        cdc[3] = "_"
        return "".join(cdc).encode()

class BrowserServer:
    ZERO_VNC_PORT = 5900
    ZERO_CHROMEDRIVER_PORT = 50000
    WINDOW_SIZE = (500, 700)
    # WINDOW_SIZE = (1600, 900)

    def __init__(
            self,
            profiles_path = browser_config.profiles_path,
            chromium_path = browser_config.chromium_path,
            chromedriver_path = browser_config.chromedriver_path,
            tmp_path = browser_config.tmp_path
        ):
        self.logger = logging.getLogger('BrowserServer')
        self.logger.setLevel(logging.INFO)
        self.profiles_path, self.chromium_path, self.chromedriver_path, self.tmp_path = profiles_path, chromium_path, chromedriver_path, tmp_path
        self.browsers: dict[str: Browser] = {}
        self.logger.info(
            f'inited browser server {self.profiles_path=}, {self.chromedriver_path=}, {self.chromium_path=}')
        self.sem = Semaphore()
        self.find_port_sem = Semaphore()
        self.reserved_ports = set()

    def start_browser(
            self, profile, virtual = False, vnc_port = None, debug_port = None, clip = None, clone_profile = True,
            start_page = None, sem = False, headless = False) -> Browser :
        if sem :
            self.sem.acquire(timeout=60)

        browser = None
        ports_reserved_for_browser = set()
        for tries in range(3) :
            try :
                self.logger.info(f'trial {tries} to start browser')
                self.stop_browser(profile)
                debug_port = self.get_free_port(self.ZERO_CHROMEDRIVER_PORT) if not debug_port else debug_port
                vnc_port = (self.get_free_port(self.ZERO_VNC_PORT) if not vnc_port else vnc_port) if virtual else None
                ports_reserved_for_browser.update({debug_port, vnc_port})
                browser = Browser(
                    profile_path = self.profiles_path + profile,
                    tmp_path = self.tmp_path,
                    debug_port = debug_port,
                    vnc_port = vnc_port,
                    chromium_path = self.chromium_path,
                    chromedriver_path = self.chromedriver_path,
                    window_size = self.WINDOW_SIZE,
                    clip = clip,
                    clone_profile = clone_profile,
                    start_page = start_page,
                    headless = headless
                )
                self.browsers[profile] = browser
                self.reserved_ports.remove(debug_port)
                if virtual :
                    self.reserved_ports.remove(vnc_port)
                break
            except BaseException :
                self.logger.critical(last_exception())

        if sem:
            self.sem.release()
        self.reserved_ports.difference_update(ports_reserved_for_browser)
        # self.logger.info(f"{self.reserved_ports=}")
        return browser

    def get_free_port(self, begin, end=None):
        if not end:
            end = begin + 10000

        for port in range(begin, end):
            with self.find_port_sem :
                s = socket.socket()
                try:
                    s.bind(('127.0.0.1', port))
                    s.close()
                    if port not in self.reserved_ports :
                        self.reserved_ports.add(port)
                        return port
                except socket.error:
                    pass

    def stop_browser(self, profile):
        if profile in self.browsers:
            browser : Browser = self.browsers[profile]
            self.logger.warning(f'stopping browser {profile}')
            del self.browsers[profile]
            browser.stop()
            return True
        else:
            return False

    def __getitem__(self, profile):
        return self.browsers[profile]

    def __setitem__(self, profile, browser):
        self.browsers[profile] = browser

    def stop(self):
        self.logger.warning('stopping browser server')
        for browser in self.browsers.values():
            browser.stop()

if __name__ == '__main__':
    pass


