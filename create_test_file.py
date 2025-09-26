with open('test_login.py', 'w', encoding='utf-8') as f:
    f.write('''"""Security testing for login and authentication"""

import unittest
from datetime import datetime
from test_config import TestSession, TEST_CONFIG

class TestLoginSecurity(unittest.TestCase):
    """Test cases for login security features"""
    
    def setUp(self):
        """Set up each test"""
        self.session = TestSession()
    
    def test_successful_login(self):
        """Test successful login with correct credentials"""
        success = self.session.login()
        self.assertTrue(success, "Login failed with correct credentials")
    
    def test_failed_login_wrong_password(self):
        """Test login with wrong password"""
        self.session.cookie_jar.clear()
        success, _ = self.session.request(
            "/login",
            method="POST",
            data={
                "username": TEST_CONFIG["TEST_USERNAME"],
                "password": "wrong_password"
            }
        )
        self.assertFalse(success, "Login succeeded with wrong password")
    
    def test_failed_login_wrong_username(self):
        """Test login with wrong username"""
        self.session.cookie_jar.clear()
        success, _ = self.session.request(
            "/login",
            method="POST",
            data={
                "username": "wrong_username",
                "password": TEST_CONFIG["TEST_PASSWORD"]
            }
        )
        self.assertFalse(success, "Login succeeded with wrong username")
    
    def test_session_protection(self):
        """Test protected routes require login"""
        self.session.cookie_jar.clear()
        success, _ = self.session.request("/dashboard")
        self.assertFalse(success, "Accessed protected route without login")
    
    def test_logout(self):
        """Test logout functionality"""
        # First login
        success = self.session.login()
        self.assertTrue(success, "Initial login failed")
        
        # Then logout
        success, _ = self.session.request("/logout")
        self.assertTrue(success, "Logout request failed")
        
        # Try accessing protected route
        success, _ = self.session.request("/dashboard")
        self.assertFalse(success, "Accessed protected route after logout")
    
    def tearDown(self):
        """Clean up after each test"""
        self.session.cleanup()

if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    except KeyboardInterrupt:
        print("\\nTests interrupted by user")
    except Exception as e:
        print(f"\\nTest execution failed: {e}")
''')