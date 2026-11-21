# Third-party notices

The app image bundles the following software. Each package's full license
text ships inside the image together with the package (Python packages in their
`*.dist-info` folders, Debian packages under `/usr/share/doc`). Exact versions:
`konzertmeister_mcp/constraints.txt`.

| Software | Used for | License | Copyright |
|---|---|---|---|
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp`) | MCP protocol implementation and server | MIT | © Anthropic, PBC and contributors |
| [HTTPX](https://github.com/encode/httpx) | HTTP client for the Konzertmeister API | BSD-3-Clause | © Encode OSS Ltd. |
| [Starlette](https://github.com/encode/starlette) | App web UI | BSD-3-Clause | © Encode OSS Ltd. |
| [Uvicorn](https://github.com/encode/uvicorn) | Web server for the app UI and the MCP servers | BSD-3-Clause | © Encode OSS Ltd. |
| [Pydantic](https://github.com/pydantic/pydantic) | Data validation (used by the MCP SDK) | MIT | © Pydantic Services Inc. and contributors |
| [AnyIO](https://github.com/agronholm/anyio) | Async support | MIT | © Alex Grönholm and contributors |
| [python-multipart](https://github.com/Kludex/python-multipart) | Form parsing in the web UI | Apache-2.0 | © Andrew Dunham and contributors |
| [tzdata](https://github.com/python/tzdata) | Time zone data | Apache-2.0 | © Python Software Foundation and contributors (data: IANA, public domain) |
| [nginx](https://nginx.org) | Secret-path reverse proxy | BSD-2-Clause | © Igor Sysoev, Nginx, Inc. |
| [Python](https://www.python.org) / Debian base image | Runtime | PSF License / various free licenses | © Python Software Foundation, Debian contributors |

Further dependencies of these packages (e.g. `h11`, `httpcore`, `sse-starlette`,
`jsonschema`, `cryptography`) are listed in `constraints.txt`; their licenses ship in the
image as well.

"Konzertmeister" is a trademark of KM Konzertmeister GmbH. It is used here only to
describe compatibility. This project is not affiliated with or endorsed by KM
Konzertmeister GmbH. It uses only the official, documented Konzertmeister API.
