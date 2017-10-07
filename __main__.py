from rotom import Bot
import argparse

parser = argparse.ArgumentParser(description='Runs Rotom.')
parser.add_argument('-c', '--config', type=str, help='Config file name (default: config.yml)')
parser.add_argument('-d', '--debug', help='Enable debug mode', action='store_true')
parser.add_argument('-s', '--setup', help='Set up the bot', action='store_true')
args = parser.parse_args()

if args.config is None:
    args.config = 'config.yml'

rotom = Bot(config=args.config, debug=args.debug)
rotom.run()
