"""Rotom's Core"""
import sys

from ruamel import yaml
from discord.ext import commands


class Bot(commands.AutoShardedBot):
    def __init__(self, config, debug):
        import time
        # Initializations
        self.boot_time = time.time()
        self._init_log(config, debug)
        self.config_name = config  # for get_conf()

        # Loading config file
        try:
            with open(config) as c:
                conf = yaml.safe_load(c)
                self.log.info("Successfully loaded config file {}!".format(config))
        except FileNotFoundError:
            self.log.error("Unable to find {}".format(config))
            sys.exit(2)

        # Initialize commands.Bot with params
        params = conf['bot']['params']
        if params is None:
            params = {}
        params.update({"command_prefix": self.when_mentioned_or(*conf['bot']['prefix'])})
        super().__init__(**params)
        self.log.info("Successfully initialized the bot with provided params!")

        self.add_cog(Builtin(self))
        self.log.info("Successfully loaded builtin command cog.")

        try:
            self.is_bot = not conf['bot']['params']['self_bot']
        except KeyError:
            self.is_bot = True

        self.token = conf['bot']['token']

    # Modified run() and start()
    def run(self, **kwargs):
        """Starts the bot. Source code from discord.py's Client.run().
        
        WARNING: This function is blocking, read discord.Client.run.__doc__'s warning for details."""
        import signal
        from discord import compat

        is_windows = sys.platform == 'win32'
        loop = self.loop
        if not is_windows:
            loop.add_signal_handler(signal.SIGINT, self._do_cleanup)
            loop.add_signal_handler(signal.SIGTERM, self._do_cleanup)

        task = compat.create_task(self.start(**kwargs), loop=loop)

        def stop_loop_on_finish(fut):
            loop.stop()

        task.add_done_callback(stop_loop_on_finish)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.discord_log.info('Received signal to terminate bot and event loop.')
        finally:
            task.remove_done_callback(stop_loop_on_finish)
            if is_windows:
                self._do_cleanup()

            loop.close()
            if task.cancelled() or not task.done():
                return None
            return task.result()

    async def start(self, **kwargs):
        """Starts the bot in an asynchronous way
        """
        bot = kwargs.pop('bot', self.is_bot)
        del self.is_bot
        reconnect = kwargs.pop('reconnect', True)
        await self.login(self.token, bot=bot)
        del self.token
        await self.connect(reconnect=reconnect)

    def _init_log(self, config, debug):
        """Initialize logging."""
        import datetime, os, logging
        # Credits to Liara: https://github.com/Thessia/Liara/blob/master/liara.py#L83
        now = str(datetime.datetime.now()).replace(' ', '_').replace(':', '-').split('.')[0]
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s', datefmt='GMT%z %Y-%m-%d %I:%M:%S %p')

        self.log = logging.getLogger('rotom')
        if debug:
            self.log.setLevel(logging.DEBUG)
        else:
            self.log.setLevel(logging.INFO)

        # Creates a log folder if it doesn't exist just in case
        if not os.path.exists("logs/"):
            os.makedirs("logs/")

        handler = logging.FileHandler('logs/rotom-{}_{}.log'.format(config, now))
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.info("Successfully set up logging!")

        self.discord_log = logging.getLogger('discord')
        self.discord_log.setLevel(logging.INFO)

        handler = logging.FileHandler('logs/discord-{}_{}.log'.format(config, now))
        handler.setFormatter(formatter)
        self.discord_log.addHandler(handler)
        self.log.info("Successfully set up discord.py logging!")

    async def on_ready(self):
        self.log.info("The bot is now ready for commands!")

    def when_mentioned_or(self, *prefixes):
        """Basically the same as discord.ext.commands.when_mentioned_or except it also checks for custom per-server prefixes via database.
        
        Added a fix for a bug that process_command() will only use the first matching prefix, thus
        if someone uses different-length same-char prefixes in order of shortest length the longer
        will be considered a CommandNotFound error.
        
        e.g. [':', '::'] as prefix, process_command only match `::help` with prefix ':', thus the bot
        will return error regarding `:help` not being a command."""

        def inner(bot, msg):
            r = list(prefixes)
            r.append(commands.when_mentioned(bot, msg))

            # Check if there's custom prefix
            try:
                if self.db is not None:
                    pass
            except AttributeError:
                pass
            # If custom prefix is not None:
            # r.append(list(custom_prefix_list))
            r = sorted(r, key=len, reverse=True)
            return r

        return inner

    def get_conf(self):
        """Gets config by searching matching config using caller module's name.
        
        If unable to find matching config, `None` will be returned instead."""
        import inspect
        conf = None

        with open(self.config_name, 'r') as c:
            conf = yaml.safe_load(c)

        # http://stackoverflow.com/questions/1095543/get-name-of-calling-functions-module-in-python
        # Can also be used on get_lang()
        frm = inspect.stack()[1]
        module = inspect.getmodule(frm[0]).__name__

        try:
            return conf[module]
        except KeyError:
            return None


class Builtin:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True, aliases=['eval'])
    @commands.is_owner()
    async def debug(self, ctx, *, code: str):
        """Evaluates code, shamelessly copied and sightly modified from Robo Danny."""
        import inspect, discord

        code = code.strip('` ')
        python = '```py\n>>> {}\n{}\n```'
        result = None

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'msg': ctx.message,
            'guild': ctx.message.guild,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }

        env.update(globals())

        try:
            result = eval(code, env)
            if inspect.isawaitable(result):
                result = await result
            # Should we include channel in the log?
            self.bot.log.info("[EVAL] {0.author.name} ({0.author.id}) ran `{1}`.".format(
                ctx.message, code))
        except Exception as e:
            if self.bot._skip_check(ctx.message.id, self.bot.user.id):
                await ctx.message.edit(python.format(code, type(e).__name__ + ': ' + str(e)))
            else:
                await ctx.message.channel.send(
                    python.format(code, type(e).__name__ + ': ' + str(e)))

            self.bot.log.info(
                "[EVAL] {0.author.name} ({0.author.id}) tried to run `{1}` but was met with `{2}: {3}`.".
                format(ctx.message, code, type(e).__name__, str(e)))

            return

        if self.bot._skip_check(ctx.message.id, self.bot.user.id):
            await ctx.message.edit(python.format(code, result))
        else:
            await ctx.message.channel.send(python.format(code, result))
