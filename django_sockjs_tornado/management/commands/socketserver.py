import logging
import os
import sys
from operator import add
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand
from importlib import import_module
from tornado import web, ioloop
from sockjs.tornado import SockJSRouter

logger = logging.getLogger('django-sockjs-tornado')


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--no-keep-alive',
            action='store_true',
            dest='no_keep_alive',
            default=False,
            help='Set no_keep_alive on the connection if your server needs it'
        ),
        make_option(
            '--host',
            action='store',
            dest='host',
            nargs=1,
            default='0.0.0.0',
            help='Set host manually'
        ),
    )

    routers = []

    def check_settings(self):
        from django.core.exceptions import ImproperlyConfigured

        if not getattr(settings, 'SOCKJS_CONNECTIONS', None):
            raise ImproperlyConfigured("Can't find SOCKJS_CONNECTIONS")

        if not getattr(settings, 'SOCKJS_PORT', None):
            raise ImproperlyConfigured("Can't find SOCKJS_PORT")

    def build_urls(self):
        for sockjs_class, channel_name in settings.SOCKJS_CONNECTIONS:
            module_name, cls_name = sockjs_class.rsplit('.', 1)
            module = import_module(module_name)

            if not channel_name.startswith('/'):
                channel_name = '/%s' % channel_name

            self.routers.append(SockJSRouter(getattr(module, cls_name), channel_name))

        urls = reduce(add, [r.urls for r in self.routers])

        if not urls:
            sys.exit("Can't find any class in SOCKJS_CONNECTIONS")
        return urls

    def build_application(self, urls, no_keep_alive):
        app_settings = {
            'debug': settings.DEBUG,
        }

        app = web.Application(urls, **app_settings)
        app.listen(
            settings.SOCKJS_PORT, address=self.host,
            no_keep_alive=no_keep_alive
        )

    def handle(self, **options):
        self.check_settings()
        self.host = options['host']

        urls = self.build_urls()

        self.build_application(urls, options['no_keep_alive'])

        logger.info("Running sock app on port %s", settings.SOCKJS_PORT)
        try:
            for router in self.routers:
                ioloop_callback = getattr(router.get_connection_class(), 'ioloop_callback', None)
                if ioloop_callback and callable(ioloop_callback):
                    ioloop.IOLoop.instance().add_callback(ioloop_callback)
            ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            # so you don't think you errored when ^C'ing out
            pass
