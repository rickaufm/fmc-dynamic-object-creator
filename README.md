# fmc-dynamic-object-creator

A Python CLI tool for managing Dynamic Object mappings in Cisco Firepower Management Center (FMC) via the REST API.

## Requirements

- Python 3.10+
- An FMC instance with API access enabled
- A Dynamic Object already created in FMC

## Installation

```bash
# Clone or download the project, then install dependencies
pip install -r requirements.txt
```

## Configuration

Copy the `.env` file and fill in your values:

| Variable             | Description                                          |
|----------------------|------------------------------------------------------|
| `FMC_IP`             | IP address or hostname of the FMC                    |
| `FMC_USERNAME`       | FMC API username                                     |
| `FMC_PASSWORD`       | FMC API password                                     |
| `DYNAMIC_OBJECT_ID`  | UUID of the Dynamic Object to manage                 |
| `DYNAMIC_OBJECT_NAME`| Name of the Dynamic Object (must match the UUID)     |
| `IP_LIST_URL`        | URL to a newline-separated list of IPv4 addresses    |

> **Note:** The Dynamic Object ID and Name can be found in the FMC UI under **Objects > Object Management > Dynamic Objects**, or via the FMC REST API.

## Usage

```
python main.py [-h] [--verify-ssl] {add,remove} ...
```

### Global flags

| Flag           | Description                                             |
|----------------|---------------------------------------------------------|
| `--verify-ssl` | Enable SSL certificate verification (off by default)    |

---

### Add mappings

```bash
# Fetch IPs from the URL defined in IP_LIST_URL (.env)
python main.py add --url

# Import IPs from a local CSV file (one IP per row, no header)
python main.py add --csv ips.csv

# Add IPs entered directly on the command line
python main.py add --manual "1.2.3.4,5.6.7.8,9.10.11.12"
```

---

### Remove mappings

```bash
# Remove specific IPs
python main.py remove --ips "1.2.3.4,5.6.7.8"

# Remove ALL mappings from the dynamic object
python main.py remove --all
```

---

### SSL verification

By default, SSL certificate verification is **disabled** to support FMC appliances with self-signed certificates (a urllib3 warning is suppressed automatically). To enforce verification against a trusted CA:

```bash
python main.py --verify-ssl add --url
```

---

## CSV file format

The CSV file must contain one IPv4 address per row in the first column. No header row is required:

```
1.2.3.4
5.6.7.8
9.10.11.12
```

---

## Authentication

The script uses the FMC token-based authentication flow:

1. `POST /api/fmc_platform/v1/auth/generatetoken` with HTTP Basic Auth
2. Access token and Domain UUID are extracted from response headers
3. All subsequent requests include the `X-auth-access-token` header

Tokens are valid for **30 minutes**. For long-running batch operations, re-run the script as needed.

---

## API reference

| Operation          | Method | Endpoint                                                                 |
|--------------------|--------|--------------------------------------------------------------------------|
| Generate token     | POST   | `/api/fmc_platform/v1/auth/generatetoken`                                |
| Add mappings       | POST   | `/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjectmappings`    |
| Remove mappings    | POST   | `/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjectmappings`    |
| Remove all         | PUT    | `/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects/{id}/mappings` |
