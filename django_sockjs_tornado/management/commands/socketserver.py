import logging
import sys
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.importlib import import_module
from tornado import web, ioloop
from sockjs.tornado import SockJSRouter


class Command(BaseCommand):
    logger = logging.getLogger('django-sockjs-tornado')

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

    def handle(self, **options):
        from django.core.exceptions import ImproperlyConfigured
        if not getattr(settings, 'SOCKJS_CLASSES', None) or getattr(settings, 'SOCKJS_CHANNELS', None):
            raise ImproperlyConfigured("Can't find SOCKJS_CLASSES or SOCKJS_CHANNELS")
        routers = []
        for sockjs_class, channel_name in zip(settings.SOCKJS_CLASSES, settings.SOCKJS_CHANNELS):
            module_name, cls_name = sockjs_class.rsplit('.', 1)
            module = import_module(module_name)
            cls = getattr(module, cls_name)
            if not channel_name.startswith('/'):
                channel_name = '/%s' % channel_name

            routers.append(SockJSRouter(cls, channel))

        app_settings = {
            'debug': settings.DEBUG,
        }

        PORT = int(options['port'])

        urls = reduce(lambda urls, router: urls + router.urls, sequence)

        if not urls:
            sys.exit("Can't find any class in SOCKJS_CLASSES")

        app = web.Application(urls, **app_settings)

        app.listen(PORT, no_keep_alive=options['no_keep_alive'])

        logger.info("Running sock app on port %s")
        try:
            ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            # so you don't think you errored when ^C'ing out
            pass
