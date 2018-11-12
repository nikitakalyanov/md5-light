# MD5 light

A simple web API for computing MD5 hash of an arbitrary file on the Internet. If email provided *attempts* (i.e. no indication if sending fails) to send the result via SMTP.
Has only 2 dependencies (apart from standard library).

## Installation

Redis (5.0.0) should be installed before using the software. Instructions at [redis web site](https://redis.io/download#installation).

Also virtualenv package is needed to set up appropriate environment. Instructions [here](https://virtualenv.pypa.io/en/stable/installation/).


    $ virtualenv -p python3.6 <path_to_desired_env_dir>
    $ source <path_to_env_dir>/bin/activate
    $ pip install -r requirements.txt

Edit `config.py` if needed.

Launch `md5light.py`:

    $ python md5light.py

Use either browser (Firefox 63.0 was tested, issues are known with Chrome) or another Terminal window and `curl` to interact with the API.

## Notes

Should **NOT** be used publicly as only basic security checks are implemented in python http.server.HTTPserver class.

A workaround was implemented for a bug found during the development - redis database fails when 'key' is string which starts with a number.  (https://github.com/antirez/redis/issues/2864#issuecomment-281055328)

Two types of 'failed' status are implemented. `failed-url-error` is used to indicate mostly invalid url, while `failed-http-code-not-200` indicates that url was succesfully reached but the server responded with not expected http code.

There is an additional type of response `error:invalid-query` which indicates that the API is being used incorrectly.