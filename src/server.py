import sys
import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from aiohttp import web

from aiohttp_session import get_session, setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage

import aiohttp_jinja2
import jinja2

import user
import search
#import personal
import friend
import share
import comment
import notification
import playlists
import history
import export
import speech

if '-debug' in sys.argv[1:]:
    print('WARNING: running in debug mode')
    import debug

import secrets
from util import routes, get_user, add_globals, error_middleware

ssl_context = None
if secrets.USE_SSL:
    import ssl
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(secrets.SSL_CRT, secrets.SSL_KEY)

async def update_certificate():
    while True:
        # let's encrypt certificate is updated every 3 months, we need to reload it
        # TODO: only do it if certificate changed
        print('reloading SSL certificate')
        ssl_context.load_cert_chain(secrets.SSL_CRT, secrets.SSL_KEY)
        await asyncio.sleep(3600 * 24) # once a day

async def run_web_app():
    app = web.Application(middlewares=[error_middleware])

    setup(app, EncryptedCookieStorage(secrets.SERVER_COOKIE_KEY))
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates/'), context_processors=[add_globals])

    # warning from doc: in production, /static should be handled by apache/nginx
    routes.static('/static', 'static', append_version=True)
    routes.static('/pictures', 'data/pictures')
    routes.static('/qrcodes', 'data/qrcodes')
    routes.static('/export', 'data/export')
    routes.static('/', 'static/favicon')
    app.add_routes(routes) 

    if secrets.USE_SSL:
        asyncio.get_event_loop().create_task(update_certificate())
    return app

app = asyncio.get_event_loop().run_until_complete(run_web_app())
print('Running app at http%s://%s:%d' % ('s' if secrets.USE_SSL else '', secrets.HOST, secrets.PORT))
web.run_app(app, ssl_context=ssl_context, host=secrets.HOST, port=secrets.PORT)
