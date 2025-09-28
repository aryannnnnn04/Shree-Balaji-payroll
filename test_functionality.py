"""Tests for core functionality of BlazeCore Payroll"""

import unittest
from datetime import datetime, date
from test_config import TestSession
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

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
                cls.session.request(f"/api/worker/{worker_id}", method="DELETE")
            except Exception:
                pass
        cls.session.cleanup()

class TestModalScrolling(unittest.TestCase):
    """Test cases for modal scrolling functionality"""
    
    def setUp(self):
        """Set up each test"""
        self.driver = webdriver.Chrome()
        self.driver.maximize_window()
        # Login first
        self.driver.get("http://localhost:5000/login")
        username = self.driver.find_element(By.NAME, "username")
        password = self.driver.find_element(By.NAME, "password")
        username.send_keys("admin")  # Replace with valid credentials
        password.send_keys("admin")  # Replace with valid credentials
        self.driver.find_element(By.TAG_NAME, "button").click()
        time.sleep(2)  # Wait for login to complete

    def test_modal_scrolling(self):
        """Test modal scrolling behavior"""
        # Navigate to dashboard
        self.driver.get("http://localhost:5000/dashboard")
        
        # Click the button to open add worker modal
        add_worker_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "addWorkerBtn"))
        )
        add_worker_btn.click()
        
        # Wait for modal to appear
        modal = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "modal"))
        )
        
        # Check if modal is visible
        self.assertTrue(modal.is_displayed(), "Modal should be visible")
        
        # Find the modal body
        modal_body = self.driver.find_element(By.CLASS_NAME, "modal-body")
        
        # Get initial scroll position
        initial_scroll = self.driver.execute_script("return arguments[0].scrollTop;", modal_body)
        
        # Scroll to bottom of modal body
        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", modal_body)
        
        # Get new scroll position
        new_scroll = self.driver.execute_script("return arguments[0].scrollTop;", modal_body)
        
        # Verify that scrolling occurred
        self.assertGreater(new_scroll, initial_scroll, "Modal should be scrollable")
        
        # Verify modal header remains visible
        modal_header = self.driver.find_element(By.CLASS_NAME, "modal-header")
        self.assertTrue(modal_header.is_displayed(), "Modal header should remain visible while scrolling")
        
        # Verify modal actions (footer) remains visible
        modal_actions = self.driver.find_element(By.CLASS_NAME, "modal-actions")
        self.assertTrue(modal_actions.is_displayed(), "Modal actions should remain visible while scrolling")

    def test_body_scroll_lock(self):
        """Test that body scrolling is locked when modal is open"""
        # Open modal
        self.driver.get("http://localhost:5000/dashboard")
        add_worker_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "addWorkerBtn"))
        )
        add_worker_btn.click()
        
        # Check if body has modal-open class
        body = self.driver.find_element(By.TAG_NAME, "body")
        self.assertIn("modal-open", body.get_attribute("class"), "Body should have modal-open class")
        
        # Try to scroll body
        initial_scroll = self.driver.execute_script("return window.pageYOffset;")
        body.send_keys(Keys.PAGE_DOWN)
        new_scroll = self.driver.execute_script("return window.pageYOffset;")
        
        # Verify body didn't scroll
        self.assertEqual(initial_scroll, new_scroll, "Body should not scroll when modal is open")

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
