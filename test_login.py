import urllib.request
import urllib.parse

# First, let's try to login
login_data = urllib.parse.urlencode({
    'username': 'admin',
    'password': 'shreebalaji2024'
}).encode()

login_req = urllib.request.Request('http://127.0.0.1:5001/login', data=login_data, method='POST')
login_req.add_header('Content-Type', 'application/x-www-form-urlencoded')

# Create an opener to handle cookies
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

# Login
login_response = opener.open(login_req)
print("Login response:")
print(login_response.read().decode())

# Now check if we're logged in by accessing the test route
test_req = urllib.request.Request('http://127.0.0.1:5001/test')
test_response = opener.open(test_req)
print("\nTest response after login:")
print(test_response.read().decode())