#!/usr/bin/env python3
"""
FMC Dynamic Object Creator
Manage Dynamic Object mappings in Cisco Firepower Management Center via REST API.

Requires Python 3.10+
"""

import argparse
import csv
import os
import sys

import requests
import urllib3
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

FMC_IP: str = os.getenv("FMC_IP", "")
FMC_USERNAME: str = os.getenv("FMC_USERNAME", "")
FMC_PASSWORD: str = os.getenv("FMC_PASSWORD", "")
DYNAMIC_OBJECT_ID: str = os.getenv("DYNAMIC_OBJECT_ID", "")
DYNAMIC_OBJECT_NAME: str = os.getenv("DYNAMIC_OBJECT_NAME", "")
IP_LIST_URL: str = os.getenv("IP_LIST_URL", "")

# ---------------------------------------------------------------------------
# API path templates
# ---------------------------------------------------------------------------

AUTH_ENDPOINT = "/api/fmc_platform/v1/auth/generatetoken"
MAPPINGS_ENDPOINT = "/api/fmc_config/v1/domain/{domain_uuid}/object/dynamicobjectmappings"
OBJECT_MAPPINGS_ENDPOINT = (
    "/api/fmc_config/v1/domain/{domain_uuid}/object/dynamicobjects/{object_id}/mappings"
)

# ---------------------------------------------------------------------------
# FMC API client
# ---------------------------------------------------------------------------


