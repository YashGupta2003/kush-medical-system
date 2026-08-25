import re
import os

frontend_client_js = "../frontend/src/api/client.js"
backend_routers_dir = "app/routers"

with open(frontend_client_js, "r") as f:
    js_code = f.read()

# Extract API endpoints called in client.js
api_fetch_regex = re.compile(r'apiFetch\(\s*[`\'"](.*?)[`\'"\?]')
called_endpoints = []
for match in api_fetch_regex.finditer(js_code):
    endpoint = match.group(1)
    # Remove dynamic parts (e.g. ${id})
    endpoint = re.sub(r'\$\{.*?\}', '*', endpoint)
    # Remove query params that were matched if any
    endpoint = endpoint.split('?')[0]
    called_endpoints.append(endpoint)

print(f"Found {len(called_endpoints)} API endpoints in client.js")

# Find all defined endpoints in backend
backend_endpoints = []
for root, _, files in os.walk(backend_routers_dir):
    for file in files:
        if file.endswith(".py"):
            with open(os.path.join(root, file), "r") as f:
                code = f.read()
                # Find @router.get/post/etc.
                router_regex = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*["\'](.*?)["\']')
                for match in router_regex.finditer(code):
                    method = match.group(1).upper()
                    path = match.group(2)
                    path = re.sub(r'\{.*?\}', '*', path)
                    backend_endpoints.append(f"/{file[:-3].replace('_', '-')}{path}")

print("Checking which frontend calls might not match a backend route prefix...")
for ce in called_endpoints:
    # A rough heuristic: the first part of the called endpoint (e.g. /bills/...) should match a router
    prefix = ce.split('/')[1] if len(ce.split('/')) > 1 else ""
    found = False
    for _, _, bp in backend_endpoints:
        pass
        
    print(ce)
