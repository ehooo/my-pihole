import argparse
import sys

from pihole import PiHoleAPI


def main():
    parser = argparse.ArgumentParser(description='Get list of non blocked hosts.')
    parser.add_argument(
        '--host', default=None,
        help='If is present use it for filter the non blocked hosts.'
    )
    options = parser.parse_args(sys.argv[1:])

    host_stream = sys.stdout

    f = 'secrets.env'
    config = {}
    for line in open(f):
        line = line.replace('\n', '').replace('\r', '')
        if line:
            key, val = line.split('=', 1)
            config[key] = val

    pi = PiHoleAPI(config.get('PIHOLE_HOST', 'http://127.0.0.1'))
    pi.auth(config.get('WEBPASSWORD'))

    hosts = pi.get_unique_non_blocked_queries(options.host)
    for host in sorted(hosts):
        host_stream.write(host)
        host_stream.write('\r\n')


if __name__ == '__main__':
    main()
