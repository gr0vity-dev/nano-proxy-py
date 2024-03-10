
# nano-proxy

## Overview

nano-proxy is designed to support whitelisting of rpc commands and applies rate limits based on auth tokens.

## Features

- **Command Whitelisting:** Only allows pre-configured commands to be executed by authenticated users, enhancing security and control over the API's usage.
- **Dynamic Rate Limiting:** Applies different rate limits to different users based on their authentication token. 
- **Hot Configuration Reload:** Supports reloading of the configuration without restarting the application, allowing updates to tokens, commands, and rate limits on the fly.
- **Forced RPC Values:** For each rpc command you can specify forced values that will overwrite user defined values.

## Setup and Running

``` cp settings.py.example settings.py && 
docker compose build && docker compose up -d
```
You can modify `settings.py` without restarting the app


## Example usage

```bash
curl -d '{"action":"receivable" , "account":"nano_37imps4zk1dfahkqweqa91xpysacb7scqxf3jqhktepeofcxqnpx531b3mnt"}' -H "Authorization: Bearer actual_secret_token" -H "Content-Type: application/json" -X POST http://localhost:5001/rpc
```

```bash
curl -d '{"action":"block_count"}' http://localhost:5001/rpc
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any improvements or bug fixes.
