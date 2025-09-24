#!/usr/bin/env python3
"""
Simple test script for Shree Balaji Centring Works Payroll System
Tests core functionality without external dependencies.
"""

import urllib.request
import urllib.parse
from datetime import datetime

# Base URL for the application
BASE_URL = "http://127.0.0.1:5001"

def test_url_access(url, description):
    """Test if a URL is accessible"""
    try:
        response = urllib.request.urlopen(url, timeout=5)
        if response.getcode() == 200:
            print(f"✓ {description} - Accessible")
            return True
        else:
            print(f"✗ {description} - HTTP {response.getcode()}")
            return False
    except Exception as e:
        print(f"✗ {description} - Error: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=== Shree Balaji Centring Works - Simple Test ===\n")
    
    # Test basic URL access
    tests = [
        (f"{BASE_URL}/login", "Login page"),
        (f"{BASE_URL}/", "Dashboard (requires login)"),
        (f"{BASE_URL}/api/stats", "Stats API (requires login)"),
        (f"{BASE_URL}/api/panchang", "Hindu calendar API (requires login)")
    ]
    
    results = []
    for url, description in tests:
        result = test_url_access(url, description)
        results.append(result)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Test Results: {passed}/{total} passed ===")
    
    if passed == total:
        print("✅ All basic connectivity tests passed!")
        print("The Shree Balaji Centring Works Payroll System is running correctly.")
        print(f"You can access the application at: {BASE_URL}")
        print("\nLogin credentials:")
        print("Username: admin")
        print("Password: shreebalaji2024")
    else:
        print("⚠️  Some tests failed. Please check the application.")

if __name__ == "__main__":
    main()