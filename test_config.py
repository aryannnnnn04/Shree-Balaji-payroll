"""Test configuration and utilities for BlazeCore Payroll Tests"""

import os
import urllib.request
import urllib.parse
import json
import http.cookiejar
from datetime import datetime
from typing import Optional

# Test configuration
TEST_CONFIG = {
    "BASE_URL": os.environ.get("TEST_BASE_URL", "http://localhost:5001"),
    "TEST_USERNAME": os.environ.get("TEST_USERNAME", "admin"),
    "TEST_PASSWORD": os.environ.get("TEST_PASSWORD", "test_password"),  # Never use production password in tests
    "DEBUG": os.environ.get("TEST_DEBUG", "true").lower() == "true",
    "POSTGRES_URL": os.environ.get("POSTGRES_URL", "postgresql://test:test@localhost:5432/test")  # Default test database URL
}

class TestSession:
    """Manages test session and authentication"""
    
    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.logged_in = False
    
    def login(self) -> bool:
        """Login to the application for testing
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            # Prepare login data
            login_data = urllib.parse.urlencode({
                "username": TEST_CONFIG["TEST_USERNAME"],
                "password": TEST_CONFIG["TEST_PASSWORD"]
            }).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                f"{TEST_CONFIG['BASE_URL']}/login",
                data=login_data,
                method='POST'
            )
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            # Send request
            response = self.opener.open(req)
            
            # Check if login was successful by trying to access a protected route
            try:
                check_req = urllib.request.Request(f"{TEST_CONFIG['BASE_URL']}/dashboard")
                check_response = self.opener.open(check_req)
                self.logged_in = check_response.getcode() == 200
                return self.logged_in
            except:
                return False
            
        except Exception as e:
            if TEST_CONFIG["DEBUG"]:
                print(f"Login failed: {str(e)}")
            return False
    
    def request(self, endpoint: str, method: str = 'GET', data: Optional[dict] = None) -> tuple:
        """Make a request to the test server
        
        Args:
            endpoint: API endpoint to call
            method: HTTP method to use
            data: Data to send with the request
            
        Returns:
            tuple: (success: bool, response_data: dict)
        """
        try:
            url = f"{TEST_CONFIG['BASE_URL']}{endpoint}"
            
            if data and method in ['POST', 'PUT']:
                request_data = json.dumps(data).encode('utf-8')
            else:
                request_data = None
            
            req = urllib.request.Request(
                url,
                data=request_data,
                method=method
            )
            
            if request_data:
                req.add_header('Content-Type', 'application/json')
            
            response = self.opener.open(req)
            content_type = response.getheader('Content-Type', '')
            
            if 'application/json' in content_type:
                response_data = json.loads(response.read().decode('utf-8'))
            else:
                response_data = {'status': response.getcode()}
            
            return True, response_data
            
        except Exception as e:
            if TEST_CONFIG["DEBUG"]:
                print(f"Request failed: {str(e)}")
            return False, {"error": str(e)}
    
    def cleanup(self):
        """Clean up test session"""
        self.cookie_jar.clear()
        self.logged_in = False

# Helper functions
def generate_test_name() -> str:
    """Generate a unique test name with timestamp
    
    Returns:
        str: Test name with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"Test_Worker_{timestamp}"