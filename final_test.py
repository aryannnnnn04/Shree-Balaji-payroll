#!/usr/bin/env python3
"""
Final comprehensive test script for Shree Balaji Centring Works Payroll System
Tests all functionality to ensure everything is working correctly after fixes.
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Base URL for the application
BASE_URL = "http://127.0.0.1:5001"

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = "shreebalaji2024"

def test_login():
    """Test login functionality"""
    print("Testing login functionality...")
    
    # Test login page access
    try:
        response = requests.get(f"{BASE_URL}/login")
        assert response.status_code == 200
        print("✓ Login page accessible")
    except Exception as e:
        print(f"✗ Failed to access login page: {e}")
        return False
    
    # Test login with correct credentials
    try:
        login_data = {
            'username': TEST_USERNAME,
            'password': TEST_PASSWORD
        }
        response = requests.post(f"{BASE_URL}/login", data=login_data, allow_redirects=False)
        assert response.status_code in [302, 200]  # Redirect or OK
        print("✓ Login with correct credentials successful")
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return False
    
    return True

def test_dashboard_access(session):
    """Test dashboard access with authenticated session"""
    print("Testing dashboard access...")
    
    try:
        response = session.get(f"{BASE_URL}/")
        assert response.status_code == 200
        assert "Shree Balaji Centring Works" in response.text
        print("✓ Dashboard accessible with correct branding")
        return True
    except Exception as e:
        print(f"✗ Dashboard access failed: {e}")
        return False

def test_worker_management(session):
    """Test worker management functionality"""
    print("Testing worker management...")
    
    # Add a test worker
    worker_data = {
        "name": "Test Worker",
        "wage": 500,
        "phone": "9876543210",
        "start_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        response = session.post(f"{BASE_URL}/api/add_worker", 
                              json=worker_data,
                              headers={'Content-Type': 'application/json'})
        result = response.json()
        assert result.get('success') == True
        worker_id = result.get('worker_id')
        print("✓ Worker added successfully")
        
        # Get workers list
        response = session.get(f"{BASE_URL}/api/workers")
        workers = response.json()
        assert isinstance(workers, list)
        assert len(workers) > 0
        print("✓ Workers list retrieved successfully")
        
        return worker_id
    except Exception as e:
        print(f"✗ Worker management failed: {e}")
        return None

def test_attendance_marking(session, worker_id):
    """Test attendance marking functionality"""
    print("Testing attendance marking...")
    
    # Mark attendance for today
    today = datetime.now().strftime("%Y-%m-%d")
    attendance_data = {
        "worker_id": worker_id,
        "date": today,
        "status": "Present"
    }
    
    try:
        response = session.post(f"{BASE_URL}/api/mark_attendance",
                              json=attendance_data,
                              headers={'Content-Type': 'application/json'})
        result = response.json()
        assert result.get('success') == True
        print("✓ Attendance marked successfully")
        
        # Get attendance records
        response = session.get(f"{BASE_URL}/api/worker/{worker_id}/attendance")
        attendance_records = response.json()
        assert isinstance(attendance_records, list)
        print("✓ Attendance records retrieved successfully")
        
        return True
    except Exception as e:
        print(f"✗ Attendance marking failed: {e}")
        return False

def test_calendar_functionality(session, worker_id):
    """Test calendar attendance marking functionality"""
    print("Testing calendar functionality...")
    
    try:
        # Test getting attendance for a specific month
        today = datetime.now()
        response = session.get(f"{BASE_URL}/api/worker/{worker_id}/attendance?year={today.year}&month={today.month}")
        attendance_data = response.json()
        assert isinstance(attendance_data, list)
        print("✓ Calendar attendance data retrieved successfully")
        
        # Test Hindu calendar API
        response = session.get(f"{BASE_URL}/api/panchang")
        panchang_data = response.json()
        assert isinstance(panchang_data, dict)
        assert 'formatted_hindu_date' in panchang_data
        print("✓ Hindu calendar data retrieved successfully")
        
        return True
    except Exception as e:
        print(f"✗ Calendar functionality test failed: {e}")
        return False

def test_api_endpoints(session):
    """Test various API endpoints"""
    print("Testing API endpoints...")
    
    try:
        # Test stats endpoint
        response = session.get(f"{BASE_URL}/api/stats")
        stats = response.json()
        assert isinstance(stats, dict)
        print("✓ Stats API endpoint working")
        
        # Test reports endpoints
        today = datetime.now()
        response = session.get(f"{BASE_URL}/api/reports/payroll?year={today.year}&month={today.month}")
        payroll_report = response.json()
        assert isinstance(payroll_report, dict)
        print("✓ Payroll report API endpoint working")
        
        response = session.get(f"{BASE_URL}/api/reports/attendance?year={today.year}&month={today.month}")
        attendance_report = response.json()
        assert isinstance(attendance_report, dict)
        print("✓ Attendance report API endpoint working")
        
        return True
    except Exception as e:
        print(f"✗ API endpoints test failed: {e}")
        return False

def main():
    """Main test function"""
    print("=== Shree Balaji Centring Works - Final Comprehensive Test ===\n")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Test 1: Login functionality
    if not test_login():
        print("\n❌ LOGIN TEST FAILED")
        return False
    
    # Login to get session
    login_data = {
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD
    }
    session.post(f"{BASE_URL}/login", data=login_data)
    
    # Test 2: Dashboard access
    if not test_dashboard_access(session):
        print("\n❌ DASHBOARD TEST FAILED")
        return False
    
    # Test 3: Worker management
    worker_id = test_worker_management(session)
    if not worker_id:
        print("\n❌ WORKER MANAGEMENT TEST FAILED")
        return False
    
    # Test 4: Attendance marking
    if not test_attendance_marking(session, worker_id):
        print("\n❌ ATTENDANCE MARKING TEST FAILED")
        return False
    
    # Test 5: Calendar functionality
    if not test_calendar_functionality(session, worker_id):
        print("\n❌ CALENDAR FUNCTIONALITY TEST FAILED")
        return False
    
    # Test 6: API endpoints
    if not test_api_endpoints(session):
        print("\n❌ API ENDPOINTS TEST FAILED")
        return False
    
    print("\n=== ALL TESTS PASSED! ===")
    print("✅ Login functionality working")
    print("✅ Dashboard accessible with correct branding")
    print("✅ Worker management working")
    print("✅ Attendance marking working")
    print("✅ Calendar functionality working")
    print("✅ All API endpoints working")
    print("\nThe Shree Balaji Centring Works Payroll System is ready for use!")
    
    return True

if __name__ == "__main__":
    main()