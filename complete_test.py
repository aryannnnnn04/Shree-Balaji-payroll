import urllib.request
import urllib.parse
import http.cookiejar

# Create a cookie jar to store cookies
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

# 1. First, let's access the login page to get any initial cookies
print("1. Accessing login page...")
login_page_req = urllib.request.Request('http://127.0.0.1:5001/login')
login_page_response = opener.open(login_page_req)
print(f"   Login page status: {login_page_response.getcode()}")

# 2. Now let's try to login
print("2. Attempting login...")
login_data = urllib.parse.urlencode({
    'username': 'admin',
    'password': 'shreebalaji2024'
}).encode()

login_req = urllib.request.Request('http://127.0.0.1:5001/login', data=login_data, method='POST')
login_req.add_header('Content-Type', 'application/x-www-form-urlencoded')

try:
    login_response = opener.open(login_req)
    print(f"   Login response status: {login_response.getcode()}")
    print(f"   Login response URL: {login_response.geturl()}")
    
    # Print cookies
    print("   Cookies after login:")
    for cookie in cookie_jar:
        print(f"     {cookie.name}: {cookie.value}")
        
except urllib.error.HTTPError as e:
    print(f"   Login failed with HTTP error: {e.code}")
    print(e.read().decode())

# 3. Now check if we're logged in by accessing the dashboard
print("3. Accessing dashboard...")
try:
    dashboard_req = urllib.request.Request('http://127.0.0.1:5001/')
    dashboard_response = opener.open(dashboard_req)
    print(f"   Dashboard status: {dashboard_response.getcode()}")
    content = dashboard_response.read().decode()
    if "Shree Balaji Centring Works" in content:
        print("   SUCCESS: Dashboard content loaded correctly")
    else:
        print("   WARNING: Dashboard content doesn't match expected content")
except urllib.error.HTTPError as e:
    print(f"   Dashboard access failed with HTTP error: {e.code}")
    print(e.read().decode())

# 4. Test the API endpoints that require login
print("4. Testing API endpoints...")
try:
    workers_req = urllib.request.Request('http://127.0.0.1:5001/api/workers')
    workers_response = opener.open(workers_req)
    print(f"   Workers API status: {workers_response.getcode()}")
    content = workers_response.read().decode()
    if "[]" in content or "[" in content:
        print("   SUCCESS: Workers API accessible")
    else:
        print("   WARNING: Workers API returned unexpected content")
except urllib.error.HTTPError as e:
    print(f"   Workers API failed with HTTP error: {e.code}")
    print(e.read().decode())

print("Test completed!")