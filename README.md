# Algorithmic Sciences Introductory Task – TCP Search Server

This repository implements the **Algorithmic Sciences Introductory Task** as specified in the PDF brief.  
It includes:

- A **multithreaded TCP server** with optional SSL, full-line search, config-driven behavior, and detailed logging.
- A **client script** for sending queries and measuring response times.
- A **streamlit app** for rapid prototyping and testing.
- A **benchmark suite** that evaluates 5+ search algorithms across multiple file sizes and QPS levels, producing a PDF report with tables, charts, and summaries.
- **Unit tests** for correctness and robustness.
- Systemd unit file for running the server as a Linux service.

---

## 📦 Project Structure

```
algosciences-task/
├── benchmarks/
│   ├── benchmark.py           # Run benchmarks on different file sizes + QPS
│   ├── generate_report.py     # Build PDF report with tables, charts, summary
│   └── tmp/                   # Temporary generated test files
├── reports/
│   └── speed_report.pdf       # Auto-generated benchmark report
├── server/
│   ├── __init__.py
│   ├── main_server.py         # Entry point for TCP server
│   ├── search_algorithms.py   # Implementations: set, list, mmap, binary, grep
│   ├── ssl_utils.py           # SSL wrapper
│   └── utils.py               # Helpers: logging, recv safety, timestamp
├── tests/  # Test input files
│   ├── test_algorithms.py      
|   ├── test_client.py            
|   ├── test_server.py          
|   └── test_performance.py 
├── client.py                  # CLI client to send queries
├── streamlit_app.py           # Web UI for prototyping
├── config.ini.example         # Example server config
├── setup_systemd.service      # Systemd unit file for daemonization
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

---

## ⚙️ Setup

### 1. Clone and Create Virtual Environment

```bash
git clone https://github.com/<your-org>/algosciences-task.git
cd algosciences-task
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download Test Data

Create the data directory and download the required data file:

```bash
mkdir -p data
curl -o data/200k.txt https://tests.quantitative-analysis.com/200k.txt
```

Alternatively, using wget:

```bash
mkdir -p data
wget -O data/200k.txt https://tests.quantitative-analysis.com/200k.txt
```

Verify the file was downloaded successfully:

```bash
ls -lh data/200k.txt
```

### 3. Configure the Server

Copy the example configuration file:

```bash
cp config.ini.example config.ini
```

The default configuration is ready to use. You can customize settings in `config.ini`:

- `LINUXPATH`: Path to your data file (default: `./data/200k.txt`).
- `DEFAULT_ALGORITHM`: Search algorithm to use (`set`, `list`, `mmap`, `binary`).
- `HOST`/`PORT`: Server binding address and port.
- `REREAD_ON_QUERY`: Whether to reload the file on each query.

**Note**: Before running the server, ensure you have completed all setup steps above, including downloading the data file and creating your `config.ini` from the example file.

---

## 🚀 Running the Server

### Standard Mode

```bash
python3 -m server.main_server --config config.ini
```

Expected output:
- INFO Starting server on 0.0.0.0:44445 SSL=False

### With SSL Enabled

#### SSL Setup

To enable SSL, set `SSL_ENABLED=True` in `config.ini` and provide valid certificate and key files.

#### Generate a Self-Signed Certificate (Linux/macOS)

```bash
mkdir -p certs
openssl req -newkey rsa:2048 -nodes -keyout certs/server.key \
  -x509 -days 365 -out certs/server.crt
```

This will create:

- `certs/server.key` → private key.
- `certs/server.crt` → self-signed certificate.

#### Generate a Self-Signed Certificate (Windows, PowerShell)

```powershell
mkdir certs
New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\CurrentUser\My"
# Export certificate and private key into certs/server.crt and certs/server.key
```

#### Update config.ini

Uncomment and set the paths:

```ini
SSL_ENABLED = True
SSL_CERTFILE = ./certs/server.crt
SSL_KEYFILE = ./certs/server.key
```

---

## Running the Client

### Send a Query That Exists in data/200.txt

#### Run Client Without SSL

```bash
python3 client.py --host 127.0.0.1 --port 44445 --string "your string"
```

#### Run Client With SSL

```bash
python3 client.py --host 127.0.0.1 --port 44445 --ssl --string "your_string"
```

Output:

```bash
Response: STRING EXISTS
Elapsed: 0.412 ms
```

### Query a String That Does Not Exist

```bash
python3 client.py --host 127.0.0.1 --port 44445 --string "1;9;2;3;6;1;0;2;"
```

Output:

```bash
Response: STRING NOT FOUND
Elapsed: 0.389 ms
```

---

## Streamlit Web UI

Start the Streamlit app:

```bash
streamlit run streamlit_app.py
```

Then open: http://localhost:8501

You can configure host/port and send queries interactively.

---

## Testing

Run the unit tests with pytest:

```bash
pytest -q
```

All algorithms and server responses are covered.
Tests use temporary files (no hard-coded paths).

---

## Benchmarks & Reports

### Run Series Benchmark (File Sizes)

```bash
python3 -m benchmarks.benchmark \
  --sizes 1000 5000 10000 50000 250000 1000000 \
  --out ./benchmarks/results_series.csv
```

### Run Series + QPS Benchmark

```bash
python3 -m benchmarks.benchmark \
  --sizes 1000 5000 10000 50000 250000 1000000 \
  --out ./benchmarks/results_series.csv \
  --qps
```

This generates:

- `benchmarks/results_series.csv` (avg ms/query per file size).
- `benchmarks/results_qps.csv` (achieved QPS per algorithm/target).

### Generate PDF Report

```bash
python3 -m benchmarks.generate_report \
  --csv ./benchmarks/results_series.csv \
  --qps ./benchmarks/results_qps.csv \
  --out ./reports/speed_report.pdf
```

The PDF includes:

- Results table (ms/query per algorithm & size).
- Bar charts for each file size.
- Line chart for throughput (QPS vs target).
- Summary table with best algorithm per file size and best throughput algorithm.

---

## Logging

Every client query is logged to stdout in PDF-compliant format:

```bash
DEBUG: query=3;0;1;28;0;7;5;0; ip=127.0.0.1:54707 time=2025-09-29T17:19:44Z exec_ms=0.035
```

Log fields:

- `query`: submitted search string.
- `ip`: client IP and port.
- `time`: ISO-8601 timestamp.
- `exec_ms`: execution time in milliseconds.

This format ensures queries can be reliably parsed for monitoring or auditing.

---

## Testing REREAD_ON_QUERY

1. Set `REREAD_ON_QUERY = True` in `config.ini`.
2. Start server.
3. Query for a string not in `data/200.txt` → expect `STRING NOT FOUND`.
4. Append that string to the file without restarting server.
5. Query again → now expect `STRING EXISTS`.

If `REREAD_ON_QUERY = False`, step 5 will still return `NOT FOUND` until the server restarts.

---

## Run as a Linux Service

Use the provided `setup_systemd.service`:

```bash
sudo cp setup_systemd.service /etc/systemd/system/algoserver.service
sudo systemctl daemon-reload
sudo systemctl enable algoserver
sudo systemctl start algoserver
sudo systemctl status algoserver
```

Adjust `User=` and `WorkingDirectory=` in the service file to your environment.

---

## Performance Benchmarks

Performance expectations (per specification):

- `REREAD_ON_QUERY = True` → average < 40 ms at 250k rows.
- `REREAD_ON_QUERY = False` → average < 0.5 ms at 250k rows.
