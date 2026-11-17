"""Small read-only ubus/jsonfilter fixture; never calls networking tools.

This adapter supports only the JSON paths used by the unit tests. It is not
an OpenWrt emulator and does not validate the real jsonfilter/netifd ABI.
"""
import json
import os
import re
import sys

if sys.argv[1] == 'ubus':
    data = json.loads(os.environ['ROUTER_FIXTURE'])
    name = sys.argv[3]
    if name not in data:
        sys.exit(1)
    print(json.dumps(data[name]))
else:
    expression = sys.argv[sys.argv.index('-e') + 1]
    value = json.load(sys.stdin)
    for field, index, key in re.findall(r'\["([^"]+)"\]|\[(\d+)\]|\.([\w-]+)', expression):
        try:
            value = value[int(index)] if index else value[field or key]
        except (KeyError, IndexError, TypeError):
            sys.exit(0)
    if isinstance(value, bool):
        print(str(value).lower())
    elif not isinstance(value, (dict, list)):
        print(value)
