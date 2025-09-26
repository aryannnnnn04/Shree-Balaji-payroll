"""Tests for core functionality of BlazeCore Payroll"""

import unittest
from datetime import datetime, date
from test_config import TestSession

class TestPayrollFunctionality(unittest.TestCase):
    """Test cases for core payroll functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - run once before all tests"""
        cls.session = TestSession()
        success = cls.session.login()
        if not success:
            raise RuntimeError("Failed to log in for tests")
        cls.test_workers = []
    
    def setUp(self):
        """Set up each test"""
        self.assertTrue(self.session.logged_in, "Test session is not logged in")
    
    def test_login_and_dashboard(self):
        """Test login and dashboard access"""
        success, response = self.session.request("/dashboard")
        self.assertTrue(success, "Failed to access dashboard")
    
    def test_worker_operations(self):
        """Test worker creation and management"""
        # Create test worker data
        worker_data = {
            "name": "Test Worker",
            "daily_wage": 500.00,
            "phone": "1234567890",
            "start_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Create worker
        success, response = self.session.request(
            "/api/workers",
            method="POST",
            data=worker_data
        )
        
        # Verify worker creation
        self.assertTrue(success, "Failed to create worker")
        self.assertTrue(response.get("success"), "Worker creation returned error")
        self.assertIn("worker_id", response, "No worker ID returned")
        
        # Store worker ID for cleanup
        worker_id = response["worker_id"]
        self.test_workers.append(worker_id)
        
        # Verify worker exists
        success, response = self.session.request(f"/api/worker/{worker_id}")
        self.assertTrue(success, "Failed to fetch worker details")
        self.assertEqual(response["name"], worker_data["name"], "Worker name mismatch")
        self.assertEqual(float(response["daily_wage"]), worker_data["daily_wage"], "Worker wage mismatch")
        
        # Test attendance marking
        attendance_data = {
            "worker_id": worker_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "status": "present"
        }
        
        success, response = self.session.request(
            "/api/attendance",
            method="POST",
            data=attendance_data
        )
        
        self.assertTrue(success, "Failed to mark attendance")
        self.assertTrue(response.get("success"), "Attendance marking returned error")
        
        # Test payroll calculation
        month = datetime.now().month
        year = datetime.now().year
        
        success, response = self.session.request(
            f"/api/payroll/{worker_id}/{year}/{month}"
        )
        
        self.assertTrue(success, "Failed to calculate payroll")
        self.assertIn("total_days", response, "No total days in payroll")
        self.assertIn("total_pay", response, "No total pay in payroll")
    
    def tearDown(self):
        """Clean up after each test"""
        pass
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Delete test workers
        for worker_id in cls.test_workers:
            try:
                cls.session.request(
                    f"/api/worker/{worker_id}",
                    method="DELETE"
                )
            except:
                pass
        cls.session.cleanup()

if __name__ == "__main__":
    unittest.main()
