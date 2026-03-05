# 🐍 smart-log-reader

**Stop grep-ing blindly.**  
smart-log-reader is an intelligent, terminal-first log analyzer that instantly parses massive log files, groups similar errors using fuzzy matching, and outputs beautifully formatted, color-coded summaries directly in your terminal.

When the terminal isn't enough, export a fully interactive HTML dashboard and serve it securely from your remote server to your local machine via an SSH tunnel.

## 🚀 Installation

Because this is a standalone CLI tool, **do not install it globally with pip**.  
Use `pipx` to install it in an isolated environment so it never conflicts with your system dependencies.

```bash
pipx install smart-log-reader
````

## 🔥 Quick Start: Real-World Scenarios
#### 1. The "Server is on fire" check (Auto-detects format, groups errors)
```
smart-log-reader -f /var/log/syslog -l ERROR
```

#### 2. The "Odoo is crashing" audit (Filter by time and keyword)
```
smart-log-reader -f odoo-server.log -t odoo -k "psycopg2" -s "2024-03-05 10:00:00"
```

#### 3. Generate an interactive HTML report and serve it securely
```
smart-log-reader -f production.log -t python -x html --serve
```

## ✨ Core Features

- **Format Auto-Detection**  
  Automatically recognizes Python, Django, Flask, Odoo, Nginx, Apache, PostgreSQL, MySQL, and JSON-line logs.

- **Intelligent Error Grouping**  
  Uses `rapidfuzz` (85% threshold) to group thousands of repetitive tracebacks into unique "Core Issues", showing you exactly what broke and how often.

- **Zero-Memory Streaming**  
  Processes multi-gigabyte log files line-by-line without eating up your server's RAM.

- **Multi-line Unification**  
  Automatically stitches stack traces and JSON payloads back together into single, readable entries.

## 🛡️ The Killer Feature: Secure HTML Export & Tunneling

When debugging remote production servers, downloading gigabytes of logs is tedious and risky.  
smart-log-reader solves this natively.

With `--serve`, it:

- generates a self-contained HTML dashboard
- starts a minimal, **localhost-only** HTTP server on the production machine
- lets you view it securely via SSH tunnel

**Your log data never leaves the server.**

### How to use it

**On the remote server:**

```bash
smart-log-reader -f /var/log/nginx/error.log -x html --serve --port 8080
```

**On your local machine:**

```bash
ssh -L 8080:127.0.0.1:8080 your-user@your-remote-server.com
```

Then open in your browser:  
**http://localhost:8080/report_name.html**

> **Alternative (LAN / VPN only):** use `--serve-public` → gets a token-protected URL, no SSH tunnel needed.

## 🛠️ CLI Reference

| Flag              | Description                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| `-f, --file`      | **(Required)** Path to the log file                                        |
| `-t, --log-type`  | Force parser: `auto`, `python`, `django`, `flask`, `odoo`, `nginx`, `apache`, `postgresql`, `mysql`, `mariadb`, `jsonline` |
| `-l, --level`     | Filter by severity: `ALL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`             |
| `-k, --keyword`   | Filter logs containing a specific string or regex pattern                  |
| `-s, --start-time`| Start time filter (e.g. `YYYY-MM-DD HH:MM:SS`)                             |
| `-e, --end-time`  | End time filter                                                            |
| `-x, --export`    | Export format: `none`, `json`, `html`                                      |
| `--serve`         | Starts a localhost-only HTTP server for the HTML export                    |
| `--serve-public`  | **[LAN/VPN ONLY]** Binds server to 0.0.0.0 with secure URL token           |
| `-p, --port`      | Specify port for the HTTP server (defaults to random available port)       |
| `-g, --no-group-errors` | Disables fuzzy error grouping                                       |

## License

[MIT](LICENSE)
