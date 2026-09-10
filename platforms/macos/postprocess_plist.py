from __future__ import annotations
import plistlib
import sys
from pathlib import Path

p = Path(sys.argv[1])
data = plistlib.loads(p.read_bytes())
data.update({
    "CFBundleDisplayName": "Memory Box",
    "CFBundleName": "Memory Box",
    "CFBundleIdentifier": "com.memorybox.desktop",
    "CFBundleShortVersionString": "0.14.0",
    "CFBundleVersion": "1400",
    "LSApplicationCategoryType": "public.app-category.productivity",
    "NSHighResolutionCapable": True,
    "LSMinimumSystemVersion": "12.0",
    "CFBundleDocumentTypes": [
        {
            "CFBundleTypeName": "Memory Box Transfer Package",
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Owner",
            "CFBundleTypeExtensions": ["mboxpack"],
        },
        {
            "CFBundleTypeName": "Memory Box Encrypted Package",
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Owner",
            "CFBundleTypeExtensions": ["mboxenc"],
        },
        {
            "CFBundleTypeName": "Memory Box Recovery Vault",
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Owner",
            "CFBundleTypeExtensions": ["mbxrecovery"],
        },
    ],
})
p.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_XML, sort_keys=False))
print(p)
