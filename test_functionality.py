import urllib.request
import urllib.parse
import json
import http.cookiejar

# Base URL for the application
BASE_URL = "http://localhost:5001"

# Create a cookie jar to maintain session
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

def test_login():
    """Test login functionality"""
    print("Testing login...")
    try:
        # Prepare login data
        login_data = urllib.parse.urlencode({
            "username": "admin",
            "password": "shreebalaji2024"
        }).encode('utf-8')
        
        # Create request
        req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        # Send request
        response = opener.open(req)
        
        if response.getcode() == 302:  # Redirect to dashboard
            print("✓ Login successful")
            return True
        else:
            print(f"✗ Login failed with status code: {response.getcode()}")
            return False
    except Exception as e:
        print(f"✗ Login failed with error: {str(e)}")
        return False

def test_dashboard_access():
    """Test dashboard access"""
    print("Testing dashboard access...")
    try:
        req = urllib.request.Request(BASE_URL)
        response = opener.open(req)
        
        if response.getcode() == 200:
            print("✓ Dashboard access successful")
            return True
        else:
            print(f"✗ Dashboard access failed with status code: {response.getcode()}")
            return False
    except Exception as e:
        print(f"✗ Dashboard access failed with error: {str(e)}")
        return False

def test_add_worker():
    """Test adding a worker"""
    print("Testing worker creation...")
    try:
        # Prepare worker data
        worker_data = {
            "name": "Test Worker",
            "wage": 500,
            "phone": "9876543210",
            "start_date": "2025-09-23"
        }
        
        # Convert to JSON and encode
        json_data = json.dumps(worker_data).encode('utf-8')
        
        # Create request
        req = urllib.request.Request(f"{BASE_URL}/api/add_worker", data=json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        # Send request
        response = opener.open(req)
        
        if response.getcode() == 200:
            result = json.loads(response.read().decode('utf-8'))
            if result.get("success"):
                print(f"✓ Worker created successfully with ID: {result.get('worker_id')}")
                return result.get('worker_id')
            else:
                print(f"✗ Worker creation failed: {result.get('error')}")
                return None
        else:
            print(f"✗ Worker creation failed with status code: {response.getcode()}")
            return None
    except Exception as e:
        print(f"✗ Worker creation failed with error: {str(e)}")
        return None

def test_worker_details(worker_id):
    """Test worker details page"""
    print(f"Testing worker details page for worker ID: {worker_id}")
    try:
        req = urllib.request.Request(f"{BASE_URL}/worker/{worker_id}")
        response = opener.open(req)
        
        if response.getcode() == 200:
            print("✓ Worker details page access successful")
            return True
        else:
            print(f"✗ Worker details page access failed with status code: {response.getcode()}")
            return False
    except Exception as e:
        print(f"✗ Worker details page access failed with error: {str(e)}")
        return False

def test_mark_attendance(worker_id):
    """Test marking attendance"""
    print(f"Testing attendance marking for worker ID: {worker_id}")
    try:
        # Prepare attendance data
        attendance_data = {
            "worker_id": worker_id,
            "date": "2025-09-23",
            "status": "Present"
        }
        
        # Convert to JSON and encode
        json_data = json.dumps(attendance_data).encode('utf-8')
        
        # Create request
        req = urllib.request.Request(f"{BASE_URL}/api/mark_attendance", data=json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        # Send request
        response = opener.open(req)
        
        if response.getcode() == 200:
            result = json.loads(response.read().decode('utf-8'))
            if result.get("success"):
                print("✓ Attendance marked successfully")
                return True
            else:
                print(f"✗ Attendance marking failed: {result.get('error')}")
                return False
        else:
            print(f"✗ Attendance marking failed with status code: {response.getcode()}")
            return False
    except Exception as e:
        print(f"✗ Attendance marking failed with error: {str(e)}")
        return False

def main():
    """Main test function"""
    print("Starting functionality tests...\n")
    
    # Test login
    if not test_login():
        return
    
    # Test dashboard access
    if not test_dashboard_access():
        return
    
    # Test adding worker
    worker_id = test_add_worker()
    if not worker_id:
        return
    
    # Test worker details page
    if not test_worker_details(worker_id):
        return
    
    # Test marking attendance
    if not test_mark_attendance(worker_id):
        return
    
    print("\n✓ All tests passed!")

if __name__ == "__main__":
    main()