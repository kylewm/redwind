import argparse
import sys


parser = argparse.ArgumentParser(prog="client.py")
parser.add_argument('--foo', action='store_true', help='foo help')

subparsers = parser.add_subparsers(help="sub-command help")
list_parser = subparsers.add_parser("list", help="List all existing posts")
create_parser = subparsers.add_parser("create", help="Create a new post")
edit_parser = subparsers.add_parser("edit", help="Edit an existing post")
delete_parser = subparsers.add_parser("delete", help="Delete an existing post")

if __name__ == '__main__':
    print(parser.parse_args())
