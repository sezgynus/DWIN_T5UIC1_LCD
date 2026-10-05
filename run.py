#!/usr/bin/env python3
import argparse
import logging
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--moonraker-url', default=os.environ.get('MOONRAKER_URL', 'http://127.0.0.1:7125'))
    parser.add_argument('--request-timeout', type=float, default=5.0)
    parser.add_argument('--serial-port', default='/dev/ttyAMA0')
    parser.add_argument('--encoder-pins', type=int, nargs=2, default=(21, 19))
    parser.add_argument('--button-pin', type=int, default=13)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from dwinlcd import DWIN_LCD
    DWIN_LCD(args.serial_port, tuple(args.encoder_pins), args.button_pin,
             os.environ.get('MOONRAKER_API_KEY', ''),
             moonraker_url=args.moonraker_url, request_timeout=args.request_timeout)


if __name__ == '__main__':
    main()
