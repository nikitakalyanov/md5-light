import smtplib
from hashlib import md5
from urllib.parse import parse_qs
from multiprocessing import Process, Queue, Lock
from http.server import BaseHTTPRequestHandler, HTTPServer

import redis
import requests

import config
# an attempt to connect to email server using SMPT
try:
    mail_server = smtplib.SMTP_SSL(config.MAIL_SMPT_SERVER, config.MAIL_SMPT_PORT)
    mail_server.login(config.MAIL_LOGIN, config.MAIL_PASSWORD)
except smtplib.SMTPException:
    mail_server = None

db = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB)


counter = 0
salt = b'Not random salt'

class HttpProcessor(BaseHTTPRequestHandler):
    q = Queue()     # used to queue downloading & hashing
    lock = Lock()   # used to ensure that only one process edits/queries database

    def make_response(self, http_code, text):   # constructs http response
        self.send_response(http_code)
        self.send_header('content-type', 'text/html')
        self.end_headers()
        self.wfile.write((text+'\n').encode('utf-8'))

    def compute_hash(self, url, db_key):
        hasher = md5()
        try:
            file = requests.get(url)
            if file.status_code != 200:
                self.lock.acquire()
                db.hset('c' + db_key, 'status', 'failed-http-code-not-200')
                self.lock.release()
            else:
                hasher.update(file.content)
                db_value = hasher.hexdigest()
                self.lock.acquire()
                db.hset('c' + db_key, 'status', 'done')
                db.hset('c' + db_key, 'hash', db_value)
                email_addr = db.hget('c' + db_key, 'email').decode('utf-8')
                self.lock.release()

                # an attempt to send an email
                if email_addr and mail_server is not None:
                    self.lock.acquire()     # lock not no get banned on email server
                    try:
                        msg = '\nYour hash for url {} is {}'.format(url, db_value)
                        mail_server.sendmail(config.MAIL_SENDER, email_addr, msg)
                    except smtplib.SMTPException:
                        pass
                    self.lock.release()

        except requests.RequestException as e:
            self.lock.acquire()
            db.hset('c'+ db_key, 'status', 'failed-url-error')
            self.lock.release()
            print(e)

    def do_GET(self):
        if not self.path.startswith('/check'):
            self.make_response(400, '{{"{0}":"{1}"}}'.format('error', 'invalid-query'))
        elif len(self.path.split('?')) != 2:
            self.make_response(400, '{{"{0}":"{1}"}}'.format('error', 'invalid-query'))
        else:
            self.lock.acquire()
            res = db.hget('c' + self.path.split('?')[1], 'status')
            self.lock.release()
            if res is None:
                self.make_response(404, '{{"{0}":"{1}"}}'.format('status', 'not-found'))
            elif res.decode('utf-8') == 'done':
                self.lock.acquire()
                res_url = db.hget('c' + self.path.split('?')[1], 'url').decode('utf-8')
                res_hash = db.hget('c' + self.path.split('?')[1], 'hash').decode('utf-8')
                self.lock.release()
                res_str = '{{"{0}":"{1}", "{2}":"{3}", "{4}":"{5}"}}'.format('status', 'done', 'md5', res_hash, 'url', res_url)
                self.make_response(200, res_str)
            else:
                if res.decode('utf-8') == 'running':
                    self.make_response(200, '{{"{0}":"{1}"}}'.format('status', 'running'))
                else:
                    self.make_response(400, '{{"{0}":"{1}"}}'.format('status', res.decode('utf-8')))

    def do_POST(self):
        global counter, salt
        if self.path == '/submit':
            email = ''
            hasher = md5()
            length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(length)
            param_dict = parse_qs(post_data.decode('utf-8'))

            # getting email (if passed in a query)
            try:
                email = param_dict['email'][0]
            except KeyError:
                pass

            try:
                hasher.update(bytes(counter) + salt)
                counter += 1
                db_key = hasher.hexdigest()     # using hash(counter + salt) as a database key
                db_dict = {'status': 'running', 'hash': '', 'url': param_dict['url'][0], 'email': email}
                self.lock.acquire()
                db.hmset('c' + db_key, db_dict)     # +'c' is workaround for the bug
                self.lock.release()
                self.make_response(200, '{{"{0}":"{1}"}}'.format('id', db_key))
                self.q.put((param_dict['url'][0], db_key))
                background_process = Process(target=self.compute_hash, args=self.q.get())
                background_process.start()
            except KeyError:    # no 'url=' was found in a query
                self.make_response(400, '{{"{0}":"{1}"}}'.format('error', 'invalid-query'))
        else:
            self.make_response(400, '{{"{0}":"{1}"}}'.format('error', 'invalid-query'))


serv = HTTPServer(config.HTTP_SERVER_ADDR, HttpProcessor)
serv.serve_forever()