class FMCClient:
    """Handles authentication and API calls against a single FMC instance."""

    def __init__(self, fmc_ip: str, username: str, password: str, verify_ssl: bool = False) -> None:
        self.base_url = f"https://{fmc_ip}"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.access_token: str = ""
        self.domain_uuid: str = ""
        self.session = requests.Session()

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Obtain an access token and domain UUID from the FMC auth endpoint."""
        url = f"{self.base_url}{AUTH_ENDPOINT}"
        print(f"[*] Authenticating to FMC at {self.base_url} ...")

        try:
            response = self.session.post(
                url,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
                verify=self.verify_ssl,
                timeout=30,
            )
        except requests.exceptions.ConnectionError:
            print(f"[!] Unable to connect to FMC at {self.base_url}. Check FMC_IP in .env.")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("[!] Connection to FMC timed out.")
            sys.exit(1)

        if response.status_code != 204:
            print(f"[!] Authentication failed: HTTP {response.status_code}")
            sys.exit(1)

        self.access_token = response.headers.get("X-auth-access-token", "")
        self.domain_uuid = response.headers.get("DOMAIN_UUID", "")

        if not self.access_token:
            print("[!] No access token found in response headers.")
            sys.exit(1)

        if not self.domain_uuid:
            print("[!] No Domain UUID found in response headers.")
            sys.exit(1)

        print(f"[+] Authenticated successfully. Domain UUID: {self.domain_uuid}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-auth-access-token": self.access_token,
        }

    def _handle_error(self, action: str, response: requests.Response) -> None:
        print(f"[!] Failed to {action}: HTTP {response.status_code}")
        if response.text:
            print(f"    Response: {response.text}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # API operations
    # ------------------------------------------------------------------

    def add_mappings(self, ip_list: list[str], object_id: str, object_name: str) -> None:
        """POST a list of IPs as new mappings for the given dynamic object."""
        url = f"{self.base_url}{MAPPINGS_ENDPOINT.format(domain_uuid=self.domain_uuid)}"
        payload = {
            "add": [
                {
                    "dynamicObject": {
                        "id": object_id,
                        "name": object_name,
                        "type": "DynamicObject",
                    },
                    "mappings": ip_list,
                }
            ]
        }

        print(f"[*] Adding {len(ip_list)} mapping(s) to '{object_name}' ...")
        response = self.session.post(
            url, json=payload, headers=self._auth_headers(), verify=self.verify_ssl, timeout=30
        )

        if response.status_code in (200, 201):
            print(f"[+] Successfully added {len(ip_list)} mapping(s).")
        else:
            self._handle_error("add mappings", response)

    def remove_mappings(self, ip_list: list[str], object_id: str, object_name: str) -> None:
        """POST a list of IPs to remove from the given dynamic object."""
        url = f"{self.base_url}{MAPPINGS_ENDPOINT.format(domain_uuid=self.domain_uuid)}"
        payload = {
            "remove": [
                {
                    "dynamicObject": {
                        "id": object_id,
                        "name": object_name,
                        "type": "DynamicObject",
                    },
                    "mappings": ip_list,
                }
            ]
        }

        print(f"[*] Removing {len(ip_list)} mapping(s) from '{object_name}' ...")
        response = self.session.post(
            url, json=payload, headers=self._auth_headers(), verify=self.verify_ssl, timeout=30
        )

        if response.status_code in (200, 201):
            print(f"[+] Successfully removed {len(ip_list)} mapping(s).")
        else:
            self._handle_error("remove mappings", response)

    def remove_all_mappings(self, object_id: str) -> None:
        """PUT to clear every mapping from the given dynamic object."""
        url = f"{self.base_url}{OBJECT_MAPPINGS_ENDPOINT.format(domain_uuid=self.domain_uuid, object_id=object_id)}"
        payload = {
            "id": object_id,
            "type": "DynamicObjectMappings",
        }

        print(f"[*] Removing ALL mappings from object ID '{object_id}' ...")
        response = self.session.put(
            url, json=payload, headers=self._auth_headers(), verify=self.verify_ssl, timeout=30
        )

        if response.status_code in (200, 201):
            print("[+] Successfully removed all mappings.")
        else:
            self._handle_error("remove all mappings", response)


# ---------------------------------------------------------------------------
# IP list sources
# ---------------------------------------------------------------------------


def fetch_ips_from_url(url: str, verify_ssl: bool = False) -> list[str]:
    """Download a newline-separated list of IPv4 addresses from a URL."""
    print(f"[*] Fetching IP list from: {url}")
    try:
        response = requests.get(url, verify=verify_ssl, timeout=30)
    except requests.exceptions.RequestException as exc:
        print(f"[!] Failed to fetch IP list: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"[!] Failed to fetch IP list: HTTP {response.status_code}")
        sys.exit(1)

    ips = [line.strip() for line in response.text.splitlines() if line.strip()]
    print(f"[+] Retrieved {len(ips)} IP address(es) from URL.")
    return ips


def fetch_ips_from_csv(filepath: str) -> list[str]:
    """Read a single-column CSV file and return a list of IP addresses."""
    path = Path(filepath)
    if not path.exists():
        print(f"[!] CSV file not found: {filepath}")
        sys.exit(1)

    ips: list[str] = []
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if row and row[0].strip():
                ips.append(row[0].strip())

    if not ips:
        print(f"[!] No IP addresses found in CSV file: {filepath}")
        sys.exit(1)

    print(f"[+] Loaded {len(ips)} IP address(es) from CSV.")
    return ips


def parse_manual_ips(ip_string: str) -> list[str]:
    """Parse a comma-separated string of IP addresses."""
    ips = [ip.strip() for ip in ip_string.split(",") if ip.strip()]
    if not ips:
        print("[!] No valid IP addresses found in manual input.")
        sys.exit(1)
    print(f"[+] Parsed {len(ips)} IP address(es) from manual input.")
    return ips


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


def validate_config() -> None:
    """Exit early if any required .env variable is missing."""
    required = {
        "FMC_IP": FMC_IP,
        "FMC_USERNAME": FMC_USERNAME,
        "FMC_PASSWORD": FMC_PASSWORD,
        "DYNAMIC_OBJECT_ID": DYNAMIC_OBJECT_ID,
        "DYNAMIC_OBJECT_NAME": DYNAMIC_OBJECT_NAME,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        print(f"[!] Missing required configuration variable(s): {', '.join(missing)}")
        print("    Please update your .env file.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fmc-dynamic-object-creator",
        description=(
            "Manage Cisco FMC Dynamic Object mappings via REST API.\n"
            "Configuration is read from a .env file in the working directory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Add IPs fetched from the URL defined in .env
  python main.py add --url

  # Add IPs from a local CSV file
  python main.py add --csv ips.csv

  # Add IPs entered manually
  python main.py add --manual "1.2.3.4,5.6.7.8"

  # Remove specific IPs
  python main.py remove --ips "1.2.3.4,5.6.7.8"

  # Remove ALL mappings from the dynamic object
  python main.py remove --all

  # Enable SSL certificate verification
  python main.py --verify-ssl add --url
""",
    )

    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        default=False,
        help="Enable SSL certificate verification (disabled by default).",
    )

    subparsers = parser.add_subparsers(dest="action", required=True, title="commands")

    # -- add --
    add_parser = subparsers.add_parser("add", help="Add IP mappings to the dynamic object.")
    add_source = add_parser.add_mutually_exclusive_group(required=True)
    add_source.add_argument(
        "--url",
        action="store_true",
        help="Fetch IPs from IP_LIST_URL defined in .env (one IP per line).",
    )
    add_source.add_argument(
        "--csv",
        metavar="FILE",
        help="Path to a CSV file containing one IP address per row.",
    )
    add_source.add_argument(
        "--manual",
        metavar="IPs",
        help='Comma-separated list of IPs to add, e.g. "1.2.3.4,5.6.7.8".',
    )

    # -- remove --
    remove_parser = subparsers.add_parser("remove", help="Remove IP mappings from the dynamic object.")
    remove_group = remove_parser.add_mutually_exclusive_group(required=True)
    remove_group.add_argument(
        "--ips",
        metavar="IPs",
        help='Comma-separated list of IPs to remove, e.g. "1.2.3.4,5.6.7.8".',
    )
    remove_group.add_argument(
        "--all",
        action="store_true",
        help="Remove ALL mappings from the dynamic object.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    validate_config()

    client = FMCClient(FMC_IP, FMC_USERNAME, FMC_PASSWORD, verify_ssl=args.verify_ssl)
    client.authenticate()

    match args.action:
        case "add":
            if args.url:
                if not IP_LIST_URL:
                    print("[!] IP_LIST_URL is not set in .env file.")
                    sys.exit(1)
                ip_list = fetch_ips_from_url(IP_LIST_URL, verify_ssl=args.verify_ssl)
            elif args.csv:
                ip_list = fetch_ips_from_csv(args.csv)
            else:
                ip_list = parse_manual_ips(args.manual)

            client.add_mappings(ip_list, DYNAMIC_OBJECT_ID, DYNAMIC_OBJECT_NAME)

        case "remove":
            if args.all:
                client.remove_all_mappings(DYNAMIC_OBJECT_ID)
            else:
                ip_list = parse_manual_ips(args.ips)
                client.remove_mappings(ip_list, DYNAMIC_OBJECT_ID, DYNAMIC_OBJECT_NAME)


if __name__ == "__main__":
    main()
