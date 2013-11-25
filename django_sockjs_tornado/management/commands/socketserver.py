import logging
import os
import sys
from operator import add
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.importlib import import_module
from tornado import web, ioloop
from sockjs.tornado import SockJSRouter

logger = logging.getLogger('django-sockjs-tornado')


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--port',
            action='store',
            dest='port',
            default=getattr(settings, 'SOCKJS_PORT', 9999),
            help='What port number to run the socket server on'),
        make_option(
            '--no-keep-alive',
            action='store_true',
            dest='no_keep_alive',
            default=False,
            help='Set no_keep_alive on the connection if your server needs it')
    )

    def check_settings(self):
        from django.core.exceptions import ImproperlyConfigured

        if not getattr(settings, 'SOCKJS_CONNECTIONS', None):
            raise ImproperlyConfigured("Can't find SOCKJS_CONNECTIONS")

        if settings.DEBUG:
            return

        # all next settings should be in none-DEBUG mode

        if not getattr(settings, 'SOCKJS_SSL', None):
            raise ImproperlyConfigured("SOCKJS_SSL isn't set in non-DEBUG mode")

        if not settings.SOCKJS_SSL.get('certfile') or not settings.SOCKJS_SSL.get('keyfile'):
            raise ImproperlyConfigured("SOCKJS_SSL should be dict with nonempty keys 'certfile' and 'keyfile'")

    def build_urls(self):
        routers = []
        for sockjs_class, channel_name in settings.SOCKJS_CONNECTIONS:
            module_name, cls_name = sockjs_class.rsplit('.', 1)
            module = import_module(module_name)

            if not channel_name.startswith('/'):
                channel_name = '/%s' % channel_name

            routers.append(SockJSRouter(getattr(module, cls_name), channel_name))

        urls = reduce(add, [r.urls for r in routers])

        if not urls:
            sys.exit("Can't find any class in SOCKJS_CONNECTIONS")
        return urls


    def build_application(self, urls, port, no_keep_alive):
        app_settings = {
            'debug': settings.DEBUG,
        }

        if not settings.DEBUG:
            app_settings.update({
                'ssl_options': {
                    'certfile': settings.SOCKJS_SSL.get('certfile'),
                    'keyfile': settings.SOCKJS_SSL.get('keyfile')
                }
            })

        app = web.Application(urls, **app_settings)

        app.listen(port, no_keep_alive=no_keep_alive)



    def handle(self, **options):
        self.check_settings()

        urls = self.build_urls()
        port = int(options['port'])

        self.build_application(urls, port, options['no_keep_alive'])

        logger.info("Running sock app on port %s", port)
        try:
            ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            # so you don't think you errored when ^C'ing out
            pass
